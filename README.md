
# identity-saml-provider-operator
[![Juju](https://img.shields.io/badge/Juju%20-3.6+-%23E95420)](https://github.com/juju/juju)
[![License](https://img.shields.io/github/license/canonical/identity-saml-provider-operator?label=License)](https://github.com/canonical/identity-saml-provider-operator/blob/main/LICENSE)

## Description

This repository contains a Juju charm for deploying the Identity SAML Provider on Kubernetes. It enables SAML authentication integration for your applications using Juju and Kubernetes.


## Usage

### Build the charm

```shell
charmcraft pack
```

### Deploy prerequisites

Deploy the [Canonical identity platform](https://canonical-identity.readthedocs-hosted.com/tutorial/canonical-identity-platform/) for the required integrations

### Deploy the charm

```shell
juju switch iam
juju deploy ./identity-saml-provider-operator_ubuntu@24.04-amd64.charm --resource oci-image=ghcr.io/canonical/identity-saml-provider:latest
```

### Offer and integrate dependencies

```shell
juju switch core
juju offer traefik-public:traefik-route
juju offer self-signed-certificates:certificates certificates
juju switch iam
juju consume core.traefik-public
juju integrate identity-saml-provider-operator:certificates admin/core.certificates
juju integrate identity-saml-provider-operator traefik-public
juju integrate identity-saml-provider-operator hydra
juju integrate identity-saml-provider-operator postgresql
```

## Integrations

This charm requires integration with the following:

- [hydra-operator](https://github.com/canonical/hydra-operator) for OAuth2 and OIDC provider
- [postgresql-k8s-operator](https://github.com/canonical/postgresql-k8s-operator) for database
- [traefik-k8s-operator](https://github.com/canonical/traefik-k8s-operator) for ingress
- [self-signed-certificates-operator](https://github.com/canonical/self-signed-certificates-operator) for certificates

Refer to the deployment steps above for integration commands.


## Contributing

Please see the [Juju docs](https://documentation.ubuntu.com/juju/3.6/) for general guidance on contributing to Juju charms.

## License

This charm is distributed under the Apache Software License, version 2.0. See [LICENSE](LICENSE).