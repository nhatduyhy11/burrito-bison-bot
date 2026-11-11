---
name: setup-ui-verify-scope
description: For setup-form UI tasks (battle_sim/web/setup), the real --setup check only needs to reach the battle, play ~20s and exit — never run a full battle
metadata:
  type: feedback
---

For tasks on the setup form UI (`battle_sim/web/setup.html` + `web/setup/`), the real
`sandbox.py --setup` check is: press Chơi → battle opens with the profile → let it run ~20s → exit.
No need to play the battle out or wait for the full timeout.

**Why:** the UI is only a shell that produces the profile JSON; battle logic does not change in
these tasks, so a full battle wastes time (user, 2026-11-11).

**How to apply:** run `sandbox.py --setup` with a short `--timeout` (~25-30s) and drive it over CDP
`127.0.0.1:9334`: confirm the URL has `&profile=1`, the battle is ticking, 0 blocked requests and
0 console errors, then close. The form checks (Node test of skin-rules, browser run via `serve.js`
compared with the previous page) still apply. Related: [[battle-sim-docs-location]].
