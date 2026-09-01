# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

from unittest.mock import MagicMock, PropertyMock, patch

import pytest
from ops import testing
from ops.model import BlockedStatus
from pytest_mock import MockerFixture

from charm import IdentitySAMLProviderCharm
from configs import PostgreSQLCertificates
from constants import VALID_DB_SSLMODES
from exceptions import MigrationError, PebbleServiceError


class TestLeaderElectedEvent:
    def test_when_all_prerequisites_met(
        self,
        base_container: testing.Container,
        peer_integration: testing.PeerRelation,
        database_integration: testing.Relation,
        mocked_database_resource_created: MagicMock,
        mocked_migration_not_needed: MagicMock,
        mocked_charm_holistic_handler: MagicMock,
    ) -> None:
        ctx = testing.Context(IdentitySAMLProviderCharm)
        state_in = testing.State(
            containers={base_container},
            relations={peer_integration, database_integration},
            leader=True,
        )

        ctx.run(ctx.on.leader_elected(), state_in)

        mocked_charm_holistic_handler.assert_called_once()


class TestConfigChangedEvent:
    def test_when_all_prerequisites_met(
        self,
        base_container: testing.Container,
        peer_integration: testing.PeerRelation,
        database_integration: testing.Relation,
        mocked_database_resource_created: MagicMock,
        mocked_migration_not_needed: MagicMock,
        mocked_charm_holistic_handler: MagicMock,
    ) -> None:
        ctx = testing.Context(IdentitySAMLProviderCharm)
        state_in = testing.State(
            containers={base_container},
            relations={peer_integration, database_integration},
            leader=True,
        )

        ctx.run(ctx.on.config_changed(), state_in)

        mocked_charm_holistic_handler.assert_called_once()


class TestStartEvent:
    def test_when_all_prerequisites_met(
        self,
        base_container: testing.Container,
        peer_integration: testing.PeerRelation,
        database_integration: testing.Relation,
        mocked_database_resource_created: MagicMock,
        mocked_migration_not_needed: MagicMock,
        mocked_charm_holistic_handler: MagicMock,
    ) -> None:
        ctx = testing.Context(IdentitySAMLProviderCharm)
        state_in = testing.State(
            containers={base_container},
            relations={peer_integration, database_integration},
            leader=True,
        )

        state_out = ctx.run(ctx.on.start(), state_in)

        mocked_charm_holistic_handler.assert_called_once()
        assert len(state_out.deferred) == 0


class TestPebbleReadyEvent:
    def test_when_container_not_connected(
        self,
        disconnected_container: testing.Container,
        mocked_charm_holistic_handler: MagicMock,
    ) -> None:
        ctx = testing.Context(IdentitySAMLProviderCharm)
        state_in = testing.State(containers={disconnected_container}, leader=True)

        state_out = ctx.run(ctx.on.pebble_ready(disconnected_container), state_in)

        mocked_charm_holistic_handler.assert_not_called()
        assert len(state_out.deferred) == 1

    def test_when_container_connected(
        self,
        base_container: testing.Container,
        peer_integration: testing.PeerRelation,
        database_integration: testing.Relation,
        mocked_database_resource_created: MagicMock,
        mocked_migration_not_needed: MagicMock,
        mocked_charm_holistic_handler: MagicMock,
    ) -> None:
        ctx = testing.Context(IdentitySAMLProviderCharm)
        state_in = testing.State(
            containers={base_container},
            relations={peer_integration, database_integration},
            leader=True,
        )

        with patch("charm.WorkloadService.open_ports") as mocked_open_ports:
            state_out = ctx.run(ctx.on.pebble_ready(base_container), state_in)

        mocked_open_ports.assert_called_once()
        assert len(state_out.deferred) == 0


