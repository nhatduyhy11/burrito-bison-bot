# Test Command & Setup Reference

This document explains how the Burrito Bison Bot test suite is run, what each
part of the command does, and why certain forms work while others don't.

## Running the tests

```bash
uv run -m unittest discover -s tests -v
```

All 9 tests pass as of this writing. They are **offline** — they match templates
against saved screenshots and never touch live screen capture.

## Command breakdown

```
uv run  -m unittest  discover  -s tests  -v
```

| Part | Meaning |
| --- | --- |
| `uv run` | Run the following in the project's `.venv` (correct Python + installed deps). |
| `-m unittest` | uv's `--module` flag: run the stdlib `unittest` **module** as the test runner, using the project interpreter. |
| `discover` | Auto-find test files instead of naming them by hand. |
| `-s tests` | `--start-directory tests` — start discovery in the `tests/` folder. |
| `-v` | Verbose — print each test name and its result. |

Discovery looks for files matching the default pattern `test*.py`, so it finds
`tests/test_vision.py`, imports it, and runs every method beginning with `test_`.

## Can `python` be dropped?

Yes — when using `-m`. `uv` provides its own `--module` (`-m`) flag, so the
explicit `python` interpreter is redundant.

| Form | Works? | Notes |
| --- | --- | --- |
| `uv run -m unittest discover -s tests -v` | Yes | uv runs the module in `.venv`. **Recommended.** |
| `uv run python -m unittest discover -s tests -v` | Yes | Identical result; `python` is redundant. |
| `uv run unittest discover -s tests -v` | **No** | `unittest` is a *module*, not an executable on `PATH` → `Failed to spawn: unittest`. |

### How this differs from `uv run main.py`

- `uv run main.py` — the argument is a **`.py` file path**. uv detects the
  extension and runs the file with the project interpreter (no `python` needed).
- `uv run -m unittest` — the argument is a **module name**, not a file. uv's
  `-m` flag is what runs it (equivalent to `python -m unittest`).

So: for files use `uv run <file>.py`; for modules use `uv run -m <module>`.

## Useful variants

- Drop `-v` for terse output (one dot per test).
- `-k name` — run only tests matching a name:
  `uv run -m unittest discover -s tests -v -k rocket` → runs `test_finds_full_rocket`.
- `-p 'test_*.py'` — change the filename discovery pattern (default already `test*.py`).

## What the suite covers

- **One module:** `tests/test_vision.py` (9 tests) using stdlib `unittest`.
- `tests/__init__.py` is empty (package marker).
- Each test pairs a screenshot in `tests/screens/` with a template in `assets/`
  and asserts `Vision.find_template` locates it.
- Because these tests pass, the template images and matching logic are healthy;
  any live "detects nothing" problem lies in the runtime screen-capture path
  (capture region, resolution/scaling, window placement) — not in the vision code.
