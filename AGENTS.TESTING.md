# Testing — Identity SAML Provider Operator

## Scope

- Applies to creating or modifying tests in `tests/unit/` and
  `tests/integration/`.
- Prefer minimal, targeted test changes that match existing fixture and helper
  patterns.

## Commands

| Task | Command |
| --- | --- |
| Run all unit tests | `tox -e unit` |
| Run one unit file | `tox -e unit -- tests/unit/test_charm.py` |
| Run one unit test | `tox -e unit -- tests/unit/test_charm.py::TestSomeClass::test_when_condition` |
| Run all integration tests | `tox -e integration` |
| Reuse existing model | `tox -e integration -- --juju-model <prefix> --no-juju-setup --no-juju-teardown` |

## External References

Before writing or modifying tests, you MUST read and understand the following
references. These are the canonical sources of truth for the testing frameworks
used in this project.

| Need | URL |
| --- | --- |
| `ops.testing` API reference | <https://documentation.ubuntu.com/ops/latest/reference/ops-testing/#> |
| How to write unit tests for a charm | <https://documentation.ubuntu.com/ops/latest/howto/write-unit-tests-for-a-charm/> |
| How to write integration tests for a charm | <https://documentation.ubuntu.com/ops/latest/howto/write-integration-tests-for-a-charm/> |
| `jubilant` API reference | <https://documentation.ubuntu.com/jubilant/reference/jubilant/> |
| `pytest-jubilant` plugin | <https://github.com/canonical/pytest-jubilant> |

---

## 1. Global Test Policy

These rules apply to **both** unit and integration tests.

- MUST include both success-path and failure/error-path coverage for any new
  behavior.
- MUST NOT embed secrets, credentials, or real tokens in test code.
- MUST NOT duplicate existing fixtures or helpers — reuse first, extend only
  when necessary.
- MUST NOT place `import` statements inside a test function body.
- MUST use existing helpers and fixtures for an operation instead of duplicating
  their logic inline in a test function.
- MUST ensure higher-level helpers delegate to lower-level ones, not copy-paste
  their body.
- MUST validate resource existence in fixtures that resolve external artifacts
  and raise a descriptive error on failure.
- MUST have at least one test exercising every recipe in the recipe table.
- MUST delete any fixture or helper that is not consumed by at least one test.
- SHOULD name test methods `test_when_<condition>` to describe the scenario
  under test.
- SHOULD use `caplog` (unit) or `logger` (integration) for logging assertions on
  error paths.

---

## 2. Unit Tests

### 2.1 Testing Stack

Installed via `unit-requirements.txt` (which pulls in `requirements.txt`):