class TestUpdateStatusEvent:
    def test_when_all_prerequisites_met(
        self,
        base_container: testing.Container,
        peer_integration: testing.PeerRelation,
        database_integration: testing.Relation,
        mocked_database_resource_created: MagicMock,
        mocked_migration_not_needed: MagicMock,
        mocked_charm_holistic_handler: MagicMock,
    ) -> None:
        ctx = testing.Context(IdentitySAMLProviderCharm)
        state_in = testing.State(
            containers={base_container},
            relations={peer_integration, database_integration},
            leader=True,
        )

        ctx.run(ctx.on.update_status(), state_in)

        mocked_charm_holistic_handler.assert_called_once()


class TestSecretChangedEvent:
    def test_when_all_prerequisites_met(
        self,
        base_container: testing.Container,
        peer_integration: testing.PeerRelation,
        database_integration: testing.Relation,
        mocked_database_resource_created: MagicMock,
        mocked_migration_not_needed: MagicMock,
        mocked_charm_holistic_handler: MagicMock,
    ) -> None:
        ctx = testing.Context(IdentitySAMLProviderCharm)
        secret = testing.Secret(
            tracked_content={"private-key": "key", "public-cert": "cert"},
        )
        state_in = testing.State(
            containers={base_container},
            relations={peer_integration, database_integration},
            secrets={secret},
            leader=True,
        )

        ctx.run(ctx.on.secret_changed(secret), state_in)

        mocked_charm_holistic_handler.assert_called_once()


