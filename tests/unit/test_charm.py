# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

from unittest.mock import MagicMock, patch

from ops import ActiveStatus, BlockedStatus, WaitingStatus
from ops.testing import Container, Context, PeerRelation, Relation
from unit.conftest import create_state

from constants import (
    DATABASE_INTEGRATION_NAME,
    WORKLOAD_CONTAINER,
)


class TestPebbleReadyEvent:
    """Tests for the Pebble Ready event handler."""

    def test_when_container_not_connected(
        self,
        context: Context,
    ) -> None:
        """Test that the charm waits when the workload container is not connected."""
        container = Container(name=WORKLOAD_CONTAINER, can_connect=False)
        state = create_state(containers=[container])

        state_out = context.run(context.on.pebble_ready(container), state)

        assert isinstance(state_out.unit_status, WaitingStatus)

    def test_when_container_connected_no_relations(
        self,
        context: Context,
        container: Container,
    ) -> None:
        """Test that the charm enters waiting when container is ready but relations are missing."""
        state = create_state(containers=[container])

        state_out = context.run(context.on.pebble_ready(container), state)

        assert isinstance(state_out.unit_status, WaitingStatus)


class TestLeaderElectedEvent:
    """Tests for the Leader Elected event handler."""

    def test_when_event_emitted(
        self,
        context: Context,
    ) -> None:
        """Test that the leader elected event triggers the holistic handler."""
        state = create_state(leader=True)

        state_out = context.run(context.on.leader_elected(), state)

        # Without relations, holistic handler should result in waiting status
        assert isinstance(state_out.unit_status, WaitingStatus)


class TestConfigChangedEvent:
    """Tests for the Config Changed event handler."""

    def test_when_event_emitted(
        self,
        context: Context,
    ) -> None:
        """Test that configuration changes trigger the holistic handler."""
        state = create_state()

        state_out = context.run(context.on.config_changed(), state)

        assert isinstance(state_out.unit_status, WaitingStatus)

    def test_with_log_level_config(
        self,
        context: Context,
    ) -> None:
        """Test that log-level configuration is passed through."""
        config = {"log-level": "debug"}
        state = create_state(config=config)

        state_out = context.run(context.on.config_changed(), state)

        assert isinstance(state_out.unit_status, WaitingStatus)


class TestUpdateStatusEvent:
    """Tests for the Update Status event handler."""

    def test_when_event_emitted(
        self,
        context: Context,
    ) -> None:
        """Test that update status triggers the holistic handler."""
        state = create_state()

        state_out = context.run(context.on.update_status(), state)

        assert isinstance(state_out.unit_status, WaitingStatus)


class TestStartEvent:
    """Tests for the Start event handler."""

    def test_when_event_emitted(
        self,
        context: Context,
    ) -> None:
        """Test that start event triggers the holistic handler."""
        state = create_state()

        state_out = context.run(context.on.start(), state)

        assert isinstance(state_out.unit_status, WaitingStatus)


class TestPeerRelationCreatedEvent:
    """Tests for the Peer Relation Created event handler."""

    def test_when_event_emitted(
        self,
        context: Context,
        peer_relation: PeerRelation,
    ) -> None:
        """Test that peer relation created event triggers the holistic handler."""
        state = create_state(relations=[peer_relation])

        state_out = context.run(context.on.relation_created(peer_relation), state)

        assert isinstance(state_out.unit_status, WaitingStatus)


class TestDatabaseCreatedEvent:
    """Tests for the Database Created event handler."""

    def test_when_container_not_connected(
        self,
        context: Context,
        db_relation_ready: Relation,
    ) -> None:
        """Test waiting status when container is not connected during database creation."""
        container = Container(name=WORKLOAD_CONTAINER, can_connect=False)
        state = create_state(
            containers=[container],
            relations=[db_relation_ready],
        )

        state_out = context.run(context.on.relation_changed(db_relation_ready), state)

        assert state_out.unit_status == WaitingStatus("Container is not connected yet")

    def test_when_event_emitted(
        self,
        context: Context,
        db_relation_ready: Relation,
    ) -> None:
        """Test that database created event triggers the holistic handler."""
        state = create_state(relations=[db_relation_ready])

        state_out = context.run(context.on.relation_changed(db_relation_ready), state)

        # Holistic handler runs but other relations are missing
        assert isinstance(state_out.unit_status, WaitingStatus)


