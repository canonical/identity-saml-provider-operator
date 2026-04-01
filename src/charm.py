#!/usr/bin/env python3
# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""A Juju charm for Identity SAML provider."""

import logging
import subprocess
from typing import Any
from urllib.parse import urljoin

import ops

from charms.certificate_transfer_interface.v1.certificate_transfer import (
    CertificateTransferRequires,
)
from charms.data_platform_libs.v0.data_interfaces import (
    DatabaseCreatedEvent,
    DatabaseEndpointsChangedEvent,
    DatabaseRequires,
)
from charms.hydra.v0.oauth import (
    ClientConfig,
    OAuthInfoChangedEvent,
    OAuthInfoRemovedEvent,
    OAuthRequirer,
)
from charms.observability_libs.v0.kubernetes_compute_resources_patch import (
    K8sResourcePatchFailedEvent,
    KubernetesComputeResourcesPatch,
    ResourceRequirements,
    adjust_resource_requirements,
)
from charms.traefik_k8s.v0.traefik_route import TraefikRouteRequirer

from ops import (
    ConfigChangedEvent,
    HookEvent,
    LeaderElectedEvent,
    MaintenanceStatus,
    PebbleReadyEvent,
    RelationBrokenEvent,
    RelationEvent,
    RelationChangedEvent,
    StartEvent,
    UpdateStatusEvent,
)
from ops.charm import CharmBase
from ops.main import main
from ops.model import ActiveStatus, BlockedStatus, WaitingStatus
from ops.pebble import Layer

