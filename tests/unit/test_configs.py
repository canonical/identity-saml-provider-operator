# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.


from collections.abc import Mapping
from unittest.mock import MagicMock, call

import pytest
from ops import SecretNotFoundError
from ops.pebble import PathError

from configs import (
    CharmConfig,
    HydraCertificates,
    JujuSecretResolver,
    SAMLBridgeCert,
    SAMLBridgeKey,
)
from constants import HYDRA_CA_CERT, SAML_BRIDGE_CERT, SAML_BRIDGE_KEY


class TestSAMLBridgeKey:
    def test_from_sources(self) -> None:
        source = MagicMock()
        source.to_service_configs.return_value = {
            "saml_credentials": {"private-key": "private-key"}
        }

        result = SAMLBridgeKey.from_sources(source)

        assert result.content == "private-key"
        assert result.file_path == SAML_BRIDGE_KEY

    def test_from_sources_with_missing_key(self) -> None:
        source = MagicMock()
        source.to_service_configs.return_value = {"saml_credentials": {}}

        result = SAMLBridgeKey.from_sources(source)

        assert result.content == ""

    def test_from_sources_with_missing_credentials(self) -> None:
        source = MagicMock()
        source.to_service_configs.return_value = {}

        result = SAMLBridgeKey.from_sources(source)

        assert result.content == ""

    def test_from_workload_container(self, mocked_container: MagicMock) -> None:
        mock_file = MagicMock()
        mock_file.read.return_value = "private-key-content"
        mocked_container.pull.return_value.__enter__ = MagicMock(return_value=mock_file)
        mocked_container.pull.return_value.__exit__ = MagicMock(return_value=False)

        result = SAMLBridgeKey.from_workload_container(mocked_container)

        assert result.content == "private-key-content"

    def test_from_workload_container_when_path_error(self, mocked_container: MagicMock) -> None:
        container = MagicMock()
        container.pull.side_effect = PathError("not-found", "file not found")

        result = SAMLBridgeKey.from_workload_container(container)

        assert result.content == ""


class TestSAMLBridgeCert:
    def test_from_sources(self) -> None:
        source = MagicMock()
        source.to_service_configs.return_value = {
            "saml_credentials": {"public-cert": "public-cert"}
        }

        result = SAMLBridgeCert.from_sources(source)

        assert result.content == "public-cert"
        assert result.file_path == SAML_BRIDGE_CERT

    def test_from_sources_with_missing_cert(self) -> None:
        source = MagicMock()
        source.to_service_configs.return_value = {"saml_credentials": {}}

        result = SAMLBridgeCert.from_sources(source)

        assert result.content == ""

    def test_from_workload_container(self, mocked_container: MagicMock) -> None:
        mock_file = MagicMock()
        mock_file.read.return_value = "cert-content"
        mocked_container.pull.return_value.__enter__ = MagicMock(return_value=mock_file)
        mocked_container.pull.return_value.__exit__ = MagicMock(return_value=False)

        result = SAMLBridgeCert.from_workload_container(mocked_container)

        assert result.content == "cert-content"

    def test_from_workload_container_when_path_error(self) -> None:
        container = MagicMock()
        container.pull.side_effect = PathError("not-found", "file not found")

        result = SAMLBridgeCert.from_workload_container(container)

        assert result.content == ""


class TestHydraCertificates:
    def test_from_sources(self) -> None:
        source = MagicMock()
        source.to_service_configs.return_value = {"hydra_ca_certs": "ca-bundle"}

        result = HydraCertificates.from_sources(source)

        assert result.content == "ca-bundle"
        assert result.file_path == HYDRA_CA_CERT

    def test_sources_with_missing_certs(self) -> None:
        source = MagicMock()
        source.to_service_configs.return_value = {}

        result = HydraCertificates.from_sources(source)

        assert result.content == ""

    def test_from_workload_container(self, mocked_container: MagicMock) -> None:
        mock_file = MagicMock()
        mock_file.read.return_value = "ca-content"
        mocked_container.pull.return_value.__enter__ = MagicMock(return_value=mock_file)
        mocked_container.pull.return_value.__exit__ = MagicMock(return_value=False)

        result = HydraCertificates.from_workload_container(mocked_container)

        assert result.content == "ca-content"

    def test_from_workload_container_when_path_error(self) -> None:
        container = MagicMock()
        container.pull.side_effect = PathError("not-found", "file not found")

        result = HydraCertificates.from_workload_container(container)

        assert result.content == ""


