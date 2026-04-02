# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

from contextlib import suppress
import json
import logging
from dataclasses import dataclass, field
from typing import Any, KeysView, Optional, Self, TypeAlias
from urllib.parse import urlparse

from jinja2 import Template
from ops.pebble import PathError
from yarl import URL

from charms.certificate_transfer_interface.v1.certificate_transfer import (
    CertificateTransferProvides,
)
from charms.tls_certificates_interface.v4.tls_certificates import (
    CertificateRequestAttributes,
    Mode,
    ProviderCertificate,
    TLSCertificatesRequiresV4,
)
from charms.data_platform_libs.v0.data_interfaces import DatabaseRequires
from ops import CharmBase, Model

from charms.traefik_k8s.v0.traefik_route import TraefikRouteRequirer
from configs import ServiceConfigs
from constants import (
    APPLICATION_PORT,
    CERTIFICATES_INTEGRATION_NAME,
    CERTIFICATE_TRANSFER_INTEGRATION_NAME,
    CONTAINER_BRIDGE_CERT,
    CONTAINER_BRIDGE_KEY,
    CONTAINER_CERTIFICATES_FILE,
    PEER_INTEGRATION_NAME,
    PUBLIC_ROUTE_INTEGRATION_NAME,
)

logger = logging.getLogger(__name__)
JsonSerializable: TypeAlias = dict[str, Any] | list[Any] | int | str | float | bool | None


class PeerData:
    def __init__(self, model: Model) -> None:
        self._model = model
        self._app = model.app

    def __getitem__(self, key: str) -> JsonSerializable:
        if not (peers := self._model.get_relation(PEER_INTEGRATION_NAME)):
            return {}

        value = peers.data[self._app].get(key)
        return json.loads(value) if value else {}

    def __setitem__(self, key: str, value: Any) -> None:
        if not (peers := self._model.get_relation(PEER_INTEGRATION_NAME)):
            return

        peers.data[self._app][key] = json.dumps(value)

    def pop(self, key: str) -> JsonSerializable:
        if not (peers := self._model.get_relation(PEER_INTEGRATION_NAME)):
            return {}

        data = peers.data[self._app].pop(key, None)
        return json.loads(data) if data else {}

    def keys(self) -> KeysView[str]:
        if not (peers := self._model.get_relation(PEER_INTEGRATION_NAME)):
            return {}.keys()

        return peers.data[self._app].keys()


@dataclass(frozen=True, slots=True)
class DatabaseConfig:
    """The data source from the database integration."""

    host: str = ""
    port: str = ""
    database: str = ""
    username: str = ""
    password: str = ""
    migration_version: str = ""

    def to_service_configs(self) -> ServiceConfigs:
        return {
            "db_host": self.host,
            "db_port": self.port,
            "db_name": self.database,
            "db_user": self.username,
            "db_password": self.password,
        }

    @classmethod
    def load(cls, requirer: DatabaseRequires) -> Self:
        if not (database_integrations := requirer.relations):
            return cls()

        integration_id = database_integrations[0].id
        integration_data: dict[str, str] = requirer.fetch_relation_data()[integration_id]

        endpoint, *_ = integration_data.get("endpoints", "").partition(",")
        host, _, port = endpoint.partition(":")
        return cls(
            host=host,
            port=port,
            database=requirer.database,
            username=integration_data.get("username", ""),
            password=integration_data.get("password", ""),
            migration_version=f"migration_version_{integration_id}",
        )


@dataclass(frozen=True, slots=True)
class PublicRouteData:
    """The data source from the public-route integration."""

    url: URL = URL()
    config: dict = field(default_factory=dict)

    def is_ready(self) -> bool:
        return bool(self.url)

    @classmethod
    def _external_host(cls, requirer: TraefikRouteRequirer) -> str:
        if not (relation := requirer._charm.model.get_relation(PUBLIC_ROUTE_INTEGRATION_NAME)):
            return
        if not relation.app:
            return
        return relation.data[relation.app].get("external_host", "")

    @classmethod
    def _scheme(cls, requirer: TraefikRouteRequirer) -> str:
        if not (relation := requirer._charm.model.get_relation(PUBLIC_ROUTE_INTEGRATION_NAME)):
            return
        if not relation.app:
            return
        return relation.data[relation.app].get("scheme", "")

    @classmethod
    def load(cls, requirer: TraefikRouteRequirer) -> "PublicRouteData":
        model, app = requirer._charm.model.name, requirer._charm.app.name
        external_host = cls._external_host(requirer)

        if not external_host:
            logger.error("External hostname is not set on the ingress provider")
            return cls()

        scheme = cls._scheme(requirer)
        external_endpoint = f"{scheme}://{external_host}"

        # template could have use PathPrefixRegexp but going for a simple one right now
        with open("templates/public-route.json.j2", "r") as file:
            template = Template(file.read())

        ingress_config = json.loads(
            template.render(
                model=model,
                app=app,
                public_port=APPLICATION_PORT,
                external_host=external_host,
            )
        )

        return cls(
            url=URL(external_endpoint),
            config=ingress_config,
        )

    @property
    def secured(self) -> bool:
        return self.url.scheme == "https"

    def to_service_configs(self) -> ServiceConfigs:
        if not (url := self.url):
            return {
                "APPLICATION_ROOT_URL": (
                    f"http://{self._charm.app.name}.{self._charm.model.name}.svc.cluster.local:"
                    f"{APPLICATION_PORT}"
                ),
            }

        parsed_url = urlparse(url)
        return {
            "APPLICATION_ROOT_URL": f"{parsed_url.scheme}://{parsed_url.netloc}",
        }


