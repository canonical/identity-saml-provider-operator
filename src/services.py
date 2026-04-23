# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
from collections import ChainMap

from ops import Container, ModelError, Unit
from ops.pebble import ConnectionError as PebbleConnectionError
from ops.pebble import Layer, LayerDict

from configs import ContainerFile
from constants import (
    APPLICATION_PORT,
    WORKLOAD_CONTAINER,
    WORKLOAD_SERVICE,
)
from env_vars import DEFAULT_CONTAINER_ENV, EnvVarConvertible
from exceptions import PebbleServiceError

logger = logging.getLogger(__name__)

PEBBLE_LAYER_DICT = {
    "summary": "pebble layer",
    "description": "pebble layer for identity saml provider",
    "services": {
        WORKLOAD_SERVICE: {
            "override": "replace",
            "summary": "Identity SAML provider service",
            "command": "/usr/bin/identity-saml-provider",
            "startup": "disabled",
        }
    },
}


class WorkloadService:
    """Workload service abstraction running in a Juju unit."""

    def __init__(self, unit: Unit) -> None:
        self._unit: Unit = unit
        self._container: Container = unit.get_container(WORKLOAD_CONTAINER)

    @property
    def is_running(self) -> bool:
        try:
            workload_service = self._container.get_service(WORKLOAD_SERVICE)
        except (ModelError, PebbleConnectionError):
            return False

        return workload_service.is_running()

    def open_ports(self) -> None:
        self._unit.open_port(protocol="tcp", port=APPLICATION_PORT)


class PebbleService:
    """Pebble service abstraction running in a Juju unit."""

    def __init__(self, unit: Unit) -> None:
        self._unit = unit
        self._container = unit.get_container(WORKLOAD_CONTAINER)
        self._layer_dict: LayerDict = PEBBLE_LAYER_DICT

    def plan(self, layer: Layer, *container_files: ContainerFile) -> None:
        self._container.add_layer(WORKLOAD_SERVICE, layer, combine=True)

        restart_needed = False
        for container_file in container_files:
            current = container_file.from_workload_container(self._container)

            if container_file != current:
                self._container.push(
                    container_file.file_path, container_file.content, make_dirs=True
                )
                restart_needed = True

        try:
            if restart_needed:
                self._container.restart(WORKLOAD_SERVICE)
            else:
                self._container.replan()
        except Exception as e:
            raise PebbleServiceError(
                f"Pebble failed to restart the workload service. Error: {e}"
            ) from e

    def render_pebble_layer(self, *env_var_sources: EnvVarConvertible) -> Layer:
        updated_env_vars = ChainMap(*(source.to_env_vars() for source in env_var_sources))  # type: ignore
        env_vars = {
            **DEFAULT_CONTAINER_ENV,
            **updated_env_vars,
        }
        self._layer_dict["services"][WORKLOAD_SERVICE]["environment"] = env_vars

        return Layer(self._layer_dict)
