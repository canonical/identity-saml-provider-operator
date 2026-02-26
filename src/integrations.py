# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

import json
import logging
from dataclasses import dataclass
from typing import Any, KeysView, Self, TypeAlias
from urllib.parse import urlparse

from charms.data_platform_libs.v0.data_interfaces import DatabaseRequires
from charms.traefik_k8s.v0.traefik_route import TraefikRouteRequirer
from charms.traefik_k8s.v2.ingress import IngressPerAppRequirer
from jinja2 import Template
from ops import Model

from configs import ServiceConfigs
from constants import APPLICATION_PORT, PEER_INTEGRATION_NAME
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


class IngressIntegration:
    def __init__(self, requirer: IngressPerAppRequirer) -> None:
        self.ingress_requirer = requirer
        self._charm = requirer.charm

    @property
    def url(self) -> str:
        return self.ingress_requirer.url if self.ingress_requirer.is_ready() else ""

    def to_service_configs(self) -> ServiceConfigs:
        hostnames = [f"{self._charm.app.name}.{self._charm.model.name}.svc.cluster.local"]

        if url := self.url:
            parsed_url = urlparse(url)
            if hostname := parsed_url.hostname:
                hostnames.append(hostname)

        return {
            "hostnames": hostnames,
        }

    def to_env_vars(self) -> EnvVars:
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


class PublicRouteIntegration:
    def __init__(self, requirer: TraefikRouteRequirer) -> None:
        self.requirer = requirer
        self._charm = requirer._charm

    @property
    def url(self) -> str:
        if not (external_host := self.requirer.external_host):
            return ""

        external_endpoint = f"{self.requirer.scheme}://{external_host}"
        return external_endpoint

    @property
    def config(self) -> dict:
        if not self.url:
            return {}

        with open("templates/public-route.j2", "r") as file:
            template = Template(file.read())

        model, app = self._charm.model.name, self._charm.app.name
        external_host = urlparse(self.url).hostname
        return json.loads(
            template.render(
                model=model,
                app=app,
                port=APPLICATION_PORT,
                external_host=external_host,
            )
        )

    def to_service_configs(self) -> ServiceConfigs:
        hostnames = [f"{self._charm.app.name}.{self._charm.model.name}.svc.cluster.local"]

        if url := self.url:
            parsed_url = urlparse(url)
            if hostname := parsed_url.hostname:
                hostnames.append(hostname)

        return {
            "hostnames": hostnames,
        }

    def to_env_vars(self) -> EnvVars:
        if not (url := self.url):
            return {
                "APPLICATION_ROOT_URL": (
                    f"http://{self._charm.app.name}.{self._charm.model.name}.svc.cluster.local:"
                    f"{APPLICATION_PORT}"
                ),
            }

        return {
            "APPLICATION_ROOT_URL": url,
        }

    @property
    def secured(self) -> bool:
        return self.url.scheme == "https"
