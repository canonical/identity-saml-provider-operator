## Why

When the PostgreSQL database relation provides a TLS Certificate Authority (CA) certificate in its relation databag (`tls-ca`), the charm currently ignores this certificate and defaults database connections to unencrypted `sslmode=disable`. To support secure deployments with TLS-enabled PostgreSQL databases, the charm must pass the PostgreSQL CA certificate down to the workload container and configure `verify-ca` mode (or an administrator-configured SSL mode override) using the same pattern as Hydra certificates.

## What Changes

- Extract the PostgreSQL CA certificate (`tls-ca`) from database relation data in `DatabaseConfig`.
- Introduce a new container file abstraction `PostgreSQLCertificates` to manage `/etc/saml/postgres-ca.pem` inside the workload container.
- Add a new Juju configuration option `db_sslmode` in `charmcraft.yaml` allowing administrators to override the PostgreSQL SSL mode (e.g., `disable`, `allow`, `prefer`, `require`, `verify-ca`, `verify-full`).
- Automatically default the SSL mode to `verify-ca` when a PostgreSQL TLS CA certificate is present and `db_sslmode` is not explicitly set, or `disable` when no TLS CA certificate is present.
- Export environment variables `SAML_PROVIDER_DB_SSLMODE` and `SAML_PROVIDER_DB_CA_CERT_PATH=/etc/saml/postgres-ca.pem` to the Pebble layer.
- Update the database migration DSN in `DatabaseConfig.dsn` to include the effective `sslmode` and `sslrootcert=/etc/saml/postgres-ca.pem` when a CA certificate is present.

## Capabilities

### New Capabilities
- `database-tls-ca`: Pass PostgreSQL CA certificates to the workload container and configure database connection SSL parameters with optional Juju config override.

### Modified Capabilities
<!-- No existing capability requirements are changing -->

## Impact

- `charmcraft.yaml`: Adds `db_sslmode` configuration option.
- `src/constants.py`: Adds `POSTGRESQL_CA_CERT = CERTS_DIR_PATH / "postgres-ca.pem"`.
- `src/integrations.py`: Updates `DatabaseConfig` to read `tls-ca`, accept optional SSL mode override, implement `to_service_configs()`, export SSL environment variables in `to_env_vars()`, and generate DSN with SSL parameters.
- `src/configs.py`: Implements `PostgreSQLCertificates` (`ContainerFile`).
- `src/charm.py`: Adds `PostgreSQLCertificates` to `IdentitySAMLProviderCharm.config_files` and passes `db_sslmode` from charm config to `DatabaseConfig`.
