# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

from dataclasses import replace
from unittest.mock import MagicMock

import pytest
from ops.testing import Container, Context, PeerRelation, Relation, State
from pytest_mock import MockerFixture

from charm import IdentitySAMLProviderCharm
from constants import (
    CERTIFICATE_TRANSFER_INTEGRATION_NAME,
    CERTIFICATES_INTEGRATION_NAME,
    DATABASE_INTEGRATION_NAME,
    HYDRA_INTEGRATION_NAME,
    PEER_INTEGRATION_NAME,
    PUBLIC_ROUTE_INTEGRATION_NAME,
    WORKLOAD_CONTAINER,
)


@pytest.fixture()
def mocked_resource_patch(mocker: MockerFixture) -> MagicMock:
    mocked = mocker.patch(
        "charms.observability_libs.v0.kubernetes_compute_resources_patch.ResourcePatcher",
        autospec=True,
    )
    mocked.return_value.is_failed.return_value = (False, "")
    mocked.return_value.is_in_progress.return_value = False
    return mocked


@pytest.fixture(autouse=True)
def mocked_k8s_resource_patch(mocker: MockerFixture, mocked_resource_patch: MagicMock) -> None:
    mocker.patch.multiple(
        "charm.KubernetesComputeResourcesPatch",
        _namespace="testing",
        _patch=lambda *a, **kw: True,
        is_ready=lambda *a, **kw: True,
    )


@pytest.fixture
def context():
    return Context(IdentitySAMLProviderCharm)


@pytest.fixture
def container() -> Container:
    return Container(
        name=WORKLOAD_CONTAINER,
        can_connect=True,
    )


@pytest.fixture
def peer_relation() -> PeerRelation:
    return PeerRelation(PEER_INTEGRATION_NAME)


@pytest.fixture
def db_relation() -> Relation:
    return Relation(DATABASE_INTEGRATION_NAME)


@pytest.fixture
def db_relation_ready(db_relation: Relation) -> Relation:
    return replace(
        db_relation,
        remote_app_data={
            "database": "saml_provider",
            "endpoints": "postgresql-k8s:5432",
            "username": "test_user",
            "password": "test_password",
        },
    )


@pytest.fixture
def public_route_relation() -> Relation:
    return Relation(PUBLIC_ROUTE_INTEGRATION_NAME)


@pytest.fixture
def public_route_relation_ready() -> Relation:
    return Relation(
        PUBLIC_ROUTE_INTEGRATION_NAME,
        remote_app_data={"external_host": "example.com", "scheme": "https"},
    )


@pytest.fixture
def oauth_relation() -> Relation:
    return Relation(HYDRA_INTEGRATION_NAME)


@pytest.fixture
def certificates_relation() -> Relation:
    return Relation(CERTIFICATES_INTEGRATION_NAME, remote_app_data={})


@pytest.fixture
def certificate_transfer_relation() -> Relation:
    return Relation(CERTIFICATE_TRANSFER_INTEGRATION_NAME)


def create_state(
    leader: bool = True,
    relations: list | None = None,
    containers: list | None = None,
    config: dict | None = None,
    can_connect: bool = True,
) -> State:
    if relations is None:
        relations = []
    if containers is None:
        containers = [
            Container(
                name=WORKLOAD_CONTAINER,
                can_connect=can_connect,
            )
        ]
    if config is None:
        config = {}

    return State(
        leader=leader,
        containers=containers,
        relations=relations,
        config=config,
    )
