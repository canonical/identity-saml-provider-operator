# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

from functools import wraps
from typing import TYPE_CHECKING, Any, Callable, Optional, TypeVar

from ops import CharmBase

from constants import (
    CERTIFICATE_TRANSFER_INTEGRATION_NAME,
    DATABASE_INTEGRATION_NAME,
    OAUTH_INTEGRATION_NAME,
    PEER_INTEGRATION_NAME,
    PUBLIC_ROUTE_INTEGRATION_NAME,
    SAML_BRIDGE_CERT,
    SAML_BRIDGE_KEY,
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
public_route_integration_exists = integration_existence(PUBLIC_ROUTE_INTEGRATION_NAME)
oauth_integration_exists = integration_existence(OAUTH_INTEGRATION_NAME)
certificate_transfer_integration_exists = integration_existence(
    CERTIFICATE_TRANSFER_INTEGRATION_NAME
)


def container_connectivity(charm: CharmBase) -> bool:
    return charm.unit.get_container(WORKLOAD_CONTAINER).can_connect()


def database_resource_is_created(charm: "IdentitySAMLProviderCharm") -> bool:
    return charm.database_requirer.is_resource_created()


def migration_is_ready(charm: "IdentitySAMLProviderCharm") -> bool:
    return not charm.migration_needed


def saml_bridge_certs_exist(charm: CharmBase) -> bool:
    container = charm.unit.get_container(WORKLOAD_CONTAINER)
    return (
        container.can_connect()
        and container.exists(SAML_BRIDGE_CERT)
        and container.exists(SAML_BRIDGE_KEY)
    )


# Condition failure causes early return without doing anything
NOOP_CONDITIONS: tuple[Condition, ...] = (
    peer_integration_exists,
    database_integration_exists,
    database_resource_is_created,
    certificate_transfer_integration_exists,
    migration_is_ready,
)

# Condition failure causes early return with corresponding event deferred
EVENT_DEFER_CONDITIONS: tuple[Condition, ...] = (container_connectivity,)
