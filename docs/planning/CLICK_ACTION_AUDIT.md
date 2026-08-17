# Click Action Audit

Audit date: 2026-08-17

## Scope

This audit covers runtime click behavior under `tools/hauntedroom`, plus the
declarative examples in `tools/hauntedroom_actions.sample.json` and
`tools/macro_record.json`. Tests, `ref_cv`, generated browser-profile data and
fixtures are excluded.

The main question is whether the recurring `click -> wait X` sequence should
become a shared helper. No runtime behavior is changed by this document.

## Executive summary

There is a real recurring pattern, but it currently represents several
different contracts:

1. **Bot click only**: suppress click recording, then issue a Playwright click.
2. **Click then cancellable settle**: click, wait for UI animation, and stop the
   flow if the stop/pause control rejects continuation.
3. **Click then unconditional settle**: click and use raw
   `page.wait_for_timeout`; stop/pause is not checked.
4. **Wait then click**: deliberate pre-click delay, often followed by template
   detection rather than another fixed wait.
5. **Click then re-detect**: the wait is only part of a state-observation loop.

The safest first extraction is the lower-level **bot click** primitive. A
shared `click_and_wait` is viable for group 2, but should not absorb the other
contracts merely because their call sites look similar.

## Existing click primitives

| Location | Current behavior | Consumers / notes |
| --- | --- | --- |
| `flows/automap_support/boss_action.py:49` | Suppress next click log, then click `(x, y)` | De facto shared helper imported by auto-map, gear and train. Its ownership is misleading because the behavior is not boss-specific. |
| `flows/exp_available.py:26` | Local copy of suppress + click | Same behavior, independent signature. |
| `flows/hero_up_available.py:74` | Local copy accepting a position tuple | Same behavior, independent signature. |
| `actions/runner.py:128` and `:250` | Inline suppress + click with configurable mouse button | Used by coordinate and template actions. |
| `control_events/blockers.py:65` | Inline suppress + click | Used while clearing overlays. |
| `flows/research.py:86` and `:139` | Inline suppress + click | Duplicated twice in one flow. |
| `flows/click_loop.py:10` | Raw click without suppression | The Shift+7 loop may be intentionally treated differently, but this should be explicit. |

The suppression expression itself appears in multiple runtime files:

```javascript
() => { window.__hauntedRoomSuppressNextClickLog = true; }
```

This duplication is independent of the wait question and is already enough to
justify a reusable `bot_click`/`click` primitive in `core/mouse.py`.

## Click followed by a fixed settle wait

### Stop/pause-aware waits

These call sites use `wait_for_flow_timeout` (or an injected equivalent) and
branch on its boolean result where continuation matters.

