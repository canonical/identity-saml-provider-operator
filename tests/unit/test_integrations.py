# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

from unittest.mock import MagicMock, create_autospec

import pytest
from charms.data_platform_libs.v0.data_interfaces import DatabaseRequires

from constants import APPLICATION_PORT, HYDRA_CA_CERT, OIDC_REDIRECT_ENDPOINT_RESOURCE_PATH
from integrations import (
    DatabaseConfig,
    OAuthIntegration,
    PeerData,
    PublicRouteIntegration,
    TransferredCertificates,
)


class TestPeerData:
    @pytest.fixture
    def mocked_app(self) -> MagicMock:
        return MagicMock()

    @pytest.fixture
    def mocked_model(self, mocked_app: MagicMock) -> MagicMock:
        model = MagicMock()
        model.app = mocked_app
        return model

    @pytest.fixture
    def peer_data(self, mocked_model: MagicMock) -> PeerData:
        return PeerData(mocked_model)

    @pytest.fixture
    def mocked_peer_integration_data(self, mocked_app: MagicMock, mocked_model: MagicMock) -> dict:
        peer_integration = MagicMock()
        peer_integration.data = {mocked_app: {}}
        mocked_model.get_relation.return_value = peer_integration
        return peer_integration.data[mocked_app]

    def test_get_with_existing_key(
        self, mocked_peer_integration_data: dict, peer_data: PeerData
    ) -> None:
        mocked_peer_integration_data["key"] = '"val"'
        assert peer_data["key"] == "val"

    def test_get_with_missing_key(
        self, mocked_peer_integration_data: dict, peer_data: PeerData
    ) -> None:
        assert not peer_data["missing"]

    def test_get_without_peer_integration(
        self, mocked_model: MagicMock, peer_data: PeerData
    ) -> None:
        mocked_model.get_relation.return_value = None
        assert not peer_data["key"]

    def test_set(self, mocked_peer_integration_data: dict, peer_data: PeerData) -> None:
        peer_data["key"] = "val"
        assert mocked_peer_integration_data["key"] == '"val"'

    def test_set_without_integration(
        self,
        mocked_model: MagicMock,
        mocked_peer_integration_data: dict,
        peer_data: PeerData,
    ) -> None:
        mocked_model.get_relation.return_value = None
        peer_data["key"] = "val"

        assert not mocked_peer_integration_data

    def test_pop_with_existing_key(
        self, mocked_peer_integration_data: dict, peer_data: PeerData
    ) -> None:
        mocked_peer_integration_data["key"] = '"val"'

        actual = peer_data.pop("key")
        assert actual == "val"
        assert "key" not in mocked_peer_integration_data

    def test_pop_with_missing_key(
        self, mocked_peer_integration_data: dict, peer_data: PeerData
    ) -> None:
        assert not peer_data.pop("key")

    def test_pop_without_integration(
        self,
        mocked_model: MagicMock,
        mocked_peer_integration_data: dict,
        peer_data: PeerData,
    ) -> None:
        mocked_model.get_relation.return_value = None
        assert not peer_data.pop("key")

    def test_keys(self, mocked_peer_integration_data: dict, peer_data: PeerData) -> None:
        mocked_peer_integration_data.update({"x": "1", "y": "2"})
        assert list(peer_data.keys()) == ["x", "y"]

    def test_keys_without_integration(self, mocked_model: MagicMock, peer_data: PeerData) -> None:
        mocked_model.get_relation.return_value = None
        assert not peer_data.keys()


