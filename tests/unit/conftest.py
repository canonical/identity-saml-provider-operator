# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

from unittest.mock import MagicMock, PropertyMock, create_autospec

import pytest
from ops import testing
from ops.model import ActiveStatus, Container, Model, Unit
from pytest_mock import MockerFixture

from constants import WORKLOAD_CONTAINER


@pytest.fixture(autouse=True)
def mocked_k8s_resource_patch(mocker: MockerFixture) -> None:
    mocked_patch = mocker.patch("charm.KubernetesComputeResourcesPatch", autospec=True)
    mocked_patch.return_value.get_status.return_value = ActiveStatus()


@pytest.fixture
def mocked_model() -> MagicMock:
    return create_autospec(Model)


@pytest.fixture
def mocked_container() -> MagicMock:
    return create_autospec(Container)


@pytest.fixture
def mocked_unit(mocked_container: MagicMock) -> MagicMock:
    mocked = create_autospec(Unit)
    mocked.get_container.return_value = mocked_container
    return mocked


@pytest.fixture
def mocked_workload_service_version(mocker: MockerFixture) -> MagicMock:
    return mocker.patch(
        "charm.WorkloadService.version", new_callable=PropertyMock, return_value="1.0.0"
    )


@pytest.fixture
def mocked_database_resource_created(mocker: MockerFixture) -> MagicMock:
    return mocker.patch("charm.DatabaseRequires.is_resource_created", return_value=True)


@pytest.fixture
def mocked_charm_holistic_handler(mocker: MockerFixture) -> MagicMock:
    return mocker.patch("charm.IdentitySAMLProviderCharm._holistic_handler")


@pytest.fixture
def mocked_migration_needed(mocker: MockerFixture) -> MagicMock:
    return mocker.patch(
        "charm.IdentitySAMLProviderCharm.migration_needed",
        new_callable=PropertyMock,
        return_value=True,
    )


@pytest.fixture
def mocked_migration_not_needed(mocker: MockerFixture) -> MagicMock:
    return mocker.patch(
        "charm.IdentitySAMLProviderCharm.migration_needed",
        new_callable=PropertyMock,
        return_value=False,
    )


@pytest.fixture()
def peer_integration() -> testing.PeerRelation:
    return testing.PeerRelation(
        endpoint="peer",
        interface="identity-saml-provider-peer",
    )


@pytest.fixture()
def database_integration() -> testing.Relation:
    return testing.Relation(
        endpoint="database",
        interface="postgresql_client",
        remote_app_name="postgresql-k8s",
        remote_app_data={
            "data": '{"database": "saml_provider", "extra-user-roles": "SUPERUSER"}',
            "database": "database",
            "endpoints": "endpoints",
            "username": "username",
            "password": "password",
        },
    )


@pytest.fixture
def oauth_integration() -> testing.Relation:
    return testing.Relation(
        endpoint="oauth",
        interface="oauth",
        remote_app_name="hydra",
        remote_app_data={
            "client_id": "test_id",
            "client_secret_id": "secret:123",
            "issuer_url": "https://issuer.com",
            "authorization_endpoint": "https://auth.com",
            "token_endpoint": "https://token.com",
            "introspection_endpoint": "https://intro.com",
            "userinfo_endpoint": "https://userinfo.com",
            "jwks_endpoint": "https://jwks.com",
            "scope": "openid",
        },
    )


@pytest.fixture
def certificate_transfer_integration() -> testing.Relation:
    return testing.Relation(
        endpoint="receive-ca-cert",
        interface="certificate_transfer",
        remote_app_name="self-signed-certificates",
    )


@pytest.fixture
def base_container() -> testing.Container:
    """Container fixture with can_connect=True."""
    return testing.Container(WORKLOAD_CONTAINER, can_connect=True)


@pytest.fixture
def disconnected_container() -> testing.Container:
    """Container fixture with can_connect=False."""
    return testing.Container(WORKLOAD_CONTAINER, can_connect=False)
