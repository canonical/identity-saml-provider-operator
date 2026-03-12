# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.


from typing import Any, MutableMapping, TypeAlias

from ops import ConfigData

from env_vars import EnvVars


class CharmConfig:
    """A class representing the data source of charm configurations."""

    def __init__(self, config: ConfigData) -> None:
        self._config = config

    def to_env_vars(self) -> EnvVars:
        return {
            "IDENTITY_SAML_LOG_LEVEL": self._config["log-level"],
        }


ServiceConfigs: TypeAlias = MutableMapping[str, Any]
