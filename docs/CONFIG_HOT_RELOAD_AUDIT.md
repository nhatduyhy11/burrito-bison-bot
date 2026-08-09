# Config and Hot Reload Audit

Date: 2026-08-09

## Summary

The runner has hot reload for the Python modules used by newly started flows.
With `--dev-reload`, the runner reloads the relevant modules before starting
`Shift+1`, `Shift+2`, `Shift+3`, `Shift+7`, or `Shift+9`.

For `Shift+2` and `Shift+3`, the runner reloads:

- `hauntedroom.core.vision`
- `hauntedroom.core.template`
- `hauntedroom.actions.loader`
- `hauntedroom.actions.runner`
- `hauntedroom.control_events.new_tab_blocker`
- `hauntedroom.control_events.blockers`
- `hauntedroom.flows.automap_support.boss_detector`
- `hauntedroom.flows.automap_support.detectors`
- `hauntedroom.flows.automap_support.boss_action`
- `hauntedroom.flows.automap_support.gear_action`
- `hauntedroom.flows.automap_support.hero_levelup`
- `hauntedroom.flows.automap_support.map_completion`
- `hauntedroom.flows.automap_support.upgrade_action`
- `hauntedroom.flows.automap_support.hero_action`
- `hauntedroom.flows.automap_support.boss_flow`
- `hauntedroom.flows.automap`

The browser process, Playwright context, current page, hotkey bindings, parsed
CLI arguments, and injected page scripts are not recreated. A flow object that is
already running also keeps the templates and config it loaded at construction.
For `Shift+1` and `Shift+3`, the action JSON file is reloaded before the flow
starts.

The project currently does not use environment variables for runtime config. A
repo scan found no `os.environ`, `os.getenv`, `process.env`, or `dotenv` usage,
and no project `.env` file outside `.venv`.

## Hot Reload Scope

Hot reload is implemented in `tools/hauntedroom_runner.py`:

- `get_automap_flow(dev_reload=True)` reloads action support, the auto-map
  support modules, and the auto-map module.
- `get_action_runner(dev_reload=True)` reloads JSON action support for
  `Shift+1`.
- `get_click_loop_flow(dev_reload=True)` and `get_research_flow(dev_reload=True)`
  reload their flow modules for `Shift+7` and `Shift+9`.
- Reload functions are called only when a new flow is started.
- `Shift+0` is still required to stop the old flow before the new code is used.

Important consequence: while `Shift+3` start-auto loop is running, it keeps the
same `automap_flow` function reference for all map iterations in that loop. Code
changes during that loop are not picked up until the loop is stopped and started
again. Action JSON changes are also picked up only when `Shift+3` is started,
not between maps inside an already running start-auto loop.

## Hot Reloadable Constants

These constants affect newly started flows after `Shift+0` and then the relevant
hotkey, assuming the runner was started with `--dev-reload`.

