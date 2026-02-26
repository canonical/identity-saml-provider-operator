# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

from functools import wraps
from typing import TYPE_CHECKING, Any, Callable, Optional, TypeVar

from ops import CharmBase

from constants import (
    DATABASE_INTEGRATION_NAME,
    PEER_INTEGRATION_NAME,
    WORKLOAD_CONTAINER,
)

if TYPE_CHECKING:
    from charm import IdentitySAMLProviderCharm

CharmEventHandler = TypeVar("CharmEventHandler", bound=Callable[..., Any])
CharmType = TypeVar("CharmType", bound=CharmBase)
Condition = Callable[[CharmType], bool]


def leader_unit(func: CharmEventHandler) -> CharmEventHandler:
    """A decorator, applied to any event hook handler, to validate juju unit leadership."""

    @wraps(func)
    def wrapper(charm: CharmBase, *args: Any, **kwargs: Any) -> Optional[Any]:
        if not charm.unit.is_leader():
            return None

        return func(charm, *args, **kwargs)

    return wrapper  # type: ignore[return-value]


def integration_existence(integration_name: str) -> Condition:
    """A factory of integration existence condition."""

    def wrapped(charm: CharmBase) -> bool:
        return bool(charm.model.relations[integration_name])

    return wrapped


peer_integration_exists = integration_existence(PEER_INTEGRATION_NAME)
database_integration_exists = integration_existence(DATABASE_INTEGRATION_NAME)


def container_connectivity(charm: CharmBase) -> bool:
    return charm.unit.get_container(WORKLOAD_CONTAINER).can_connect()


def database_resource_is_created(charm: "IdentitySAMLProviderCharm") -> bool:
    return charm.database_requirer.is_resource_created()


def migration_is_ready(charm: "IdentitySAMLProviderCharm") -> bool:
    return not charm.migration_needed


# Condition failure causes early return without doing anything
NOOP_CONDITIONS: tuple[Condition, ...] = (
    peer_integration_exists,
    database_integration_exists,
    database_resource_is_created,
)

# Condition failure causes early return with corresponding event deferred
EVENT_DEFER_CONDITIONS: tuple[Condition, ...] = (container_connectivity,)
