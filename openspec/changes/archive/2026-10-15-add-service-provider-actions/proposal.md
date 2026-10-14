# Proposal: Add Service Provider Charm Actions

## Why

Administrators operating the Identity SAML Provider charm currently lack Juju
actions to manage SAML Service Providers (SPs) directly through Juju. Adding
`create-service-provider`, `update-service-provider`, `get-service-provider`,
and `delete-service-provider` charm actions enables operators to register SPs,
inspect SP configurations, update ACS endpoints or attribute mappings, and
remove custom SP attribute mappings via the workload's internal Admin HTTP API
(`localhost:8082`).

## What Changes

- Add `create-service-provider`, `update-service-provider`,
  `get-service-provider`, and `delete-service-provider` action schemas to
  `charmcraft.yaml`.
- Add Admin HTTP API endpoint constants (`ADMIN_SERVICE_PROVIDERS_URL`,
  `ADMIN_SP_ATTRIBUTE_MAPPING_URL`) and `DEFAULT_ACS_BINDING` to
  `src/constants.py`.
- Add `ServiceProviderError` domain exception to `src/exceptions.py`.
- Add `workload_ready` action handler decorator to `src/utils.py`.
- Extend `WorkloadService` in `src/services.py` with `create_service_provider`,
  `update_service_provider`, `get_service_provider`, and
  `delete_service_provider` methods that call the workload Admin HTTP API and
  normalize response keys for Juju action results.
- Register action event observers and handlers
  (`_on_create_service_provider_action`, `_on_update_service_provider_action`,
  `_on_get_service_provider_action`, `_on_delete_service_provider_action`) on
  `IdentitySAMLProviderCharm` in `src/charm.py`.
- Add unit tests in `tests/unit/test_actions.py` and
  `tests/unit/test_services.py`, and integration test coverage in
  `tests/integration/test_charm.py`.

## Capabilities

### New Capabilities

- `service-provider-actions`: Juju actions (`create-service-provider`,
  `update-service-provider`, `get-service-provider`, `delete-service-provider`)
  to manage SAML Service Providers and their attribute mappings via the workload
  Admin HTTP API.

### Modified Capabilities

<!-- No existing capability requirements are changing -->

## Impact

- `charmcraft.yaml`: Defines `create-service-provider`,
  `update-service-provider`, `get-service-provider`, and
  `delete-service-provider` actions and their parameter schemas.
- `src/constants.py`: Adds `ADMIN_SERVICE_PROVIDERS_URL`,
  `ADMIN_SP_ATTRIBUTE_MAPPING_URL`, and `DEFAULT_ACS_BINDING`.
- `src/exceptions.py`: Adds `ServiceProviderError`.
- `src/utils.py`: Adds `workload_ready` decorator to gate action handlers on
  container connectivity and workload readiness.
- `src/services.py`: Implements `WorkloadService.create_service_provider()`,
  `WorkloadService.update_service_provider()`,
  `WorkloadService.get_service_provider()`, and
  `WorkloadService.delete_service_provider()` along with HTTP client helpers.
- `src/charm.py`: Wires Juju action events to `WorkloadService` methods.
- `tests/unit/conftest.py`, `tests/unit/test_actions.py`,
  `tests/unit/test_services.py`, `tests/integration/test_charm.py`: Adds unit
  and integration tests for the new actions.
