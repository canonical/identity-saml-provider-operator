# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Pytest fixtures for integration tests."""

import functools
import logging
import os
import subprocess
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Generator

import jubilant
import pytest
import requests
from cryptography import x509
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.hashes import SHA256
from cryptography.x509.oid import NameOID

from tests.integration.util import SAML_APP, get_app_integration_data

logger = logging.getLogger(__name__)


@pytest.fixture(scope="session")
def saml_charm() -> Path:
    if charm_path := os.getenv("CHARM_PATH"):
        path = Path(charm_path)
        if not path.exists():
            raise FileNotFoundError(
                f"CHARM_PATH is set to '{charm_path}' but the file does not exist"
            )
        return path.resolve()

    if local := next(Path(".").glob("identity-saml-provider-operator*.charm"), None):
        return local.resolve()

    logger.info("No charm file found — running 'charmcraft pack'")
    try:
        subprocess.run(["charmcraft", "pack"], check=True)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"SAML charm build failed: {e}") from e

    if packed := next(Path(".").glob("identity-saml-provider-operator*.charm"), None):
        return packed.resolve()

    raise RuntimeError("charmcraft pack succeeded but no .charm file was produced")


@pytest.fixture(scope="module")
def saml_credentials_secret(juju: jubilant.Juju) -> str:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_key_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")

    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, "test-saml-provider"),
    ])
    cert = (
        x509
        .CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(timezone.utc))
        .not_valid_after(datetime.now(timezone.utc) + timedelta(days=1))
        .sign(private_key, SHA256())
    )
    public_cert_pem = cert.public_bytes(serialization.Encoding.PEM).decode("utf-8")

    secret_content = {
        "private-key": private_key_pem,
        "public-cert": public_cert_pem,
    }
    secret_uri = juju.add_secret("test-saml-credentials", content=secret_content)

    return secret_uri


@pytest.fixture
def app_integration_data(juju: jubilant.Juju) -> Callable:
    return functools.partial(get_app_integration_data, juju)


@pytest.fixture
def database_integration_data(app_integration_data: Callable) -> dict | None:
    return app_integration_data(SAML_APP, "database")


@pytest.fixture
def oauth_integration_data(app_integration_data: Callable) -> dict | None:
    return app_integration_data(SAML_APP, "oauth")


@pytest.fixture
def public_route_integration_data(app_integration_data: Callable) -> dict | None:
    return app_integration_data(SAML_APP, "public-route")


@pytest.fixture
def certificate_transfer_integration_data(app_integration_data: Callable) -> dict | None:
    return app_integration_data(SAML_APP, "receive-ca-cert")


@pytest.fixture
def unit_address(juju: jubilant.Juju) -> str:
    status = juju.status()
    unit = status.apps[SAML_APP].units[f"{SAML_APP}/0"]
    return unit.address


@pytest.fixture
def http_client() -> Generator[requests.Session, None, None]:
    with requests.Session() as client:
        client.verify = False
        yield client
