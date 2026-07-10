# Legacy `requirements.txt` Archive

This document records the dependency cleanup performed when migrating the project
from a stale `requirements.txt` (2017-era pinned versions) to a modern
`pyproject.toml` + `uv` workflow.

## Original `requirements.txt`

```
cycler==0.10.0
matplotlib==2.1.2
mss==3.1.2
nose==1.3.7
pkg-resources==0.0.0
pynput==1.3.9
python-dateutil==2.6.1
python-xlib==0.21
pytz==2017.3
```

## Dropped packages and why

| Package | Why dropped |
| --- | --- |
| `matplotlib` | **Not imported anywhere** in the code. It was never used. |
| `cycler`, `python-dateutil`, `pytz` | These are **transitive dependencies of matplotlib**. They only appeared because someone ran `pip freeze` and dumped everything. Useless without matplotlib. |
| `nose` | A test runner that's been **abandoned since 2015** (breaks on Python 3.10+). The tests use the stdlib `unittest`, not nose. |
| `python-xlib` | A **Linux-only** transitive dep of `pynput` (its X11 backend). On Windows it's irrelevant, and on Linux the resolver pulls it automatically — so it shouldn't be a *direct* dependency. |
| `pkg-resources` | **Phantom entry.** `pkg_resources` is a module that ships *inside* `setuptools`, not a standalone package. The `0.0.0` is a known `pip freeze` artifact — not installable, meaningless. |

The dropped packages were verified by grepping imports across `main.py`,
`vision.py`, `game.py`, `controller.py`, and `tests/` — none of them are imported.

## Kept dependencies (the actually-imported ones)

- `opencv-python` — `cv2`, used everywhere.
- `numpy` — imported directly in `main.py`, `game.py`, `vision.py`.
- `mss` — screen capture in `vision.py`.
- `pynput` — mouse control in `controller.py`.
- `pillow` — `from PIL import Image` in `vision.py`.

## Notes

- The old `requirements.txt` was actually **missing two real dependencies**:
  `opencv-python` (which the old README installed globally) and `pillow`
  (imported but unlisted — it must have been pulled in transitively back then).
  Both are now listed explicitly.
- The kept packages were upgraded from 2017-era pins to modern versions:
  `mss` 3.1.2 → 10.2.0, `pynput` 1.3.9 → 1.8.2.
- Exact versions are now pinned in `uv.lock` for reproducibility. The old pinned
  versions would not install on Python 3.12.

## Removal of `requirements.txt`

After the cleanup above, the project switched to `pyproject.toml` + `uv.lock` as
the single source of truth, and `requirements.txt` was deleted.

`pip` can read the dependencies straight from `pyproject.toml` via `pip install .`
— but **only when a `[build-system]` is declared**. The project therefore adds:

```toml
[build-system]
requires = ["setuptools>=61"]
build-backend = "setuptools.build_meta"

[tool.setuptools]
py-modules = []
```

This was verified: `pip install .` in a clean virtual environment installed the
same five dependencies (`opencv-python`, `numpy`, `mss`, `pillow`, `pynput`) that
`uv sync` does.

Because both tools now read from `pyproject.toml`, keeping a separate
`requirements.txt` would be a second source of truth prone to drift. It was
removed; `pyproject.toml` and `uv.lock` are committed instead. The original
contents are preserved at the top of this file.
