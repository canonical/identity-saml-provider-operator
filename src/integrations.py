# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

import json
import logging
from dataclasses import dataclass, field
from typing import Any, KeysView, Self, TypeAlias
from urllib.parse import urlparse

from jinja2 import Template
from yarl import URL

from charms.certificate_transfer_interface.v1.certificate_transfer import (
    CertificateTransferRequires,
)
from charms.data_platform_libs.v0.data_interfaces import DatabaseRequires
from ops import Model

from charms.traefik_k8s.v0.traefik_route import TraefikRouteRequirer
from configs import ServiceConfigs
from constants import (
    APPLICATION_PORT,
    CERTIFICATE_TRANSFER_INTEGRATION_NAME,
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


@dataclass(frozen=True)
class TLSCertificates:
    ca_bundle: str

    @classmethod
    def load(cls, requirer: CertificateTransferRequires) -> "TLSCertificates":
        """Fetch the CA certificates from all "receive-ca-cert" integrations."""
        # deal with v1 relations
        ca_certs = requirer.get_all_certificates()

        # deal with v0 relations
        cert_transfer_integrations = requirer.charm.model.relations[
            CERTIFICATE_TRANSFER_INTEGRATION_NAME
        ]

        for integration in cert_transfer_integrations:
            ca = {
                integration.data[unit]["ca"]
                for unit in integration.units
                if "ca" in integration.data.get(unit, {})
            }
            ca_certs.update(ca)

        ca_bundle = "\n".join(sorted(ca_certs))

        return cls(ca_bundle=ca_bundle)
