# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
from typing import Optional

from charms.hydra.v0.oauth import OauthProviderConfig
from ops import Container, ModelError, Unit
from ops.pebble import Layer, LayerDict

from constants import (
    APPLICATION_PORT,
    CERTIFICATES_FILE,
    LOCAL_CERTIFICATES_FILE,
    WORKLOAD_CONTAINER,
    WORKLOAD_RUN_COMMAND,
    WORKLOAD_SERVICE,
)
from exceptions import PebbleServiceError
from integrations import DatabaseConfig

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

    def update_ca_certs(self) -> None:
        ca_certs = LOCAL_CERTIFICATES_FILE.read_text() if LOCAL_CERTIFICATES_FILE.exists() else ""

        current = (
            self._container.pull(CERTIFICATES_FILE).read()
            if self._container.exists(CERTIFICATES_FILE)
            else ""
        )

        if current == ca_certs:
            return

        self._container.push(CERTIFICATES_FILE, ca_certs, make_dirs=True)


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
    ) -> Layer:
        hydra_oath_url = oauth.issuer_url if oauth else ""

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
            },
        }

        pebble_layer: LayerDict = {
            "summary": "identity-saml-provider layer",
            "description": "pebble config layer for identity platform saml provider",
            "services": {WORKLOAD_CONTAINER: container},
            # "checks": {
            #     "http-check": {
            #         "override": "replace",
            #         "period": "1m",
            #         "level": "alive",
            #         "http": {
            #             "url": f"http://localhost:{APPLICATION_PORT}/_status/ping",
            #         },
            #     }
            # },
        }
        return Layer(pebble_layer)