class TestDatabaseConfig:
    @pytest.fixture
    def database_config(self) -> DatabaseConfig:
        return DatabaseConfig(
            host="host",
            port="port",
            database="database",
            username="username",
            password="password",
            migration_version="migration_version",
        )

    @pytest.fixture
    def mocked_requirer(self) -> MagicMock:
        return create_autospec(DatabaseRequires)

    def test_load_with_integration(self, mocked_requirer: MagicMock) -> None:
        integration_id = 1
        mocked_requirer.relations = [MagicMock(id=integration_id)]
        mocked_requirer.database = "database"
        mocked_requirer.fetch_relation_data.return_value = {
            integration_id: {
                "endpoints": "host:port",
                "read-only-endpoints": "read-only-host:read-only-port",
                "username": "username",
                "password": "password",
            }
        }

        actual = DatabaseConfig.load(mocked_requirer)
        assert actual == DatabaseConfig(
            host="host",
            port="port",
            username="username",
            password="password",
            database="database",
            migration_version="migration_version_1",
        )

    def test_load_without_integration(self, mocked_requirer: MagicMock) -> None:
        mocked_requirer.database = "database"
        mocked_requirer.relations = []

        actual = DatabaseConfig.load(mocked_requirer)
        assert actual == DatabaseConfig()

    def test_dsn(self, database_config: DatabaseConfig) -> None:
        result = database_config.dsn
        assert result == "postgres://username:password@host:port/database?sslmode=disable"

    def test_to_env_vars(self, database_config: DatabaseConfig) -> None:
        env = database_config.to_env_vars()

        assert env["SAML_PROVIDER_DB_HOST"] == "host"
        assert env["SAML_PROVIDER_DB_PORT"] == "port"
        assert env["SAML_PROVIDER_DB_NAME"] == "database"
        assert env["SAML_PROVIDER_DB_USER"] == "username"
        assert env["SAML_PROVIDER_DB_PASSWORD"] == "password"


class TestPublicRouteIntegration:
    @pytest.fixture
    def mocked_requirer(self) -> MagicMock:
        requirer = MagicMock()
        requirer._charm = MagicMock()
        requirer._charm.model.name = "test-model"
        requirer._charm.app.name = "saml"
        requirer._charm.internal_base_url = (
            f"http://saml.test-model.svc.cluster.local:{APPLICATION_PORT}"
        )
        requirer.scheme = "https"
        requirer.external_host = ""
        return requirer

    @pytest.fixture
    def public_route_integration(self, mocked_requirer: MagicMock) -> PublicRouteIntegration:
        return PublicRouteIntegration(mocked_requirer)

    def test_external_base_url_without_external_host(
        self, public_route_integration: PublicRouteIntegration
    ) -> None:
        assert public_route_integration.external_base_url == ""

    def test_external_base_url_with_external_host(
        self,
        mocked_requirer: MagicMock,
        public_route_integration: PublicRouteIntegration,
    ) -> None:
        mocked_requirer.external_host = "public.example.com"

        assert public_route_integration.external_base_url == "https://public.example.com"

    def test_config_without_external_host(
        self, public_route_integration: PublicRouteIntegration
    ) -> None:
        assert public_route_integration.config == {}

    def test_config_with_url(
        self,
        mocked_requirer: MagicMock,
        public_route_integration: PublicRouteIntegration,
    ) -> None:
        mocked_requirer.external_host = "public.example.com"

        config = public_route_integration.config

        assert (
            config["http"]["routers"]["juju-test-model-saml-public-api-router-saml"]["service"]
            == "juju-test-model-saml-public-api-service"
        )
        assert (
            config["http"]["routers"]["juju-test-model-saml-public-api-router-saml-tls"]["tls"][
                "domains"
            ][0]["main"]
            == "public.example.com"
        )
        assert config["http"]["services"]["juju-test-model-saml-public-api-service"][
            "loadBalancer"
        ]["servers"][0]["url"] == (f"http://saml.test-model.svc.cluster.local:{APPLICATION_PORT}")

        expected_rule = "PathPrefix(`/saml`)"
        assert (
            config["http"]["routers"]["juju-test-model-saml-public-api-router-saml"]["rule"]
            == expected_rule
        )
        assert (
            config["http"]["routers"]["juju-test-model-saml-public-api-router-saml-tls"]["rule"]
            == expected_rule
        )

    def test_to_env_vars_with_external_host(
        self,
        mocked_requirer: MagicMock,
        public_route_integration: PublicRouteIntegration,
    ) -> None:
        mocked_requirer.external_host = "example.com"

        env = public_route_integration.to_env_vars()

        assert env["SAML_PROVIDER_BRIDGE_BASE_URL"] == "https://example.com"
        assert (
            env["SAML_PROVIDER_OIDC_REDIRECT_URL"]
            == "https://example.com" + OIDC_REDIRECT_ENDPOINT_RESOURCE_PATH
        )

    def test_to_env_vars_without_external_host(
        self,
        mocked_requirer: MagicMock,
        public_route_integration: PublicRouteIntegration,
    ) -> None:
        env = public_route_integration.to_env_vars()

        assert (
            env["SAML_PROVIDER_BRIDGE_BASE_URL"]
            == f"http://saml.test-model.svc.cluster.local:{APPLICATION_PORT}"
        )