from constants import (
    APPLICATION_PORT,
    CERTIFICATE_TRANSFER_INTEGRATION_NAME,
    DATABASE_INTEGRATION_NAME,
    DATABASE_NAME,
    HYDRA_INTEGRATION_NAME,
    REDIRECT_URL,
    PUBLIC_ROUTE_INTEGRATION_NAME,
    OAUTH_GRANT_TYPES,
    OAUTH_SCOPES,
    PEER_INTEGRATION_NAME,
    PEER_DATA_CA_BUNDLE,
    PEER_DATA_BRIDGE_CERT,
    PEER_DATA_BRIDGE_KEY,
    WORKLOAD_CONTAINER,
    LOCAL_CERTIFICATES_PATH,
    LOCAL_CHARM_CERTIFICATES_FILE,
    LOCAL_CHARM_CERTIFICATES_PATH,
    LOCAL_BRIDGE_CERT_FILE,
    LOCAL_BRIDGE_KEY_FILE,
)
from exceptions import PebbleServiceError
from integrations import (
    DatabaseConfig,
    PeerData,
    PublicRouteData,
    TLSCertificates,
)
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

        # public route via raw traefik routing configuration
        self.public_route = TraefikRouteRequirer(
            self,
            self.model.get_relation(PUBLIC_ROUTE_INTEGRATION_NAME),
            PUBLIC_ROUTE_INTEGRATION_NAME,
            raw=True,
        )
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

        # Certificate transfer integration
        self.certificate_transfer_requirer = CertificateTransferRequires(
            self,
            relationship_name=CERTIFICATE_TRANSFER_INTEGRATION_NAME,
        )
        self.framework.observe(
            self.certificate_transfer_requirer.on.certificate_set_updated,
            self._on_certificate_transfer_changed,
        )
        self.framework.observe(
            self.certificate_transfer_requirer.on.certificates_removed,
            self._on_certificate_transfer_changed,
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

        # Oauth integration
        oauth_client_config = ClientConfig(
            redirect_uri=urljoin(self._external_url, REDIRECT_URL),
            grant_types=OAUTH_GRANT_TYPES,
            scope=OAUTH_SCOPES,
        )
        self.oauth = OAuthRequirer(self, oauth_client_config, relation_name=HYDRA_INTEGRATION_NAME)
        self.framework.observe(
            self.oauth.on.oauth_info_changed,
            self._on_oauth_info_changed,
        )
        self.framework.observe(
            self.oauth.on.oauth_info_removed,
            self._on_oauth_info_changed,
        )

        # Resources patching
        self.resources_patch = KubernetesComputeResourcesPatch(
            self,
            WORKLOAD_CONTAINER,
            resource_reqs_func=self._resource_reqs_from_config,
        )
        self.framework.observe(
            self.resources_patch.on.patch_failed, self._on_resource_patch_failed
        )

    @property
    def _external_url(self) -> str:
        if url := PublicRouteData.load(self.public_route).url:
            return str(url)
        return f"http://{self.app.name}.{self.model.name}.svc.cluster.local:{APPLICATION_PORT}"

    @property
    def _pebble_layer(self) -> Layer:
        oauth_info = self.oauth.get_provider_info()
        database_config = DatabaseConfig.load(self.database_requirer)
        public_route_config = PublicRouteData.load(self.public_route)

        return self._pebble_service.render_pebble_layer(
            oauth_info, database_config, public_route_config
        )

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

    def _on_oauth_info_changed(self, event: OAuthInfoChangedEvent | OAuthInfoRemovedEvent) -> None:
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

    def _on_public_route_changed(self, event: RelationEvent) -> None:
        self.unit.status = MaintenanceStatus("Configuring resources")

        # needed due to how traefik_route lib is handling the event
        self.public_route._relation = event.relation

        if not self.public_route.is_ready():
            return

        if event.relation.app is None:
            # We need to defer the event as this is not handled in the holistic handler
            # TODO(nsklikas): move this to the holistic handler and remove defer
            # TODO 2(nsklikas): Fix this in traefik_route lib, this is a bug and the lib should handle
            # this in the `is_ready` method, like it does for the Provider side.
            event.defer()
            return

        if self.unit.is_leader():
            public_route_config = PublicRouteData.load(self.public_route).config
            self.public_route.submit_to_traefik(public_route_config)

        self._set_client_config()

        self._holistic_handler(event)

    def _on_public_route_broken(self, event: RelationBrokenEvent) -> None:
        self.unit.status = MaintenanceStatus("Configuring resources")

        # needed due to how traefik_route lib is handling the event
        self.public_route._relation = event.relation

        self._holistic_handler(event)

    def _ensure_tls(self) -> None:
        """Ensure TLS CA bundle is available locally from source and in container.

        Leader publishes CA bundle to peer data for all units to consume.
        All units apply the CA bundle from peer data to local and container paths.
        """
        LOCAL_CHARM_CERTIFICATES_FILE.parent.mkdir(parents=True, exist_ok=True)

        # Leader loads from certificate transfer relation and publishes to peers
        if self.unit.is_leader():
            if certificates := TLSCertificates.load(self.certificate_transfer_requirer).ca_bundle:
                LOCAL_CHARM_CERTIFICATES_FILE.write_text(certificates)
            elif LOCAL_CHARM_CERTIFICATES_FILE.exists():
                LOCAL_CHARM_CERTIFICATES_FILE.unlink()
            # Publish CA bundle to peer data
            ca_bundle_content = (
                LOCAL_CHARM_CERTIFICATES_FILE.read_text()
                if LOCAL_CHARM_CERTIFICATES_FILE.exists()
                else ""
            )
            self.peer_data[PEER_DATA_CA_BUNDLE] = ca_bundle_content
        else:
            # Followers read from peer data
            ca_bundle_content = self.peer_data[PEER_DATA_CA_BUNDLE]
            if ca_bundle_content:
                LOCAL_CHARM_CERTIFICATES_FILE.write_text(ca_bundle_content)
            elif LOCAL_CHARM_CERTIFICATES_FILE.exists():
                LOCAL_CHARM_CERTIFICATES_FILE.unlink()

        subprocess.run([
            "update-ca-certificates",
            "--fresh",
            "--etccertsdir",
            LOCAL_CERTIFICATES_PATH,
            "--localcertsdir",
            LOCAL_CHARM_CERTIFICATES_PATH,
        ])
        self._workload_service.update_ca_certs()

    def _ensure_bridge_certificates(self) -> None:
        """Ensure bridge TLS certificates are available and shared across peers.

        Leader generates bridge cert/key on first run and publishes to peer data.
        All units apply the bridge cert/key from peer data to local and container paths.
        """
        LOCAL_BRIDGE_CERT_FILE.parent.mkdir(parents=True, exist_ok=True)

        # Leader generates bridge certificates and publishes to peer data
        if self.unit.is_leader():
            if not (LOCAL_BRIDGE_CERT_FILE.exists() and LOCAL_BRIDGE_KEY_FILE.exists()):
                try:
                    subprocess.run(
                        [
                            "openssl",
                            "req",
                            "-x509",
                            "-newkey",
                            "rsa:2048",
                            "-keyout",
                            str(LOCAL_BRIDGE_KEY_FILE),
                            "-out",
                            str(LOCAL_BRIDGE_CERT_FILE),
                            "-days",
                            "365",
                            "-nodes",
                            "-subj",
                            "/CN=localhost",
                        ],
                        check=True,
                        capture_output=True,
                        text=True,
                    )
                except Exception as e:
                    logger.error("unexpected error generating bridge cert: %s", e)
                    try:
                        if (
                            LOCAL_BRIDGE_KEY_FILE.exists()
                            and LOCAL_BRIDGE_KEY_FILE.read_text() == ""
                        ):
                            LOCAL_BRIDGE_KEY_FILE.unlink()
                        if (
                            LOCAL_BRIDGE_CERT_FILE.exists()
                            and LOCAL_BRIDGE_CERT_FILE.read_text() == ""
                        ):
                            LOCAL_BRIDGE_CERT_FILE.unlink()
                    except Exception:
                        pass
                    self.unit.status = BlockedStatus(
                        "Failed to generate bridge TLS certificate; unexpected error"
                    )
                    return

            # Publish bridge cert/key to peer data
            cert_content = (
                LOCAL_BRIDGE_CERT_FILE.read_text() if LOCAL_BRIDGE_CERT_FILE.exists() else ""
            )
            key_content = (
                LOCAL_BRIDGE_KEY_FILE.read_text() if LOCAL_BRIDGE_KEY_FILE.exists() else ""
            )
            self.peer_data[PEER_DATA_BRIDGE_CERT] = cert_content
            self.peer_data[PEER_DATA_BRIDGE_KEY] = key_content
        else:
            # Followers read and apply from peer data
            cert_content = self.peer_data[PEER_DATA_BRIDGE_CERT]
            key_content = self.peer_data[PEER_DATA_BRIDGE_KEY]
            if cert_content and key_content:
                LOCAL_BRIDGE_CERT_FILE.write_text(cert_content)
                LOCAL_BRIDGE_KEY_FILE.write_text(key_content)
            else:
                # Peer data not yet available, defer this action
                self.unit.status = WaitingStatus("Waiting for bridge certificates from leader")
                return

        self._workload_service.update_bridge_certificates()

    def _on_certificate_transfer_changed(self, event: ops.EventBase) -> None:
        self._holistic_handler(event)

    def _on_resource_patch_failed(self, event: K8sResourcePatchFailedEvent) -> None:
        logger.error("Failed to patch resource constraints: %s", event.message)
        self.unit.status = BlockedStatus(event.message)

    def _resource_reqs_from_config(self) -> ResourceRequirements:
        limits = {"cpu": self.model.config.get("cpu"), "memory": self.model.config.get("memory")}
        requests = {"cpu": "100m", "memory": "200Mi"}
        return adjust_resource_requirements(limits, requests, adhere_to_requests=True)

    def _holistic_handler(self, event: HookEvent) -> None:
        if not container_connectivity(self):
            self.unit.status = WaitingStatus("Container is not connected yet")
            event.defer()
            return

        if not PublicRouteData.load(self.public_route).url:
            self.unit.status = WaitingStatus("Waiting for public-route URL")
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

        self._ensure_tls()

        # Followers gate on peer TLS data availability
        if not self.unit.is_leader():
            if not (
                self.peer_data[PEER_DATA_BRIDGE_CERT] and self.peer_data[PEER_DATA_BRIDGE_KEY]
            ):
                self.unit.status = WaitingStatus("Waiting for bridge certificates from leader")
                return

        self._ensure_bridge_certificates()

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
            urljoin(self._external_url, REDIRECT_URL),
            OAUTH_SCOPES,
            OAUTH_GRANT_TYPES,
        )
        self.oauth.update_client_config(client_config)


logger = logging.getLogger(__name__)

if __name__ == "__main__":
    main(IdentitySAMLProviderCharm)
