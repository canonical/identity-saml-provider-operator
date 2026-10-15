# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

from unittest.mock import MagicMock, PropertyMock, patch

import pytest
from ops import testing

from charm import IdentitySAMLProviderCharm
from constants import DEFAULT_ACS_BINDING
from exceptions import MigrationError, ServiceProviderError


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


class TestCreateServiceProviderAction:
    @patch("charm.WorkloadService.create_service_provider")
    def test_when_container_not_connected(
        self,
        mocked_create: MagicMock,
        disconnected_container: testing.Container,
    ) -> None:
        ctx = testing.Context(IdentitySAMLProviderCharm)
        state_in = testing.State(containers={disconnected_container})

        with pytest.raises(testing.ActionFailed, match="Container is not connected yet"):
            ctx.run(
                ctx.on.action(
                    "create-service-provider",
                    params={
                        "entity-id": "https://sp.example.com",
                        "acs-url": "https://sp.example.com/acs",
                    },
                ),
                state_in,
            )

        mocked_create.assert_not_called()

    @patch("charm.WorkloadService.create_service_provider")
    def test_when_service_not_running(
        self,
        mocked_create: MagicMock,
        base_container: testing.Container,
    ) -> None:
        ctx = testing.Context(IdentitySAMLProviderCharm)
        state_in = testing.State(containers={base_container})

        with (
            patch(
                "charm.WorkloadService.is_running", new_callable=PropertyMock, return_value=False
            ),
            pytest.raises(testing.ActionFailed, match="Workload service is not ready yet"),
        ):
            ctx.run(
                ctx.on.action(
                    "create-service-provider",
                    params={
                        "entity-id": "https://sp.example.com",
                        "acs-url": "https://sp.example.com/acs",
                    },
                ),
                state_in,
            )

        mocked_create.assert_not_called()

    @patch("charm.WorkloadService.create_service_provider")
    def test_when_service_not_ready(
        self,
        mocked_create: MagicMock,
        base_container: testing.Container,
        mocked_workload_service_running: MagicMock,
    ) -> None:
        ctx = testing.Context(IdentitySAMLProviderCharm)
        state_in = testing.State(containers={base_container})

        with (
            patch("charm.WorkloadService.is_ready", new_callable=PropertyMock, return_value=False),
            pytest.raises(testing.ActionFailed, match="Workload service is not ready yet"),
        ):
            ctx.run(
                ctx.on.action(
                    "create-service-provider",
                    params={
                        "entity-id": "https://sp.example.com",
                        "acs-url": "https://sp.example.com/acs",
                    },
                ),
                state_in,
            )

        mocked_create.assert_not_called()

    @patch(
        "charm.WorkloadService.create_service_provider",
        side_effect=ServiceProviderError("invalid acs_url"),
    )
    def test_when_creation_fails(
        self,
        mocked_create: MagicMock,
        base_container: testing.Container,
        mocked_workload_service_running: MagicMock,
        mocked_workload_service_ready: MagicMock,
    ) -> None:
        ctx = testing.Context(IdentitySAMLProviderCharm)
        state_in = testing.State(containers={base_container})

        with pytest.raises(
            testing.ActionFailed, match="Failed to create service provider: invalid acs_url"
        ):
            ctx.run(
                ctx.on.action(
                    "create-service-provider",
                    params={
                        "entity-id": "https://sp.example.com",
                        "acs-url": "invalid",
                    },
                ),
                state_in,
            )

        mocked_create.assert_called_once()

    @patch("charm.WorkloadService.create_service_provider")
    def test_when_creation_succeeds(
        self,
        mocked_create: MagicMock,
        base_container: testing.Container,
        mocked_workload_service_running: MagicMock,
        mocked_workload_service_ready: MagicMock,
    ) -> None:
        mocked_create.return_value = {
            "status": "success",
            "message": "Service provider registered",
            "entity-id": "https://sp.example.com",
        }
        ctx = testing.Context(IdentitySAMLProviderCharm)
        state_in = testing.State(containers={base_container})

        ctx.run(
            ctx.on.action(
                "create-service-provider",
                params={
                    "entity-id": "https://sp.example.com",
                    "acs-url": "https://sp.example.com/acs",
                    "attribute-mapping": '{"name_id_format": "email"}',
                },
            ),
            state_in,
        )

        mocked_create.assert_called_once_with(
            entity_id="https://sp.example.com",
            acs_url="https://sp.example.com/acs",
            acs_binding=DEFAULT_ACS_BINDING,
            attribute_mapping='{"name_id_format": "email"}',
        )
        assert ctx.action_results == {
            "status": "success",
            "message": "Service provider registered",
            "entity-id": "https://sp.example.com",
        }


