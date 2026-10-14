# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from collections import ChainMap
from typing import Any

from ops import Container, ModelError, Unit
from ops.pebble import CheckStatus
from ops.pebble import ConnectionError as PebbleConnectionError
from ops.pebble import Layer, LayerDict

from cli import CommandLine
from configs import ContainerFile
from constants import (
    ADMIN_SERVICE_PROVIDERS_URL,
    ADMIN_SP_ATTRIBUTE_MAPPING_URL,
    APPLICATION_PORT,
    DEFAULT_ACS_BINDING,
    WORKLOAD_ALIVE_CHECK,
    WORKLOAD_CONTAINER,
    WORKLOAD_READY_CHECK,
    WORKLOAD_SERVICE,
)
from env_vars import DEFAULT_CONTAINER_ENV, EnvVarConvertible
from exceptions import PebbleServiceError, ServiceProviderError

logger = logging.getLogger(__name__)

PEBBLE_LAYER_DICT = {
    "summary": "pebble layer",
    "description": "pebble layer for identity saml provider",
    "services": {
        WORKLOAD_SERVICE: {
            "override": "replace",
            "summary": "Identity SAML provider service",
            "command": "/usr/bin/identity-saml-provider serve",
            "startup": "disabled",
            "on-check-failure": {WORKLOAD_ALIVE_CHECK: "restart"},
        }
    },
    "checks": {
        WORKLOAD_ALIVE_CHECK: {
            "override": "replace",
            "period": "10s",
            "timeout": "5s",
            "threshold": 3,
            "http": {"url": f"http://localhost:{APPLICATION_PORT}/healthz"},
        },
        WORKLOAD_READY_CHECK: {
            "override": "replace",
            "level": "ready",
            "period": "5s",
            "timeout": "3s",
            "threshold": 1,
            "http": {"url": f"http://localhost:{APPLICATION_PORT}/readyz"},
        },
    },
}