| Flow | Click | Wait | Result handling |
| --- | --- | --- | --- |
| Clear blockers | `control_events/blockers.py:68` | `poll_ms` at `:69` | Returns `False` when stopped; resets the blocker deadline after a successful cycle. There is also a separate pre-click `delay_ms`. |
| Boss pet menu | `automap_support/boss_action.py:119` | `PET_MENU_RECHECK_MS = 300` | Breaks the retry loop when stopped, otherwise captures and detects the active summon button. |
| EXP badges | `flows/exp_available.py:125` | Default `800 ms` at `:126` | Returns `False` when stopped, then captures again on the next loop. |
| Hero change arrow | `flows/hero_up_available.py:101` | Default `2000 ms` at `:107` | Returns `False` when stopped, then verifies the next hero. |
| Breakthrough first click | `flows/hero_up_available.py:131` | Default `800 ms` at `:132` | Returns `False` when stopped, then performs the second click. |
| Breakthrough second click | `flows/hero_up_available.py:139` | Default `1000 ms` at `:140` | Returns `False` when stopped, then re-detects availability. |
| Train challenge | `flows/train.py:127` | `TRAIN_ENTRY_SETTLE_MS = 2000` | Returns `False` when stopped, then waits for the start-battle template. |
| Train start battle | `flows/train.py:153` | `TRAIN_BATTLE_LOAD_MS = 5000` | Returns `False` when stopped, then enters hero selection. |
| Train selection | `flows/train.py:196` | `TRAIN_SELECTION_SETTLE_MS = 600` | Returns `False` when stopped, then captures the next selection state. |
| Hero picker open | `automap_support/hero_action.py:185` | `HERO_LEVELUP_OPTION_SETTLE_MS = 1500` | Returns a handled outcome when stopped. The wait protects against picker animation. |
| Hero option select | `automap_support/hero_action.py:222`, `:248` | `HERO_LEVELUP_SELECTION_SETTLE_MS = 600` | Return value is currently ignored; the handler returns handled either way. |
| Level-spin interrupt | `automap_support/upgrade_action.py:53` | `AUTOMAP_POLL_MS = 600` | Return value is ignored; the handler returns `True`. |
| Completion blocker | `completion_flow/blocker.py:57` | Auto-map `poll_ms` (currently `600`) | Converts the boolean to `CONTINUE` or `STOP`. |
| First-win checkbox | `completion_flow/first_win.py:122` | `DAILY_FIRST_WIN_CHECK_DELAY_MS = 1000` | Returns `False` when stopped, then captures checkbox state again. |
| Win reward | `completion_flow/reward.py:64` | `WIN_REWARD_RECHECK_MS = 2000` | Converts the boolean to `CONTINUE` or `STOP`. |
| Reward-list title | `completion_flow/reward.py:96` | `WIN_REWARD_RECHECK_MS = 2000` | Converts the boolean to `CONTINUE` or `STOP`. |
| Reward fallback click | `completion_flow/reward.py:114` | `WIN_REWARD_RECHECK_MS = 2000` | Converts the boolean to `CONTINUE` or `STOP`. |

### Countdown waits

These use `wait_with_countdown`, which is also stop/pause-aware but adds log
output and splits long waits into short checkpoints.

| Flow | Sequence | Wait |
| --- | --- | --- |
| Level up | Click detected level at `upgrade_action.py:88`, then wait at `:89` | `AUTOMAP_ACTION_DELAY_MS = 800`; afterward capture and either handle level spin or click confirm. |
| Build structure | Click marker at `upgrade_action.py:133`, then wait at `:134` | `AUTOMAP_ACTION_DELAY_MS = 800`; afterward detect and click an available option. |

Although these waits are currently below the countdown threshold, their log
and cooperative-cancellation contract differs from a raw timeout.

### Raw Playwright waits

| Flow | Sequence | Risk / distinction |
| --- | --- | --- |
| Boss spell | Click spell at `boss_action.py:76`, raw wait `200 ms` at `:77`, click boss at `:78` | Short target-selection gesture; no stop/pause check between the two clicks. |
| Gear menu | Click gear button at `gear_action.py:164`, raw wait `1000 ms` at `:165` | Then capture and verify that the menu opened. |
| Gear placement | Smooth drag ending at `gear_action.py:185`, raw wait `800 ms` at `:195` | Interaction is drag rather than click, but the same settle concept applies. |
| Research available/active | Clicks at `research.py:89` and `:142`; the active loop waits `RESEARCH_POLL_MS = 600` before its next capture | Stop is checked after the raw wait, not through `FlowControl.checkpoint()`. |

These should not silently become cancellable or pause-aware as part of a
mechanical refactor; that would be a behavior change worth testing explicitly.

## Related patterns that are not `click -> wait`

### Wait before click

| Flow | Sequence |
| --- | --- |
| Template actions | `actions/runner.py:222` waits `delay_ms` before each click at `:251`. Repeat clicks optionally re-detect the template after waiting. |
| Clear blockers | `control_events/blockers.py:63` waits `delay_ms`, clicks, then separately waits `poll_ms`. |
| Research | `flows/research.py:77` and `:129` wait with countdown before clicking the detected target. |
| Reward follow-up | `completion_flow/reward.py:139` waits `3000 ms`, then clicks at `:147`; there is no post-click wait inside that handler. |

