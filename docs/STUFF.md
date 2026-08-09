# Stuff

## Cleanup: unused imports

This is housekeeping and is not relevant to the main runtime logic.

Scan unused Python imports with Ruff's `F401` rule.

`F401` means an imported module, object, or symbol is not used anywhere in
that file. Ruff inherits this rule code from Pyflakes.

```bash
UV_CACHE_DIR=.uv-cache uvx ruff check . --select F401
```

Auto-remove them:

```bash
UV_CACHE_DIR=.uv-cache uvx ruff check . --select F401 --fix
```

Current scan found unused imports in:

- `ref_cv/main.py`
- `ref_cv/tests/test_vision.py`
- `ref_cv/vision.py`
- `tools/hauntedroom/flows/automap.py`
- `tools/hauntedroom/flows/automap_support/boss_action.py`
- `tools/hauntedroom/runner/reload.py`