class WorkloadService:
    """Workload service abstraction running in a Juju unit."""

    def __init__(self, unit: Unit) -> None:
        self._version = ""

        self._unit: Unit = unit
        self._container: Container = unit.get_container(WORKLOAD_CONTAINER)
        self._cli = CommandLine(self._container)

    @property
    def application_version(self) -> str:
        self._version = self._cli.get_application_version() or ""
        return self._version

    @property
    def version(self) -> str:
        return self.application_version

    @version.setter
    def version(self, new_version: str) -> None:
        if not new_version:
            return

        try:
            self._unit.set_workload_version(new_version)
        except Exception as e:
            logger.error("Failed to set workload version: %s", e)
            return

        self._version = new_version

    @property
    def is_running(self) -> bool:
        try:
            workload_service = self._container.get_service(WORKLOAD_SERVICE)
        except (ModelError, PebbleConnectionError):
            return False

        if not workload_service.is_running():
            return False

        return self._no_failing_checks(WORKLOAD_ALIVE_CHECK)

    @property
    def is_ready(self) -> bool:
        return self._no_failing_checks(WORKLOAD_READY_CHECK)

    def open_ports(self) -> None:
        self._unit.open_port(protocol="tcp", port=APPLICATION_PORT)

    def create_service_provider(
        self,
        entity_id: str,
        acs_url: str,
        acs_binding: str = DEFAULT_ACS_BINDING,
        attribute_mapping: str | None = None,
    ) -> dict[str, Any]:
        """Register a new SAML service provider via the Admin HTTP API.

        Args:
            entity_id: The unique URI that identifies the service provider.
            acs_url: The Assertion Consumer Service (ACS) URL.
            acs_binding: The SAML binding type.
            attribute_mapping: Optional JSON string defining attribute mapping rules.

        Returns:
            A dictionary with the action result payload.

        Raises:
            ServiceProviderError: If validation or the Admin HTTP API request fails.
        """
        parsed_mapping = self._parse_attribute_mapping(attribute_mapping)
        payload: dict[str, Any] = {
            "entity_id": entity_id,
            "acs_url": acs_url,
            "acs_binding": acs_binding,
        }
        if parsed_mapping is not None:
            payload["attribute_mapping"] = parsed_mapping

        return self._send_admin_request("POST", ADMIN_SERVICE_PROVIDERS_URL, payload=payload)

    def update_service_provider(
        self,
        entity_id: str,
        acs_url: str | None = None,
        acs_binding: str | None = None,
        attribute_mapping: str | None = None,
    ) -> dict[str, Any]:
        """Update an existing SAML service provider or its attribute mapping.

        Args:
            entity_id: The unique URI of the target service provider.
            acs_url: Optional updated ACS URL.
            acs_binding: Optional updated SAML binding type.
            attribute_mapping: Optional JSON string replacing the attribute mapping rules.

        Returns:
            A dictionary with the action result payload.

        Raises:
            ServiceProviderError: If no update fields are provided, JSON is invalid,
                or the Admin HTTP API request fails.
        """
        if not any([acs_url, acs_binding, attribute_mapping]):
            raise ServiceProviderError(
                "At least one of acs-url, acs-binding, or attribute-mapping must be provided"
            )

        parsed_mapping = self._parse_attribute_mapping(attribute_mapping)
        if parsed_mapping is not None and not acs_url and not acs_binding:
            query = urllib.parse.urlencode({"entity_id": entity_id})
            return self._send_admin_request(
                "PUT",
                f"{ADMIN_SP_ATTRIBUTE_MAPPING_URL}?{query}",
                payload=parsed_mapping,
            )

        existing = self._get_service_provider(entity_id)
        resolved_acs_url = acs_url or existing.get("acs-url")
        if not resolved_acs_url:
            raise ServiceProviderError(
                "Existing service provider record is missing required acs-url"
            )
        merged_mapping = (
            parsed_mapping if parsed_mapping is not None else existing.get("attribute-mapping")
        )
        payload: dict[str, Any] = {
            "entity_id": entity_id,
            "acs_url": resolved_acs_url,
            "acs_binding": acs_binding or existing.get("acs-binding", DEFAULT_ACS_BINDING),
        }
        if merged_mapping is not None:
            payload["attribute_mapping"] = merged_mapping

        return self._send_admin_request("POST", ADMIN_SERVICE_PROVIDERS_URL, payload=payload)

    def get_service_provider(self, entity_id: str) -> dict[str, Any]:
        """Retrieve a registered SAML service provider via the Admin HTTP API.

        Args:
            entity_id: The unique URI of the target service provider.

        Returns:
            A dictionary with the action result payload.

        Raises:
            ServiceProviderError: If the Admin HTTP API request fails.
        """
        result = self._get_service_provider(entity_id)
        if isinstance(result.get("attribute-mapping"), dict):
            result["attribute-mapping"] = json.dumps(result["attribute-mapping"])
        return result

    def delete_service_provider(self, entity_id: str) -> dict[str, Any]:
        """Clear the attribute mapping rules for a SAML service provider.

        Args:
            entity_id: The unique URI of the target service provider.

        Returns:
            A dictionary with the action result payload.

        Raises:
            ServiceProviderError: If the Admin HTTP API request fails.
        """
        query = urllib.parse.urlencode({"entity_id": entity_id})
        return self._send_admin_request(
            "DELETE",
            f"{ADMIN_SP_ATTRIBUTE_MAPPING_URL}?{query}",
        )

    def _get_service_provider(self, entity_id: str) -> dict[str, Any]:
        query = urllib.parse.urlencode({"entity_id": entity_id})
        return self._send_admin_request("GET", f"{ADMIN_SERVICE_PROVIDERS_URL}?{query}")

    @staticmethod
    def _parse_attribute_mapping(attribute_mapping: str | None) -> dict[str, Any] | None:
        if not attribute_mapping:
            return None

        try:
            parsed = json.loads(attribute_mapping)
        except json.JSONDecodeError as err:
            raise ServiceProviderError(f"Invalid attribute-mapping JSON: {err}") from err

        if not isinstance(parsed, dict):
            raise ServiceProviderError("Invalid attribute-mapping: must be a JSON object")

        return parsed

    @staticmethod
    def _extract_http_error_message(err: urllib.error.HTTPError) -> str:
        try:
            body = err.read().decode("utf-8")
            data = json.loads(body)
            if isinstance(data, dict) and "message" in data:
                return str(data["message"])
        except Exception as parse_err:
            logger.debug("Failed to parse HTTP error body: %s", parse_err)

        return str(err.reason or f"HTTP {err.code}")

    def _send_admin_request(
        self,
        method: str,
        url: str,
        payload: dict[str, Any] | None = None,
        timeout: float = 10.0,
    ) -> dict[str, Any]:
        data: bytes | None = None
        headers: dict[str, str] = {}
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"

        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                raw_body = response.read().decode("utf-8")
                response_data: dict[str, Any] = json.loads(raw_body) if raw_body else {}
        except urllib.error.HTTPError as err:
            message = self._extract_http_error_message(err)
            logger.error(
                "Admin API request %s %s failed with status %d: %s",
                method,
                url,
                err.code,
                message,
            )
            raise ServiceProviderError(message) from err
        except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as err:
            logger.error("Failed to communicate with Admin API %s %s: %s", method, url, err)
            raise ServiceProviderError(
                f"Failed to communicate with workload admin API: {err}"
            ) from err

        return {k.replace("_", "-"): v for k, v in response_data.items()}

    def _no_failing_checks(self, *names: str) -> bool:
        try:
            checks = self._container.get_checks(*names)
        except (ModelError, PebbleConnectionError):
            return False

        if not checks:
            # No matching checks configured: treat as not contradictory.
            return True

        return all(info.status == CheckStatus.UP for info in checks.values())


class PebbleService:
    """Pebble service abstraction running in a Juju unit."""

    def __init__(self, unit: Unit) -> None:
        self._unit = unit
        self._container = unit.get_container(WORKLOAD_CONTAINER)
        self._layer_dict: LayerDict = PEBBLE_LAYER_DICT

    def push_files(self, *container_files: ContainerFile) -> bool:
        restart_needed = False
        for container_file in container_files:
            current = container_file.from_workload_container(self._container)

            if container_file != current:
                self._container.push(
                    container_file.file_path, container_file.content, make_dirs=True
                )
                restart_needed = True

        return restart_needed

    def plan(self, layer: Layer, *container_files: ContainerFile) -> None:
        self._container.add_layer(WORKLOAD_SERVICE, layer, combine=True)

        restart_needed = self.push_files(*container_files)

        try:
            # Pebble services configured with startup: "disabled" are not started by replan() if they are inactive
            if restart_needed or not self._container.get_service(WORKLOAD_SERVICE).is_running():
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