class TestOAuthIntegration:
    @pytest.fixture
    def mocked_requirer(self) -> MagicMock:
        requirer = MagicMock()
        requirer.is_client_created.return_value = True
        provider_info = MagicMock()
        provider_info.issuer_url = "https://hydra.example.com"
        provider_info.client_id = "client-id"
        provider_info.client_secret = "client-secret"
        requirer.get_provider_info.return_value = provider_info
        return requirer

    @pytest.fixture
    def oauth_integration(self, mocked_requirer: MagicMock) -> OAuthIntegration:
        return OAuthIntegration(mocked_requirer)

    def test_to_env_vars_with_client(self, oauth_integration: OAuthIntegration) -> None:
        env = oauth_integration.to_env_vars()

        assert env["SAML_PROVIDER_HYDRA_PUBLIC_URL"] == "https://hydra.example.com"
        assert env["SAML_PROVIDER_OIDC_CLIENT_ID"] == "client-id"
        assert env["SAML_PROVIDER_OIDC_CLIENT_SECRET"] == "client-secret"

    def test_to_env_vars_without_client(
        self, mocked_requirer: MagicMock, oauth_integration: OAuthIntegration
    ) -> None:
        mocked_requirer.is_client_created.return_value = False

        assert oauth_integration.to_env_vars() == {}

    def test_update_oauth_client_config(
        self, mocked_requirer: MagicMock, oauth_integration: OAuthIntegration
    ) -> None:
        oauth_integration.update_oauth_client_config("https://saml.example.com")

        mocked_requirer.update_client_config.assert_called_once()


class TestTransferredCertificates:
    @pytest.fixture
    def mocked_requirer(self) -> MagicMock:
        requirer = MagicMock()
        requirer.get_all_certificates.return_value = ["cert-b", "cert-a"]
        return requirer

    @pytest.fixture
    def transferred_certificates(self) -> TransferredCertificates:
        return TransferredCertificates(ca_bundle="ca-bundle-content")

    def test_load_with_certificates(self, mocked_requirer: MagicMock) -> None:
        actual = TransferredCertificates.load(mocked_requirer)
        assert actual.ca_bundle == "cert-a\ncert-b"

    def test_load_without_certificates(self, mocked_requirer: MagicMock) -> None:
        mocked_requirer.get_all_certificates.return_value = []

        actual = TransferredCertificates.load(mocked_requirer)
        assert actual.ca_bundle == ""

    def test_to_env_vars_with_bundle(
        self, transferred_certificates: TransferredCertificates
    ) -> None:
        env = transferred_certificates.to_env_vars()
        assert env["SAML_PROVIDER_HYDRA_CA_CERT_PATH"] == str(HYDRA_CA_CERT)

    def test_to_env_vars_without_bundle(self) -> None:
        ca = TransferredCertificates(ca_bundle="")
        assert ca.to_env_vars() == {}

    def test_to_service_configs(self, transferred_certificates: TransferredCertificates) -> None:
        configs = transferred_certificates.to_service_configs()
        assert configs["hydra_ca_certs"] == "ca-bundle-content"
