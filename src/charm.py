#!/usr/bin/env python3
# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""A Juju charm for Identity SAML provider."""

import logging
from typing import Any
from urllib.parse import urljoin

from charms.data_platform_libs.v0.data_interfaces import (
    DatabaseCreatedEvent,
    DatabaseEndpointsChangedEvent,
    DatabaseRequires,
)
from charms.hydra.v0.oauth import ClientConfig, OAuthRequirer
from charms.traefik_k8s.v2.ingress import (
    IngressPerAppReadyEvent,
    IngressPerAppRequirer,
    IngressPerAppRevokedEvent,
)
from ops import (
    ConfigChangedEvent,
    HookEvent,
    LeaderElectedEvent,
    PebbleReadyEvent,
    RelationBrokenEvent,
    StartEvent,
    UpdateStatusEvent,
)
from ops.charm import CharmBase, RelationChangedEvent
from ops.main import main
from ops.model import ActiveStatus, BlockedStatus, WaitingStatus
from ops.pebble import Layer

from constants import (
    APPLICATION_PORT,
    DATABASE_INTEGRATION_NAME,
    DATABASE_NAME,
    HYDRA_INTEGRATION_NAME,
    INGRESS_INTEGRATION_NAME,
    OAUTH_GRANT_TYPES,
    OAUTH_SCOPES,
    PEER_INTEGRATION_NAME,
    WORKLOAD_CONTAINER,
)
from exceptions import PebbleServiceError
from integrations import DatabaseConfig, IngressIntegration, PeerData
from services import PebbleService, WorkloadService
from utils import (
    container_connectivity,
)


