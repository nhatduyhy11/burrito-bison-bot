"""Isolated browser for the battle simulator page.

    uv run python battle_sim/sandbox.py [--page /sim.html] [--battle <uuid>] [--keep] [--headless]

- Starts `node battle_sim/serve.js` (offline mirror) on 127.0.0.1:8090.
- Fresh throwaway Chromium profile: no cookies, no account, service workers blocked.
- Every request that is not http://127.0.0.1:8090/ is aborted and logged, WebSockets are
  closed: the game code cannot reach any game server or third party even if it tries.
- --battle <uuid> opens /sim.html?battle=<uuid>: replays that captured battle in the game's
  battle view (web/battle/) and compares the resulting QuitRoom with the captured one.
- --battle <uuid> --play [--seed random|<uuid>]: play that battle's StartGameP yourself in a
  real window (implies --keep). The played battle is saved to .tmp/battle_sim/played/*.jsonl
  (capture format) for `node battle_sim/replay.js <file>`.
- --setup: open the profile setup page (web/setup.html) first. Its "Chơi" button saves the profile
  to .tmp/battle_sim/profiles/last.json (+ last-setup.json with the chosen battle and seed) and
  starts --play on the chosen captured battle with it.
- Waits for window.__sim.state ("ready" / "done" / "error"), prints the boot steps, checks, blocked
  requests, mirror 404s and console errors. Full log -> .tmp/battle_sim/sandbox-<ts>.log.
- --keep leaves the window open (CDP on 127.0.0.1:9334 for poking around) until closed.
"""

import argparse
import asyncio
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / ".tmp" / "battle_sim"
ORIGIN = "http://127.0.0.1:8090"
CDP_PORT = 9334
PLAYED = CACHE / "played"
PROFILES = CACHE / "profiles"
SETUP_PAGE = "/__sim/setup.html"
UUID_RE = re.compile(r"^[0-9a-f]{24}$")
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


def as_list(items):
    """Plain list -> the hook's List JSON shape ({"0": .., "_length": n}) that lib/capture.js reads."""
    out = {str(i): v for i, v in enumerate(items)}
    out["_length"] = len(items)
    return out


async def save_played(page, battle):
    """Write a played battle as a capture-style jsonl (StartGameP + QuitRoom) so
    `node battle_sim/replay.js <file>` can replay it headless and check the result."""
    start = await page.evaluate("() => window.__simPlayedStart")
    quit_ = dict(battle["quit"])
    quit_["operations"] = as_list(quit_.get("operations") or [])
    path = PLAYED / f"played-{start['uuid']}-{time.strftime('%Y%m%d-%H%M%S')}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        f.write(json.dumps({"kind": "room", "data": {"msg": "StartGameP (sim play)", "obj": start}}, ensure_ascii=False) + "\n")
        f.write(json.dumps({"kind": "sock", "data": {"msg": "QuitRoom( (sim play)", "obj": quit_}}, ensure_ascii=False) + "\n")
    rel = path.relative_to(ROOT).as_posix()
    print(f"\nplayed battle saved: {rel} ({quit_['operations']['_length']} ops)")
    print(f"  check: node battle_sim/replay.js {rel}")


