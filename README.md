# Charmed Identity SAML Provider Operator

[![Juju](https://img.shields.io/badge/Juju%20-3.6+-%23E95420)](https://github.com/juju/juju)
[![License](https://img.shields.io/github/license/canonical/identity-saml-provider-operator?label=License)](https://github.com/canonical/identity-saml-provider-operator/blob/main/LICENSE)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit)](https://github.com/pre-commit/pre-commit)
[![Conventional Commits](https://img.shields.io/badge/Conventional%20Commits-1.0.0-%23FE5196.svg)](https://conventionalcommits.org)

## Description

This repository contains a Juju charm for deploying the
[Identity SAML Provider](https://github.com/canonical/identity-saml-provider)
on Kubernetes.

## Usage

Build identity SAML provider charm:

```shell
charmcraft pack -v
```

Deploy identity SAML provider charm:

```shell
juju deploy ./identity-saml-provider-operator_ubuntu@24.04-amd64.charm --resource oci-image=ghcr.io/canonical/identity-saml-provider:latest --trust
```

Deploy dependency charms:

```shell
juju deploy postgresql-k8s --channel 14/stable --trust
juju deploy traefik-k8s --channel latest/stable --trust
juju deploy self-signed-certificates-operator --channel 1/stable --trust
```

Please also deploy the
[Canonical identity platform](https://canonical-identity.readthedocs-hosted.com/tutorial/canonical-identity-platform/).

Integrate identity SAML provider charm with its required
integrations:

```shell
juju integrate identity-saml-provider-operator postgresql-k8s
juju integrate identity-saml-provider-operator traefik-k8s:traefik-route
juju integrate identity-saml-provider-operator hydra:oauth
juju integrate identity-saml-provider-operator self-signed-certificates:send-ca-cert
```

## Configurations and secrets

Identity SAML provider charm requires some sensitive settings
to be provided as Juju secrets.

```shell
juju add-secret saml-credential private-key#file=<private-key-file> public-cert#file=<public-certificate-file>
juju grant-secret saml-credential identity-saml-provider-operator
juju config identity-saml-provider-operator saml_credentials=secret:<saml-credential-secret-id>
```

## Integrations

### PostgreSQL

Identity SAML provider charm requires an integration with
[postgresql-k8s-operator](https://github.com/canonical/postgresql-k8s-operator).

### Ingress (via traefik-route)

Identity SAML provider charm requires an integration with
[traefik-k8s-operator](https://github.com/canonical/traefik-k8s-operator)
for ingress routing using the `traefik-route` interface.

### OAuth

Identity SAML provider charm requires an integration with
[hydra-operator](https://github.com/canonical/hydra-operator)
for OIDC authentication using the `oauth` interface.

### Certificate Transfer

Identity SAML provider charm requires an integration with a
CA provider charm for TLS certificate management. In the
example above, we use
[self-signed-certificates](https://github.com/canonical/self-signed-certificates-operator).

## Contributing

Please see the [Juju docs](https://documentation.ubuntu.com/juju/3.6/)
for general guidance on contributing to Juju charms, and
refer to [`CONTRIBUTING.md`](CONTRIBUTING.md) for developer
guidance.

## License

This charm is distributed under the Apache Software License,
version 2.0. See [LICENSE](LICENSE).