class TestDatabaseCreatedEvent:
    def test_when_container_not_connected(
        self,
        disconnected_container: testing.Container,
        peer_integration: testing.PeerRelation,
        database_integration: testing.Relation,
        mocked_charm_holistic_handler: MagicMock,
    ) -> None:
        ctx = testing.Context(IdentitySAMLProviderCharm)
        state_in = testing.State(
            containers={disconnected_container},
            relations={peer_integration, database_integration},
            leader=True,
        )

        state_out = ctx.run(ctx.on.relation_changed(database_integration), state_in)

        mocked_charm_holistic_handler.assert_not_called()
        assert len(state_out.deferred) == 1

    def test_when_peer_integration_missing(
        self,
        base_container: testing.Container,
        database_integration: testing.Relation,
        mocked_charm_holistic_handler: MagicMock,
    ) -> None:
        ctx = testing.Context(IdentitySAMLProviderCharm)
        state_in = testing.State(
            containers={base_container},
            relations={database_integration},
            leader=True,
        )

        state_out = ctx.run(ctx.on.relation_changed(database_integration), state_in)

        mocked_charm_holistic_handler.assert_not_called()
        assert len(state_out.deferred) == 1

    def test_when_migration_not_needed(
        self,
        base_container: testing.Container,
        peer_integration: testing.PeerRelation,
        database_integration: testing.Relation,
        mocked_migration_not_needed: MagicMock,
        mocked_charm_holistic_handler: MagicMock,
        mocker: MockerFixture,
    ) -> None:
        mocked_migrate = mocker.patch("charm.CommandLine.migrate")
        ctx = testing.Context(IdentitySAMLProviderCharm)
        state_in = testing.State(
            containers={base_container},
            relations={peer_integration, database_integration},
            leader=True,
        )

        ctx.run(ctx.on.relation_changed(database_integration), state_in)

        mocked_charm_holistic_handler.assert_called_once()
        mocked_migrate.assert_not_called()

    def test_when_migration_needed_but_not_leader(
        self,
        base_container: testing.Container,
        peer_integration: testing.PeerRelation,
        database_integration: testing.Relation,
        mocked_charm_holistic_handler: MagicMock,
        mocker: MockerFixture,
    ) -> None:
        mocker.patch(
            "charm.IdentitySAMLProviderCharm.migration_needed",
            new_callable=PropertyMock,
            return_value=True,
        )
        mocked_migrate = mocker.patch("charm.CommandLine.migrate")
        ctx = testing.Context(IdentitySAMLProviderCharm)
        state_in = testing.State(
            containers={base_container},
            relations={peer_integration, database_integration},
            leader=False,
        )

        state_out = ctx.run(ctx.on.relation_changed(database_integration), state_in)

        assert len(state_out.deferred) == 1
        mocked_charm_holistic_handler.assert_not_called()
        mocked_migrate.assert_not_called()

    @patch("charm.CommandLine.migrate", side_effect=MigrationError)
    def test_when_migration_failed(
        self,
        mocked_migrate: MagicMock,
        mocked_migration_needed: MagicMock,
        base_container: testing.Container,
        peer_integration: testing.PeerRelation,
        database_integration: testing.Relation,
        mocked_charm_holistic_handler: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        ctx = testing.Context(IdentitySAMLProviderCharm)
        state_in = testing.State(
            containers={base_container},
            relations={peer_integration, database_integration},
            leader=True,
        )

        state_out = ctx.run(ctx.on.relation_changed(database_integration), state_in)

        mocked_charm_holistic_handler.assert_not_called()
        mocked_migrate.assert_called_once()
        assert len(state_out.deferred) == 0
        assert "Auto migration job failed" in caplog.text

    @patch("charm.CommandLine.migrate")
    def test_when_migration_succeeded(
        self,
        mocked_migrate: MagicMock,
        mocked_migration_needed: MagicMock,
        base_container: testing.Container,
        peer_integration: testing.PeerRelation,
        database_integration: testing.Relation,
        mocked_charm_holistic_handler: MagicMock,
        mocked_workload_service_version: MagicMock,
    ) -> None:
        ctx = testing.Context(IdentitySAMLProviderCharm)
        state_in = testing.State(
            containers={base_container},
            relations={peer_integration, database_integration},
            leader=True,
        )

        state_out = ctx.run(ctx.on.relation_changed(database_integration), state_in)

        mocked_charm_holistic_handler.assert_called_once()
        mocked_migrate.assert_called_once()

        peer = state_out.get_relation(peer_integration.id)
        assert peer is not None
        assert peer.local_app_data[f"migration_version_{database_integration.id}"] == '"1.0.0"'


class TestDatabaseChangedEvent:
    def test_when_all_prerequisites_met(
        self,
        base_container: testing.Container,
        peer_integration: testing.PeerRelation,
        database_integration: testing.Relation,
        mocked_database_resource_created: MagicMock,
        mocked_migration_not_needed: MagicMock,
        mocked_charm_holistic_handler: MagicMock,
    ) -> None:
        ctx = testing.Context(IdentitySAMLProviderCharm)
        state_in = testing.State(
            containers={base_container},
            relations={peer_integration, database_integration},
            leader=True,
        )

        ctx.run(ctx.on.relation_changed(database_integration), state_in)

        mocked_charm_holistic_handler.assert_called_once()


class TestDatabaseRelationBrokenEvent:
    def test_when_all_prerequisites_met(
        self,
        base_container: testing.Container,
        peer_integration: testing.PeerRelation,
        database_integration: testing.Relation,
        mocked_database_resource_created: MagicMock,
        mocked_migration_not_needed: MagicMock,
        mocked_charm_holistic_handler: MagicMock,
    ) -> None:
        ctx = testing.Context(IdentitySAMLProviderCharm)
        state_in = testing.State(
            containers={base_container},
            relations={peer_integration, database_integration},
            leader=True,
        )

        state_out = ctx.run(ctx.on.relation_broken(database_integration), state_in)

        mocked_charm_holistic_handler.assert_called_once()
        assert len(state_out.deferred) == 0


class TestOAuthInfoChangedEvent:
    def test_when_all_prerequisites_met(
        self,
        base_container: testing.Container,
        oauth_integration: testing.Relation,
        mocked_charm_holistic_handler: MagicMock,
    ) -> None:
        ctx = testing.Context(IdentitySAMLProviderCharm)
        state_in = testing.State(
            containers={base_container},
            relations={oauth_integration},
            leader=True,
        )

        ctx.run(ctx.on.relation_changed(oauth_integration), state_in)

        mocked_charm_holistic_handler.assert_called_once()


class TestCertificateTransferAvailableEvent:
    def test_when_all_prerequisites_met(
        self,
        base_container: testing.Container,
        certificate_transfer_integration: testing.Relation,
        mocked_charm_holistic_handler: MagicMock,
    ) -> None:
        ctx = testing.Context(IdentitySAMLProviderCharm)
        state_in = testing.State(
            containers={base_container},
            relations={certificate_transfer_integration},
            leader=True,
        )

        ctx.run(ctx.on.relation_changed(certificate_transfer_integration), state_in)

        mocked_charm_holistic_handler.assert_called_once()


class TestCertificateTransferBrokenEvent:
    def test_when_all_prerequisites_met(
        self,
        base_container: testing.Container,
        certificate_transfer_integration: testing.Relation,
        mocked_charm_holistic_handler: MagicMock,
    ) -> None:
        ctx = testing.Context(IdentitySAMLProviderCharm)
        state_in = testing.State(
            containers={base_container},
            relations={certificate_transfer_integration},
            leader=True,
        )

        ctx.run(ctx.on.relation_broken(certificate_transfer_integration), state_in)

        mocked_charm_holistic_handler.assert_called_once()


class TestHolisticHandler:
    def test_when_noop_conditions_not_met(
        self,
        base_container: testing.Container,
    ) -> None:
        ctx = testing.Context(IdentitySAMLProviderCharm)
        state_in = testing.State(containers={base_container}, leader=True)

        with patch("charm.PebbleService.plan") as mocked_plan:
            state_out = ctx.run(ctx.on.start(), state_in)

        mocked_plan.assert_not_called()
        assert len(state_out.deferred) == 0

    def test_when_container_not_connected(
        self,
        disconnected_container: testing.Container,
        peer_integration: testing.PeerRelation,
        database_integration: testing.Relation,
        oauth_integration: testing.Relation,
        oauth_secret: testing.Secret,
        mocked_database_resource_created: MagicMock,
        mocked_migration_not_needed: MagicMock,
    ) -> None:
        ctx = testing.Context(IdentitySAMLProviderCharm)
        state_in = testing.State(
            containers={disconnected_container},
            relations={peer_integration, database_integration, oauth_integration},
            secrets={oauth_secret},
            leader=True,
        )

        with patch("charm.PebbleService.plan") as mocked_plan:
            state_out = ctx.run(ctx.on.start(), state_in)

        assert len(state_out.deferred) == 1
        mocked_plan.assert_not_called()

    def test_when_pebble_service_plan_fails(
        self,
        base_container: testing.Container,
        peer_integration: testing.PeerRelation,
        database_integration: testing.Relation,
        oauth_integration: testing.Relation,
        oauth_secret: testing.Secret,
        mocked_database_resource_created: MagicMock,
        mocked_migration_not_needed: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        ctx = testing.Context(IdentitySAMLProviderCharm)
        state_in = testing.State(
            containers={base_container},
            relations={peer_integration, database_integration, oauth_integration},
            secrets={oauth_secret},
            leader=True,
        )

        with patch("charm.PebbleService.plan", side_effect=PebbleServiceError) as mocked_plan:
            ctx.run(ctx.on.start(), state_in)

        mocked_plan.assert_called_once()
        assert "Failed to start the service, please check the container logs" in caplog.text

    def test_when_database_has_tls_ca(
        self,
        base_container: testing.Container,
        peer_integration: testing.PeerRelation,
        oauth_integration: testing.Relation,
        oauth_secret: testing.Secret,
        mocked_database_resource_created: MagicMock,
        mocked_migration_not_needed: MagicMock,
    ) -> None:
        db_integration = testing.Relation(
            endpoint="database",
            interface="postgresql_client",
            remote_app_name="postgresql-k8s",
            remote_app_data={
                "data": '{"database": "saml_provider", "extra-user-roles": "SUPERUSER"}',
                "database": "database",
                "endpoints": "endpoints",
                "username": "username",
                "password": "password",
                "tls-ca": "-----BEGIN CERTIFICATE-----\nCA\n-----END CERTIFICATE-----",
            },
        )
        ctx = testing.Context(IdentitySAMLProviderCharm)
        state_in = testing.State(
            containers={base_container},
            relations={peer_integration, db_integration, oauth_integration},
            secrets={oauth_secret},
            leader=True,
        )

        with patch("charm.PebbleService.plan") as mocked_plan:
            ctx.run(ctx.on.start(), state_in)

        mocked_plan.assert_called_once()
        config_files = mocked_plan.call_args[0][1:]
        pg_certs = [f for f in config_files if isinstance(f, PostgreSQLCertificates)]
        assert len(pg_certs) == 1
        assert pg_certs[0].content == "-----BEGIN CERTIFICATE-----\nCA\n-----END CERTIFICATE-----"

    def test_when_db_sslmode_invalid_noop(
        self,
        base_container: testing.Container,
        peer_integration: testing.PeerRelation,
        database_integration: testing.Relation,
        oauth_integration: testing.Relation,
        oauth_secret: testing.Secret,
        mocked_database_resource_created: MagicMock,
        mocked_migration_not_needed: MagicMock,
    ) -> None:
        ctx = testing.Context(IdentitySAMLProviderCharm)
        state_in = testing.State(
            config={"db_sslmode": "invalid-sslmode"},
            containers={base_container},
            relations={peer_integration, database_integration, oauth_integration},
            secrets={oauth_secret},
            leader=True,
        )

        with patch("charm.PebbleService.plan") as mocked_plan:
            ctx.run(ctx.on.start(), state_in)

        mocked_plan.assert_not_called()


class TestCollectStatus:
    def test_when_invalid_db_sslmode(
        self,
        base_container: testing.Container,
        peer_integration: testing.PeerRelation,
        database_integration: testing.Relation,
        oauth_integration: testing.Relation,
        mocked_database_resource_created: MagicMock,
        mocked_migration_not_needed: MagicMock,
    ) -> None:
        public_route_integration = testing.Relation(
            endpoint="public-route",
            interface="traefik_route",
        )
        ctx = testing.Context(IdentitySAMLProviderCharm)
        state_in = testing.State(
            config={"db_sslmode": "invalid-mode"},
            containers={base_container},
            relations={
                peer_integration,
                database_integration,
                oauth_integration,
                public_route_integration,
            },
            leader=True,
        )

        state_out = ctx.run(ctx.on.collect_unit_status(), state_in)

        expected_status = BlockedStatus(
            f"Invalid db_sslmode 'invalid-mode'. Must be one of: {', '.join(VALID_DB_SSLMODES)}"
        )
        assert state_out.unit_status == expected_status

    def test_when_valid_db_sslmode(
        self,
        base_container: testing.Container,
        peer_integration: testing.PeerRelation,
        database_integration: testing.Relation,
        oauth_integration: testing.Relation,
        mocked_database_resource_created: MagicMock,
        mocked_migration_not_needed: MagicMock,
    ) -> None:
        public_route_integration = testing.Relation(
            endpoint="public-route",
            interface="traefik_route",
        )
        ctx = testing.Context(IdentitySAMLProviderCharm)
        state_in = testing.State(
            config={"db_sslmode": "verify-full"},
            containers={base_container},
            relations={
                peer_integration,
                database_integration,
                oauth_integration,
                public_route_integration,
            },
            leader=True,
        )

        state_out = ctx.run(ctx.on.collect_unit_status(), state_in)

        assert (
            not isinstance(state_out.unit_status, BlockedStatus)
            or "Invalid db_sslmode" not in state_out.unit_status.message
        )