async def run_setup(page):
    """Show the setup page until its "Chơi" button calls window.simPlay({battle, seed, profile}).
    Returns that choice (profile saved under PROFILES), or None if the window was closed first."""
    chosen = asyncio.get_running_loop().create_future()

    async def sim_play(choice):
        battle, seed, profile = choice.get("battle"), choice.get("seed") or None, choice.get("profile")
        if not isinstance(battle, str) or not UUID_RE.match(battle):
            raise ValueError(f"invalid battle uuid: {battle!r}")
        if seed is not None and seed != "random" and not UUID_RE.match(str(seed)):
            raise ValueError(f"invalid seed: {seed!r}")
        if not isinstance(profile, dict):
            raise ValueError("profile must be an object")
        PROFILES.mkdir(parents=True, exist_ok=True)
        setup = {"battle": battle, "seed": seed, "profile": profile}
        for name, data in (("last.json", profile), ("last-setup.json", setup)):
            (PROFILES / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        rel = (PROFILES / "last.json").relative_to(ROOT).as_posix()
        print(f"setup: battle {battle}, seed {seed or 'captured'}, profile saved to {rel}", flush=True)
        if not chosen.done():
            chosen.set_result(setup)
        return rel

    await page.expose_function("simPlay", sim_play)
    await page.goto(ORIGIN + SETUP_PAGE, wait_until="domcontentloaded")
    print(f"setup page open: {ORIGIN + SETUP_PAGE}", flush=True)
    while not chosen.done():
        if page.is_closed():
            return None
        await asyncio.sleep(0.3)
    return chosen.result()


def find_node() -> str:
    """node for serve.js: $BATTLE_SIM_NODE, else node on PATH."""
    node = os.environ.get("BATTLE_SIM_NODE") or shutil.which("node")
    if not node:
        raise SystemExit("node not found on PATH; set BATTLE_SIM_NODE to the full path of node(.exe)")
    return node


def start_server() -> subprocess.Popen:
    # A debug terminal (VS Code auto-attach, NODE_OPTIONS=--inspect) would attach to serve.js and
    # print "Debugger listening/attached" first; the server needs no debugger.
    env = {k: v for k, v in os.environ.items() if k not in ("NODE_OPTIONS", "VSCODE_INSPECTOR_OPTIONS")}
    proc = subprocess.Popen(
        [find_node(), str(ROOT / "battle_sim" / "serve.js"), "--port", "8090"],
        cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8",
    )
    seen = []
    while len(seen) < 20:  # skip stray startup lines (debugger notices etc.) until the ready line
        line = proc.stdout.readline()
        if not line:
            break
        if "serving mirror" in line:
            print(line.strip(), flush=True)
            return proc
        seen.append(line.strip())
    proc.kill()
    raise SystemExit("serve.js did not start:\n  " + "\n  ".join(seen or ["(no output)"]))


async def run(args) -> int:
    profile_data = json.loads(args.profile.read_text(encoding="utf-8")) if args.profile else None
    log_path = CACHE / f"sandbox-{time.strftime('%Y%m%d-%H%M%S')}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log = log_path.open("w", encoding="utf-8")
    blocked, page_errors, console_errors, misses = [], [], [], []

    def emit(kind, msg):
        log.write(f"{time.strftime('%H:%M:%S')} {kind} {msg}\n")
        log.flush()

    server = start_server()

    async def pump_server():
        loop = asyncio.get_running_loop()
        while True:
            line = await loop.run_in_executor(None, server.stdout.readline)
            if not line:
                return
            line = line.rstrip()
            emit("server", line)
            if line.startswith("404 "):
                misses.append(line[4:])

    pump = asyncio.create_task(pump_server())
    try:
        async with async_playwright() as pw:
            with tempfile.TemporaryDirectory(prefix="battle_sim_profile_") as profile:
                ctx = await pw.chromium.launch_persistent_context(
                    profile,
                    channel=args.browser,
                    headless=args.headless,
                    # Portrait game (design 720x1280, FIXED_WIDTH): a landscape window only shows a
                    # 720x400 strip. Headed defaults to the hauntedroom runner's 640x720.
                    viewport=dict(zip(("width", "height"), map(int, args.size.split("x")))),
                    service_workers="block",
                    **({"record_video_dir": args.record,
                        "record_video_size": dict(zip(("width", "height"), map(int, args.size.split("x"))))}
                       if args.record else {}),
                    args=[f"--remote-debugging-port={CDP_PORT}", "--remote-debugging-address=127.0.0.1"],
                )

                async def guard(route):
                    url = route.request.url
                    if profile_data is not None and url == ORIGIN + "/__sim/active-profile.json":
                        await route.fulfill(json=profile_data)
                    elif url.startswith(ORIGIN + "/"):
                        await route.continue_()
                    else:
                        blocked.append(url)
                        emit("BLOCKED", f"{route.request.method} {url}")
                        await route.abort("blockedbyclient")

                async def ws_guard(ws):
                    blocked.append("ws " + ws.url)
                    emit("BLOCKED", f"WS {ws.url}")
                    await ws.close()

                await ctx.route("**/*", guard)
                await ctx.route_web_socket(re.compile(".*"), ws_guard)
                page = ctx.pages[0] if ctx.pages else await ctx.new_page()

                def on_console(m):
                    emit(f"console.{m.type}", m.text)
                    if m.type == "error":
                        console_errors.append(m.text)

                def on_pageerror(e):
                    emit("pageerror", str(e))
                    page_errors.append(str(e))

                page.on("console", on_console)
                page.on("pageerror", on_pageerror)

                if args.setup:
                    chosen = await run_setup(page)
                    if chosen is None:
                        print("setup page closed without starting a battle")
                        await ctx.close()
                        return 0
                    profile_data, args.battle, args.seed = chosen["profile"], chosen["battle"], chosen["seed"]

                url = ORIGIN + args.page
                if args.battle:
                    url += ("&" if "?" in url else "?") + "battle=" + args.battle
                if args.play:
                    url += "&play=1" + (f"&seed={args.seed}" if args.seed else "")
                    if profile_data is not None:
                        url += "&profile=1"
                await page.goto(url, wait_until="domcontentloaded")
                sim = None
                deadline = time.time() + args.timeout
                next_progress = time.time() + 30
                while time.time() < deadline:
                    try:
                        sim = await page.evaluate("() => window.__sim && JSON.parse(JSON.stringify(window.__sim))")
                    except Exception as e:  # window closed by the player
                        print(f"page gone: {str(e).splitlines()[0]}")
                        break
                    if sim and sim.get("state") in TERMINAL:
                        break
                    b = (sim or {}).get("battle")
                    if b and time.time() >= next_progress:
                        next_progress = time.time() + 30
                        print(f"  ... tick {b.get('tick')}, ops {b.get('applied')}/{b.get('ops')}", flush=True)
                    await asyncio.sleep(0.5)

                print(f"\nstate: {sim and sim.get('state')}" + ("" if sim and sim.get("state") in TERMINAL else " (timeout)"))
                for s in (sim or {}).get("steps", []):
                    extra = "" if s.get("extra") is None else " " + json.dumps(s["extra"], ensure_ascii=False)
                    print(f"  {s['t'] / 1000:6.1f}s {s['name']}{extra}")
                print_battle((sim or {}).get("battle"))
                if sim and sim.get("error"):
                    print("error:", json.dumps(sim["error"], ensure_ascii=False, indent=1))
                print(f"\nblocked requests (outside {ORIGIN}): {len(blocked)}")
                for u in sorted(set(blocked))[:30]:
                    print("  ", u)
                print(f"mirror 404s: {len(misses)}")
                for u in sorted(set(misses))[:30]:
                    print("  ", u)
                print(f"page errors: {len(page_errors)}, console errors: {len(console_errors)}")
                for e in (page_errors + console_errors)[:15]:
                    print("  ", e[:300])
                print("log:", log_path.relative_to(ROOT))
                if args.play and sim and (sim.get("battle") or {}).get("quit"):
                    await save_played(page, sim["battle"])

                if args.keep:
                    print(f"\nwindow kept open (CDP 127.0.0.1:{CDP_PORT}); close it to exit", flush=True)
                    while ctx.pages:
                        await asyncio.sleep(1)
                await ctx.close()
                battle = (sim or {}).get("battle") or {}
                if args.play:
                    ok = bool(sim) and sim.get("state") == "done" and not blocked
                elif args.battle:
                    ok = bool(sim) and sim.get("state") == "done" and (battle.get("compare") or {}).get("ok") and not blocked
                else:
                    ok = bool(sim) and sim.get("state") == "ready" and not blocked
                return 0 if ok else 1
    finally:
        server.terminate()
        pump.cancel()
        log.close()


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # game logs are Chinese
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--page", default="/sim.html")
    ap.add_argument("--battle", help="captured battle uuid to replay in the battle view")
    ap.add_argument("--play", action="store_true",
                    help="with --battle: play that battle's StartGameP yourself instead of replaying (implies --keep)")
    ap.add_argument("--seed", help="with --play: battle uuid / RNG seed ('random' = new battle; default = captured)")
    ap.add_argument("--profile", type=Path, help="with --play: JSON file with local formation overrides")
    ap.add_argument("--setup", action="store_true",
                    help="open the profile setup page first; its Play button starts --play with the chosen battle and profile")
    ap.add_argument("--keep", action="store_true", help="keep the window open after the run")
    ap.add_argument("--headless", action="store_true")
    ap.add_argument("--browser", choices=("chrome", "chromium"), default="chrome")
    ap.add_argument("--timeout", type=float, default=120)
    ap.add_argument("--record", help="record the page as .webm into this directory (saved when the window closes)")
    ap.add_argument("--size", help="viewport WxH (default 720x1280 headless, 640x720 headed like the runner)")
    args = ap.parse_args()
    if args.setup:
        if args.headless:
            ap.error("--setup needs a window (no --headless)")
        if args.profile or args.battle:
            ap.error("--setup picks the battle and profile on the page (no --battle / --profile)")
        args.play = True
    if args.profile and not args.play:
        ap.error("--profile requires --play")
    if not args.size:
        args.size = "720x1280" if args.headless else "640x720"
    if args.play:
        if not args.battle and not args.setup:
            ap.error("--play needs --battle <uuid> (whose StartGameP to use)")
        args.keep = args.keep or not args.headless  # headless play = smoke test, nobody to close it
        if args.timeout == ap.get_default("timeout"):
            args.timeout = 3600
    return asyncio.run(run(args))


if __name__ == "__main__":
    sys.exit(main())