@dataclass
class CertificateData:
    ca_cert: Optional[str] = None
    ca_chain: Optional[list[str]] = None
    cert: Optional[str] = None


class CertificatesIntegration:
    def __init__(self, charm: CharmBase) -> None:
        self._charm = charm
        self._container = charm._container

        self.csr_attributes = CertificateRequestAttributes(
            common_name="cd.iam.prod.canonical.com",
            sans_dns=frozenset(("cd.iam.prod.canonical.com",)),
        )
        self.cert_requirer = TLSCertificatesRequiresV4(
            charm,
            relationship_name=CERTIFICATES_INTEGRATION_NAME,
            certificate_requests=[self.csr_attributes],
            mode=Mode.UNIT,
        )

    @property
    def tls_enabled(self) -> bool:
        if not self._container.can_connect():
            return False

        return (
            self._container.exists(CONTAINER_BRIDGE_KEY)
            and self._container.exists(CONTAINER_BRIDGE_CERT)
            and self._container.exists(CONTAINER_CERTIFICATES_FILE)
        )

    @property
    def uri_scheme(self) -> str:
        return "https" if self.tls_enabled else "http"

    @property
    def _ca_cert(self) -> Optional[str]:
        return str(self._certs.ca) if self._certs else None

    @property
    def _server_key(self) -> Optional[str]:
        private_key = self.cert_requirer.private_key
        return str(private_key) if private_key else None

    @property
    def _server_cert(self) -> Optional[str]:
        return str(self._certs.certificate) if self._certs else None

    @property
    def _ca_chain(self) -> Optional[list[str]]:
        return [str(chain) for chain in self._certs.chain] if self._certs else None

    @property
    def _certs(self) -> Optional[ProviderCertificate]:
        cert, *_ = self.cert_requirer.get_assigned_certificate(self.csr_attributes)
        return cert

    @property
    def cert_data(self) -> CertificateData:
        return CertificateData(
            ca_cert=self._ca_cert,
            ca_chain=self._ca_chain,
            cert=self._server_cert,
        )

    def update_certificates(self) -> None:
        if not self._charm.model.get_relation(CERTIFICATES_INTEGRATION_NAME):
            logger.info("The certificates integration is not ready.")
            self._remove_certificates()
            return

        if not self._certs_ready():
            logger.info("The certificates data is not ready.")
            # self._remove_certificates()
            return

        logger.info("Certificates data is ready, preparing to push.")

        # Collect the root CA and all chain certs for the trust bundle.
        all_ca_certs: list[str] = []
        if ca_cert := self._ca_cert:
            all_ca_certs.append(ca_cert)
            logger.debug("Added root CA to bundle.")
        for chain_cert in self._ca_chain or []:
            if chain_cert not in all_ca_certs:
                all_ca_certs.append(chain_cert)
                logger.debug("Added chain cert to bundle.")

        ca_bundle = "\n".join(all_ca_certs)
        logger.info(f"CA bundle ready with {len(all_ca_certs)} certificate(s).")

        self._push_certificates(ca_bundle=ca_bundle)

    def _certs_ready(self) -> bool:
        certs, private_key = self.cert_requirer.get_assigned_certificate(self.csr_attributes)
        return all((certs, private_key))

    def _push_certificates(self, *, ca_bundle: str) -> None:
        logger.info("Pushing certificates to the workload container.")
        logger.info(
            f"CA Bundle: {CONTAINER_CERTIFICATES_FILE}\nServer Cert: {CONTAINER_BRIDGE_CERT}\nServer Key: {CONTAINER_BRIDGE_KEY}"
        )

        self._container.push(CONTAINER_CERTIFICATES_FILE, ca_bundle, make_dirs=True)
        self._container.push(CONTAINER_BRIDGE_KEY, self._server_key, make_dirs=True)
        self._container.push(CONTAINER_BRIDGE_CERT, self._server_cert, make_dirs=True)

    def _remove_certificates(self) -> None:
        for file in (
            CONTAINER_CERTIFICATES_FILE,
            CONTAINER_BRIDGE_KEY,
            CONTAINER_BRIDGE_CERT,
        ):
            with suppress(PathError):
                self._container.remove_path(file)


class CertificatesTransferIntegration:
    def __init__(self, charm: CharmBase):
        self._charm = charm
        self._certs_transfer_provider = CertificateTransferProvides(
            charm, relationship_name=CERTIFICATE_TRANSFER_INTEGRATION_NAME
        )

    def transfer_certificates(
        self, /, data: CertificateData, relation_id: Optional[int] = None
    ) -> None:
        if not (
            relations := self._charm.model.relations.get(CERTIFICATE_TRANSFER_INTEGRATION_NAME)
        ):
            return

        if relation_id is not None:
            relations = [relation for relation in relations if relation.id == relation_id]

        ca_cert, ca_chain, certificate = data.ca_cert, data.ca_chain, data.cert
        if not all((ca_cert, ca_chain, certificate)):
            for relation in relations:
                self._certs_transfer_provider.remove_certificate(relation_id=relation.id)
            return

        for relation in relations:
            self._certs_transfer_provider.set_certificate(
                ca=data.ca_cert,  # type: ignore[arg-type]
                chain=data.ca_chain,  # type: ignore[arg-type]
                certificate=data.cert,  # type: ignore[arg-type]
                relation_id=relation.id,
            )
