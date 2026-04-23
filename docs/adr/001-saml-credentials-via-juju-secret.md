# ADR-001: SAML Credentials via Juju Secret

## Status

Accepted

## Date

2026-04-23

## Context

The Identity SAML Provider operator requires a public
certificate and private key for signing and verifying SAML
assertions. Previously, the charm relied on the
`tls-certificates` integration to obtain these credentials
from a certificate provider charm.

Two issues were identified with this approach:

1. **Incompatible interface requirements across certificate
   provider charms.** Different certificate provider charms
   (e.g., `self-signed-certificates`, `lego`)
   impose varying requirements on the
   Common Name (CN) and Subject Alternative Names (SANs)
   supplied in the Certificate Signing Request (CSR). The
   charm must satisfy these requirements to successfully
   obtain a certificate, coupling the charm's
   implementation to the specifics of whichever certificate
   provider is deployed.

2. **SAML assertions do not require a certificate bound to
   a Common Name.** The certificate used to sign SAML
   assertions serves solely as a cryptographic signing key
   pair. Unlike TLS server certificates, it does not
   authenticate a hostname or service endpoint.
   Consequently, the CN field and SAN extensions are
   semantically irrelevant, and the requirement to populate
   them introduces unnecessary complexity and potential for
   misconfiguration.

## Decision

Drop the `tls-certificates` integration for SAML assertion
signing credentials. Instead, require operators to provision
the private key and public certificate as a Juju secret and
pass the secret ID to the charm via the `saml_credentials`
configuration option.

The expected workflow is:

```shell
juju add-secret saml-credential \
  private-key#file=<private-key-file> \
  public-cert#file=<public-certificate-file>

juju grant-secret saml-credential identity-saml-provider-operator

juju config identity-saml-provider-operator saml_credentials=secret:<secret-id>
```

## Consequences

### Positive

- **Decoupled from certificate provider charms.** The charm
  no longer depends on a certificate provider charm for
  SAML signing credentials, eliminating the coupling to
  provider-specific CSR field requirements (CN, SANs).
- **Full operator control over key lifecycle.** Operators
  manage generation, rotation, and revocation of the key
  pair externally, enabling use of organisation-specific
  PKI tooling and policies.
- **Secure credential transport.** Juju secrets ensure that
  private key material is neither exposed in plaintext
  configuration values nor transmitted via unencrypted
  relation data.
- **Simplified charm logic.** Removal of the
  `tls-certificates` integration eliminates CSR generation,
  certificate renewal event handling, and
  provider-compatibility logic from the charm codebase.

### Negative

- **Additional operational step.** Operators must generate
  the key pair and create the Juju secret prior to
  deployment, adding a prerequisite to the deployment
  workflow.
- **Manual rotation responsibility.** Certificate and key
  rotation is no longer automated via the integration;
  operators must update the Juju secret contents and ensure
  the charm picks up the new credentials.
