# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

from typing import Mapping, Protocol, TypeAlias, Union

EnvVars: TypeAlias = Mapping[str, Union[str, bool]]

DEFAULT_CONTAINER_ENV = {
    "KRATOS_OIDC_PROVIDER_CLIENT_ID": "my-client-id",
    "KRATOS_OIDC_PROVIDER_CLIENT_SECRET": "my-client-secret",
}


class EnvVarConvertible(Protocol):
    """An interface enforcing the contribution to workload service environment variables."""

    def to_env_vars(self) -> EnvVars:
        pass
