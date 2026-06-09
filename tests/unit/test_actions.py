# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

from unittest.mock import MagicMock, patch

import pytest
from ops import testing

from charm import IdentitySAMLProviderCharm
from exceptions import MigrationError


class TestRunMigrationAction:
    @patch("charm.CommandLine.migrate")
    def test_when_not_leader_unit(
        self,
        mocked_cli: MagicMock,
        base_container: testing.Container,
        peer_integration: testing.PeerRelation,
        database_integration: testing.Relation,
        mocked_database_resource_created: MagicMock,
    ) -> None:
        ctx = testing.Context(IdentitySAMLProviderCharm)
        state_in = testing.State(
            containers={base_container},
            relations={peer_integration},
            leader=False,
        )

        with pytest.raises(
            testing.ActionFailed, match="Only the leader unit can run the database migration"
        ):
            ctx.run(ctx.on.action(name="run-migration"), state_in)

        mocked_cli.assert_not_called()

    @patch("charm.CommandLine.migrate")
    def test_when_container_not_connected(
        self,
        mocked_cli: MagicMock,
        disconnected_container: testing.Container,
        peer_integration: testing.PeerRelation,
        database_integration: testing.Relation,
        mocked_database_resource_created: MagicMock,
    ) -> None:
        ctx = testing.Context(IdentitySAMLProviderCharm)
        state_in = testing.State(
            containers={disconnected_container},
            relations={peer_integration},
            leader=True,
        )

        with pytest.raises(testing.ActionFailed, match="Container is not connected yet"):
            ctx.run(ctx.on.action(name="run-migration"), state_in)

        mocked_cli.assert_not_called()

    @patch("charm.CommandLine.migrate")
    def test_when_peer_integration_not_ready(
        self,
        mocked_cli: MagicMock,
        base_container: testing.Container,
        database_integration: testing.Relation,
        mocked_database_resource_created: MagicMock,
    ) -> None:
        ctx = testing.Context(IdentitySAMLProviderCharm)
        state_in = testing.State(
            containers={base_container},
            leader=True,
        )

        with pytest.raises(testing.ActionFailed, match="Peer integration is not ready"):
            ctx.run(ctx.on.action(name="run-migration"), state_in)

        mocked_cli.assert_not_called()

    @patch("charm.CommandLine.migrate", side_effect=MigrationError("boom"))
    def test_when_migration_fails(
        self,
        mocked_cli: MagicMock,
        base_container: testing.Container,
        peer_integration: testing.PeerRelation,
        database_integration: testing.Relation,
        mocked_database_resource_created: MagicMock,
    ) -> None:
        ctx = testing.Context(IdentitySAMLProviderCharm)
        state_in = testing.State(
            containers={base_container},
            relations={peer_integration, database_integration},
            leader=True,
        )

        with pytest.raises(testing.ActionFailed, match="Database migration failed: boom"):
            ctx.run(ctx.on.action("run-migration"), state_in)

        mocked_cli.assert_called_once()

    @patch("charm.CommandLine.migrate")
    def test_when_migration_succeeds(
        self,
        mocked_cli: MagicMock,
        base_container: testing.Container,
        peer_integration: testing.PeerRelation,
        database_integration: testing.Relation,
        mocked_workload_service_version: MagicMock,
    ) -> None:
        ctx = testing.Context(IdentitySAMLProviderCharm)
        state_in = testing.State(
            containers={base_container},
            relations={peer_integration, database_integration},
            leader=True,
        )

        state_out = ctx.run(ctx.on.action("run-migration"), state_in)

        mocked_cli.assert_called_once()
        assert "Started migrating the database" in ctx.action_logs
        assert "Successfully migrated the database" in ctx.action_logs
        assert "Successfully updated migration version" in ctx.action_logs

        peer = state_out.get_relation(peer_integration.id)
        assert peer is not None
        assert peer.local_app_data[f"migration_version_{database_integration.id}"] == '"1.0.0"'
