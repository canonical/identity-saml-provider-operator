# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
from collections import ChainMap
from dataclasses import dataclass
from pathlib import PurePath
from typing import Any, ClassVar, MutableMapping, Protocol, TypeAlias

from charms.observability_libs.v0.kubernetes_compute_resources_patch import (
    adjust_resource_requirements,
)
from lightkube.models.core_v1 import ResourceRequirements
from ops import ConfigData, Container, Model, SecretNotFoundError
from ops.pebble import PathError
from typing_extensions import Self

from constants import HYDRA_CA_CERT, SAML_BRIDGE_CERT, SAML_BRIDGE_KEY

logger = logging.getLogger(__name__)

ServiceConfigs: TypeAlias = MutableMapping[str, Any]


class ServiceConfigSource(Protocol):
    """An interface enforcing the contribution to workload service configs."""

    def to_service_configs(self) -> ServiceConfigs:
        pass


class ContainerFile(Protocol):
    """An interface representing a file in the workload container that can be used as a source of service configuration."""

    file_path: ClassVar[str | PurePath]

    @property
    def content(self) -> str: ...

    @classmethod
    def from_sources(cls, *service_config_sources: ServiceConfigSource) -> Self: ...

    @classmethod
    def from_workload_container(cls, workload_container: Container) -> Self: ...


@dataclass(frozen=True)
class SAMLBridgeKey:
    file_path: ClassVar[str | PurePath] = SAML_BRIDGE_KEY
    content: str

    @classmethod
    def from_sources(cls, *service_config_sources: ServiceConfigSource) -> Self:
        configs: MutableMapping[str, Any] = ChainMap(
            *(source.to_service_configs() for source in service_config_sources)
        )

        saml_credentials = configs.get("saml_credentials", {})
        private_key = saml_credentials.get("private-key", "")
        return cls(private_key)

    @classmethod
    def from_workload_container(cls, workload_container: Container) -> Self:
        try:
            with workload_container.pull(cls.file_path, encoding="utf-8") as f:
                return cls(f.read())
        except PathError:
            return cls("")


@dataclass(frozen=True)
class SAMLBridgeCert:
    file_path: ClassVar[str | PurePath] = SAML_BRIDGE_CERT
    content: str

    @classmethod
    def from_sources(cls, *service_config_sources: ServiceConfigSource) -> Self:
        configs: MutableMapping[str, Any] = ChainMap(
            *(source.to_service_configs() for source in service_config_sources)
        )

        saml_credentials = configs.get("saml_credentials", {})
        public_cert = saml_credentials.get("public-cert", "")
        return cls(public_cert)

    @classmethod
    def from_workload_container(cls, workload_container: Container) -> Self:
        try:
            with workload_container.pull(cls.file_path, encoding="utf-8") as f:
                return cls(f.read())
        except PathError:
            return cls("")


@dataclass(frozen=True)
class HydraCertificates:
    file_path: ClassVar[str | PurePath] = HYDRA_CA_CERT
    content: str

    @classmethod
    def from_sources(cls, *service_config_sources: ServiceConfigSource) -> Self:
        configs: MutableMapping[str, Any] = ChainMap(
            *(source.to_service_configs() for source in service_config_sources)
        )

        ca_certs = configs.get("hydra_ca_certs", "")
        return cls(ca_certs)

    @classmethod
    def from_workload_container(cls, workload_container: Container) -> Self:
        try:
            with workload_container.pull(cls.file_path, encoding="utf-8") as f:
                return cls(f.read())
        except PathError:
            return cls("")


class SecretResolver(Protocol):
    """An interface for resolving Juju secrets."""

    def resolve(self, secret_id: str) -> dict[str, str]:
        pass


class JujuSecretResolver:
    def __init__(self, model: Model) -> None:
        self._model = model

    def resolve(self, secret_id: str) -> dict[str, str]:
        if not secret_id:
            return {}

        if not secret_id.startswith("secret:"):
            logger.warning(
                "Secret ID '%s' is missing the required 'secret:' prefix. "
                "This likely indicates a misconfiguration.",
                secret_id,
            )
            return {}

        try:
            secret = self._model.get_secret(id=secret_id)
        except SecretNotFoundError:
            logger.error("Juju secret with id %s not found.", secret_id)
            return {}

        return secret.get_content(refresh=True)


class CharmConfig:
    """A class representing the data source of charm configurations."""

    CONFIGS: set[str] = set()

    SECRET_CONFIGS = {
        "saml_credentials",
    }

    def __init__(self, config: ConfigData, secret_resolver: SecretResolver) -> None:
        self._config = config
        self._secret_resolver = secret_resolver

    def to_service_configs(self) -> ServiceConfigs:
        configs = {key: self._config.get(key, "") for key in self.CONFIGS}

        secret_configs = {
            key: self._secret_resolver.resolve(self._config.get(key))
            for key in self.SECRET_CONFIGS
        }

        return {**configs, **secret_configs}


class KubernetesResources:
    """A Callable class for Kubernetes resource requirements."""

    def __init__(
        self,
        config: ConfigData,
    ) -> None:
        self._config = config

    def __call__(self) -> ResourceRequirements:
        requests = {"cpu": "1", "memory": "1Gi"}
        limits = {
            "cpu": self._config.get("cpu_limit"),
            "memory": self._config.get("memory_limit"),
        }

        return adjust_resource_requirements(limits, requests, adhere_to_requests=True)