| Area | File | Constants / config | Notes |
| --- | --- | --- | --- |
| Auto-map coordinator/templates | `tools/hauntedroom/flows/automap.py` | `*_TEMPLATE_PATH`, `AUTOMAP_TEMPLATE_DIR`, `ROOM_TEMPLATE_DIR`, `BOSS_TEMPLATE_DIR`, `AUTOMAP_TEMPLATE_THRESHOLD`, `AutomapConfig` | New flow loads templates in `AutomapFlow.__init__`. Running flow keeps old loaded images. Phase constants imported from support modules are re-exported here for compatibility. |
| Map completion | `tools/hauntedroom/flows/automap_support/map_completion.py` | `MAP_END_*`, `WIN_REWARD_*`, `REWARD_LIST_TITLE_*`, `START_HOME_TEMPLATE_THRESHOLD` | Explicitly reloaded before `automap`; newly started auto-map imports the refreshed constants/functions. |
| Upgrade/build actions | `tools/hauntedroom/flows/automap_support/upgrade_action.py` | `BUILT_TEMPLATE_THRESHOLD`, `AUTOMAP_POLL_MS`, `AUTOMAP_ACTION_DELAY_MS`, `LV_SPIN_*`, `UPGRADE_CONFIRM_CLICK` | Explicitly reloaded before `automap`; newly started auto-map imports the refreshed constants/functions. |
| Boss detectors | `tools/hauntedroom/flows/automap_support/boss_detector.py` | `BOSS_HP_*`, `BOSS_PROGRESS_*`, `PET_READY_REGION`, `SPELL_READY_REGION` | Explicitly reloaded before `automap`. |
| Boss flow policy | `tools/hauntedroom/flows/automap_support/boss_flow.py` | `EXIT_CLICK_TEMPLATE_THRESHOLD`, boss handoff/deploy orchestration | Explicitly reloaded before `automap`. |
| Small auto-map detectors | `tools/hauntedroom/flows/automap_support/detectors.py` | `BUILD_BUTTON_*`, `HERO_LEVELUP_PRICE_REGION`, `WHITE_*` | Explicitly reloaded before `automap`. |
| Boss actions | `tools/hauntedroom/flows/automap_support/boss_action.py` | pet/spell template paths, action positions, delays, thresholds | Explicitly reloaded before `automap`. |
| Hero level-up | `tools/hauntedroom/flows/automap_support/hero_levelup.py` | search regions, thresholds, priorities, template directory/glob | Explicitly reloaded before `automap`. Adding/removing PNGs is picked up on reload because `HERO_LEVELUP_TEMPLATE_PATHS` is rebuilt. |
| Hero level-up action | `tools/hauntedroom/flows/automap_support/hero_action.py` | `HERO_LEVELUP_OPEN_CLICK`, `HERO_LEVELUP_OPTION_*`, `HERO_LEVELUP_SELECTION_SETTLE_MS`, fallback screenshot path | Explicitly reloaded before `automap`. |
| Gear placement | `tools/hauntedroom/flows/automap_support/gear_action.py` | gear regions, HSV thresholds, drag timings, drop offsets | Explicitly reloaded before `automap`. |
| Core template matching for auto-map | `tools/hauntedroom/core/template.py` | `DEFAULT_TEMPLATE_THRESHOLD`, `TEMPLATE_SCALES`, matching functions | Explicitly reloaded. Auto-map sees updated imports after `automap` is reloaded. |
| Core vision for auto-map | `tools/hauntedroom/core/vision.py` | screenshot capture, generic OpenCV region helpers | Explicitly reloaded. Auto-map sees updated imports after `automap` is reloaded. |
| Action loader/runner | `tools/hauntedroom/actions/*.py` | action defaults, loader validation, runner behavior | Reloaded for `Shift+1`, and before `Shift+2`/`Shift+3` so entry actions use the new runner. |
| Blocker fallback Python code | `tools/hauntedroom/control_events/*.py` | blocker fallback behavior, popup host/path used by Python fallback | Reloaded for action flows. Already injected JavaScript guards are not re-injected. |
| Research flow | `tools/hauntedroom/flows/research.py` | research templates, threshold, scale, poll/miss counts | Reloaded when `Shift+9` starts. |
| Fixed click loop | `tools/hauntedroom/flows/click_loop.py` | `CLICK_POSITION`, `CLICK_INTERVAL_MS` | Reloaded when `Shift+7` starts. |
| Top-level auto-map settings | `tools/hauntedroom/settings.py` | `CAPTURE_HERO_FALLBACK_SCREENSHOTS`, `CLICK_EXIT_ON_BOSS` | Reloaded before auto-map support modules when `Shift+2`/`Shift+3` starts with `--dev-reload`. |

## Boot-Only / Env-Like Runtime Config

These behave like boot-time config. Changing source or JSON while the runner is
open will not affect the active process unless it is restarted, except where
noted.

