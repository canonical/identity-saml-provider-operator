# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import json
import logging
from dataclasses import dataclass
from typing import Any, KeysView, Self, TypeAlias
from urllib.parse import urlparse

from charms.certificate_transfer_interface.v1.certificate_transfer import (
    CertificateTransferRequires,
)
from charms.data_platform_libs.v0.data_interfaces import DatabaseRequires
from charms.hydra.v0.oauth import ClientConfig, OAuthRequirer
from charms.traefik_k8s.v0.traefik_route import TraefikRouteRequirer
from jinja2 import Template
from ops import Model

from configs import ServiceConfigs
from constants import (
    APPLICATION_PORT,
    OAUTH_GRANT_TYPES,
    OAUTH_SCOPES,
    OIDC_REDIRECT_ENDPOINT_RESOURCE_PATH,
    PEER_INTEGRATION_NAME,
    POSTGRESQL_DSN_TEMPLATE,
)
from env_vars import EnvVars

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

    @property
    def dsn(self) -> str:
        return POSTGRESQL_DSN_TEMPLATE.substitute(
            username=self.username,
            password=self.password,
            endpoint=f"{self.host}:{self.port}",
            database=self.database,
        )

    def to_env_vars(self) -> EnvVars:
        return {
            "SAML_PROVIDER_DB_HOST": self.host,
            "SAML_PROVIDER_DB_PORT": self.port,
            "SAML_PROVIDER_DB_NAME": self.database,
            "SAML_PROVIDER_DB_USER": self.username,
            "SAML_PROVIDER_DB_PASSWORD": self.password,
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


class PublicRouteIntegration:
    def __init__(self, requirer: TraefikRouteRequirer) -> None:
        self.requirer = requirer
        self._charm = requirer._charm

    @property
    def external_base_url(self) -> str:
        if not (external_host := self.requirer.external_host):
            return ""

        return f"{self.requirer.scheme}://{external_host}"

    @property
    def config(self) -> dict:
        if not self.requirer.external_host:
            return {}

        with open("templates/public-route.json.j2", "r") as file:
            template = Template(file.read())

        model, app = self._charm.model.name, self._charm.app.name
        external_host = urlparse(self.external_base_url).hostname
        return json.loads(
            template.render(
                model=model,
                app=app,
                port=APPLICATION_PORT,
                external_host=external_host,
            )
        )

    def to_env_vars(self) -> EnvVars:
        if not self.requirer.external_host:
            return {
                "SAML_PROVIDER_BRIDGE_BASE_URL": self._charm.internal_base_url,
                "SAML_PROVIDER_OIDC_REDIRECT_URL": self._charm.internal_base_url
                + OIDC_REDIRECT_ENDPOINT_RESOURCE_PATH,
            }

        return {
            "SAML_PROVIDER_BRIDGE_BASE_URL": self.external_base_url,
            "SAML_PROVIDER_OIDC_REDIRECT_URL": self.external_base_url
            + OIDC_REDIRECT_ENDPOINT_RESOURCE_PATH,
        }


class OAuthIntegration:
    def __init__(self, requirer: OAuthRequirer) -> None:
        self._requirer = requirer

    def to_env_vars(self) -> EnvVars:
        if not self._requirer.is_client_created():
            return {}

        oauth_provider_info = self._requirer.get_provider_info()
        return {
            "SAML_PROVIDER_HYDRA_PUBLIC_URL": oauth_provider_info.issuer_url,
            "SAML_PROVIDER_OIDC_CLIENT_ID": oauth_provider_info.client_id or "default",
            "SAML_PROVIDER_OIDC_CLIENT_SECRET": oauth_provider_info.client_secret or "default",
        }

    def update_oauth_client_config(self, saml_provider_url: str) -> None:
        oauth_client_config = ClientConfig(
            redirect_uri=saml_provider_url + OIDC_REDIRECT_ENDPOINT_RESOURCE_PATH,
            scope=OAUTH_SCOPES,
            grant_types=OAUTH_GRANT_TYPES,
        )
        self._requirer.update_client_config(oauth_client_config)


@dataclass(frozen=True, slots=True)
class TransferredCertificates:
    ca_bundle: str

    @classmethod
    def load(cls, requirer: CertificateTransferRequires) -> Self:
        ca_certs = requirer.get_all_certificates()
        ca_bundle = "\n".join(sorted(ca_certs))

        return cls(ca_bundle=ca_bundle)

    def to_service_configs(self) -> ServiceConfigs:
        return {
            "hydra_ca_certs": self.ca_bundle,
        }
