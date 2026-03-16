# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
from typing import Optional

from charms.hydra.v0.oauth import OauthProviderConfig
from ops import Container, ModelError, Unit
from ops.pebble import Layer, LayerDict

from constants import (
    APPLICATION_PORT,
    CONTAINER_CERTIFICATES_FILE,
    CONTAINER_BRIDGE_CERT,
    CONTAINER_BRIDGE_KEY,
    WORKLOAD_CONTAINER,
    WORKLOAD_RUN_COMMAND,
    WORKLOAD_SERVICE,
)
from exceptions import PebbleServiceError
from integrations import DatabaseConfig, PublicRouteData

logger = logging.getLogger(__name__)


class WorkloadService:
    """Workload service abstraction running in a Juju unit."""

    def __init__(self, unit: Unit) -> None:
        self._unit: Unit = unit
        self._container: Container = unit.get_container(WORKLOAD_CONTAINER)

    @property
    def is_running(self) -> bool:
        try:
            workload_service = self._container.get_service(WORKLOAD_SERVICE)
        except ModelError:
            return False

        return workload_service.is_running()

    def open_ports(self) -> None:
        self._unit.open_port(protocol="tcp", port=APPLICATION_PORT)


class PebbleService:
    """Pebble service abstraction running in a Juju unit."""

    def __init__(self, unit: Unit) -> None:
        self._unit = unit
        self._container = unit.get_container(WORKLOAD_CONTAINER)

    def _restart_service(self) -> None:
        if not self._container.get_service(WORKLOAD_SERVICE).is_running():
            self._container.start(WORKLOAD_SERVICE)
        else:
            self._container.replan()

    def plan(self, layer: Layer) -> None:
        self._container.add_layer(WORKLOAD_SERVICE, layer, combine=True)

        try:
            self._restart_service()
        except Exception as e:
            raise PebbleServiceError(f"Pebble failed to restart the workload service. Error: {e}")

    def render_pebble_layer(
        self,
        oauth: Optional[OauthProviderConfig] = None,
        database: Optional[DatabaseConfig] = None,
        public_route: Optional[PublicRouteData] = None,
    ) -> Layer:
        hydra_oath_url = oauth.issuer_url if oauth else ""
        root_url = public_route.url if public_route else ""
        client_id = oauth.client_id if oauth else ""
        client_secret = oauth.client_secret if oauth else ""

        container = {
            "override": "replace",
            "summary": "Identity SAML provider service",
            "command": (WORKLOAD_RUN_COMMAND),
            "startup": "disabled",
            "environment": {
                "SAML_PROVIDER_HYDRA_PUBLIC_URL": hydra_oath_url,
                "SAML_PROVIDER_BRIDGE_BASE_PORT": str(APPLICATION_PORT),
                "SAML_PROVIDER_DB_HOST": database.host if database else "",
                "SAML_PROVIDER_DB_PORT": str(database.port) if database else "",
                "SAML_PROVIDER_DB_NAME": database.database if database else "",
                "SAML_PROVIDER_DB_USER": database.username if database else "",
                "SAML_PROVIDER_DB_PASSWORD": database.password if database else "",
                "SAML_PROVIDER_HYDRA_CA_CERT_PATH": str(CONTAINER_CERTIFICATES_FILE),
                "SAML_PROVIDER_CERT_PATH": str(CONTAINER_BRIDGE_CERT),
                "SAML_PROVIDER_KEY_PATH": str(CONTAINER_BRIDGE_KEY),
                "SAML_PROVIDER_BRIDGE_BASE_URL": str(root_url),
                "SAML_PROVIDER_OIDC_CLIENT_ID": client_id,
                "SAML_PROVIDER_OIDC_CLIENT_SECRET": client_secret,
            },
        }

        pebble_layer: LayerDict = {
            "summary": "identity-saml-provider layer",
            "description": "pebble config layer for identity platform saml provider",
            "services": {WORKLOAD_CONTAINER: container},
        }
        return Layer(pebble_layer)