class IdentitySAMLProviderCharm(CharmBase):
    def __init__(self, *args: Any) -> None:
        super().__init__(*args)

        self.peer_data = PeerData(self.model)
        self._container = self.unit.get_container(WORKLOAD_CONTAINER)
        self._workload_service = WorkloadService(self.unit)
        self._pebble_service = PebbleService(self.unit)

        # Database integration
        self.database_requirer = DatabaseRequires(
            self,
            relation_name=DATABASE_INTEGRATION_NAME,
            database_name=DATABASE_NAME,
            extra_user_roles="SUPERUSER",
        )
        self.framework.observe(
            self.database_requirer.on.database_created,
            self._on_database_created,
        )
        self.framework.observe(
            self.database_requirer.on.endpoints_changed,
            self._on_database_changed,
        )
        self.framework.observe(
            self.on[DATABASE_INTEGRATION_NAME].relation_broken,
            self._on_database_relation_broken,
        )

        # Ingress integration
        self.ingress_requirer = IngressPerAppRequirer(
            self,
            relation_name=INGRESS_INTEGRATION_NAME,
            port=APPLICATION_PORT,
            strip_prefix=True,
        )
        self.ingress_integration = IngressIntegration(self.ingress_requirer)
        self.framework.observe(
            self.ingress_requirer.on.ready,
            self._on_ingress_ready,
        )
        self.framework.observe(
            self.ingress_requirer.on.revoked,
            self._on_ingress_revoked,
        )

        # Lifecycle event handlers
        self.framework.observe(
            self.on.identity_saml_provider_pebble_ready,
            self._on_identity_saml_provider_pebble_ready,
        )
        self.framework.observe(self.on.leader_elected, self._on_leader_elected)
        self.framework.observe(self.on.config_changed, self._on_config_changed)
        self.framework.observe(self.on.update_status, self._on_update_status)
        self.framework.observe(self.on.start, self._on_start)
        self.framework.observe(self.on.peer_relation_changed, self._on_peer_relation_changed)

        # peers
        self.framework.observe(
            self.on[PEER_INTEGRATION_NAME].relation_created, self._holistic_handler
        )
        self.framework.observe(
            self.on[PEER_INTEGRATION_NAME].relation_changed, self._holistic_handler
        )

        oauth_client_config = ClientConfig(
            redirect_uri=self._external_url + "/callback",
            grant_types=OAUTH_GRANT_TYPES,
            scope=OAUTH_SCOPES,
        )
        self.oauth = OAuthRequirer(self, oauth_client_config, relation_name=HYDRA_INTEGRATION_NAME)

    @property
    def _external_url(self) -> str:
        if self.ingress_requirer.url:
            return self.ingress_requirer.url
        return f"http://{self.app.name}.{self.model.name}.svc.cluster.local:{APPLICATION_PORT}"

    @property
    def _pebble_layer(self) -> Layer:
        oauth_info = self.oauth.get_provider_info()
        logger.info(f"Generating Pebble layer with OAuth info: {oauth_info}")
        database_config = DatabaseConfig.load(self.database_requirer)
        return self._pebble_service.render_pebble_layer(oauth_info, database_config)

    def _on_identity_saml_provider_pebble_ready(self, event: PebbleReadyEvent) -> None:
        if not container_connectivity(self):
            self.unit.status = WaitingStatus("Container is not connected yet")
            event.defer()
            return

        self._workload_service.open_ports()

        self._holistic_handler(event)

    def _on_leader_elected(self, event: LeaderElectedEvent) -> None:
        self._holistic_handler(event)

    def _on_config_changed(self, event: ConfigChangedEvent) -> None:
        self._holistic_handler(event)

    def _on_update_status(self, event: UpdateStatusEvent) -> None:
        self._holistic_handler(event)

    def _on_start(self, event: StartEvent) -> None:
        self._holistic_handler(event)

    def _on_peer_relation_changed(self, event: RelationChangedEvent) -> None:
        self._holistic_handler(event)

    def _on_database_created(self, event: DatabaseCreatedEvent) -> None:
        if not container_connectivity(self):
            self.unit.status = WaitingStatus("Container is not connected yet")
            event.defer()
            return

        self._holistic_handler(event)

        if not self.unit.is_leader():
            logger.info(
                "Unit does not have leadership. Wait for leader unit to run the migration."
            )
            event.defer()
            return

    def _on_database_changed(self, event: DatabaseEndpointsChangedEvent) -> None:
        self._holistic_handler(event)

    def _on_database_relation_broken(self, event: RelationBrokenEvent) -> None:
        self._holistic_handler(event)

    def _on_ingress_ready(self, event: IngressPerAppReadyEvent) -> None:
        self._set_client_config()
        self._holistic_handler(event)

    def _on_ingress_revoked(self, event: IngressPerAppRevokedEvent) -> None:
        self._holistic_handler(event)

    def _holistic_handler(self, event: HookEvent) -> None:
        if not container_connectivity(self):
            self.unit.status = WaitingStatus("Container is not connected yet")
            event.defer()
            return

        if not self.ingress_requirer.url:
            self.unit.status = WaitingStatus("Waiting for ingress URL")
            return

        if not self.oauth.is_client_created():
            self.unit.status = WaitingStatus("Waiting for OAuth provider relation")
            return

        if not self.model.relations[DATABASE_INTEGRATION_NAME]:
            self.unit.status = BlockedStatus(f"Missing integration {DATABASE_INTEGRATION_NAME}")
            return
        if not self.database_requirer.is_resource_created():
            self.unit.status = WaitingStatus("Waiting for database creation")
            return

        try:
            self._pebble_service.plan(self._pebble_layer)
        except PebbleServiceError:
            logger.error("Failed to start the service, please check the container logs")
            self.unit.status = BlockedStatus(
                f"Failed to restart the service, please check the {WORKLOAD_CONTAINER} logs"
            )
            return

        self.unit.status = ActiveStatus()

    def _set_client_config(self):
        client_config = ClientConfig(
            urljoin(self._external_url, "/callback"),
            OAUTH_SCOPES,
            OAUTH_GRANT_TYPES,
        )
        self.oauth.update_client_config(client_config)


logger = logging.getLogger(__name__)

if __name__ == "__main__":
    main(IdentitySAMLProviderCharm)
