# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.


# Charm constants
from pathlib import Path


WORKLOAD_CONTAINER = "identity-saml-provider"
WORKLOAD_SERVICE = "identity-saml-provider"
OAUTH = "oauth"
OAUTH_SCOPES = "openid email profile"
OAUTH_GRANT_TYPES = ["authorization_code", "refresh_token"]
DATABASE_NAME = "saml_provider"


# Bridge certificate (used by the workload service)
CONTAINER_BRIDGE_CERT = Path("/root/.local/certs/bridge.crt")
CONTAINER_BRIDGE_KEY = Path("/root/.local/certs/bridge.key")


# Application constants
APPLICATION_PORT = 8082
ORY_HYDRA_HTTP_PORT = 8080
ORY_KRATOS_HTTP_PORT = 8081
WORKLOAD_RUN_COMMAND = f"/usr/bin/{WORKLOAD_SERVICE}"
CONTAINER_CERTIFICATES_PATH = Path("/etc/ssl/certs/")
CONTAINER_CERTIFICATES_FILE = Path(CONTAINER_CERTIFICATES_PATH / "ca-certificates.crt")

# Integration constants
PEER_INTEGRATION_NAME = "peer"
HYDRA_INTEGRATION_NAME = "oauth"
PUBLIC_ROUTE_INTEGRATION_NAME = "public-route"
DATABASE_INTEGRATION_NAME = "database"
CERTIFICATES_INTEGRATION_NAME = "certificates"
CERTIFICATE_TRANSFER_INTEGRATION_NAME = "receive-ca-cert"
HYDRA_TOKEN_HOOK_INTEGRATION_NAME = "hydra-token-hook"
