# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import os
import secrets
import subprocess
from contextlib import suppress
from pathlib import Path
from typing import Callable, Generator

import jubilant
import pytest
from integration.constants import (
    APP_NAME,
    CA_APP,
    DB_APP,
    HYDRA_APP,
    TRAEFIK_PUBLIC_APP,
)
from integration.utils import (
    get_app_integration_data,
    juju_model_factory,
)

from src.constants import (
    CERTIFICATES_INTEGRATION_NAME,
    DATABASE_INTEGRATION_NAME,
    HYDRA_INTEGRATION_NAME,
    PUBLIC_ROUTE_INTEGRATION_NAME,
)


def pytest_addoption(parser: pytest.Parser) -> None:
    """Add custom command-line options for model management and deployment control."""
    parser.addoption(
        "--keep-models",
        "--no-teardown",
        action="store_true",
        dest="no_teardown",
        default=False,
        help="Keep the model after the test is finished.",
    )
    parser.addoption(
        "--model",
        action="store",
        dest="model",
        default=None,
        help="The model to run the tests on.",
    )
    parser.addoption(
        "--no-deploy",
        "--no-setup",
        action="store_true",
        dest="no_setup",
        default=False,
        help="Skip deployment of the charm.",
    )


def pytest_configure(config: pytest.Config) -> None:
    """Register custom markers for test selection."""
    config.addinivalue_line("markers", "setup: tests that setup some parts of the environment")
    config.addinivalue_line(
        "markers", "teardown: tests that teardown some parts of the environment."
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Modify collected test items based on command-line options."""
    skip_setup = pytest.mark.skip(reason="no_setup provided")
    skip_teardown = pytest.mark.skip(reason="no_teardown provided")
    for item in items:
        if config.getoption("no_setup") and "setup" in item.keywords:
            item.add_marker(skip_setup)
        if config.getoption("no_teardown") and "teardown" in item.keywords:
            item.add_marker(skip_teardown)


@pytest.fixture(scope="module")
def juju(request: pytest.FixtureRequest) -> Generator[jubilant.Juju, None, None]:
    """Create a temporary Juju model for integration tests."""
    model_name = request.config.getoption("--model")
    if not model_name:
        model_name = f"test-saml-{secrets.token_hex(4)}"

    juju_ = juju_model_factory(model_name)
    juju_.wait_timeout = 10 * 60

    try:
        yield juju_
    finally:
        if request.session.testsfailed:
            log = juju_.debug_log(limit=1000)
            print(log, end="")

        no_teardown = bool(request.config.getoption("--no-teardown"))
        keep_model = no_teardown or request.session.testsfailed > 0
        if not keep_model:
            with suppress(jubilant.CLIError):
                args = [
                    "destroy-model",
                    juju_.model,
                    "--no-prompt",
                    "--destroy-storage",
                    "--force",
                    "--timeout",
                    "600s",
                ]
                juju_.cli(*args, include_model=False)


@pytest.fixture(scope="session")
def local_charm() -> Path:
    """Get the path to the charm-under-test."""
    charm: str | Path | None = os.getenv("CHARM_PATH")
    if not charm:
        subprocess.run(["charmcraft", "pack"], check=True)
        if not (charms := list(Path(".").glob("*.charm"))):
            raise RuntimeError("Charm not found and build failed")
        charm = charms[0].absolute()
    return Path(charm)


@pytest.fixture
def app_integration_data(juju: jubilant.Juju) -> Callable:
    def _get_data(app_name: str, integration_name: str, unit_num: int = 0):
        return get_app_integration_data(juju, app_name, integration_name, unit_num)

    return _get_data


@pytest.fixture
def leader_public_route_integration_data(app_integration_data: Callable) -> dict | None:
    return app_integration_data(APP_NAME, PUBLIC_ROUTE_INTEGRATION_NAME)


@pytest.fixture
def leader_oauth_integration_data(app_integration_data: Callable) -> dict | None:
    return app_integration_data(APP_NAME, HYDRA_INTEGRATION_NAME)


@pytest.fixture
def leader_database_integration_data(app_integration_data: Callable) -> dict | None:
    return app_integration_data(APP_NAME, DATABASE_INTEGRATION_NAME)


@pytest.fixture
def leader_peer_integration_data(app_integration_data: Callable) -> dict | None:
    return app_integration_data(APP_NAME, APP_NAME)


def integrate_dependencies(juju: jubilant.Juju) -> None:
    """Integrate the charm with all required dependencies."""
    juju.integrate(APP_NAME, DB_APP)
    juju.integrate(f"{APP_NAME}:{PUBLIC_ROUTE_INTEGRATION_NAME}", TRAEFIK_PUBLIC_APP)
    juju.integrate(f"{APP_NAME}:{HYDRA_INTEGRATION_NAME}", HYDRA_APP)
    juju.integrate(f"{APP_NAME}:{CERTIFICATES_INTEGRATION_NAME}", f"{CA_APP}:certificates")