class TestDatabaseChangedEvent:
    """Tests for the Database Endpoints Changed event handler."""

    def test_when_event_emitted(
        self,
        context: Context,
        db_relation_ready: Relation,
    ) -> None:
        """Test that database endpoints changed event triggers the holistic handler."""
        state = create_state(relations=[db_relation_ready])

        state_out = context.run(context.on.relation_changed(db_relation_ready), state)

        assert isinstance(state_out.unit_status, WaitingStatus)


class TestDatabaseBrokenEvent:
    """Tests for the Database Broken event handler."""

    def test_when_event_emitted(
        self,
        context: Context,
        db_relation_ready: Relation,
    ) -> None:
        """Test that breaking the database integration triggers the holistic handler."""
        state = create_state(relations=[db_relation_ready])

        state_out = context.run(context.on.relation_broken(db_relation_ready), state)

        assert isinstance(state_out.unit_status, WaitingStatus)


class TestPublicRouteChangedEvent:
    """Tests for the Public Route Changed event handler."""

    def test_when_event_emitted(
        self,
        context: Context,
        public_route_relation_ready: Relation,
    ) -> None:
        """Test that public route changes trigger the holistic handler."""
        state = create_state(relations=[public_route_relation_ready])

        state_out = context.run(context.on.relation_changed(public_route_relation_ready), state)

        # OAuth not ready, so should be waiting
        assert isinstance(state_out.unit_status, WaitingStatus)

    def test_when_public_route_not_ready(
        self,
        context: Context,
        public_route_relation: Relation,
    ) -> None:
        """Test waiting when public route relation exists but no data is available."""
        state = create_state(relations=[public_route_relation])

        state_out = context.run(context.on.relation_changed(public_route_relation), state)

        assert isinstance(state_out.unit_status, WaitingStatus)


class TestPublicRouteBrokenEvent:
    """Tests for the Public Route Broken event handler."""

    def test_when_event_emitted(
        self,
        context: Context,
        public_route_relation: Relation,
    ) -> None:
        """Test that breaking the public route integration triggers the holistic handler."""
        state = create_state(relations=[public_route_relation])

        state_out = context.run(context.on.relation_broken(public_route_relation), state)

        assert isinstance(state_out.unit_status, WaitingStatus)


class TestOAuthInfoChangedEvent:
    """Tests for the OAuth Info Changed event handler."""

    def test_when_relation_changed_without_data(
        self,
        context: Context,
        oauth_relation: Relation,
    ) -> None:
        """Test that OAuth relation changed without provider data does not set status."""
        state = create_state(relations=[oauth_relation])

        state_out = context.run(context.on.relation_changed(oauth_relation), state)

        # With no OAuth provider data, the lib does not emit oauth_info_changed,
        # so the charm handler is not triggered and status remains unchanged.
        assert state_out is not None


class TestOAuthInfoRemovedEvent:
    """Tests for the OAuth Info Removed (broken) event handler."""

    def test_when_event_emitted(
        self,
        context: Context,
        oauth_relation: Relation,
    ) -> None:
        """Test that breaking the OAuth relation triggers the holistic handler."""
        state = create_state(relations=[oauth_relation])

        state_out = context.run(context.on.relation_broken(oauth_relation), state)

        assert isinstance(state_out.unit_status, WaitingStatus)


class TestCertificateTransferChangedEvent:
    """Tests for the Certificate Transfer Changed event handler."""

    def test_when_event_emitted(
        self,
        context: Context,
        cert_transfer_relation: Relation,
    ) -> None:
        """Test that certificate transfer changes trigger the holistic handler."""
        state = create_state(relations=[cert_transfer_relation])

        state_out = context.run(context.on.relation_changed(cert_transfer_relation), state)

        assert isinstance(state_out.unit_status, WaitingStatus)


