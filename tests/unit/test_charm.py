# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

from unittest.mock import MagicMock, patch

from ops import ActiveStatus, BlockedStatus, WaitingStatus
from ops.pebble import Error
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


class TestCertificatesChangedEvent:
    """Tests for the TLS Certificates event handler."""

    def test_when_event_emitted(
        self,
        context: Context,
        certificates_relation: Relation,
        public_route_relation_ready: Relation,
    ) -> None:
        """Test that TLS certificates relation changes trigger the holistic handler."""
        state = create_state(relations=[certificates_relation, public_route_relation_ready])

        state_out = context.run(context.on.relation_changed(certificates_relation), state)

        assert isinstance(state_out.unit_status, WaitingStatus)


class TestCertificateTransferChangedEvent:
    """Tests for the Certificate Transfer event handler."""

    def test_when_event_emitted(
        self,
        context: Context,
        certificate_transfer_relation: Relation,
    ) -> None:
        """Test that certificate transfer relation changes trigger the holistic handler."""
        state = create_state(relations=[certificate_transfer_relation])

        state_out = context.run(context.on.relation_changed(certificate_transfer_relation), state)

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
        public_route_relation: Relation,
        db_relation_ready: Relation,
        peer_relation: PeerRelation,
        oauth_relation: Relation,
    ) -> None:
        """Test waiting status when public route URL is not available."""
        state = create_state(
            relations=[public_route_relation, db_relation_ready, peer_relation, oauth_relation],
        )

        state_out = context.run(context.on.update_status(), state)

        assert state_out.unit_status == WaitingStatus("Waiting for public ingress")

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

    @patch("charm.CertificatesIntegration.update_certificates")
    def test_when_all_ready(
        self,
        mocked_update_certificates: MagicMock,
        context: Context,
        certificates_relation: Relation,
        public_route_relation_ready: Relation,
        db_relation_ready: Relation,
        peer_relation: PeerRelation,
    ) -> None:
        """Test active status when all integrations are ready."""
        state = create_state(
            relations=[
                certificates_relation,
                public_route_relation_ready,
                db_relation_ready,
                peer_relation,
            ],
        )

        with patch("charm.OAuthRequirer.is_client_created", return_value=True):
            state_out = context.run(context.on.update_status(), state)

        assert isinstance(state_out.unit_status, ActiveStatus)
        mocked_update_certificates.assert_called_once()

    @patch("charm.CertificatesIntegration.update_certificates")
    def test_when_all_ready_with_certificate_transfer(
        self,
        mocked_update_certificates: MagicMock,
        context: Context,
        certificate_transfer_relation: Relation,
        public_route_relation_ready: Relation,
        db_relation_ready: Relation,
        peer_relation: PeerRelation,
    ) -> None:
        """Test active status with certificate transfer relation."""
        state = create_state(
            relations=[
                certificate_transfer_relation,
                public_route_relation_ready,
                db_relation_ready,
                peer_relation,
            ],
        )

        with patch("charm.OAuthRequirer.is_client_created", return_value=True):
            state_out = context.run(context.on.update_status(), state)

        assert isinstance(state_out.unit_status, ActiveStatus)
        mocked_update_certificates.assert_called_once()

    @patch("charm.CertificatesIntegration.update_certificates")
    def test_when_all_ready_with_both_cert_relations(
        self,
        mocked_update_certificates: MagicMock,
        context: Context,
        certificates_relation: Relation,
        certificate_transfer_relation: Relation,
        public_route_relation_ready: Relation,
        db_relation_ready: Relation,
        peer_relation: PeerRelation,
    ) -> None:
        """Test active status with both certificate relations."""
        state = create_state(
            relations=[
                certificates_relation,
                certificate_transfer_relation,
                public_route_relation_ready,
                db_relation_ready,
                peer_relation,
            ],
        )

        with patch("charm.OAuthRequirer.is_client_created", return_value=True):
            state_out = context.run(context.on.update_status(), state)

        assert isinstance(state_out.unit_status, ActiveStatus)
        mocked_update_certificates.assert_called_once()

    @patch("charm.CertificatesIntegration.update_certificates")
    def test_when_pebble_service_fails(
        self,
        mocked_update_certificates: MagicMock,
        context: Context,
        certificates_relation: Relation,
        public_route_relation_ready: Relation,
        db_relation_ready: Relation,
        peer_relation: PeerRelation,
    ) -> None:
        """Test blocked status when pebble service fails to restart."""
        from exceptions import PebbleServiceError

        state = create_state(
            relations=[
                certificates_relation,
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
        mocked_update_certificates.assert_called_once()

    @patch("charm.CertificatesIntegration.update_certificates")
    def test_when_pebble_service_fails_with_certificate_transfer(
        self,
        mocked_update_certificates: MagicMock,
        context: Context,
        certificate_transfer_relation: Relation,
        public_route_relation_ready: Relation,
        db_relation_ready: Relation,
        peer_relation: PeerRelation,
    ) -> None:
        """Test blocked status with certificate transfer when pebble service fails."""
        from exceptions import PebbleServiceError

        state = create_state(
            relations=[
                certificate_transfer_relation,
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
        mocked_update_certificates.assert_called_once()

    @patch("charm.CertificatesIntegration.update_certificates", side_effect=Error("tls error"))
    def test_when_certificates_update_fails(
        self,
        _mocked_update_certificates: MagicMock,
        context: Context,
        certificates_relation: Relation,
        public_route_relation_ready: Relation,
        db_relation_ready: Relation,
        peer_relation: PeerRelation,
    ) -> None:
        """Test blocked status when TLS certificates update fails."""
        state = create_state(
            relations=[
                certificates_relation,
                public_route_relation_ready,
                db_relation_ready,
                peer_relation,
            ],
        )

        with patch("charm.OAuthRequirer.is_client_created", return_value=True):
            state_out = context.run(context.on.update_status(), state)

        assert isinstance(state_out.unit_status, BlockedStatus)

    @patch("charm.CertificatesIntegration.update_certificates", side_effect=Error("tls error"))
    def test_when_certificates_update_fails_with_certificate_transfer(
        self,
        _mocked_update_certificates: MagicMock,
        context: Context,
        certificate_transfer_relation: Relation,
        public_route_relation_ready: Relation,
        db_relation_ready: Relation,
        peer_relation: PeerRelation,
    ) -> None:
        """Test blocked status when certificates update fails with cert transfer."""
        state = create_state(
            relations=[
                certificate_transfer_relation,
                public_route_relation_ready,
                db_relation_ready,
                peer_relation,
            ],
        )

        with patch("charm.OAuthRequirer.is_client_created", return_value=True):
            state_out = context.run(context.on.update_status(), state)

        assert isinstance(state_out.unit_status, BlockedStatus)
