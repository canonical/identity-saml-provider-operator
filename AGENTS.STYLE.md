# 🐍 Python Style Guide & Code Conventions for AI Agents

## 1. 🧭 Core Philosophy

When generating Python code, prioritize **clarity, maintainability, and safety
over cleverness**. AI agents must write code that is easily parsed by static
analysis tools and easily understood by human reviewers.

* **Explicit > Implicit:** Write out full logic instead of relying on implicit
  behavior or hidden side effects.
* **Fail Fast:** Validate inputs early and raise specific exceptions
  immediately.
* **Modern Standards:** Target **Python 3.12** syntax exclusively. Avoid
  deprecated libraries and legacy conventions.
* **EAFP over LBYL:** Prefer *Easier to Ask Forgiveness than Permission*.
  Attempt the operation and handle the exception rather than checking
  preconditions. This produces cleaner code and avoids race conditions between
  the check and the action.

```python
# GOOD — EAFP
try:
    secret = model.get_secret(id=secret_id)
except SecretNotFoundError:
    logger.error("Juju secret with id %s not found.", secret_id)
    return {}

# BAD — LBYL
if secret_exists(secret_id):
    secret = model.get_secret(id=secret_id)
else:
    logger.error("Juju secret with id %s not found.", secret_id)
    return {}
```

---

## 2. ✏️ Code Style and Formatting

Strictly adhere to **PEP 8** compliance with the following specific
enforcements:

* **Indentation:** Use exactly **4 spaces** per indentation level. Do not use
  tabs.
* **Line Length:** Maximum line length is **99 characters** (enforced by `ruff`
  and `isort` in `pyproject.toml`).
* **Naming Conventions:**
  * `snake_case`: Variables, functions, methods, modules, and packages.
  * `PascalCase`: Classes and Exception types.
  * `UPPER_CASE`: Constants defined at the module level.
  * `_single_leading_underscore`: Weak indicators for internal/private use
    within a class or module.

---

## 3. 🏷️ Mandatory Type Hinting

All code must be statically typed. Do not omit type hints for function arguments
or return values.

* **Modern Union Syntax:** Use the `|` operator for unions. **Do not** use
  `typing.Union`.
* **Built-in Collections:** Use built-in generic types (`list`, `dict`, `set`,
  `tuple`). **Do not** import capitalized versions from `typing` (e.g., use
  `list[str]`, not `List[str]`).
* **Optional Values:** Use `Type | None` instead of `Optional[Type]`.
* **Any:** Use `Any` only as a last resort when the type truly cannot be
  determined.

```python
# GOOD
def process_user_data(user_id: int, tags: list[str]) -> dict[str, str] | None:
    ...

# BAD
from typing import List, Dict, Union, Optional

def process_user_data(user_id: int, tags: List[str]) -> Optional[Dict[str, str]]:
    ...
```

---

## 4. 📝 Documentation and Docstrings

Every module, class, public function, and method must include a docstring. Use
the **Google Python Style** docstring format.

* Docstrings must accurately describe the purpose, parameters, return values,
  and raised exceptions.
* Do not duplicate type annotations in docstrings when they are already present
  in the function signature.

```python
def calculate_metrics(data: list[float], scale: float = 1.0) -> float:
    """Calculates the adjusted average of a dataset.

    Args:
        data: A list of floats representing the raw data points.
        scale: A multiplier applied to the final average. Defaults to 1.0.

    Returns:
        The scaled average of the data points.

    Raises:
        ValueError: If the data list is empty.
    """
    if not data:
        raise ValueError("The data list cannot be empty.")

    return (sum(data) / len(data)) * scale
```

---

## 5. 🔀 Control Flow and Modern Python Features

Leverage modern Python 3.12 constructs to keep code clean and optimal.

* **Pattern Matching:** Use `match/case` statements instead of deeply nested
  `if/elif/else` blocks when inspecting structural data or enums.
* **F-Strings:** Use f-strings for **general** string formatting. Do not use
  `.format()` or `%` formatting outside of logging calls (see §6 for
  logging-specific rules).
* **Context Managers:** Always use `with` statements for resource management
  (files, network connections, database sessions).

```python
# GOOD: Pattern Matching (Python 3.10+)
match response.status_code:
    case 200 | 201:
        return response.json()
    case 404:
        raise ResourceNotFoundError("Endpoint not found.")
    case _:
        raise APIError(f"Unexpected status code: {response.status_code}")
```

---

## 6. 🛡️ Error Handling and Logging

AI agents must write resilient code. Avoid generic error suppression.

* **No Bare `except:`:** Never use a bare `except:`. Always catch specific
  exceptions (`ValueError`, `KeyError`, etc.). If a catch-all is necessary,
  catch `Exception`.