class TestUpdateServiceProviderAction:
    @patch("charm.WorkloadService.update_service_provider")
    def test_when_container_not_connected(
        self,
        mocked_update: MagicMock,
        disconnected_container: testing.Container,
    ) -> None:
        ctx = testing.Context(IdentitySAMLProviderCharm)
        state_in = testing.State(containers={disconnected_container})

        with pytest.raises(testing.ActionFailed, match="Container is not connected yet"):
            ctx.run(
                ctx.on.action(
                    "update-service-provider",
                    params={"entity-id": "https://sp.example.com"},
                ),
                state_in,
            )

        mocked_update.assert_not_called()

    @patch("charm.WorkloadService.update_service_provider")
    def test_when_service_not_ready(
        self,
        mocked_update: MagicMock,
        base_container: testing.Container,
        mocked_workload_service_running: MagicMock,
    ) -> None:
        ctx = testing.Context(IdentitySAMLProviderCharm)
        state_in = testing.State(containers={base_container})

        with (
            patch("charm.WorkloadService.is_ready", new_callable=PropertyMock, return_value=False),
            pytest.raises(testing.ActionFailed, match="Workload service is not ready yet"),
        ):
            ctx.run(
                ctx.on.action(
                    "update-service-provider",
                    params={"entity-id": "https://sp.example.com"},
                ),
                state_in,
            )

        mocked_update.assert_not_called()

    @patch(
        "charm.WorkloadService.update_service_provider",
        side_effect=ServiceProviderError("service_provider not found"),
    )
    def test_when_update_fails(
        self,
        mocked_update: MagicMock,
        base_container: testing.Container,
        mocked_workload_service_running: MagicMock,
        mocked_workload_service_ready: MagicMock,
    ) -> None:
        ctx = testing.Context(IdentitySAMLProviderCharm)
        state_in = testing.State(containers={base_container})

        with pytest.raises(
            testing.ActionFailed,
            match="Failed to update service provider: service_provider not found",
        ):
            ctx.run(
                ctx.on.action(
                    "update-service-provider",
                    params={
                        "entity-id": "https://sp.example.com",
                        "acs-url": "https://sp.example.com/new-acs",
                    },
                ),
                state_in,
            )

        mocked_update.assert_called_once()

    @patch("charm.WorkloadService.update_service_provider")
    def test_when_update_succeeds(
        self,
        mocked_update: MagicMock,
        base_container: testing.Container,
        mocked_workload_service_running: MagicMock,
        mocked_workload_service_ready: MagicMock,
    ) -> None:
        mocked_update.return_value = {
            "status": "success",
            "message": "Attribute mapping updated",
        }
        ctx = testing.Context(IdentitySAMLProviderCharm)
        state_in = testing.State(containers={base_container})

        ctx.run(
            ctx.on.action(
                "update-service-provider",
                params={
                    "entity-id": "https://sp.example.com",
                    "attribute-mapping": '{"name_id_format": "persistent"}',
                },
            ),
            state_in,
        )

        mocked_update.assert_called_once_with(
            entity_id="https://sp.example.com",
            acs_url=None,
            acs_binding=None,
            attribute_mapping='{"name_id_format": "persistent"}',
        )
        assert ctx.action_results == {
            "status": "success",
            "message": "Attribute mapping updated",
        }


