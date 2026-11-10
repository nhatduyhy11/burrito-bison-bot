"""Isolated browser for the battle simulator page.

    uv run python battle_sim/sandbox.py [--page /sim.html] [--keep] [--headless]

- Starts `node battle_sim/serve.js` (offline mirror) on 127.0.0.1:8090.
- Fresh throwaway Chromium profile: no cookies, no account, service workers blocked.
- Every request that is not http://127.0.0.1:8090/ is aborted and logged, WebSockets are
  closed: the game code cannot reach any game server or third party even if it tries.
- Waits for window.__sim.state ("ready" / "error"), prints the boot steps, checks, blocked
  requests, mirror 404s and console errors. Full log -> .tmp/battle_sim/sandbox-<ts>.log.
- --keep leaves the window open (CDP on 127.0.0.1:9334 for poking around) until closed.
"""

import argparse
import asyncio
import json
import re
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


def start_server() -> subprocess.Popen:
    proc = subprocess.Popen(
        ["node", str(ROOT / "battle_sim" / "serve.js"), "--port", "8090"],
        cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8",
    )
    line = proc.stdout.readline()
    if "serving mirror" not in line:
        proc.kill()
        raise SystemExit(f"serve.js did not start: {line.strip()}")
    print(line.strip(), flush=True)
    return proc


async def run(args) -> int:
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
                    viewport={"width": 720, "height": 1280} if args.headless else None,
                    service_workers="block",
                    args=[f"--remote-debugging-port={CDP_PORT}", "--remote-debugging-address=127.0.0.1"],
                )

                async def guard(route):
                    url = route.request.url
                    if url.startswith(ORIGIN + "/"):
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

                await page.goto(ORIGIN + args.page, wait_until="domcontentloaded")
                sim = None
                deadline = time.time() + args.timeout
                while time.time() < deadline:
                    sim = await page.evaluate("() => window.__sim && JSON.parse(JSON.stringify(window.__sim))")
                    if sim and sim.get("state") in ("ready", "error"):
                        break
                    await asyncio.sleep(0.5)

                print(f"\nstate: {sim and sim.get('state')}" + ("" if sim and sim.get("state") in ("ready", "error") else " (timeout)"))
                for s in (sim or {}).get("steps", []):
                    extra = "" if s.get("extra") is None else " " + json.dumps(s["extra"], ensure_ascii=False)
                    print(f"  {s['t'] / 1000:6.1f}s {s['name']}{extra}")
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

                if args.keep:
                    print(f"\nwindow kept open (CDP 127.0.0.1:{CDP_PORT}); close it to exit", flush=True)
                    while ctx.pages:
                        await asyncio.sleep(1)
                await ctx.close()
                ok = bool(sim) and sim.get("state") == "ready" and not blocked
                return 0 if ok else 1
    finally:
        server.terminate()
        pump.cancel()
        log.close()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--page", default="/sim.html")
    ap.add_argument("--keep", action="store_true", help="keep the window open after the run")
    ap.add_argument("--headless", action="store_true")
    ap.add_argument("--browser", choices=("chrome", "chromium"), default="chrome")
    ap.add_argument("--timeout", type=float, default=120)
    return asyncio.run(run(ap.parse_args()))


if __name__ == "__main__":
    sys.exit(main())