| Package | Purpose |
| --- | --- |
| `ops[testing]` | Provides `ops.testing.Context`, `ops.testing.State`, `ops.testing.Container`, `ops.testing.Relation`, etc. for declarative charm unit testing. See [ops.testing reference](https://documentation.ubuntu.com/ops/latest/reference/ops-testing/#). |
| `pytest` | Test runner and assertion framework. |
| `pytest-mock` | `MockerFixture` wrapper around `unittest.mock` for concise patching. |
| `coverage[toml]` | Branch-aware coverage measurement; config in `pyproject.toml`. |

The runtime charm dependencies (e.g. `ops`, `cosl`, `Jinja2`, `lightkube`,
`pydantic`) are also available at test time through `-r requirements.txt`.

### 2.2 Unit Test Categories

Unit tests fall into two categories depending on what is being tested:

| Category | What to test | Testing approach |
| --- | --- | --- |
| **Charm & Actions** (`src/charm.py`) | Event handlers and Juju action handlers | Use `ops.testing.Context` / `ops.testing.State` to simulate events and assert state transitions. Do NOT use the legacy `ops.testing.Harness`. |
| **Supporting modules** (everything else under `src/`) | Services, configs, CLI wrappers, integrations, secrets, utilities | Use plain `pytest` with `unittest.mock` / `pytest-mock` patching. No `ops.testing` needed — test the class or function directly. |

### 2.3 Unit Test Policy

- MUST follow the **Arrange → Act → Assert** structure in every test:
  1. **Arrange** — set up state, fixtures, mocks, and inputs.
  2. **Act** — call the function or trigger the event under test (single
     action).
  3. **Assert** — verify outcomes: return values, state mutations, mock calls,
     logs.
- MUST reuse fixtures from `tests/unit/conftest.py` before adding new ones.
- MUST patch at the import/call site used by the code under test (e.g. for charm
  handlers, patch `charm.<Symbol>`).
- MUST assert observable outcomes — state mutations (defer count, ports,
  relation data, status) — not only mock invocations.
- MUST NOT perform real network, Juju, or Kubernetes operations in unit tests.
- MUST add or update tests in the corresponding test file when source logic
  changes (see [Source-To-Test Mapping](#27-source-to-test-mapping)).
- MUST run `tox -e unit` locally before proposing changes.
- SHOULD group tests by event or component into classes (`TestStartEvent`,
  `TestPebbleService`) and name methods `test_when_<condition>`.
- SHOULD use `caplog` for logging assertions on error paths.

### 2.4 Fixture Authoring Guide

Fixtures live in `tests/unit/conftest.py`. Before adding a new fixture, check if
one already exists for the same purpose. When creating fixtures, follow these
patterns:

#### Autouse fixtures for global environment mocking

Patch infrastructure that every test needs neutralised (e.g. Kubernetes clients,
resource patchers). Mark with `autouse=True` so no test has to opt-in.

```python
@pytest.fixture(autouse=True)
def mocked_k8s_client(mocker: MockerFixture) -> None:
    """Prevent real K8s API calls in every unit test."""
    mocker.patch("charm.Client", autospec=True)
```

#### Relation / PeerRelation fixtures

Create one fixture per integration endpoint the charm declares. Use
`testing.Relation` for regular relations and `testing.PeerRelation` for peer
relations. Populate `remote_app_data` with representative values matching what
the remote charm would provide.

```python
@pytest.fixture
def database_integration() -> testing.Relation:
    return testing.Relation(
        endpoint="database",
        interface="postgresql_client",
        remote_app_name="postgresql-k8s",
        remote_app_data={
            "endpoints": "postgresql-k8s-primary.model.svc.cluster.local:5432",
            "username": "username",
            "password": "password",
        },
    )
```

#### Mocking charm methods or properties

Patch the method/property on the charm class at its import site (usually
`charm.<Class>.<method>`). Use `new_callable=PropertyMock` for properties.
Return the mock so tests can make assertions on it.

```python
@pytest.fixture
def mocked_charm_handler(mocker: MockerFixture) -> MagicMock:
    return mocker.patch("charm.MyCharm._some_handler")

@pytest.fixture
def mocked_service_running(mocker: MockerFixture) -> MagicMock:
    return mocker.patch(
        "charm.WorkloadService.is_running", new_callable=PropertyMock, return_value=True
    )
```

#### Mocking external library symbols

Patch library classes/functions at the charm's import site, not at the library's
source.

```python
@pytest.fixture
def mocked_database_resource_created(mocker: MockerFixture) -> MagicMock:
    return mocker.patch("charm.DatabaseRequires.is_resource_created", return_value=True)
```

### 2.5 Unit Test Recipes

| Recipe | Pattern |
| --- | --- |
| Event handler flow | Build `state_in` → `ctx.run(ctx.on.<event>(...), state_in)` → assert `state_out` and mocks. |
| Defer behavior | Set unmet prerequisite (e.g. `can_connect=False`) → run event → assert `len(state_out.deferred) == 1`. |
| Leader-gated behavior | Run once with `leader=True` and once with `leader=False` → assert gated side effects. |
| Relation data updates | Run relation event with fixture relations → assert `state_out.get_relation(...).local_app_data[...]`. |

### 2.6 Unit Test Templates

#### Charm / Action tests (ops.testing)

```python
class TestSomeEvent:
    def test_when_condition(self, some_relation: testing.Relation) -> None:
        # Arrange
        ctx = testing.Context(MyCharm)
        container = testing.Container(WORKLOAD_CONTAINER, can_connect=True)
        state_in = testing.State(
            containers={container}, relations=[some_relation], leader=True
        )

        # Act
        with patch("charm.SomeDependency") as mocked_dep:
            state_out = ctx.run(ctx.on.relation_changed(some_relation), state_in)

        # Assert
        assert len(state_out.deferred) == 0
        mocked_dep.assert_called_once()

    def test_when_container_not_ready(self) -> None:
        # Arrange
        ctx = testing.Context(MyCharm)
        container = testing.Container(WORKLOAD_CONTAINER, can_connect=False)
        state_in = testing.State(containers={container}, leader=True)

        # Act
        state_out = ctx.run(ctx.on.pebble_ready(container), state_in)

        # Assert
        assert len(state_out.deferred) == 1
```

#### Supporting module tests (pure pytest + mocking)

```python
class TestWorkloadService:
    def test_when_service_starts_successfully(self, mocker: MockerFixture) -> None:
        # Arrange
        mocked_container = mocker.MagicMock()
        service = WorkloadService(mocked_container)

        # Act
        service.start()

        # Assert
        mocked_container.add_layer.assert_called_once()
        mocked_container.replan.assert_called_once()

    def test_when_container_not_connected(self, mocker: MockerFixture) -> None:
        # Arrange
        mocked_container = mocker.MagicMock()
        mocked_container.can_connect.return_value = False
        service = WorkloadService(mocked_container)

        # Act & Assert
        with pytest.raises(PebbleServiceError):
            service.start()
```

### 2.7 Source-To-Test Mapping

Each source module under `src/` MUST have a corresponding test file under
`tests/unit/`. The naming convention is:

| Source module | Test file |
| --- | --- |
| `src/<module>.py` | `tests/unit/test_<module>.py` |

For `src/charm.py`, action handlers MAY be tested in a separate
`tests/unit/test_actions.py` file.

### 2.8 Charm Event Coverage Checklist

When writing unit tests for a charm, ensure the following event categories are
covered:

| Event category | Required coverage |
| --- | --- |
| Lifecycle events (`start`, `install`, `config_changed`, `leader_elected`, `update_status`) | Assert the main handler is dispatched and produces expected status/state. |
| `pebble_ready` | Cover `can_connect=False` (defer) and `can_connect=True` (service started, ports opened). |
| Relation `*_changed` events | Cover: no container, missing prerequisites, happy-path with data, leader vs non-leader when relevant. |
| Relation `*_broken` events | Assert handler invocation and resulting blocked/waiting status. |
| `secret_changed` | Ensure secret-triggered reconcile path is exercised. |
| Actions | Cover success return and failure/error raise for each action. |

---

## 3. Integration Tests

### 3.1 Testing Stack

Installed via `integration-requirements.txt` (which pulls in
`requirements.txt`):

| Package | Purpose |
| --- | --- |
| `jubilant` | Python client for Juju CLI — deploy, integrate, wait, status, debug-log. See [jubilant reference](https://documentation.ubuntu.com/jubilant/reference/jubilant/). |
| `pytest-jubilant` ≥ 2.0 | Pytest plugin providing built-in `juju` and `juju_factory` fixtures, `juju_setup` / `juju_teardown` markers, and CLI options (`--juju-model`, `--no-juju-setup`, `--no-juju-teardown`, `--juju-dump-logs`). See [pytest-jubilant](https://github.com/canonical/pytest-jubilant). |
| `pytest` | Test runner and assertion framework. |
| `requests` | HTTP client for verifying charm endpoints. |
| `tenacity` | Retry logic for transient Juju CLI failures. |

### 3.2 Integration Runtime Requirements

| Requirement | Details |
| --- | --- |
| **Juju controller** | A bootstrapped Juju controller accessible from the test runner. |
| **Environment variables** | Check `tests/integration/util.py` for project-specific constants and `tests/integration/conftest.py` for `CHARM_PATH` support. |
| **Optional env var** | `CHARM_PATH` — path to a pre-built `.charm` file; skips local `charmcraft pack`. |
| **pytest CLI options** (from `pytest-jubilant` 2.x) | `--juju-model <prefix>`, `--no-juju-setup`, `--no-juju-teardown`, `--juju-switch`, `--juju-dump-logs [path]`. |

### 3.3 Integration Test Policy

- MUST use the `juju` fixture provided by `pytest-jubilant` for all Juju
  operations. Do NOT define a custom `juju` fixture — the plugin provides it
  automatically (module-scoped, via `juju_factory`).
- MUST use `@pytest.mark.juju_setup` for deployment/bootstrap tests and
  `@pytest.mark.juju_teardown` for destructive cleanup tests. Do NOT define
  custom `setup` / `teardown` markers — use the plugin's built-in markers.
- MUST use helpers from `tests/integration/util.py` for waits, predicates, and
  integration data reads.
- MUST validate behavior using Juju status and relation data (e.g. `juju.wait`,
  `get_app_integration_data`).
- MUST preserve app name constants defined in `tests/integration/util.py`.
- MUST NOT hard-code model names — the `juju` fixture handles model
  creation/reuse.
- MUST NOT implement custom CLI options for `--model`, `--no-setup`, or
  `--no-teardown` — use the plugin's `--juju-model`, `--no-juju-setup`,
  `--no-juju-teardown` instead.
- SHOULD use `--juju-dump-logs [path]` for persisting debug logs instead of
  custom log-dumping logic.

### 3.4 Integration Fixture Authoring Guide

Fixtures live in `tests/integration/conftest.py`. `pytest-jubilant` 2.x provides
core fixtures out of the box — do NOT reimplement them. Add only
project-specific fixtures.

#### Built-in fixtures from `pytest-jubilant` 2.x (do NOT redefine)

| Fixture | Scope | What it provides |
| --- | --- | --- |
| `juju_factory` | module | `JujuFactory` that manages model creation/teardown, debug-log dumping. Call `juju_factory.get_juju(suffix)` to create additional models. |
| `juju` | module | `jubilant.Juju` bound to the default model (calls `juju_factory.get_juju("")`). Automatically created and torn down. |

#### Charm artifact fixture

Returns the path to the `.charm` file, supporting `CHARM_PATH` env var, local
glob, and fallback to `charmcraft pack`. MUST validate that the resolved path
exists and raise explicit errors on failure.

```python
@pytest.fixture(scope="session")
def charm_artifact() -> Path:
    if charm_path := os.getenv("CHARM_PATH"):
        path = Path(charm_path)
        if not path.exists():
            raise FileNotFoundError(
                f"CHARM_PATH is set to '{charm_path}' but the file does not exist"
            )
        return path.resolve()
    if local := next(Path(".").glob("*.charm"), None):
        return local.resolve()
    subprocess.run(["charmcraft", "pack"], check=True)
    if packed := next(Path(".").glob("*.charm"), None):
        return packed.resolve()
    raise RuntimeError("charmcraft pack succeeded but no .charm file was produced")
```

#### Integration data convenience fixtures

Wrap `get_app_integration_data` for frequently-queried endpoints.

```python
@pytest.fixture
def app_integration_data(juju: jubilant.Juju) -> Callable:
    return functools.partial(get_app_integration_data, juju)
```

### 3.5 Integration Helper Authoring Guide

Helpers live in `tests/integration/util.py`. These complement the
`pytest-jubilant` plugin with project-specific utilities. Do NOT reimplement
model management — the plugin handles it.

#### App name constants

Define all app/charm names as module-level constants so tests never hard-code
strings.

```python
METADATA = yaml.safe_load(Path("./charmcraft.yaml").read_text())
OCI_IMAGE = METADATA["resources"]["oci-image"]["upstream-source"]

MY_APP = "my-app"
DB_APP = "postgresql"
DB_CHARM = "postgresql-k8s"
```

#### Status predicates

Build composable predicates using `jubilant.all_active`, `jubilant.all_blocked`,
etc. Combine with `and_` / `or_` helpers for complex wait conditions.

```python
StatusPredicate = Callable[[jubilant.Status], bool]

def all_active(*apps: str) -> StatusPredicate:
    return lambda status: jubilant.all_active(status, *apps)

def is_blocked(app: str) -> StatusPredicate:
    return lambda status: status.apps[app].is_blocked

def unit_number(app: str, expected_num: int) -> StatusPredicate:
    return lambda status: len(status.apps[app].units) == expected_num

def and_(*predicates: StatusPredicate) -> StatusPredicate:
    return lambda status: all(p(status) for p in predicates)
```

#### Integration data readers

Wrap `juju.cli("show-unit", ...)` to extract relation and unit data.
`get_app_integration_data` MUST delegate to `get_integration_data` to avoid
duplicated CLI parsing logic.

```python
def get_integration_data(
    juju: jubilant.Juju, app_name: str, integration_name: str, unit_num: int = 0
) -> dict | None:
    unit_name = f"{app_name}/{unit_num}"
    result = juju.cli("show-unit", unit_name, "--format", "json")
    unit_data = json.loads(result.stdout)
    relations = unit_data.get(unit_name, {}).get("relation-info", [])
    for relation in relations:
        if relation.get("endpoint") == integration_name:
            return relation
    return None

def get_app_integration_data(
    juju: jubilant.Juju, app_name: str, integration_name: str, unit_num: int = 0
) -> dict | None:
    data = get_integration_data(juju, app_name, integration_name, unit_num)
    return data.get("application-data") if data else None
```

#### Remove & restore context manager

Temporarily removes an integration and restores it after the `with` block, with
retry logic.

```python
@contextmanager
def remove_integration(
    juju: jubilant.Juju, remote_app_name: str, integration_name: str
) -> Generator[None, None, None]:
    juju.remove_relation(f"{MY_APP}:{integration_name}", remote_app_name)
    try:
        yield
    finally:
        # re-integrate with retry ...
```

### 3.6 Integration Test Recipes

| Recipe | Pattern |
| --- | --- |
| Deploy & wait | `juju.deploy(...)` → `juju.integrate(...)` → `juju.wait(ready=all_active(...), error=any_error(...), timeout=N)`. |
| Assert integration data | `data = get_app_integration_data(juju, APP, "endpoint")` → `assert data["key"]`. |
| Remove & restore integration | `with remove_integration(juju, REMOTE_APP, "endpoint"):` → `juju.wait(ready=is_blocked(APP), ...)`. |
| Scale up/down | `juju.cli("scale-application", APP, "N")` → `juju.wait(ready=and_(all_active(APP), unit_number(APP, N)), ...)`. |
| HTTP smoke test | `requests.get(f"http://{unit_ip}:{port}/path")` → `assert resp.status_code < 500`. Use `pytest.skip()` when the unit IP is unreachable from the test runner. |
| Action (success) | `result = juju.run_action(f"{APP}/leader", "action-name")` → `assert result.status == "completed"`. |
| Action (failure) | `result = juju.run_action(f"{APP}/0", "action-name")` → `assert result.status == "failed"`. |
| Optional integration | After adding/removing an optional integration, assert charm stays `active` (not `blocked`). |

### 3.7 Integration Test Template

```python
@pytest.mark.juju_setup
def test_build_and_deploy(juju: jubilant.Juju, charm_artifact: Path) -> None:
    """Deploy the charm and its dependencies, then wait for active."""
    juju.deploy(charm=DB_CHARM, app=DB_APP, channel="14/stable", trust=True)
    juju.deploy(charm=charm_artifact, app=MY_APP, resources={"oci-image": OCI_IMAGE}, trust=True)
    juju.integrate(MY_APP, f"{DB_APP}:database")

    juju.wait(
        ready=all_active(DB_APP, MY_APP),
        error=any_error(DB_APP, MY_APP),
        timeout=10 * 60,
    )

def test_when_integration_data_is_present(app_integration_data: Callable) -> None:
    """Validate that integration data is available via the fixture."""
    data = app_integration_data(MY_APP, "database")
    assert data
    assert data["endpoints"]

def test_when_required_integration_is_removed(juju: jubilant.Juju) -> None:
    """Validate the charm goes blocked when a required integration is removed."""
    with remove_integration(juju, DB_APP, "database"):
        juju.wait(
            ready=is_blocked(MY_APP),
            timeout=5 * 60,
        )

def test_when_optional_integration_is_removed(juju: jubilant.Juju) -> None:
    """Validate the charm stays active when an optional integration is removed."""
    with remove_integration(juju, CERTS_APP, "receive-ca-cert"):
        juju.wait(
            ready=all_active(MY_APP),
            timeout=5 * 60,
        )

def test_when_http_endpoint_is_reachable(juju: jubilant.Juju) -> None:
    """Validate the workload HTTP endpoint responds."""
    status = juju.status()
    unit_ip = status.apps[MY_APP].units[f"{MY_APP}/0"].address
    try:
        resp = requests.get(f"http://{unit_ip}:{PORT}/path", timeout=10)
    except requests.ConnectionError:
        pytest.skip("Unit IP not reachable from test runner")
        return
    assert resp.status_code < 500

def test_when_action_succeeds(juju: jubilant.Juju) -> None:
    """Validate a Juju action completes successfully."""
    result = juju.run_action(f"{MY_APP}/leader", "my-action")
    assert result.status == "completed"
```

---

## 4. PR Checklist

- [ ] Unit tests added or updated in the mapped file under `tests/unit/`.
- [ ] New logic has both success-path and failure/defer-path assertions.
- [ ] Patches target symbols as imported by the code under test (usually
  `charm.*` for charm handlers).
- [ ] Integration tests updated when model behavior or integrations changed.
- [ ] `tox -e unit` passes locally before proposing changes.
- [ ] For integration changes, commands and assumptions are compatible with
  `tests/integration/conftest.py` options.
