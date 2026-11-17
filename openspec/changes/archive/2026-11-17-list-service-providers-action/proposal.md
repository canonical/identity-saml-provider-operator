# Proposal

## Why

Operators cannot enumerate the service providers registered in the workload.
Issue [#168](https://github.com/canonical/identity-saml-provider-operator/issues/168)
asks for a `list-service-providers` action that returns all registered service
providers and their entity-ids. The missing action blocks the application
onboarding workflow.

## What Changes

- Add a `list-service-providers` Juju action (no parameters) to
  `charmcraft.yaml`. It returns all registered service providers and their
  entity-ids as a JSON string under the `service-providers` result key.
- Add `CommandLine.list_service_providers` in `src/cli.py`. It runs
  `identity-saml-provider service-provider list --format json` in the workload
  container with the database environment.
- Add `WorkloadService.list_service_providers` in `src/services.py`. It parses
  the CLI JSON envelope and raises `ServiceProviderError` on failure.
- Add a `_on_list_service_providers_action` handler in `src/charm.py`, observed
  with the other service provider actions and guarded by `@workload_ready`.
- Add unit tests in `tests/unit/test_cli.py`, `tests/unit/test_services.py`,
  and `tests/unit/test_actions.py`.
- The action reads through the workload CLI, not the Admin HTTP API. The Admin
  HTTP API has no list endpoint. The companion upstream change
  `service-provider-list-command` (canonical/identity-saml-provider) adds the
  `service-provider list` cobra subcommand.
- The pinned workload image (`ghcr.io/canonical/identity-saml-provider:v0.2.1`)
  does not contain the new subcommand. The `upstream-source` bump in
  `charmcraft.yaml` is a required final task after the upstream release.

## Capabilities

### New Capabilities

(None)

### Modified Capabilities

- `service-provider-actions`: add a requirement for the `list-service-providers`
  action. The action returns the full provider list as a JSON string, uses the
  workload CLI with the database environment, and fails cleanly when the
  workload is not ready or the CLI fails.

## Impact

- Code: `charmcraft.yaml`, `src/charm.py`, `src/services.py`, `src/cli.py`.
- Tests: `tests/unit/test_cli.py`, `tests/unit/test_services.py`,
  `tests/unit/test_actions.py`.
- Dependencies: the upstream release of canonical/identity-saml-provider that
  ships the `service-provider list` subcommand; the `upstream-source` bump in
  `charmcraft.yaml` must follow that release before the action works end to
  end. The existing `get-service-provider`, `create-service-provider`,
  `update-service-provider`, and `delete-service-provider` actions keep their
  Admin HTTP API behavior; this change does not alter them.