class TestJujuSecretResolver:
    @pytest.fixture
    def secret_resolver(self, mocked_model: MagicMock) -> JujuSecretResolver:
        return JujuSecretResolver(mocked_model)

    def test_resolve_with_empty_secret_id(
        self,
        mocked_model: MagicMock,
        secret_resolver: JujuSecretResolver,
    ) -> None:
        actual = secret_resolver.resolve("")

        assert actual == {}
        mocked_model.get_secret.assert_not_called()

    def test_resolve_with_invalid_secret_id_prefix(
        self,
        mocked_model: MagicMock,
        secret_resolver: JujuSecretResolver,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        with caplog.at_level("WARNING"):
            actual = secret_resolver.resolve("invalid_id")

        assert actual == {}
        mocked_model.get_secret.assert_not_called()
        assert (
            "Secret ID 'invalid_id' is missing the required 'secret:' prefix. "
            "This likely indicates a misconfiguration." in caplog.text
        )

    def test_resolve_with_secret_not_found(
        self,
        mocked_model: MagicMock,
        secret_resolver: JujuSecretResolver,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        secret_id = "secret:missing"
        mocked_model.get_secret.side_effect = SecretNotFoundError

        with caplog.at_level("ERROR"):
            actual = secret_resolver.resolve(secret_id)

        assert actual == {}
        mocked_model.get_secret.assert_called_once_with(id=secret_id)
        assert f"Juju secret with id {secret_id} not found." in caplog.text

    def test_resolve_with_valid_secret_id(
        self,
        mocked_model: MagicMock,
        secret_resolver: JujuSecretResolver,
    ) -> None:
        secret_id = "secret:my-secret"
        expected = {"username": "foo", "password": "bar"}
        mocked_secret = MagicMock()
        mocked_secret.get_content.return_value = expected
        mocked_model.get_secret.return_value = mocked_secret

        actual = secret_resolver.resolve(secret_id)

        assert actual == expected
        mocked_model.get_secret.assert_called_once_with(id=secret_id)
        mocked_secret.get_content.assert_called_once_with(refresh=True)


class TestCharmConfig:
    @pytest.fixture
    def mocked_secret_resolver(self) -> MagicMock:
        return MagicMock()

    def test_to_service_configs(self, mocked_secret_resolver: MagicMock) -> None:
        config = {
            "saml_credentials": "secret:saml-credentials",
            "dev": False,
        }
        mocked_secret_resolver.resolve.side_effect = lambda secret_id: (
            {"resolved": secret_id} if secret_id else {}
        )
        charm_config = CharmConfig(config, mocked_secret_resolver)

        actual = charm_config.to_service_configs()

        assert actual["saml_credentials"] == {"resolved": "secret:saml-credentials"}
        assert actual["dev"] is False
        assert set(actual) == CharmConfig.CONFIGS | CharmConfig.SECRET_CONFIGS
        mocked_secret_resolver.resolve.assert_has_calls(
            [call(config.get(key)) for key in CharmConfig.SECRET_CONFIGS],
            any_order=True,
        )
        assert mocked_secret_resolver.resolve.call_count == len(CharmConfig.SECRET_CONFIGS)

    def test_to_service_configs_with_empty_values(self, mocked_secret_resolver: MagicMock) -> None:
        config: Mapping[str, str] = {}
        mocked_secret_resolver.resolve.return_value = {}
        charm_config = CharmConfig(config, mocked_secret_resolver)

        actual = charm_config.to_service_configs()

        for key in CharmConfig.CONFIGS:
            assert actual[key] == ""
        for key in CharmConfig.SECRET_CONFIGS:
            assert actual[key] == {}

    @pytest.mark.parametrize(
        "dev_config, expected_env_var",
        [
            (True, "true"),
            (False, "false"),
        ],
    )
    def test_to_env_vars(
        self,
        mocked_secret_resolver: MagicMock,
        dev_config: bool,
        expected_env_var: str,
    ) -> None:
        config = {
            "dev": dev_config,
            "saml_credentials": "secret:saml-credentials",
        }
        mocked_secret_resolver.resolve.side_effect = lambda secret_id: (
            {"resolved": secret_id} if secret_id else {}
        )
        charm_config = CharmConfig(config, mocked_secret_resolver)

        actual = charm_config.to_env_vars()

        assert actual == {"SAML_PROVIDER_DEV_MODE": expected_env_var}