| Area | File | Constants / config | Why boot-only |
| --- | --- | --- | --- |
| CLI defaults | `tools/hauntedroom/core/cli.py` | `GAME_URL`, `DEFAULT_VIEWPORT_WIDTH`, `DEFAULT_VIEWPORT_HEIGHT`, `DEFAULT_BROWSER`, `DEFAULT_PROFILE_DIR` | Parsed once in `prepare_runner()`. |
| CLI args | command line | `--actions`, `--profile`, `--url`, `--headless`, `--browser`, `--width`, `--height`, `--keep-open`, `--dev-reload`, `--debug` | `argparse` runs once. Browser/context choices cannot be changed without relaunch. |
| Browser launch | `tools/hauntedroom_runner.py` | `launch_options`, persistent context | Created once in `main()`. Viewport, channel, profile, headless are fixed for that context. |
| Action file path | command line | `--actions` | The selected file path is parsed once. In dev reload mode, that same file is re-read before `Shift+1` and `Shift+3`. |
| Injected page guards | `tools/hauntedroom/settings.py`, `tools/hauntedroom/control_events/new_tab_blocker.py` | `ENABLE_SCRIPT_INJECTION`, profile popup guard script, iframe guard script and delay | `ENABLE_SCRIPT_INJECTION` is effectively startup-only because scripts already injected into the page are not replaced without explicit reinjection or page restart. |
| Runtime globals | `tools/hauntedroom/core/runtime.py` | `ACTION_LOOP_COUNT`, `COUNTDOWN_WAIT_THRESHOLD_MS`, screenshot dirs, `HOTKEY_SCRIPT` | Imported at process startup; hotkey script is injected once. |
| Runner-level constants | `tools/hauntedroom_runner.py` | `START_BATTLE_TEMPLATE_NAME`, `BETWEEN_MAPS_WAIT_MS`, command mapping | Entrypoint module is not reloaded. |

Template PNG contents are a partial exception. `run_actions()` loads template
images at the start of each action-flow run, and `AutomapFlow.__init__` loads
auto-map templates at the start of each auto-map run. Replacing a PNG can affect
a newly started flow without restarting the whole runner, but not an already
running flow.

## Import and Constant Placement Audit

Checked patterns:

- Indented imports: `rg -n "^\s+(import|from)\s+" tools tests ref_cv --glob '*.py'`
- Indented uppercase assignments: `rg -n "^\s+[A-Z][A-Z0-9_]+\s*=" tools tests ref_cv --glob '*.py'`
- Top-level ordering in the Haunted Room runner package.

Findings:

- No indented imports were found in `tools/`.
- No UPPERCASE constant assignments were found inside functions/classes in
  `tools/`, `tests`, or `ref_cv`.
- Top-level imports and constants in `tools/hauntedroom_runner.py` and
  `tools/hauntedroom/**/*.py` are placed before functions/classes.
- The only indented imports found are in tests:
  - `tests/runner/test_standby_controller.py`: imports inside tests that patch
    or assert reload behavior.
  - `tests/automap/test_boss.py`: local import of `find_template` inside one
    test.

Those test-local imports are acceptable, but if the goal is strict consistency,
they can be moved to module top level after verifying patch/import ordering.

## Should Be Environment Variables?

Recommended as CLI options first, with optional env fallback only if the runner
is used from scripts or multiple machines:

- Game URL.
- Browser channel.
- Headless mode.
- Viewport width/height.
- Persistent profile directory.
- Action file path.

Keep in code or versioned JSON, not env:

- OpenCV thresholds.
- HSV color thresholds.
- Search regions and fixed click coordinates.
- Template paths inside the repo.
- Hero level-up priority order.
- Action sequence and blocker priority.
- Timing values that are part of flow behavior.

Reasoning: these values are domain tuning tied to captured fixtures and tests.
Keeping them in code or versioned JSON makes changes reviewable and reproducible.
Environment variables are better for machine/session concerns, secrets, and
deployment differences. This project has no secrets and is primarily local
automation, so env should stay minimal.

## Potential Improvements

1. Re-inject page guards during dev reload if JavaScript guard changes need to
   take effect without restarting or navigating the page.
2. Consider reloading `core.runtime` only after separating boot-only injected
   scripts/classes from reloadable helper functions. Reloading it wholesale would
   create multiple `FlowControl` class identities in one process.
3. Consider moving boot-time machine config to CLI/env fallback only if there is a
   real need to run the same code on multiple local setups without changing the
   command line.
