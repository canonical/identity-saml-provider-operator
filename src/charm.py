#!/usr/bin/env python3
# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""A Juju charm for Identity SAML provider."""

import logging
from typing import Any, Iterable, TypeVar

from charms.certificate_transfer_interface.v1.certificate_transfer import (
    CertificatesAvailableEvent,
    CertificateTransferRequires,
)
from charms.data_platform_libs.v0.data_interfaces import (
    DatabaseCreatedEvent,
    DatabaseEndpointsChangedEvent,
    DatabaseRequires,
)
from charms.hydra.v0.oauth import ClientConfig as OAuthClientConfig
from charms.hydra.v0.oauth import (
    OAuthInfoChangedEvent,
    OAuthInfoRemovedEvent,
    OAuthRequirer,
)
from charms.observability_libs.v0.kubernetes_compute_resources_patch import (
    KubernetesComputeResourcesPatch,
)
from charms.traefik_k8s.v0.traefik_route import TraefikRouteRequirer
from ops import (
    ConfigChangedEvent,
    EventBase,
    LeaderElectedEvent,
    PebbleReadyEvent,
    RelationBrokenEvent,
    RelationChangedEvent,
    RelationEvent,
    StartEvent,
    UpdateStatusEvent,
)
from ops.charm import CharmBase, CollectStatusEvent, SecretChangedEvent
from ops.main import main
from ops.model import ActiveStatus, BlockedStatus, WaitingStatus
from ops.pebble import Layer

from configs import (
    CharmConfig,
    ContainerFile,
    HydraCertificates,
    JujuSecretResolver,
    KubernetesResources,
    SAMLBridgeCert,
    SAMLBridgeKey,
)
from constants import (
    APPLICATION_PORT,
    CERTIFICATE_TRANSFER_INTEGRATION_NAME,
    DATABASE_INTEGRATION_NAME,
    DATABASE_NAME,
    OAUTH_GRANT_TYPES,
    OAUTH_INTEGRATION_NAME,
    OAUTH_SCOPES,
    OIDC_REDIRECT_ENDPOINT_RESOURCE_PATH,
    PEER_INTEGRATION_NAME,
    PUBLIC_ROUTE_INTEGRATION_NAME,
    WORKLOAD_CONTAINER,
)
from exceptions import PebbleServiceError
from integrations import (
    DatabaseConfig,
    OAuthIntegration,
    PeerData,
    PublicRouteIntegration,
    TransferredCertificates,
)
from services import PebbleService, WorkloadService
from utils import (
    EVENT_DEFER_CONDITIONS,
    NOOP_CONDITIONS,
    certificate_transfer_integration_exists,
    container_connectivity,
    database_integration_exists,
    database_resource_is_created,
    oauth_integration_exists,
    peer_integration_exists,
    public_route_integration_exists,
    saml_bridge_certs_exist,
)

logger = logging.getLogger(__name__)

HookEventType = TypeVar("HookEventType", bound=EventBase)


