# TODO

Planning notes only. Do not treat these as current implementation tasks.

## Pending Tasks

- [ ] Handle the 1st-win-of-the-day blocker.
- [ ] Retest with 2 incorrect fallback images.
- [ ] Fix the train flow.
  - [ ] Check scaling pattern matching.
- [ ] Unify blockers containing the `để đóng` text pattern.
  - [ ] Replace the separate `hero_spin`, `lv_spin`, and related handling with the shared `để đóng` blocker.
  - [ ] Capture live full-screen samples for both the dim-text and clear-text `để đóng` cases to confirm where they occur in the screen flow.
  - [ ] Research whether the detector should use scale matching or separate captured `để đóng` pattern variants.
- [ ] Add macro: collect hero EXP.
  - Priority: low
  - Type: new special flow
- [ ] Add macro: collect new account hero-up.
  - Priority: low
  - Type: new special flow
