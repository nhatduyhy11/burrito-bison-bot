# TODO

Planning notes only. Do not treat these as current implementation tasks.

## Pending Tasks

- [ ] Stabilize the train flow on its temporary `Shift+T` binding, cover the
  reused priority-template scale `0.8`, then merge it into `Shift+1` screen
  auto-switching.
- [ ] Add an OS-global `Ctrl+Shift+F12` recovery hotkey that re-installs the
  browser listener across the current Playwright context without changing flow
  state. See [handoff](GLOBAL_HOTKEY_RECOVERY_HANDOFF.md).
- [ ] Unify blockers containing the `để đóng` text pattern.
  - [ ] Replace the separate `hero_spin`, `lv_spin`, and related handling with the shared `để đóng` blocker.
  - [ ] Capture live full-screen samples for both the dim-text and clear-text `để đóng` cases to confirm where they occur in the screen flow.
  - [ ] Research whether the detector should use scale matching or separate captured `để đóng` pattern variants.
