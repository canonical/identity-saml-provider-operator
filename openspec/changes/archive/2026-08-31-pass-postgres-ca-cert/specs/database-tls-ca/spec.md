## Purpose

Passes PostgreSQL TLS CA certificates to the workload container and configures secure database connection settings using verify-ca mode or an explicit Juju config override.

## ADDED Requirements

### Requirement: Workload PostgreSQL CA Certificate File Provisioning
The charm SHALL write the PostgreSQL Certificate Authority (CA) certificate received from the database relation to `/etc/saml/postgres-ca.pem` in the workload container whenever a TLS CA is present.

#### Scenario: Database relation provides TLS CA certificate
- **WHEN** the `database` relation data contains a `tls-ca` certificate string
- **THEN** the charm writes the CA certificate to `/etc/saml/postgres-ca.pem` (mode 0644, parent directory `/etc/saml` created with mode 0755) and restarts/replans the workload service if the certificate content changes

#### Scenario: Database relation does not provide TLS CA certificate
- **WHEN** the `database` relation data does not contain a `tls-ca` certificate
- **THEN** the charm does not configure custom certificate paths in the environment, ensuring backward compatibility with existing unencrypted deployments

#### Scenario: TLS CA certificate is removed
- **WHEN** a previously provided `tls-ca` certificate is removed or the database relation is broken
- **THEN** the charm removes `SAML_PROVIDER_DB_CA_CERT_PATH` from the workload environment and replans/restarts the service

### Requirement: Database SSL Mode Resolution and Juju Config Override
The charm SHALL allow overriding the PostgreSQL SSL mode via the `db_sslmode` Juju configuration option, falling back to `verify-ca` when a TLS CA certificate is present or `disable` when absent.

#### Scenario: Explicit Juju config override provided
- **WHEN** the operator sets the Juju config `db_sslmode` to a valid SSL mode (e.g. `require` or `verify-full`)
- **THEN** the charm uses the configured `db_sslmode` value in the Pebble layer environment (`SAML_PROVIDER_DB_SSLMODE`) and in the database migration DSN

#### Scenario: Automatic verify-ca default when TLS CA is present
- **WHEN** `db_sslmode` is not set (empty) and the database relation includes a `tls-ca` certificate
- **THEN** the charm automatically defaults `SAML_PROVIDER_DB_SSLMODE=verify-ca` and sets `SAML_PROVIDER_DB_CA_CERT_PATH=/etc/saml/postgres-ca.pem`

#### Scenario: Automatic disable default for backward compatibility
- **WHEN** `db_sslmode` is not set (empty) and the database relation does not include a `tls-ca` certificate
- **THEN** the charm defaults `SAML_PROVIDER_DB_SSLMODE=disable` and omits `SAML_PROVIDER_DB_CA_CERT_PATH`, matching existing deployment behavior

#### Scenario: Invalid SSL mode configured
- **WHEN** the operator sets `db_sslmode` to an invalid or unsupported SSL mode value
- **THEN** the charm blocks with a descriptive status message indicating the invalid SSL mode configuration

### Requirement: Database Migration DSN with TLS
The charm SHALL format the database migration connection string with the effective `sslmode` and `sslrootcert` parameters when TLS is active.

#### Scenario: Running migration action or automated migration with TLS CA
- **WHEN** database migrations are executed and the database relation has a `tls-ca` certificate
- **THEN** the charm passes a DSN containing the effective `sslmode` and `sslrootcert=/etc/saml/postgres-ca.pem` to the migration CLI command
