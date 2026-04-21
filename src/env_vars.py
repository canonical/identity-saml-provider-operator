# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

from typing import Mapping, Protocol, TypeAlias

from constants import APPLICATION_PORT, HYDRA_CA_CERT, SAML_BRIDGE_CERT, SAML_BRIDGE_KEY

EnvVars: TypeAlias = Mapping[str, str | bool]

DEFAULT_CONTAINER_ENV = {
    "SAML_PROVIDER_BRIDGE_BASE_PORT": str(APPLICATION_PORT),
    "SAML_PROVIDER_HYDRA_CA_CERT_PATH": str(HYDRA_CA_CERT),
    "SAML_PROVIDER_CERT_PATH": str(SAML_BRIDGE_CERT),
    "SAML_PROVIDER_KEY_PATH": str(SAML_BRIDGE_KEY),
}


class EnvVarConvertible(Protocol):
    """An interface enforcing the contribution to workload service environment variables."""

    def to_env_vars(self) -> EnvVars:
        pass
