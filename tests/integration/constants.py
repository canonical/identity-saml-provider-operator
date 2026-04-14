# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

from pathlib import Path

import yaml

METADATA = yaml.safe_load(Path("./charmcraft.yaml").read_text())
APP_NAME = METADATA["name"]
APP_IMAGE = METADATA["resources"]["oci-image"]["upstream-source"]
DB_APP = "postgresql-k8s"
HYDRA_APP = "hydra"
CA_APP = "self-signed-certificates"
TRAEFIK_CHARM = "traefik-k8s"
TRAEFIK_PUBLIC_APP = "traefik-public"
PUBLIC_INGRESS_DOMAIN = "public"
