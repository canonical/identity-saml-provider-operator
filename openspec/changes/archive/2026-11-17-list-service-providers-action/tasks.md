# Tasks

## 1. CLI Layer

- [x] 1.1 Add `CommandLine.list_service_providers(environment: dict)` in `src/cli.py`; exec `["/usr/bin/identity-saml-provider", "service-provider", "list", "--format", "json"]` via `_run_cmd` with `environment` and return stdout. Keep the `# Copyright 2026 Canonical Ltd.` header.
- [x] 1.2 Add `TestCommandLine` tests in `tests/unit/test_cli.py` that patch `_run_cmd` and verify the command list, the `environment` pass-through, and the returned stdout; run `tox -e unit -- tests/unit/test_cli.py`.

## 2. Service Layer

- [x] 2.1 Add `WorkloadService.list_service_providers(db_env: dict[str, str])` in `src/services.py`; call `CommandLine.list_service_providers`, parse the `{"status": "success", "data": [...]}` envelope, return `{"service-providers": json.dumps(list)}`.
- [x] 2.2 Raise `ServiceProviderError` on non-zero exit, an error envelope, or invalid JSON; cover all three cases in `tests/unit/test_services.py`, mirroring `test_get_service_provider_when_succeeds`; run `tox -e unit -- tests/unit/test_services.py`.

## 3. Charm Action Handler

- [x] 3.1 Observe `self.on.list_service_providers_action` in `src/charm.py` beside the existing action observers (~lines 204-213).
- [x] 3.2 Add `_on_list_service_providers_action` with `@workload_ready`, mirroring `_on_get_service_provider_action`; call `self._workload_service.list_service_providers(self.database_config.to_env_vars())`, `event.set_results(result)`, and `event.fail(f"Failed to list service providers: {err}")` on `ServiceProviderError`.
- [x] 3.3 Add a `TestListServiceProvidersAction` class in `tests/unit/test_actions.py` mirroring `TestGetServiceProviderAction`: container-not-connected, service-not-ready, failure, success, and empty-list cases; run `tox -e unit -- tests/unit/test_actions.py`.

## 4. Action Declaration

- [x] 4.1 Add the `list-service-providers` action entry to `charmcraft.yaml` under `actions:`, description "List all registered service providers and their entity-ids.", with no params and no required fields; run `tox -e lint` and `tox -e fmt`.

## 5. Workload Image Bump

- [x] 5.1 Bumped `upstream-source` in `charmcraft.yaml` from `v0.2.1` to `v0.2.2` after upstream release #425 merged and tag v0.2.2 available; ran full `tox` suite (fmt, lint, unit) and verified the action works end to end on the new image.

## Workflow follow-up

- Archive the change after the project's review requirements are satisfied.
- Verify the archived result.

- Review follow-ups (2026-11-18): `list_service_providers` now runs with
  `service_context=WORKLOAD_SERVICE` (parity with `migrate`), surfaces the
  CLI error envelope printed to stdout on non-zero exit (`ExecError`), and
  serializes the action output with `ensure_ascii=False`. Action tests
  include `database_integration` in state and assert the forwarded
  `SAML_PROVIDER_DB_*` env vars.
  - Image bump completed (2026-11-18) as part of the PR #169 finalization.
