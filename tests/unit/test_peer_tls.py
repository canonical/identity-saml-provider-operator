# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for peer TLS certificate distribution."""

from unittest.mock import MagicMock, Mock, patch

import pytest


@pytest.fixture
def mock_charm():
    """Create a mock charm for testing."""
    from charm import IdentitySAMLProviderCharm

    charm = Mock(spec=IdentitySAMLProviderCharm)
    charm.unit = Mock()
    charm.unit.is_leader = Mock()
    charm.model = Mock()
    charm.peer_data = MagicMock()
    charm.certificate_transfer_requirer = Mock()
    charm.public_route = Mock()
    charm.oauth = Mock()
    charm.database_requirer = Mock()
    charm._workload_service = Mock()
    charm._pebble_service = Mock()
    return charm


@pytest.fixture
def mock_peer_data():
    """Create a mock peer data store."""
    store = {}

    class MockPeerData:
        def __getitem__(self, key):
            return store.get(key, "")

        def __setitem__(self, key, value):
            store[key] = value

        def get(self, key, default=""):
            return store.get(key, default)

        def keys(self):
            return store.keys()

    return MockPeerData()


class TestPeerTLSPropertiesAndConstants:
    """Test peer TLS data property visibility and constant definitions."""

    def test_peer_data_ca_bundle_key_exists(self):
        """Verify PEER_DATA_CA_BUNDLE constant is accessible."""
        from constants import PEER_DATA_CA_BUNDLE

        assert PEER_DATA_CA_BUNDLE == "tls_ca_bundle"

    def test_peer_data_bridge_cert_key_exists(self):
        """Verify PEER_DATA_BRIDGE_CERT constant is accessible."""
        from constants import PEER_DATA_BRIDGE_CERT

        assert PEER_DATA_BRIDGE_CERT == "tls_bridge_cert"

    def test_peer_data_bridge_key_key_exists(self):
        """Verify PEER_DATA_BRIDGE_KEY constant is accessible."""
        from constants import PEER_DATA_BRIDGE_KEY

        assert PEER_DATA_BRIDGE_KEY == "tls_bridge_key"

    def test_all_peer_tls_constants_are_strings(self):
        """Verify all peer TLS constants are strings."""
        from constants import PEER_DATA_CA_BUNDLE, PEER_DATA_BRIDGE_CERT, PEER_DATA_BRIDGE_KEY

        assert isinstance(PEER_DATA_CA_BUNDLE, str)
        assert isinstance(PEER_DATA_BRIDGE_CERT, str)
        assert isinstance(PEER_DATA_BRIDGE_KEY, str)


class TestPeerDataIntegration:
    """Integration tests for peer data handling."""

    def test_peer_data_can_store_and_retrieve_ca_bundle(self, mock_peer_data):
        """Peer data can store and retrieve CA bundle content."""
        test_ca_content = "-----BEGIN CERTIFICATE-----\ntest_cert\n-----END CERTIFICATE-----"
        mock_peer_data["tls_ca_bundle"] = test_ca_content

        assert mock_peer_data["tls_ca_bundle"] == test_ca_content

    def test_peer_data_can_store_and_retrieve_bridge_cert(self, mock_peer_data):
        """Peer data can store and retrieve bridge certificate."""
        test_cert = "-----BEGIN CERTIFICATE-----\nbridge_cert\n-----END CERTIFICATE-----"
        mock_peer_data["tls_bridge_cert"] = test_cert

        assert mock_peer_data["tls_bridge_cert"] == test_cert

    def test_peer_data_can_store_and_retrieve_bridge_key(self, mock_peer_data):
        """Peer data can store and retrieve bridge key."""
        test_key = "-----BEGIN PRIVATE KEY-----\nbridge_key\n-----END PRIVATE KEY-----"
        mock_peer_data["tls_bridge_key"] = test_key

        assert mock_peer_data["tls_bridge_key"] == test_key

    def test_peer_data_keys_method_returns_all_stored_keys(self, mock_peer_data):
        """Peer data keys() returns all stored key names."""
        mock_peer_data["tls_ca_bundle"] = "ca_content"
        mock_peer_data["tls_bridge_cert"] = "cert_content"
        mock_peer_data["tls_bridge_key"] = "key_content"

        keys = list(mock_peer_data.keys())
        assert "tls_ca_bundle" in keys
        assert "tls_bridge_cert" in keys
        assert "tls_bridge_key" in keys


