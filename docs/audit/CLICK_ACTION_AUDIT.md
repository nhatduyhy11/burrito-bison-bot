# Click Action Audit

Audit date: 2026-08-18

## Current result

Runtime mouse gestures under `tools/hauntedroom` have been re-audited against
`core/mouse.py`.

- `bot_click` is the single primitive for automation clicks. It suppresses the
  user-click logger before forwarding the click to Playwright.
- `click_and_wait` composes `bot_click` with `wait_for_flow_timeout` and returns
  whether the flow may continue.
- `click_and_wait(..., click_count=N)` supports repeated clicks at the same
  position. A non-positive count is normalized to one click. Each click is
  followed by the configured cooperative wait; cancellation prevents the next
  repeat.
- `smooth_drag` remains the shared drag primitive.

The artifact-only `_click_activation_three_times` wrapper was removed. Artifact
activation now calls `click_and_wait(..., click_count=3)` directly.

## Reuse completed

| Area | Shared primitive | Notes |
| --- | --- | --- |
| Declarative action runner | `bot_click` | Preserves configurable mouse buttons and separate declarative waits. |
| Artifact | `click_and_wait` | Includes the three-click activation sequence through `click_count=3`. Popup retry and re-detection remain flow-owned. |
| Train | `click_and_wait` | Entry, battle loading, and hero-selection settles are cooperative. |
| Clear blockers | `click_and_wait` | The deliberate pre-click delay remains separate; the post-click poll is composed. |
| EXP available | `click_and_wait` | Replaces the local `_click` plus flow wait. |
| Hero breakthrough | `click_and_wait` | Removes the local `_click`; the two breakthrough clicks remain separate because their waits differ (`800 ms`, then `1000 ms`). |
| Boss pet menu | `click_and_wait` | The click/recheck loop still owns template validation and retry policy. |
| Boss spell | `click_and_wait` then `bot_click` | The first click and its raw `200 ms` settle are composed; the final target click has no local wait. |
| Gear menu | `click_and_wait` | The helper replaces click + raw settle. Menu detection, target refresh, and bounded retry remain flow-owned. |
| Auto-map click callback | `bot_click` | Auto-map no longer imports a generic click helper from the boss module. |
| Research | `bot_click` | Waits are intentionally separate because they occur before a click or at the start of the next detection iteration. |
| Shift+7 click loop | `bot_click` | Its interruptible `asyncio.wait_for(stop_event.wait())` interval is intentionally not replaced by `click_and_wait`. |

After this normalization, direct `page.mouse.click` calls exist only inside
`core/mouse.py`. The click logger's own JavaScript state handling in
`core/runtime.py` is not an input action.

## Patterns that should remain distinct

### Click then validate state

Artifact popup opening, boss pet deployment, and gear menu opening use a state
machine with this contract:

```text
for each bounded attempt:
    click and settle
    capture current state
    return success when the expected state is present
return retry exhaustion
```

`click_and_wait` is reusable for the click/settle step, but must not absorb the
capture, expected-state detector, coordinate refresh, or retry outcome. Those
rules belong to the owning flow.

### Injected auto-map actions

Hero level-up, level-spin interruption, completion blockers, first-win handling,
and reward handling receive `click_fn` and `wait_for_flow_timeout_fn` separately.
They contain several exact click-then-wait pairs, so they could technically be
changed to receive a composed `click_and_wait_fn`.

That migration is not currently worthwhile: it would widen multiple context
objects and test seams merely to replace two explicit injected calls with one.
Their click behavior already reaches `bot_click` through auto-map's shared click
callback, so input mechanics are centralized even though orchestration remains
explicit.

### Countdown waits

Level-up, build, and research use `wait_with_countdown`. This adds progress
logging and cooperative checkpoints and is not equivalent to
`click_and_wait`. Keep the click and countdown calls explicit.

### Wait before click

Template actions, blocker clearing, research, and reward follow-up contain
intentional pre-click waits. A post-click helper must not reverse or hide this
ordering.

### Declarative click and wait records

`json_macro/hauntedroom_actions.sample.json` and `json_macro/macro_record.json` should retain separate
click and wait records. Combining them would reduce record count but weaken
recording, editing, and replay visibility while adding another action schema.

## Remaining gesture exception

Gear drag suppression is still performed immediately before `smooth_drag`.
This is intentional: the logger flag applies to the click event produced by the
drag gesture, while `smooth_drag` itself remains independent of Haunted Room's
browser logger. If another flow needs the same suppressed drag contract, add a
narrow `bot_drag` composition rather than teaching `smooth_drag` about runtime
logging.

## Conclusion

The reusable boundary is now:

1. `bot_click` for click mechanics;
2. `click_and_wait` for a fixed post-click cooperative settle, including same-
   coordinate repeats;
3. `smooth_drag` for drag mechanics;
4. flow-owned code for pre-click timing, countdown output, template/state
   validation, retries, and outcome policy.

No additional generic click helper is justified by the remaining call sites.