### Click with no local fixed wait

| Flow | Notes |
| --- | --- |
| Plain `ClickAction` | `actions/runner.py:129` returns immediately. A wait is a separate declarative action. |
| Boss exit handoff | `boss_flow.py:72` clicks and stops auto-map immediately. |
| Boss spell target / active pet summon | Final click returns immediately. |
| Map end | `automap.py:239` clicks, then enters the completion state machine and captures state. |
| First-win decline | `completion_flow/first_win.py:106` returns success immediately. |
| Level-up confirm / build option | Final click returns handled immediately. |

### Declarative files

- `tools/hauntedroom_actions.sample.json` mostly uses `click_template`. Its
  `delay_ms` is a **pre-click** delay, while the following template action acts
  as state-based synchronization.
- `tools/macro_record.json` contains eight literal `click` + `wait` pairs
  (`800`, `1000`, `1500`, or `30000 ms`). This is the clearest exact repetition,
  but keeping click and wait as separate action records is useful for recording,
  editing and replay visibility.

## Extraction options

### Option A: extract only `bot_click` now — recommended first step

```python
async def bot_click(
    page,
    position: tuple[int, int],
    *,
    button: str = "left",
) -> None:
    ...
```

Place it beside `smooth_drag` in `core/mouse.py`. It owns only input mechanics:
suppression of the click logger and the Playwright click. It does not know
about flow state or UI settle timing.

Benefits:

- removes the click-related copies of the suppression JavaScript (the gear
  drag suppression remains a separate gesture concern);
- removes the accidental dependency on boss-specific `click` from gear/train;
- remains usable by flows, action runner and control-event handlers;
- does not change cancellation or timing behavior.

### Option B: add a narrow `click_and_wait` after click normalization

A useful contract would be:

```python
async def click_and_wait(
    page,
    position: tuple[int, int],
    wait_ms: int,
    stop_event=None,
    *,
    button: str = "left",
) -> bool:
    """Bot-click, then cooperatively wait; return whether flow may continue."""
```

Only the stop/pause-aware rows in the first table are candidates. Callers must
still decide what `False` means (`return False`, `STOP`, `break`, or a handled
outcome), so the helper should return a boolean and never choose flow policy.

There is one architectural issue: `core/mouse.py` currently has no internal
dependencies, while cooperative waiting lives in `core/runtime.py`; the
architecture test requires every `core/*.py` module to have no
`hauntedroom.*` imports. Avoid solving this with duplicated wait logic or an
injected `wait_fn` parameter solely to satisfy the test.

If Option B is adopted, first choose one explicit boundary:

1. allow a small, directed dependency between core modules and place the
   composed helper in `core/interaction.py`; or
2. split flow control/timing out of the oversized `core/runtime.py` into a
   lower-level module, then let the interaction helper depend on it.

### Option C: add a declarative `click_wait` action — not recommended yet

This would only reduce alternating records in `macro_record.json`. It would
increase the action schema and loader/runner branches, while ordinary
`click` + `wait` remains clearer and more composable. Consider it only if
recording or authoring files becomes a concrete pain point.

## Recommendation

1. Extract and migrate `bot_click` first.
2. Preserve explicit `click` followed by `wait_for_flow_timeout` while the
   different return policies remain visible and small.
3. Normalize raw waits separately, with behavior tests, if pause/stop should be
   honored during boss spell, gear and research settle periods.
4. Re-audit after normalization. Add `click_and_wait` only if the remaining
   stop-aware pairs still create meaningful maintenance cost.

The repeated code is real, but most of the value comes from centralizing bot
click mechanics. Combining click and wait immediately would save one line at
many call sites while hiding distinctions that currently matter.
