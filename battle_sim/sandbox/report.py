"""Sandbox run report: the console summary of a sim run and the played-battle capture file."""

import json
import time

# window.__sim.state values that end the wait for a run.
TERMINAL = ("ready", "done", "error")


def print_battle(b):
    if not b:
        return
    print(f"\nbattle {b.get('uuid')}: tick {b.get('tick')}, ops applied {b.get('applied')}/{b.get('ops')}, "
          f"failed {len(b.get('failed') or [])}, dropped UI ops {len(b.get('dropped') or [])}, "
          f"foreign handleClientRequest {b.get('foreignOps')}, stubbed net calls {len(b.get('netCalls') or [])}")
    print(f"  via UI commit {b.get('viaUi', 0)}, wheel closed {b.get('wheelClosed', 0)}, "
          f"director pauses skipped {json.dumps(b.get('pausesSkipped') or {}, ensure_ascii=False)}")
    for f in (b.get("failed") or [])[:10]:
        print("  fail", json.dumps(f, ensure_ascii=False)[:300])
    for d in (b.get("dropped") or [])[:10]:
        print("  dropped", json.dumps(d, ensure_ascii=False)[:300])
    seen = set()
    for n in b.get("netCalls") or []:
        key = json.dumps(n, ensure_ascii=False)
        if key not in seen:
            seen.add(key)
            print("  net", key[:300])
    for m in (b.get("moduleErrors") or [])[:40]:
        print("  module", json.dumps(m, ensure_ascii=False)[:300])
    for e in (b.get("errors") or [])[:8]:
        print("  console.error", json.dumps(e, ensure_ascii=False)[:1200])
    cmp_ = b.get("compare")
    if cmp_:
        for line in cmp_.get("lines", []):
            print("  " + line)
        print("  QUITROOM " + ("MATCH" if cmp_.get("ok") else "MISMATCH"))


def print_summary(sim, cap, misses, origin, log_rel):
    """Final state, boot steps, battle details, blocked requests, mirror 404s and page errors of one run.
    `cap` is the browser.Capture of the run."""
    state = sim and sim.get("state")
    print(f"\nstate: {state}" + ("" if state in TERMINAL else " (timeout)"))
    for s in (sim or {}).get("steps", []):
        extra = "" if s.get("extra") is None else " " + json.dumps(s["extra"], ensure_ascii=False)
        print(f"  {s['t'] / 1000:6.1f}s {s['name']}{extra}")
    print_battle((sim or {}).get("battle"))
    if sim and sim.get("error"):
        print("error:", json.dumps(sim["error"], ensure_ascii=False, indent=1))
    print(f"\nblocked requests (outside {origin}): {len(cap.blocked)}")
    for u in sorted(set(cap.blocked))[:30]:
        print("  ", u)
    print(f"mirror 404s: {len(misses)}")
    for u in sorted(set(misses))[:30]:
        print("  ", u)
    print(f"page errors: {len(cap.page_errors)}, console errors: {len(cap.console_errors)}")
    for e in (cap.page_errors + cap.console_errors)[:15]:
        print("  ", e[:300])
    print("log:", log_rel)


def as_list(items):
    """Plain list -> the hook's List JSON shape ({"0": .., "_length": n}) that lib/capture.js reads."""
    out = {str(i): v for i, v in enumerate(items)}
    out["_length"] = len(items)
    return out


async def save_played(page, battle, out_dir, root):
    """Write a played battle as a capture-style jsonl (StartGameP + QuitRoom) under `out_dir` so
    `node battle_sim/replay.js <file>` can replay it headless and check the result."""
    start = await page.evaluate("() => window.__simPlayedStart")
    quit_ = dict(battle["quit"])
    quit_["operations"] = as_list(quit_.get("operations") or [])
    path = out_dir / f"played-{start['uuid']}-{time.strftime('%Y%m%d-%H%M%S')}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        f.write(json.dumps({"kind": "room", "data": {"msg": "StartGameP (sim play)", "obj": start}}, ensure_ascii=False) + "\n")
        f.write(json.dumps({"kind": "sock", "data": {"msg": "QuitRoom( (sim play)", "obj": quit_}}, ensure_ascii=False) + "\n")
    rel = path.relative_to(root).as_posix()
    print(f"\nplayed battle saved: {rel} ({quit_['operations']['_length']} ops)")
    print(f"  check: node battle_sim/replay.js {rel}")