* **No Silencing:** Never use `pass` in an exception block unless explicitly
  logging or handling it first.
* **Logging:** Use Python's built-in `logging` module. Do not use `print()`
  statements for application logs or errors.
* **No String Formatting in Log Calls:** Strictly use `%s`-style deferred
  parameter substitution in all `logger.*()` calls. The logging module lazily
  evaluates the message only if the log level is enabled. Do **not** use
  f-strings, `.format()`, or `%` interpolation to construct the message string
  before passing it to the logger.

```python
import logging

logger = logging.getLogger(__name__)

# GOOD — deferred formatting
logger.info("Processing integration %s with endpoint %s", integration_name, endpoint)
logger.error("Juju secret with id %s not found.", secret_id)

# BAD — eager formatting (wastes cycles when log level is disabled)
logger.info(f"Processing integration {integration_name} with endpoint {endpoint}")
logger.error("Juju secret with id {} not found.".format(secret_id))
logger.error("Juju secret with id %s not found." % secret_id)
```

---

## 7. 🧊 Data Classes and Structural Code

When building classes that primarily serve to store data or state, use Python's
`dataclasses` module.

* Enable `frozen=True` if the data structure should be immutable.
* Enable `slots=True` on frozen dataclasses to reduce memory footprint and
  prevent dynamic attribute assignment.
* Always provide type hints for all fields.

```python
from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class UserProfile:
    user_id: int
    username: str
    email: str
    is_active: bool = True
```

---

## 8. 🔌 Integration Adapter Patterns

Integration adapters encapsulate all access to Juju relation databags. The
choice of instantiation pattern depends on whether the integration adapter
carries **behavioural side-effects** (writing back to databags, updating remote
state) or simply **reads and transforms** data.

### 📖 Data-only integrations — use a `@classmethod` factory

When an integration adapter only reads from a relation databag and transforms
the data into internal domain objects (environment variables, DSNs,
configuration dicts), expose a `load` class method that accepts the library
requirer and returns a frozen instance. The orchestration layer calls `load` on
demand — no long-lived object is stored on the charm.

```python
@dataclass(frozen=True, slots=True)
class DatabaseConfig:
    """The data source from the database integration."""

    host: str = ""
    port: str = ""
    database: str = ""

    @classmethod
    def load(cls, requirer: DatabaseRequires) -> Self:
        """Build from the current relation databag snapshot."""
        if not (relations := requirer.relations):
            return cls()

        integration_data = requirer.fetch_relation_data()[relations[0].id]
        endpoint, *_ = integration_data.get("endpoints", "").partition(",")
        host, _, port = endpoint.partition(":")
        return cls(host=host, port=port, database=requirer.database)
```

### ⚡ Behavioural integrations — use a long-lived instance

When an integration adapter needs to **write back** to the relation databag or
**mutate remote state** (e.g., submitting a Traefik route config, updating an
OAuth client), instantiate it once during charm `__init__` and store it as a
charm attribute. The instance wraps the library requirer and exposes
domain-specific methods.

```python
class OAuthIntegration:
    """Adapter with side-effects — updates the OAuth client config on the provider."""

    def __init__(self, requirer: OAuthRequirer) -> None:
        self._requirer = requirer

    def update_oauth_client_config(self, saml_provider_url: str) -> None:
        self._requirer.update_client_config(...)

    def to_env_vars(self) -> EnvVars:
        ...
```

### 🧭 Decision rule

| Integration characteristic | Pattern | Example |
| --- | --- | --- |
| Read-only data extraction, no writes to databag | `@classmethod load()` factory returning a frozen dataclass | `DatabaseConfig`, `TransferredCertificates` |
| Writes to the relation databag or triggers remote updates | Long-lived instance stored on the charm | `PublicRouteIntegration`, `OAuthIntegration` |

---

## 9. 🚫 Prohibited Practices (The "Never" List)

To ensure safety and execution predictability, the AI agent **must never**:

1. **Never** use `eval()`, `exec()`, or `compile()` due to critical security
   risks.
2. **Never** use wildcards for imports (e.g., `from module import *`). Always
   import explicitly.
3. **Never** mutate a collection (list, dict) while iterating over it.
4. **Never** hardcode secrets, API keys, tokens, or passwords. Always fetch them
   via the Juju secret API (`model.get_secret`) or a configuration provider.
5. **Never** use global variables to maintain application state. Use classes,
   dependency injection, or functional state passing.
6. **Never** use f-strings, `.format()`, or `%` interpolation inside
   `logger.*()` calls. Always use `%s`-style deferred parameter substitution.