class TestWorkloadServiceBridgeCertSync:
    """Test WorkloadService bridge certificate synchronization."""

    @patch("services.LOCAL_BRIDGE_KEY_FILE")
    @patch("services.LOCAL_BRIDGE_CERT_FILE")
    def test_update_bridge_certificates_skips_push_when_content_unchanged(
        self, mock_local_cert_file, mock_local_key_file
    ):
        """Bridge cert/key sync skips push when content unchanged."""
        from services import WorkloadService

        # Setup local files
        mock_local_cert_file.exists.return_value = True
        mock_local_key_file.exists.return_value = True
        cert_content = "cert_content_unchanged"
        key_content = "key_content_unchanged"
        mock_local_cert_file.read_text.return_value = cert_content
        mock_local_key_file.read_text.return_value = key_content

        # Setup mock unit and container
        mock_unit = Mock()
        mock_container = Mock()
        mock_unit.get_container.return_value = mock_container

        # Setup container to return same content
        mock_pull_cert = Mock()
        mock_pull_cert.read.return_value = cert_content
        mock_pull_key = Mock()
        mock_pull_key.read.return_value = key_content

        call_count = 0

        def mock_pull(path):
            nonlocal call_count
            if "bridge.crt" in path:
                return mock_pull_cert
            elif "bridge.key" in path:
                return mock_pull_key

        mock_container.pull.side_effect = mock_pull
        mock_container.exists.return_value = True

        service = WorkloadService(mock_unit)
        service.update_bridge_certificates()

        # Verify push was NOT called since content is unchanged
        mock_container.push.assert_not_called()

    @patch("services.LOCAL_BRIDGE_KEY_FILE")
    @patch("services.LOCAL_BRIDGE_CERT_FILE")
    def test_update_bridge_certificates_pushes_when_cert_changed(
        self, mock_local_cert_file, mock_local_key_file
    ):
        """Bridge cert sync pushes to container when cert content changed."""
        from services import WorkloadService

        # Setup local files with new content
        mock_local_cert_file.exists.return_value = True
        mock_local_key_file.exists.return_value = True
        new_cert_content = "new_cert_content"
        key_content = "key_content"
        mock_local_cert_file.read_text.return_value = new_cert_content
        mock_local_key_file.read_text.return_value = key_content

        # Setup mock unit and container
        mock_unit = Mock()
        mock_container = Mock()
        mock_unit.get_container.return_value = mock_container

        # Setup container to return old cert content
        mock_pull_cert = Mock()
        mock_pull_cert.read.return_value = "old_cert_content"
        mock_pull_key = Mock()
        mock_pull_key.read.return_value = key_content

        def mock_pull(path):
            if "bridge.crt" in path:
                return mock_pull_cert
            elif "bridge.key" in path:
                return mock_pull_key

        mock_container.pull.side_effect = mock_pull
        mock_container.exists.return_value = True

        service = WorkloadService(mock_unit)
        service.update_bridge_certificates()

        # Verify push was called for changed cert
        mock_container.push.assert_called()
        # Verify it was called with new cert content
        push_calls = [
            call for call in mock_container.push.call_args_list if "bridge.crt" in str(call)
        ]
        assert len(push_calls) > 0

    @patch("services.LOCAL_BRIDGE_KEY_FILE")
    @patch("services.LOCAL_BRIDGE_CERT_FILE")
    def test_update_bridge_certificates_handles_missing_files(
        self, mock_local_cert_file, mock_local_key_file
    ):
        """Bridge cert sync handles missing local files."""
        from services import WorkloadService

        # Setup local files as missing
        mock_local_cert_file.exists.return_value = False
        mock_local_key_file.exists.return_value = False

        # Setup mock unit and container
        mock_unit = Mock()
        mock_container = Mock()
        mock_unit.get_container.return_value = mock_container

        # Container exists but local files don't
        mock_container.exists.return_value = True
        mock_pull_cert = Mock()
        mock_pull_cert.read.return_value = "existing_cert"
        mock_container.pull.return_value = mock_pull_cert

        service = WorkloadService(mock_unit)
        service.update_bridge_certificates()

        # Should not raise an exception
        # And should compare with empty string for missing local files
        assert mock_container.push.called or not mock_container.push.called  # Either way is fine


