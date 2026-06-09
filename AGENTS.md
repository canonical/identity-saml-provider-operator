# AI Agent Instructions - Identity SAML Provider Operator

## 1. Core Guardrails & System Constraints

### 🚫 Absolute Restrictions

- **Do Not Edit Vendored Libraries:** All files under `lib/charms/` are upstream
  libraries fetched via Charmcraft. **Never** modify them by hand. If updates
  are needed, instruct the user to run `charmcraft fetch-lib`.
- **Single Source of Truth for Config:** Linter, formatter, and tool settings
  must reside exclusively in `pyproject.toml`. Do not duplicate or create
  isolated configurations in separate files.

### ⚠️ Required File Headers

Every new or modified Python file must begin with the following exact copyright
header as the very first lines of the file:

```python
# Copyright 2026 Canonical Ltd.
```

*(Note: This rule is strictly validated by the ruff `CPY` rule. Do not skip
it).*

### 📋 Mandatory Verification Loop

Whenever you create, refactor, or touch any Python source code:

1. You must immediately execute or instruct the user to execute the verification
   suite: `tox`.
2. Do not mark a task as complete if any warnings, formatting failures, or unit
   test regressions are present.

---

## 2. Project Layout & Framework Constraints

The project follows the Canonical **ops** (Charmed Operator Framework) targeting
**Juju ≥ 3.6 on Kubernetes**.

- `src/` — Operator source directory. `src/charm.py` is the absolute entrypoint.
- `lib/charms/` — Strict read-only vendored charm libraries.
- `templates/` — Jinja2 template ecosystem for Traefik routing configuration
  blocks.
- `terraform/` — Companion Terraform module infrastructure for deploying the
  charm bundle.

---

## 3. Development Commands & Playbook

### Task Reference Matrix

Use **tox** as the orchestrator for all local execution blocks. Dependencies are
bound inside `requirements.txt` and relative `*-requirements.txt` manifests.

| Task Category | Execution Command |
| --- | --- |
| **Format Code** | `tox -e fmt` |
| **Lint Check** | `tox -e lint` |
| **Unit Testing** | `tox -e unit` |
| **Integration Testing** | `tox -e integration` |
| **Complete Verification Loop** | `tox` |
| **Spawn Dev Environment** | `tox devenv .venv && source .venv/bin/activate` |
| **Compile & Pack Charm** | `charmcraft pack -v` |

### External Documentation Mapping

Before changing integration or metadata blocks, read these local tracking
matrices:

- Architecture deep-dive: See `AGENTS.ARCHITECTURE.md`
- Implementation design reference: See `AGENTS.DESIGN.md`
- Python style & code conventions: See `AGENTS.STYLE.md`
- Testing conventions and framework usage: See `AGENTS.TESTING.md`
- Setup & testing parameters: See `CONTRIBUTING.md`
- Metadata & Juju relations schema: See `charmcraft.yaml`