class IdentitySAMLProviderCharm(CharmBase):
    def __init__(self, *args: Any) -> None:
        super().__init__(*args)

        self.peer_data = PeerData(self.model)
        self.charm_config = CharmConfig(self.config, JujuSecretResolver(self.model))

        self._container = self.unit.get_container(WORKLOAD_CONTAINER)
        self._workload_service = WorkloadService(self.unit)
        self._pebble_service = PebbleService(self.unit)

        # Lifecycle event handlers
        self.framework.observe(self.on.leader_elected, self._on_leader_elected)
        self.framework.observe(self.on.config_changed, self._on_config_changed)
        self.framework.observe(self.on.start, self._on_start)
        self.framework.observe(
            self.on.identity_saml_provider_pebble_ready,
            self._on_identity_saml_provider_pebble_ready,
        )
        self.framework.observe(self.on.peer_relation_changed, self._on_peer_relation_changed)
        self.framework.observe(self.on.update_status, self._on_update_status)
        self.framework.observe(self.on.collect_unit_status, self._on_collect_status)

        # Secrets
        self.framework.observe(self.on.secret_changed, self._on_secret_changed)

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

        # Public route integration
        self.public_route_requirer = TraefikRouteRequirer(
            self,
            self.model.get_relation(PUBLIC_ROUTE_INTEGRATION_NAME),
            PUBLIC_ROUTE_INTEGRATION_NAME,
            raw=True,
        )
        self.public_route_integration = PublicRouteIntegration(self.public_route_requirer)
        self.framework.observe(
            self.on[PUBLIC_ROUTE_INTEGRATION_NAME].relation_joined,
            self._on_public_route_changed,
        )
        self.framework.observe(
            self.on[PUBLIC_ROUTE_INTEGRATION_NAME].relation_changed,
            self._on_public_route_changed,
        )
        self.framework.observe(
            self.on[PUBLIC_ROUTE_INTEGRATION_NAME].relation_broken,
            self._on_public_route_broken,
        )

        # OAuth integration
        self.oauth_requirer = OAuthRequirer(
            self,
            self._oauth_client_config,
            relation_name=OAUTH_INTEGRATION_NAME,
        )
        self.oauth_integration = OAuthIntegration(self.oauth_requirer)
        self.framework.observe(
            self.oauth_requirer.on.oauth_info_changed, self._on_oauth_info_changed
        )
        self.framework.observe(
            self.oauth_requirer.on.oauth_info_removed, self._on_oauth_info_changed
        )

        # Certificate transfer integration
        self.certificate_transfer_requirer = CertificateTransferRequires(
            self, relationship_name=CERTIFICATE_TRANSFER_INTEGRATION_NAME
        )
        self.framework.observe(
            self.certificate_transfer_requirer.on.certificate_set_updated,
            self._on_certificate_transfer_available,
        )

        # Kubernetes resources management
        self._resources_patch = KubernetesComputeResourcesPatch(
            self,
            WORKLOAD_CONTAINER,
            resource_reqs_func=KubernetesResources(self.config),
        )

    @property
    def internal_base_url(self) -> str:
        return f"http://{self.app.name}.{self.model.name}.svc.cluster.local:{APPLICATION_PORT}"

    @property
    def _oauth_client_config(self) -> OAuthClientConfig:
        base_url = self.public_route_integration.external_base_url or self.internal_base_url
        return OAuthClientConfig(
            redirect_uri=base_url + OIDC_REDIRECT_ENDPOINT_RESOURCE_PATH,
            scope=OAUTH_SCOPES,
            grant_types=OAUTH_GRANT_TYPES,
        )

    @property
    def _pebble_layer(self) -> Layer:
        database_config = DatabaseConfig.load(self.database_requirer)

        return self._pebble_service.render_pebble_layer(
            database_config,
            self.public_route_integration,
            self.oauth_integration,
        )

    @property
    def config_files(self) -> Iterable[ContainerFile]:
        hydra_ca = TransferredCertificates.load(self.certificate_transfer_requirer)
        return [
            SAMLBridgeCert.from_sources(self.charm_config),
            SAMLBridgeKey.from_sources(self.charm_config),
            HydraCertificates.from_sources(hydra_ca),
        ]

    def _on_leader_elected(self, event: LeaderElectedEvent) -> None:
        self._holistic_handler(event)

    def _on_start(self, event: StartEvent) -> None:
        self._holistic_handler(event)

    def _on_config_changed(self, event: ConfigChangedEvent) -> None:
        self._holistic_handler(event)

    def _on_identity_saml_provider_pebble_ready(self, event: PebbleReadyEvent) -> None:
        if not container_connectivity(self):
            self.unit.status = WaitingStatus("Container is not connected yet")
            event.defer()
            return

        self._workload_service.open_ports()

        self._holistic_handler(event)

    def _on_update_status(self, event: UpdateStatusEvent) -> None:
        self._holistic_handler(event)

    def _on_peer_relation_changed(self, event: RelationChangedEvent) -> None:
        self._holistic_handler(event)

    def _on_secret_changed(self, event: SecretChangedEvent) -> None:
        self._holistic_handler(event)

    def _on_database_created(self, event: DatabaseCreatedEvent) -> None:
        if not container_connectivity(self):
            self.unit.status = WaitingStatus("Container is not connected yet")
            event.defer()
            return

        if not self.unit.is_leader():
            logger.info(
                "Unit does not have leadership. Wait for leader unit to run the migration."
            )
            return

        self._holistic_handler(event)

    def _on_database_changed(self, event: DatabaseEndpointsChangedEvent) -> None:
        self._holistic_handler(event)

    def _on_database_relation_broken(self, event: RelationBrokenEvent) -> None:
        self._holistic_handler(event)

    def _on_public_route_changed(self, event: RelationEvent) -> None:
        # This is needed due to how traefik_route lib handles the event
        self.public_route_requirer._relation = event.relation

        if not self.public_route_requirer.is_ready():
            return

        if self.unit.is_leader():
            public_route_config = self.public_route_integration.config
            self.public_route_requirer.submit_to_traefik(public_route_config)

            external_base_url = (
                self.public_route_integration.external_base_url or self.internal_base_url
            )
            self.oauth_integration.update_oauth_client_config(saml_provider_url=external_base_url)

        self._holistic_handler(event)

    def _on_public_route_broken(self, event: RelationBrokenEvent) -> None:
        if self.unit.is_leader():
            logger.info("This application no longer has public-route integration")

        # This is needed due to how traefik_route lib handles the event
        self.public_route_requirer._relation = event.relation

        self._holistic_handler(event)

    def _on_oauth_info_changed(self, event: OAuthInfoChangedEvent | OAuthInfoRemovedEvent) -> None:
        self._holistic_handler(event)

    def _on_certificate_transfer_available(self, event: CertificatesAvailableEvent) -> None:
        self._holistic_handler(event)

    def _on_collect_status(self, event: CollectStatusEvent) -> None:
        if not (can_connect := container_connectivity(self)):
            event.add_status(WaitingStatus("Container is not connected yet"))

        if not peer_integration_exists(self):
            event.add_status(WaitingStatus(f"Missing integration {PEER_INTEGRATION_NAME}"))

        if not database_integration_exists(self):
            event.add_status(BlockedStatus(f"Missing integration {DATABASE_INTEGRATION_NAME}"))

        if not database_resource_is_created(self):
            event.add_status(WaitingStatus("Waiting for database creation"))

        if not public_route_integration_exists(self):
            event.add_status(BlockedStatus(f"Missing integration {PUBLIC_ROUTE_INTEGRATION_NAME}"))

        if not oauth_integration_exists(self):
            event.add_status(BlockedStatus(f"Missing integration {OAUTH_INTEGRATION_NAME}"))

        if not certificate_transfer_integration_exists(self):
            event.add_status(
                BlockedStatus(f"Missing integration {CERTIFICATE_TRANSFER_INTEGRATION_NAME}")
            )

        if not saml_bridge_certs_exist(self):
            event.add_status(BlockedStatus("Missing SAML bridge certificate and/or key file"))

        if can_connect and not self._workload_service.is_running:
            event.add_status(
                BlockedStatus(
                    f"Failed to start the service, please check the {WORKLOAD_CONTAINER} container logs"
                )
            )

        event.add_status(self._resources_patch.get_status())

        event.add_status(ActiveStatus())

    def _holistic_handler(self, event: HookEventType) -> None:
        if not all(condition(self) for condition in NOOP_CONDITIONS):
            return

        if not all(condition(self) for condition in EVENT_DEFER_CONDITIONS):
            event.defer()
            return

        try:
            self._pebble_service.plan(self._pebble_layer, *self.config_files)
        except PebbleServiceError:
            logger.error("Failed to start the service, please check the container logs")
            self.unit.status = BlockedStatus(
                f"Failed to restart the service, please check the {WORKLOAD_CONTAINER} logs"
            )


if __name__ == "__main__":
    main(IdentitySAMLProviderCharm)
