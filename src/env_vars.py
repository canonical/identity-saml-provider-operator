# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

from typing import Mapping, Protocol, TypeAlias

EnvVars: TypeAlias = Mapping[str, str | bool]


class EnvVarConvertible(Protocol):
    """An interface enforcing the contribution to workload service environment variables."""

    def to_env_vars(self) -> EnvVars:
        pass
