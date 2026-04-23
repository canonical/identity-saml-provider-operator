# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

from pathlib import Path

# Charm constants
DATABASE_NAME = "saml_provider"
WORKLOAD_CONTAINER = "identity-saml-provider"
WORKLOAD_SERVICE = "identity-saml-provider"
CERTS_DIR_PATH = Path("/etc/saml")
HYDRA_CA_CERT = CERTS_DIR_PATH / "hydra-ca.pem"
SAML_BRIDGE_CERT = CERTS_DIR_PATH / "bridge.crt"
SAML_BRIDGE_KEY = CERTS_DIR_PATH / "bridge.key"

# Application constants
APPLICATION_PORT = 8082
OAUTH_SCOPES = "openid email profile"
OAUTH_GRANT_TYPES = ["authorization_code", "refresh_token"]
OIDC_REDIRECT_ENDPOINT_RESOURCE_PATH = "/saml/callback"

# Integration constants
PEER_INTEGRATION_NAME = "peer"
DATABASE_INTEGRATION_NAME = "database"
PUBLIC_ROUTE_INTEGRATION_NAME = "public-route"
OAUTH_INTEGRATION_NAME = "oauth"
CERTIFICATE_TRANSFER_INTEGRATION_NAME = "receive-ca-cert"
