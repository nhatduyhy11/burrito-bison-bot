# Config and Hot Reload Audit

Date: 2026-08-15

## Summary

The runner has hot reload for the Python modules used by newly started flows.
With `--dev-reload`, it refreshes the relevant modules when `Shift+1`,
`Shift+T`, or `Shift+5` starts a flow.

For `Shift+2`, `Shift+3`, and `Shift+4`, the runner reloads:

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
- `hauntedroom.flows.automap_support.hero_levelup_vision`
- `hauntedroom.flows.automap_support.map.model_state`
- `hauntedroom.flows.automap_support.map.first_win`
- `hauntedroom.flows.automap_support.map.reward`
- `hauntedroom.flows.automap_support.map.blocker`
- `hauntedroom.flows.automap_support.map.lifecycle`
- `hauntedroom.flows.automap_support.upgrade_action`
- `hauntedroom.flows.automap_support.hero_action`
- `hauntedroom.flows.automap_support.boss_flow`
- `hauntedroom.flows.automap`

The browser process, Playwright context, current page, hotkey bindings, parsed
CLI arguments, and injected page scripts are not recreated. A flow object that is
already running also keeps the templates and config it loaded at construction.
Action JSON is not loaded at process startup and is not used by screen-dispatched
`Shift+1` flows or train. It is loaded each time the direct `Shift+5` JSON action
loop starts, even without `--dev-reload`.

The project currently does not use environment variables for runtime config. A
repo scan found no `os.environ`, `os.getenv`, `process.env`, or `dotenv` usage,
and no project `.env` file outside `.venv`.

## Hot Reload Scope

Hot reload is implemented in `tools/hauntedroom/runner/reload.py` and wired into
the default command table by `tools/hauntedroom/runner/default_commands.py`:

- `get_automap_flow(dev_reload=True)` reloads action support, the auto-map
  support modules, and the auto-map module.
- `get_action_runner(dev_reload=True)` reloads JSON action support for the
  direct `Shift+5` action loop and supplies the typed-action runner used by the
  fixed Python start-auto entry sequence.
- `get_automap_runtime(dev_reload=True)` returns both the refreshed auto-map flow
  and action runner for `Shift+2`, `Shift+3`, and `Shift+4`. The default
  `Shift+3` command passes that action runner into
  `flows.start_auto.run_start_automap_loop()`, while `Shift+4` passes the
  refreshed auto-map callable into the train flow.
- `get_train_flow(dev_reload=True)` reloads `automap_support/train_select.py`
  followed by `flows/train.py` for `Shift+4`.
- `get_exp_available_flow(dev_reload=True)` and
  `get_hero_up_available_flow(dev_reload=True)` reload their detector/flow
  modules for `Shift+5` and `Shift+6`.
- `get_research_flow(dev_reload=True)` reloads the research flow module.
- Reload functions are called only when a new flow is started.
- `Shift+0` is still required to stop the old flow before the new code is used.

Important consequence: while a start-auto loop is running, it keeps the
same `automap_flow` function reference for all map iterations in that loop. Code
changes during that loop are not picked up until the loop is stopped and started
again. Action JSON changes are picked up the next time `Shift+5` starts.

## Hot Reloadable Constants

These constants affect newly started flows after `Shift+0` and then the relevant
hotkey, assuming the runner was started with `--dev-reload`.