class TestGetServiceProviderAction:
    @patch("charm.WorkloadService.get_service_provider")
    def test_when_container_not_connected(
        self,
        mocked_get: MagicMock,
        disconnected_container: testing.Container,
    ) -> None:
        ctx = testing.Context(IdentitySAMLProviderCharm)
        state_in = testing.State(containers={disconnected_container})

        with pytest.raises(testing.ActionFailed, match="Container is not connected yet"):
            ctx.run(
                ctx.on.action(
                    "get-service-provider",
                    params={"entity-id": "https://sp.example.com"},
                ),
                state_in,
            )

        mocked_get.assert_not_called()

    @patch("charm.WorkloadService.get_service_provider")
    def test_when_service_not_ready(
        self,
        mocked_get: MagicMock,
        base_container: testing.Container,
        mocked_workload_service_running: MagicMock,
    ) -> None:
        ctx = testing.Context(IdentitySAMLProviderCharm)
        state_in = testing.State(containers={base_container})

        with (
            patch("charm.WorkloadService.is_ready", new_callable=PropertyMock, return_value=False),
            pytest.raises(testing.ActionFailed, match="Workload service is not ready yet"),
        ):
            ctx.run(
                ctx.on.action(
                    "get-service-provider",
                    params={"entity-id": "https://sp.example.com"},
                ),
                state_in,
            )

        mocked_get.assert_not_called()

    @patch(
        "charm.WorkloadService.get_service_provider",
        side_effect=ServiceProviderError("service_provider not found"),
    )
    def test_when_get_fails(
        self,
        mocked_get: MagicMock,
        base_container: testing.Container,
        mocked_workload_service_running: MagicMock,
        mocked_workload_service_ready: MagicMock,
    ) -> None:
        ctx = testing.Context(IdentitySAMLProviderCharm)
        state_in = testing.State(containers={base_container})

        with pytest.raises(
            testing.ActionFailed,
            match="Failed to get service provider: service_provider not found",
        ):
            ctx.run(
                ctx.on.action(
                    "get-service-provider",
                    params={"entity-id": "https://sp.example.com"},
                ),
                state_in,
            )

        mocked_get.assert_called_once()

    @patch("charm.WorkloadService.get_service_provider")
    def test_when_get_succeeds(
        self,
        mocked_get: MagicMock,
        base_container: testing.Container,
        mocked_workload_service_running: MagicMock,
        mocked_workload_service_ready: MagicMock,
    ) -> None:
        mocked_get.return_value = {
            "entity-id": "https://sp.example.com",
            "acs-url": "https://sp.example.com/acs",
            "acs-binding": DEFAULT_ACS_BINDING,
            "attribute-mapping": '{"options": {}}',
        }
        ctx = testing.Context(IdentitySAMLProviderCharm)
        state_in = testing.State(containers={base_container})

        ctx.run(
            ctx.on.action(
                "get-service-provider",
                params={"entity-id": "https://sp.example.com"},
            ),
            state_in,
        )

        mocked_get.assert_called_once_with(entity_id="https://sp.example.com")
        assert ctx.action_results == {
            "entity-id": "https://sp.example.com",
            "acs-url": "https://sp.example.com/acs",
            "acs-binding": DEFAULT_ACS_BINDING,
            "attribute-mapping": '{"options": {}}',
        }


class TestDeleteServiceProviderAction:
    @patch("charm.WorkloadService.delete_service_provider")
    def test_when_container_not_connected(
        self,
        mocked_delete: MagicMock,
        disconnected_container: testing.Container,
    ) -> None:
        ctx = testing.Context(IdentitySAMLProviderCharm)
        state_in = testing.State(containers={disconnected_container})

        with pytest.raises(testing.ActionFailed, match="Container is not connected yet"):
            ctx.run(
                ctx.on.action(
                    "delete-service-provider",
                    params={"entity-id": "https://sp.example.com"},
                ),
                state_in,
            )

        mocked_delete.assert_not_called()

    @patch("charm.WorkloadService.delete_service_provider")
    def test_when_service_not_ready(
        self,
        mocked_delete: MagicMock,
        base_container: testing.Container,
        mocked_workload_service_running: MagicMock,
    ) -> None:
        ctx = testing.Context(IdentitySAMLProviderCharm)
        state_in = testing.State(containers={base_container})

        with (
            patch("charm.WorkloadService.is_ready", new_callable=PropertyMock, return_value=False),
            pytest.raises(testing.ActionFailed, match="Workload service is not ready yet"),
        ):
            ctx.run(
                ctx.on.action(
                    "delete-service-provider",
                    params={"entity-id": "https://sp.example.com"},
                ),
                state_in,
            )

        mocked_delete.assert_not_called()

    @patch(
        "charm.WorkloadService.delete_service_provider",
        side_effect=ServiceProviderError("service_provider not found"),
    )
    def test_when_delete_fails(
        self,
        mocked_delete: MagicMock,
        base_container: testing.Container,
        mocked_workload_service_running: MagicMock,
        mocked_workload_service_ready: MagicMock,
    ) -> None:
        ctx = testing.Context(IdentitySAMLProviderCharm)
        state_in = testing.State(containers={base_container})

        with pytest.raises(
            testing.ActionFailed,
            match="Failed to delete service provider: service_provider not found",
        ):
            ctx.run(
                ctx.on.action(
                    "delete-service-provider",
                    params={"entity-id": "https://sp.example.com"},
                ),
                state_in,
            )

        mocked_delete.assert_called_once()

    @patch("charm.WorkloadService.delete_service_provider")
    def test_when_delete_succeeds(
        self,
        mocked_delete: MagicMock,
        base_container: testing.Container,
        mocked_workload_service_running: MagicMock,
        mocked_workload_service_ready: MagicMock,
    ) -> None:
        mocked_delete.return_value = {
            "status": "success",
            "message": "Attribute mapping cleared",
        }
        ctx = testing.Context(IdentitySAMLProviderCharm)
        state_in = testing.State(containers={base_container})

        ctx.run(
            ctx.on.action(
                "delete-service-provider",
                params={"entity-id": "https://sp.example.com"},
            ),
            state_in,
        )

        mocked_delete.assert_called_once_with(entity_id="https://sp.example.com")
        assert ctx.action_results == {
            "status": "success",
            "message": "Attribute mapping cleared",
        }