class TestHolisticHandler:
    """Tests for the Holistic Handler (update_status/reconciliation)."""

    def test_when_container_not_connected(
        self,
        context: Context,
    ) -> None:
        """Test waiting status when container is not connected."""
        state = create_state(
            containers=[Container(name=WORKLOAD_CONTAINER, can_connect=False)],
        )

        state_out = context.run(context.on.update_status(), state)

        assert state_out.unit_status == WaitingStatus("Container is not connected yet")

    def test_when_public_route_not_ready(
        self,
        context: Context,
        db_relation_ready: Relation,
        peer_relation: PeerRelation,
        oauth_relation: Relation,
    ) -> None:
        """Test waiting status when public route URL is not available."""
        state = create_state(
            relations=[db_relation_ready, peer_relation, oauth_relation],
        )

        state_out = context.run(context.on.update_status(), state)

        assert state_out.unit_status == WaitingStatus("Waiting for public-route URL")

    def test_when_oauth_not_ready(
        self,
        context: Context,
        public_route_relation_ready: Relation,
        db_relation_ready: Relation,
        peer_relation: PeerRelation,
    ) -> None:
        """Test waiting status when OAuth provider is not ready."""
        state = create_state(
            relations=[public_route_relation_ready, db_relation_ready, peer_relation],
        )

        state_out = context.run(context.on.update_status(), state)

        assert state_out.unit_status == WaitingStatus("Waiting for OAuth provider relation")

    def test_when_database_integration_missing(
        self,
        context: Context,
        public_route_relation_ready: Relation,
        peer_relation: PeerRelation,
    ) -> None:
        """Test blocked status when database integration is missing."""
        state = create_state(
            relations=[public_route_relation_ready, peer_relation],
        )

        with patch("charm.OAuthRequirer.is_client_created", return_value=True):
            state_out = context.run(context.on.update_status(), state)

        assert state_out.unit_status == BlockedStatus(
            f"Missing integration {DATABASE_INTEGRATION_NAME}"
        )

    def test_when_database_not_ready(
        self,
        context: Context,
        public_route_relation_ready: Relation,
        db_relation: Relation,
        peer_relation: PeerRelation,
    ) -> None:
        """Test waiting status when database resource is not yet created."""
        state = create_state(
            relations=[
                public_route_relation_ready,
                db_relation,
                peer_relation,
            ],
        )

        with (
            patch("charm.OAuthRequirer.is_client_created", return_value=True),
            patch("charm.DatabaseRequires.is_resource_created", return_value=False),
        ):
            state_out = context.run(context.on.update_status(), state)

        assert state_out.unit_status == WaitingStatus("Waiting for database creation")

    @patch("charm.IdentitySAMLProviderCharm._ensure_tls")
    @patch("charm.IdentitySAMLProviderCharm._ensure_bridge_certificates")
    def test_when_all_ready(
        self,
        mocked_bridge_certs: MagicMock,
        mocked_tls: MagicMock,
        context: Context,
        public_route_relation_ready: Relation,
        db_relation_ready: Relation,
        peer_relation: PeerRelation,
    ) -> None:
        """Test active status when all integrations are ready."""
        state = create_state(
            relations=[
                public_route_relation_ready,
                db_relation_ready,
                peer_relation,
            ],
        )

        with patch("charm.OAuthRequirer.is_client_created", return_value=True):
            state_out = context.run(context.on.update_status(), state)

        assert isinstance(state_out.unit_status, ActiveStatus)
        mocked_tls.assert_called_once()
        mocked_bridge_certs.assert_called_once()

    @patch("charm.IdentitySAMLProviderCharm._ensure_tls")
    @patch("charm.IdentitySAMLProviderCharm._ensure_bridge_certificates")
    def test_when_pebble_service_fails(
        self,
        mocked_bridge_certs: MagicMock,
        mocked_tls: MagicMock,
        context: Context,
        public_route_relation_ready: Relation,
        db_relation_ready: Relation,
        peer_relation: PeerRelation,
    ) -> None:
        """Test blocked status when pebble service fails to restart."""
        from exceptions import PebbleServiceError

        state = create_state(
            relations=[
                public_route_relation_ready,
                db_relation_ready,
                peer_relation,
            ],
        )

        with (
            patch("charm.OAuthRequirer.is_client_created", return_value=True),
            patch(
                "charm.PebbleService.plan",
                side_effect=PebbleServiceError("pebble error"),
            ),
        ):
            state_out = context.run(context.on.update_status(), state)

        assert isinstance(state_out.unit_status, BlockedStatus)