| Area | File | Constants / config | Notes |
| --- | --- | --- | --- |
| Auto-map coordinator/templates | `tools/hauntedroom/flows/automap.py` | `*_TEMPLATE_PATH`, `AUTOMAP_TEMPLATE_DIR`, `ROOM_TEMPLATE_DIR`, `BOSS_TEMPLATE_DIR`, `AUTOMAP_TEMPLATE_THRESHOLD`, `AutomapConfig` | New flow loads templates in `AutomapFlow.__init__`. Running flow keeps old loaded images. Phase constants imported from support modules are re-exported here for compatibility. |
| Daily first win | `tools/hauntedroom/flows/automap_support/map/first_win.py` | `DAILY_FIRST_WIN_*`, prompt/checkbox handlers | Reloaded before `map/lifecycle.py`; owns the daily-first-win branch. |
| Map reward | `tools/hauntedroom/flows/automap_support/map/reward.py` | `WIN_REWARD_*`, `REWARD_LIST_TITLE_*` | Reloaded before `map/lifecycle.py`; owns reward popup, reward-list and fallback clicks. |
| Map blocker | `tools/hauntedroom/flows/automap_support/map/blocker.py` | `MAP_BLOCKER_*`, blocker detector/handler | Reloaded before `map/lifecycle.py`; owns blocker matching and cleanup. |
| Map lifecycle | `tools/hauntedroom/flows/automap_support/map/lifecycle.py`, `map/model_state.py` | `MAP_END_*`, `START_HOME_TEMPLATE_THRESHOLD`, runtime contexts and shared map state | Model and helper modules are reloaded before lifecycle, then scheduler and public facade. |
| Upgrade/build actions | `tools/hauntedroom/flows/automap_support/upgrade_action.py` | `BUILT_TEMPLATE_THRESHOLD`, `AUTOMAP_POLL_MS`, `AUTOMAP_ACTION_DELAY_MS`, `LV_SPIN_*`, `UPGRADE_CONFIRM_CLICK` | Explicitly reloaded before `automap`; newly started auto-map imports the refreshed constants/functions. |
| Boss detectors | `tools/hauntedroom/flows/automap_support/vision/boss_hp.py`, `tools/hauntedroom/flows/automap_support/vision/boss_progress.py`, `tools/hauntedroom/flows/automap_support/vision/boss_controls.py` | `BOSS_HP_*`, `BOSS_PROGRESS_*`, pet/spell ready regions and color-component patterns | Explicitly reloaded before `automap`. |
| Boss flow policy | `tools/hauntedroom/flows/automap_support/boss_flow.py` | `EXIT_CLICK_TEMPLATE_THRESHOLD`, manual boss pause/deploy orchestration | Explicitly reloaded before `automap`. |
| Small auto-map detectors | `tools/hauntedroom/flows/automap_support/detectors.py` | `BUILD_BUTTON_*`, `HERO_LEVELUP_PRICE_REGION`, `WHITE_*` | Explicitly reloaded before `automap`. |
| Boss actions | `tools/hauntedroom/flows/automap_support/boss_action.py` | pet summon template path, ready-bar click offset, spell position, delays, thresholds | Explicitly reloaded before `automap`. |
| Hero level-up vision | `tools/hauntedroom/flows/automap_support/hero_levelup_vision.py` | template directory/glob, match calibration, search regions, HSV thresholds, visual queries | Explicitly reloaded before `automap`; action controls query order and selection priority. Adding/removing PNGs is picked up because `HERO_LEVELUP_TEMPLATE_PATHS` is rebuilt. |
| Hero level-up action | `tools/hauntedroom/flows/automap_support/hero_action.py` | selection priority, `HERO_LEVELUP_OPEN_CLICK`, `HERO_LEVELUP_OPTION_*`, `HERO_LEVELUP_SELECTION_SETTLE_MS`, fallback live-screenshot gate | Explicitly reloaded before `automap`. |
| Gear placement | `tools/hauntedroom/flows/automap_support/gear_action.py` | gear regions, HSV thresholds, drag timings, drop offsets | Explicitly reloaded before `automap`. |
| Core template matching for auto-map | `tools/hauntedroom/core/template.py` | `DEFAULT_TEMPLATE_THRESHOLD`, `TEMPLATE_SCALES`, matching functions | Explicitly reloaded. Auto-map sees updated imports after `automap` is reloaded. |
| Core vision for auto-map | `tools/hauntedroom/core/vision.py` | screenshot capture, generic OpenCV region helpers | Explicitly reloaded. Auto-map sees updated imports after `automap` is reloaded. |
| Action loader/runner | `tools/hauntedroom/actions/*.py` | action defaults, loader validation, runner behavior | Reloaded for `Shift+1`, and before `Shift+2`/`Shift+3`/`Shift+4`; start-auto and train receive the refreshed dependencies through the command resolver. |
| Blocker fallback Python code | `tools/hauntedroom/control_events/*.py` | blocker fallback behavior, popup host/path used by Python fallback | Reloaded for action flows. Already injected JavaScript guards are not re-injected. |
| Research flow | `tools/hauntedroom/flows/research.py` | research templates, threshold, scale, poll/miss counts | Reloaded when `Shift+9` starts. |
| Train flow | `tools/hauntedroom/flows/train.py`, `tools/hauntedroom/flows/automap_support/train_select.py` | availability/button detector, selection matcher, click positions and delays | Reloaded when `Shift+4` starts; its auto-map dependency is refreshed separately by `get_automap_runtime()`. |
| EXP available flow | `tools/hauntedroom/flows/exp_available.py` | EXP badge color/slot detector and click delay | Reloaded when `Shift+5` starts. |
| Hero breakthrough flow | `tools/hauntedroom/flows/hero_up_available.py` | yellow popup button plus red `!` availability detector, click positions and delays | Reloaded when `Shift+6` starts. |
| JSON action loop | `tools/json_macro/macro.env.json` or `--actions` | action sequence and timing | Loaded every time `Shift+5` starts. |
| Top-level auto-map settings | `tools/hauntedroom/settings.py` | `CAPTURE_HERO_FALLBACK_SCREENSHOTS`, `START_AUTO_HOTKEYS` | Reloaded before auto-map support modules when `Shift+2`/`Shift+3` starts with `--dev-reload`. |

