# TODO

Planning notes only. Do not treat these as current implementation tasks.

## Pending Tasks

- [ ] Fix the train flow and cover the reused priority-template scale `0.8`.
- [ ] Add an OS-global `Ctrl+Shift+F12` recovery hotkey that re-installs the
  browser listener across the current Playwright context without changing flow
  state. See [handoff](GLOBAL_HOTKEY_RECOVERY_HANDOFF.md).
- [ ] Fold the active-artifact flow into the unified `Shift+9` wrapper and
  retire the temporary binding.
- [ ] Unify `Shift+5`, `Shift+6`, and `Shift+9` into one `Shift+9` wrapper flow.
  - [ ] Capture once at startup and detect which screen is currently active.
  - [ ] Use the detected screen to select and switch into its existing flow
    logic, without re-detecting or switching flows mid-run.
  - [ ] Remove the standalone `Shift+5`/`Shift+6` commands and cover routing with
    tests. See [handoff](SHIFT_9_UNIFIED_FLOW_HANDOFF.md).
- [ ] Unify blockers containing the `để đóng` text pattern.
  - [ ] Replace the separate `hero_spin`, `lv_spin`, and related handling with the shared `để đóng` blocker.
  - [ ] Capture live full-screen samples for both the dim-text and clear-text `để đóng` cases to confirm where they occur in the screen flow.
  - [ ] Research whether the detector should use scale matching or separate captured `để đóng` pattern variants.
