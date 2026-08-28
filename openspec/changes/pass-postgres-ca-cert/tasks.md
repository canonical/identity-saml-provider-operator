## 1. Charm Configuration and Constants

- [ ] 1.1 Add `db_sslmode` string option to `charmcraft.yaml` config options.
- [ ] 1.2 Add `POSTGRESQL_CA_CERT = CERTS_DIR_PATH / "postgres-ca.pem"` to `src/constants.py` and update DSN formatting templates.

## 2. Integration & Container File Updates

- [ ] 2.1 Update `DatabaseConfig` in `src/integrations.py` to extract `tls_ca` from relation data, accept an optional `db_sslmode` override, implement `to_service_configs()`, export effective `SAML_PROVIDER_DB_SSLMODE` and `SAML_PROVIDER_DB_CA_CERT_PATH` in `to_env_vars()`, and generate DSN with effective SSL parameters (Unit tests: `tests/unit/test_integrations.py`).
- [ ] 2.2 Implement `PostgreSQLCertificates` in `src/configs.py` as a `ContainerFile` (Unit tests: `tests/unit/test_configs.py`).
- [ ] 2.3 Register `PostgreSQLCertificates` in `IdentitySAMLProviderCharm.config_files` and pass `db_sslmode` from `CharmConfig` in `src/charm.py` (Unit tests: `tests/unit/test_charm.py`).
- [ ] 2.4 Add validation in charm status collection for invalid `db_sslmode` values.

## 3. Verification Suite

- [ ] 3.1 Run `tox` to format, lint, and run the entire test suite.