## Boot-Only / Env-Like Runtime Config

These behave like boot-time config. Changing source or JSON while the runner is
open will not affect the active process unless it is restarted, except where
noted.

| Area | File | Constants / config | Why boot-only |
| --- | --- | --- | --- |
| CLI defaults | `tools/hauntedroom/core/cli.py` | `GAME_URL`, `DEFAULT_VIEWPORT_WIDTH`, `DEFAULT_VIEWPORT_HEIGHT`, `DEFAULT_BROWSER`, `DEFAULT_PROFILE_DIR` | Parsed once in `prepare_runner()`. |
| CLI args | command line | `--actions`, `--profile`, `--url`, `--headless`, `--browser`, `--width`, `--height`, `--keep-open`, `--dev-reload`, `--debug` | `argparse` runs once. Browser/context choices cannot be changed without relaunch. |
| Browser launch | `tools/hauntedroom_runner.py` | `launch_options`, persistent context, blocked service workers | Created once in `main()`. Viewport, channel, profile, headless, and service-worker policy are fixed for that context. |
| Startup navigation | `tools/hauntedroom/runner/navigation.py` | `NAVIGATION_ATTEMPTS`, `NAVIGATION_TIMEOUT_MS`, `NAVIGATION_RETRY_DELAY_SECONDS` | Read when the process starts and used only for the initial game navigation. Changing them requires relaunch. |
| Action file path | command line | `--actions` | The selected path is parsed every time `Shift+5` starts; it is not read at startup. |
| Injected page guards | `tools/hauntedroom/settings.py`, `tools/hauntedroom/control_events/new_tab_blocker.py` | `ENABLE_SCRIPT_INJECTION`, profile popup guard script, iframe guard script and delay | `ENABLE_SCRIPT_INJECTION` is effectively startup-only because scripts already injected into the page are not replaced without explicit reinjection or page restart. |
| Runtime globals | `tools/hauntedroom/core/runtime.py` | `ACTION_LOOP_COUNT`, `COUNTDOWN_WAIT_THRESHOLD_MS`, screenshot dirs, `HOTKEY_SCRIPT` | Imported at process startup; hotkey script is injected once. |
| Runner entrypoint | `tools/hauntedroom_runner.py` | browser `launch_options`, composition of standby/action mode | Entrypoint module is not reloaded. |
| Start-auto wrapper constants | `tools/hauntedroom/flows/start_auto.py` | `START_BATTLE_TEMPLATE_NAME`, `BETWEEN_MAPS_WAIT_MS` | Module is imported once. Changing these requires process restart unless explicit reload support is added. |
| Command spec factory | `tools/hauntedroom/runner/commands.py` | `FlowCommand`, resolver factory functions, menu labels | Module is imported once. Adding/removing hotkeys requires process restart. |
| Default command wiring | `tools/hauntedroom/runner/default_commands.py` | `FLOW_COMMANDS`, default reload/start-auto dependencies | Module is imported once. Adding/removing hotkeys requires process restart. |

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
  - `tests/runner/test_reload.py`: imports inside tests that patch
    or assert reload behavior across `runner/reload.py` and its module graph.
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
