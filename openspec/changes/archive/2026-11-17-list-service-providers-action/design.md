# Design

## Context

The charm manages service providers through the Admin HTTP API
(`src/services.py`, `_send_admin_request`). The Admin HTTP API has no list
endpoint: `GET /admin/service-providers` without `entity_id` returns HTTP 400
("entity_id query parameter is required"). Its handlers cover only register,
get, update attribute mapping, and delete attribute mapping.

The companion change `service-provider-list-command` in
canonical/identity-saml-provider adds a cobra subcommand
`identity-saml-provider service-provider list`. The subcommand reads database
settings from `SAML_PROVIDER_DB_*` environment variables (envconfig). The
charm's `DatabaseConfig.to_env_vars()` (`src/integrations.py`) already emits
exactly those variables: `SAML_PROVIDER_DB_HOST`, `SAML_PROVIDER_DB_PORT`,
`SAML_PROVIDER_DB_NAME`, `SAML_PROVIDER_DB_USER`, `SAML_PROVIDER_DB_PASSWORD`,
`SAML_PROVIDER_DB_SSLMODE`, and `SAML_PROVIDER_DB_CA_CERT_PATH` when a TLS CA
is set. The charm already executes the workload binary through pebble for
`version` and `migrations apply` (`src/cli.py`, `_run_cmd`).

The pinned image `ghcr.io/canonical/identity-saml-provider:v0.2.1` does not
contain the new subcommand. The action works end to end only after the
upstream release and the `upstream-source` bump in `charmcraft.yaml`.

## Goals / Non-Goals

**Goals:**

- Expose `list-service-providers` with no parameters in the existing service
  provider action family.
- Reuse the existing pebble exec path (`CommandLine._run_cmd`) and the
  existing database environment builder (`DatabaseConfig.to_env_vars()`).
- Keep the layering: `src/cli.py` runs the command, `src/services.py` parses
  the envelope, `src/charm.py` handles the action event.
- Return the provider list as a JSON string under the `service-providers`
  result key. Juju action results require flat string values. The existing
  `get-service-provider` action serializes `attribute-mapping` the same way.

**Non-Goals:**

- No change to the Admin HTTP API actions (create, update, get, delete).
- No new unauthenticated admin HTTP endpoint on the workload.
- No filtering, pagination, or search parameters on the action.
- No client-side enrichment of provider entries; the CLI output is the source
  of truth.

## Decisions

### Decision 1: CLI-backed integration, not the Admin HTTP API

The action executes `identity-saml-provider service-provider list --format
json` in the workload container. The Admin HTTP API at image v0.2.1 and
upstream main has no list endpoint, and adding one would expose a new
unauthenticated admin surface. The charm already execs the binary for
`version` and `migrations apply`, so the pattern and the plumbing exist. A CLI
subcommand also stays usable outside HTTP contexts (debugging, scripts).

Alternatives considered:

- *Add `GET /admin/service-providers` without `entity_id` to the workload
  API*: rejected because it widens the unauthenticated admin surface and
  contradicts the upstream design where `entity_id` is required.
- *Query PostgreSQL directly from the charm*: rejected because it duplicates
  the workload's schema knowledge in the charm and bypasses the workload's
  data model.

### Decision 2: Integration seam through environment variables

The charm handler passes `self.database_config.to_env_vars()` down to
`CommandLine.list_service_providers(environment=...)`, which passes it to
`_run_cmd` as the pebble exec environment. The CLI reads the same
`SAML_PROVIDER_DB_*` variables through envconfig. No DSN construction, no new
config surface, and TLS CA handling (`SAML_PROVIDER_DB_CA_CERT_PATH`) comes
along unchanged.

Alternatives considered:

- *Pass a `--dsn` flag like `migrations apply` does*: rejected because the
  upstream CLI command contract specifies envconfig-based database settings,
  and the charm's `to_env_vars()` already produces the exact variable set.

### Decision 3: Result shape as a serialized JSON string

`WorkloadService.list_service_providers(db_env)` parses the CLI envelope
(`{"status": "success", "data": [...]}`) and returns
`{"service-providers": json.dumps(list)}`. The handler passes the dict to
`event.set_results(result)` unchanged, matching the get/delete handler
pattern. An empty provider list yields the JSON string `[]`.

Alternatives considered:

- *Return one result key per provider*: rejected because Juju action result
  keys must be known and flat; a dynamic key set does not fit the Juju model.

### Decision 4: Error mapping

`WorkloadService.list_service_providers` raises `ServiceProviderError` on a
non-zero exit, an error envelope (`{"status": "error", "error": "..."}`), or
invalid JSON output. The handler fails the action with
`event.fail(f"Failed to list service providers: {err}")`, matching the
existing service provider action error style. Workload readiness stays with
the `@workload_ready` decorator used by the get and delete handlers.

## Risks / Trade-offs

- [The action fails on the pinned v0.2.1 image because the subcommand does not
  exist] → tasks.md carries the `upstream-source` bump as an explicit final
  task after the upstream release; the spec states the CLI contract so the
  failure mode is clear until then.
- [The action path (CLI + DB env) diverges from the other service provider
  actions (Admin HTTP API)] → documented in the spec delta and in code
  comments; the divergence comes from the missing API endpoint, not from a
  style choice.
- [A large provider list could exceed Juju action result size limits] → the
  onboarding workflow that requested the action expects a modest provider
  count; no pagination is added (Non-Goal), and the limit can be revisited if
  deployments hit it.
- [Concurrent CLI exec and running pebble service share the database] → the
  list command is read-only; no locking or transaction concerns beyond normal
  read isolation.
