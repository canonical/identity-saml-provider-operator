# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.


# Charm constants
WORKLOAD_CONTAINER = "identity-saml-provider"
WORKLOAD_SERVICE = "identity-saml-provider"

# Application constants
APPLICATION_PORT = 8082
ORY_HYDRA_HTTP_PORT = 8080
ORY_KRATOS_HTTP_PORT = 8081
WORKLOAD_RUN_COMMAND = f"/usr/bin/{WORKLOAD_SERVICE}"

# Integration constants
PEER_INTEGRATION_NAME = "peer"
HYDRA_INTEGRATION_NAME = "hydra-endpoint-info"
INGRESS_INTEGRATION_NAME = "ingress"
PUBLIC_ROUTE_INTEGRATION_NAME = "public-route"
