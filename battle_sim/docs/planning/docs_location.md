---
name: battle-sim-docs-location
description: All battle_sim docs/planning live in battle_sim/docs/planning/, never in the repo-level docs/planning/ — battle_sim will be split out into its own project
metadata:
  type: project
---

battle_sim docs, planning, research and notes live in `battle_sim/docs/planning/` (moved from
`docs/planning/battle_sim/` on 2026-11-11). Do not create battle_sim files under the repo-level `docs/`.

**Why:** battle_sim is sensitive and will later be split out of burrito-bison-bot into its own
project, so everything it owns must stay inside `battle_sim/` to move out cleanly.

**How to apply:** new battle_sim files (plans, research, handoffs, memory notes) go in
`battle_sim/docs/planning/`; links to other battle_sim code/docs use relative paths that stay inside
`battle_sim/` (e.g. `../../README.md`). The repo-wide rule (keep only open items, remove done ones)
still applies: [[specs-location]].
