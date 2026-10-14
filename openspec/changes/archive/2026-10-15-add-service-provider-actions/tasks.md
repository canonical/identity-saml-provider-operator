# Tasks: Add Service Provider Charm Actions

## 1. Action Metadata and Constants

- [x] 1.1 Define `create-service-provider`, `update-service-provider`,
  `get-service-provider`, and `delete-service-provider` actions in
  `charmcraft.yaml`.
- [x] 1.2 Add `ADMIN_SERVICE_PROVIDERS_URL`, `ADMIN_SP_ATTRIBUTE_MAPPING_URL`,
  and `DEFAULT_ACS_BINDING` to `src/constants.py`.
- [x] 1.3 Add `ServiceProviderError` exception class to `src/exceptions.py`.

## 2. Workload Service and Action Handlers

- [x] 2.1 Implement `create_service_provider`, `update_service_provider`,
  `get_service_provider`, `delete_service_provider`, and Admin HTTP API
  request/validation helpers on `WorkloadService` in `src/services.py`.
- [x] 2.2 Add `workload_ready` decorator to `src/utils.py` and register action
  observers (`_on_create_service_provider_action`,
  `_on_update_service_provider_action`, `_on_get_service_provider_action`, and
  `_on_delete_service_provider_action`) in `src/charm.py`.

## 3. Testing and Verification

- [x] 3.1 Add unit tests for the new action handlers in
  `tests/unit/test_actions.py` and fixtures in `tests/unit/conftest.py`.
- [x] 3.2 Add unit tests for `WorkloadService` Service Provider methods and HTTP
  error handling in `tests/unit/test_services.py`.
- [x] 3.3 Add `test_service_provider_actions` integration test in
  `tests/integration/test_charm.py`.
- [x] 3.4 Run `tox` to verify formatting, linting, type checking, and unit test
  coverage.
