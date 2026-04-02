#!/usr/bin/env python3
# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
from pathlib import Path
from typing import Callable, Optional

import jubilant
import pytest
from integration.conftest import integrate_dependencies
from integration.constants import (
    APP_IMAGE,
    APP_NAME,
    CA_APP,
    DB_APP,
    HYDRA_APP,
    PUBLIC_INGRESS_DOMAIN,
    TRAEFIK_CHARM,
    TRAEFIK_PUBLIC_APP,
)
from integration.utils import (
    StatusPredicate,
    all_active,
    and_,
    any_error,
    is_blocked,
    is_waiting,
    remove_integration,
    unit_number,
)

from src.constants import (
    DATABASE_INTEGRATION_NAME,
    HYDRA_INTEGRATION_NAME,
    PUBLIC_ROUTE_INTEGRATION_NAME,
)

logger = logging.getLogger(__name__)


@pytest.mark.setup
def test_build_and_deploy(juju: jubilant.Juju, local_charm: Path) -> None:
    """Build and deploy the Identity SAML Provider charm with dependencies."""
    juju.deploy(
        DB_APP,
        channel="14/stable",
        trust=True,
    )
    juju.deploy(
        CA_APP,
        channel="latest/stable",
        trust=True,
    )
    juju.deploy(
        TRAEFIK_CHARM,
        app=TRAEFIK_PUBLIC_APP,
        channel="latest/edge",
        config={"external_hostname": PUBLIC_INGRESS_DOMAIN},
        trust=True,
    )
    juju.deploy(
        HYDRA_APP,
        channel="latest/edge",
        trust=True,
    )

    # Integrate Hydra with its dependencies
    juju.integrate(HYDRA_APP, DB_APP)
    juju.integrate(f"{TRAEFIK_PUBLIC_APP}:certificates", f"{CA_APP}:certificates")

    # Deploy the charm under test
    juju.deploy(
        str(local_charm),
        app=APP_NAME,
        resources={"oci-image": APP_IMAGE},
        trust=True,
    )

    # Integrate with dependencies
    integrate_dependencies(juju)

    juju.wait(
        ready=all_active(APP_NAME, DB_APP, CA_APP, TRAEFIK_PUBLIC_APP, HYDRA_APP),
        error=any_error(APP_NAME, DB_APP, CA_APP, TRAEFIK_PUBLIC_APP, HYDRA_APP),
        timeout=15 * 60,
    )


def test_public_route_integration(
    leader_public_route_integration_data: Optional[dict],
) -> None:
    """Test that public route integration data is present and valid."""
    assert leader_public_route_integration_data
    assert leader_public_route_integration_data.get("external_host") == PUBLIC_INGRESS_DOMAIN


def test_database_integration(
    leader_database_integration_data: Optional[dict],
) -> None:
    """Test that database integration data is present."""
    assert leader_database_integration_data


def test_oauth_integration(
    leader_oauth_integration_data: Optional[dict],
) -> None:
    """Test that OAuth integration data is present."""
    assert leader_oauth_integration_data


def test_scale_up(
    juju: jubilant.Juju,
    app_integration_data: Callable,
) -> None:
    """Test scaling up the application."""
    target_unit_number = 2
    juju.cli("scale-application", APP_NAME, str(target_unit_number))

    juju.wait(
        ready=and_(
            all_active(APP_NAME),
            unit_number(APP_NAME, target_unit_number),
        ),
        error=any_error(APP_NAME),
        timeout=5 * 60,
    )


@pytest.mark.parametrize(
    "remote_app_name,integration_name,is_status",
    [
        (DB_APP, DATABASE_INTEGRATION_NAME, is_blocked),
        (TRAEFIK_PUBLIC_APP, PUBLIC_ROUTE_INTEGRATION_NAME, is_waiting),
        (HYDRA_APP, HYDRA_INTEGRATION_NAME, is_waiting),
    ],
)
def test_remove_integration(
    juju: jubilant.Juju,
    remote_app_name: str,
    integration_name: str,
    is_status: Callable[[str], StatusPredicate],
) -> None:
    """Test removing and re-adding integrations."""
    with remove_integration(juju, remote_app_name, integration_name):
        juju.wait(
            ready=is_status(APP_NAME),
            error=any_error(APP_NAME),
            timeout=10 * 60,
        )
    juju.wait(
        ready=all_active(APP_NAME, remote_app_name),
        error=any_error(APP_NAME, remote_app_name),
        timeout=10 * 60,
    )


def test_scale_down(juju: jubilant.Juju) -> None:
    """Test scaling down the application."""
    target_unit_num = 1
    juju.cli("scale-application", APP_NAME, str(target_unit_num))

    juju.wait(
        ready=and_(
            all_active(APP_NAME),
            unit_number(APP_NAME, target_unit_num),
        ),
        error=any_error(APP_NAME),
        timeout=5 * 60,
    )


@pytest.mark.teardown
def test_remove_application(juju: jubilant.Juju) -> None:
    """Test removing the application."""
    juju.remove_application(APP_NAME, destroy_storage=True)
    juju.wait(lambda s: APP_NAME not in s.apps, timeout=1000)
