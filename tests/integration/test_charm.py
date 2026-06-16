# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration tests for Identity SAML Provider Operator."""

import http
import logging
from pathlib import Path

import jubilant
import pytest
import requests

from tests.integration.util import (
    CA_APP,
    CA_CHARM,
    DB_APP,
    DB_CHARM,
    HYDRA_APP,
    HYDRA_CHARM,
    LOGIN_UI_APP,
    LOGIN_UI_CHARM,
    OCI_IMAGE,
    SAML_APP,
    TRAEFIK_APP,
    TRAEFIK_CHARM,
    all_active,
    and_,
    any_error,
    is_active,
    is_blocked,
    remove_integration,
    unit_number,
)

logger = logging.getLogger(__name__)

DEPLOY_TIMEOUT = 10 * 60
SETTLE_TIMEOUT = 5 * 60


@pytest.mark.juju_setup
def test_build_and_deploy(
    juju: jubilant.Juju, saml_charm: Path, saml_credentials_secret: str
) -> None:
    juju.deploy(
        charm=DB_CHARM,
        app=DB_APP,
        channel="14/stable",
        trust=True,
    )

    juju.deploy(
        charm=TRAEFIK_CHARM,
        app=TRAEFIK_APP,
        channel="latest/edge",
        trust=True,
    )

    juju.deploy(
        charm=LOGIN_UI_CHARM,
        app=LOGIN_UI_APP,
        channel="latest/stable",
        trust=True,
    )

    juju.deploy(
        charm=HYDRA_CHARM,
        app=HYDRA_APP,
        channel="latest/stable",
        trust=True,
    )

    juju.deploy(
        charm=CA_CHARM,
        app=CA_APP,
        channel="1/stable",
        revision=588,
        trust=True,
    )

    juju.deploy(
        charm=saml_charm,
        app=SAML_APP,
        resources={"oci-image": OCI_IMAGE},
        trust=True,
    )

    juju.grant_secret(saml_credentials_secret, SAML_APP)
    juju.config(SAML_APP, {"saml_credentials": saml_credentials_secret})

    juju.integrate(f"{TRAEFIK_APP}:certificates", CA_APP)
    juju.integrate(f"{HYDRA_APP}:pg-database", DB_APP)
    juju.integrate(f"{HYDRA_APP}:public-route", TRAEFIK_APP)
    juju.integrate(f"{HYDRA_APP}:ui-endpoint-info", LOGIN_UI_APP)

    # Wire up required integrations
    juju.integrate(f"{SAML_APP}:database", DB_APP)
    juju.integrate(f"{SAML_APP}:public-route", TRAEFIK_APP)
    juju.integrate(f"{SAML_APP}:oauth", HYDRA_APP)
    juju.integrate(f"{SAML_APP}:receive-ca-cert", CA_APP)

    juju.wait(
        ready=all_active(
            DB_APP,
            HYDRA_APP,
            TRAEFIK_APP,
            SAML_APP,
        ),
        error=any_error(
            DB_APP,
            HYDRA_APP,
            TRAEFIK_APP,
            SAML_APP,
        ),
        timeout=DEPLOY_TIMEOUT,
    )


def test_database_integration(database_integration_data: dict | None) -> None:
    assert database_integration_data, "Database integration data is empty."
    assert database_integration_data["database"]
    assert database_integration_data["endpoints"]
    assert database_integration_data["read-only-endpoints"]


def test_when_oauth_integration_data_is_present(oauth_integration_data: dict | None) -> None:
    assert oauth_integration_data, "OAuth integration data is empty."
    assert oauth_integration_data["issuer_url"]


def test_public_route_integration(public_route_integration_data: dict | None) -> None:
    assert public_route_integration_data, "Public route integration data is empty."
    assert public_route_integration_data["external_host"]
    assert public_route_integration_data["scheme"] == "https"


def test_certificate_transfer_integration(
    certificate_transfer_integration_data: dict | None,
) -> None:
    assert certificate_transfer_integration_data, "Certificate transfer integration data is empty."
    assert certificate_transfer_integration_data["certificates"]


@pytest.mark.parametrize(
    "endpoint",
    ["/healthz", "/readyz", "/saml/metadata"],
)
def test_application_endpoint(
    unit_address: str, http_client: requests.Session, endpoint: str
) -> None:
    url = f"http://{unit_address}:8082{endpoint}"

    resp = http_client.get(url, timeout=10)
    assert resp.status_code == http.HTTPStatus.OK, (
        f"{endpoint} returned unexpected status: {resp.status_code}"
    )


def test_run_migration_action(juju: jubilant.Juju) -> None:
    result = juju.run(f"{SAML_APP}/leader", "run-migration")
    assert result.status == "completed", (
        f"Expected run-migration action to complete, got {result.status}: {result.message}"
    )


def test_scale_up(juju: jubilant.Juju) -> None:
    juju.cli("scale-application", SAML_APP, "2")

    juju.wait(
        ready=and_(is_active(SAML_APP), unit_number(SAML_APP, 2)),
        error=any_error(SAML_APP),
        timeout=SETTLE_TIMEOUT,
    )


def test_remove_database_integration(juju: jubilant.Juju) -> None:
    with remove_integration(juju, DB_APP, "database"):
        juju.wait(
            ready=is_blocked(SAML_APP),
            timeout=SETTLE_TIMEOUT,
        )


def test_remove_public_route_integration(juju: jubilant.Juju) -> None:
    with remove_integration(juju, TRAEFIK_APP, "public-route"):
        juju.wait(
            ready=is_blocked(SAML_APP),
            timeout=SETTLE_TIMEOUT,
        )


def test_remove_oauth_integration(juju: jubilant.Juju) -> None:
    with remove_integration(juju, HYDRA_APP, "oauth"):
        juju.wait(
            ready=is_blocked(SAML_APP),
            timeout=SETTLE_TIMEOUT,
        )


def test_scale_down(juju: jubilant.Juju) -> None:
    juju.cli("scale-application", SAML_APP, "1")

    juju.wait(
        ready=and_(is_active(SAML_APP), unit_number(SAML_APP, 1)),
        error=any_error(SAML_APP),
        timeout=SETTLE_TIMEOUT,
    )


@pytest.mark.juju_teardown
def test_remove_application(juju: jubilant.Juju) -> None:
    juju.remove_application(SAML_APP)