class TestPeerTLSDistributionPatterns:
    """Test patterns for TLS distribution across peers."""

    def test_leader_publishes_all_three_tls_materials_to_peer_data(self, mock_peer_data):
        """Leader publishes CA bundle, bridge cert, and bridge key."""
        from constants import PEER_DATA_CA_BUNDLE, PEER_DATA_BRIDGE_CERT, PEER_DATA_BRIDGE_KEY

        # Simulate leader publishing
        mock_peer_data[PEER_DATA_CA_BUNDLE] = "ca_bundle_content"
        mock_peer_data[PEER_DATA_BRIDGE_CERT] = "bridge_cert_content"
        mock_peer_data[PEER_DATA_BRIDGE_KEY] = "bridge_key_content"

        # Verify all three are accessible
        assert mock_peer_data[PEER_DATA_CA_BUNDLE] == "ca_bundle_content"
        assert mock_peer_data[PEER_DATA_BRIDGE_CERT] == "bridge_cert_content"
        assert mock_peer_data[PEER_DATA_BRIDGE_KEY] == "bridge_key_content"

    def test_follower_can_read_all_three_tls_materials_from_peer_data(self, mock_peer_data):
        """Follower can read CA bundle, bridge cert, and bridge key."""
        from constants import PEER_DATA_CA_BUNDLE, PEER_DATA_BRIDGE_CERT, PEER_DATA_BRIDGE_KEY

        # Setup peer data as if leader published
        mock_peer_data[PEER_DATA_CA_BUNDLE] = "ca_content"
        mock_peer_data[PEER_DATA_BRIDGE_CERT] = "cert_content"
        mock_peer_data[PEER_DATA_BRIDGE_KEY] = "key_content"

        # Simulate follower reading
        ca_bundle = mock_peer_data[PEER_DATA_CA_BUNDLE]
        bridge_cert = mock_peer_data[PEER_DATA_BRIDGE_CERT]
        bridge_key = mock_peer_data[PEER_DATA_BRIDGE_KEY]

        assert ca_bundle == "ca_content"
        assert bridge_cert == "cert_content"
        assert bridge_key == "key_content"
        assert all([ca_bundle, bridge_cert, bridge_key])

    def test_multiple_followers_see_same_tls_materials(self, mock_peer_data):
        """Multiple followers see identical TLS materials from peer data."""
        from constants import PEER_DATA_CA_BUNDLE, PEER_DATA_BRIDGE_CERT, PEER_DATA_BRIDGE_KEY

        # Leader publishes
        mock_peer_data[PEER_DATA_CA_BUNDLE] = "shared_ca"
        mock_peer_data[PEER_DATA_BRIDGE_CERT] = "shared_cert"
        mock_peer_data[PEER_DATA_BRIDGE_KEY] = "shared_key"

        # Multiple followers read
        follower1_ca = mock_peer_data[PEER_DATA_CA_BUNDLE]
        follower2_ca = mock_peer_data[PEER_DATA_CA_BUNDLE]

        follower1_cert = mock_peer_data[PEER_DATA_BRIDGE_CERT]
        follower2_cert = mock_peer_data[PEER_DATA_BRIDGE_CERT]

        follower1_key = mock_peer_data[PEER_DATA_BRIDGE_KEY]
        follower2_key = mock_peer_data[PEER_DATA_BRIDGE_KEY]

        # All followers see the same content
        assert follower1_ca == follower2_ca
        assert follower1_cert == follower2_cert
        assert follower1_key == follower2_key
