# TODO

Planning notes only. Do not treat these as current implementation tasks.

## Pending Tasks

- [ ] Teach the normal auto-map flow to stop when it detects a special game-mode
  end signal instead of a traditional map-completion screen.
  - [ ] Support the `blood_mode` and `udo_mode` signals.
  - [ ] Complete and validate the currently staged reference images before
    implementing the detectors.
- [x] Stabilize the train flow on its `Shift+T` binding, cover the reused
  priority-template scale `0.8`, and expose it through `Shift+1` screen
  auto-switching using the train screen template.
- [ ] Add an OS-global `Ctrl+Shift+F12` recovery hotkey that re-installs the
  browser listener across the current Playwright context without changing flow
  state. See [handoff](GLOBAL_HOTKEY_RECOVERY_HANDOFF.md).
- [ ] Unify blockers containing the `để đóng` text pattern.
  - [ ] Replace the separate `hero_spin`, `lv_spin`, and related handling with the shared `để đóng` blocker.
  - [ ] Capture live full-screen samples for both the dim-text and clear-text `để đóng` cases to confirm where they occur in the screen flow.
  - [ ] Research whether the detector should use scale matching or separate captured `để đóng` pattern variants.
- [ ] Add detection for the `hero_pre-enter` screen.
  - [ ] Support swapping priority 1-2 between Lubu and Hanuman depending on this screen's state.
- [ ] Add missing screen detection for the hero level up screen.
- [x] Add detection for the train screen and integrate it into screen auto-switching.
