"""Isolated browser for the battle simulator page.

    uv run python battle_sim/sandbox [--page /sim.html] [--battle <uuid>] [--keep] [--headless]

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
import sys
import tempfile
import time
from pathlib import Path

from playwright.async_api import async_playwright

import browser
import server
from report import TERMINAL, print_summary, save_played
from setup import SetupPage

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / ".tmp" / "battle_sim"
PORT = 8090
ORIGIN = f"http://127.0.0.1:{PORT}"
CDP_PORT = 9334
PLAYED = CACHE / "played"
PROFILES = CACHE / "profiles"


async def run(args) -> int:
    profile_data = json.loads(args.profile.read_text(encoding="utf-8")) if args.profile else None
    log_path = CACHE / f"sandbox-{time.strftime('%Y%m%d-%H%M%S')}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log = log_path.open("w", encoding="utf-8")

    def emit(kind, msg):
        log.write(f"{time.strftime('%H:%M:%S')} {kind} {msg}\n")
        log.flush()

    try:
        async with server.mirror(ROOT, PORT, emit) as misses, async_playwright() as pw:
            with tempfile.TemporaryDirectory(prefix="battle_sim_profile_") as profile:
                ctx, page, cap = await browser.launch(
                    pw, profile, origin=ORIGIN, cdp_port=CDP_PORT, channel=args.browser,
                    headless=args.headless, size=args.size, record=args.record, emit=emit,
                    profile_json=lambda: profile_data,  # read per request: --setup swaps it between runs
                )

                setup = await SetupPage.install(page, ORIGIN, PROFILES, ROOT) if args.setup else None
                ok = True
                while True:
                    if args.setup:
                        chosen = await setup.choose()
                        if chosen is None:
                            print("setup page closed without starting a battle")
                            break
                        profile_data, args.battle, args.seed = chosen["profile"], chosen["battle"], chosen["seed"]
                        cap.clear()
                        misses.clear()

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

                    print_summary(sim, cap, misses, ORIGIN, log_path.relative_to(ROOT))
                    if args.play and sim and (sim.get("battle") or {}).get("quit"):
                        await save_played(page, sim["battle"], PLAYED, ROOT)

                    # Play mode: closing the result view sets window.__simLeave (web/battle/stubs.js),
                    # since leaving the battle would go to the lobby this page does not have.
                    leave = None
                    if args.keep:
                        then = "go back to the setup page" if args.setup else "end the run"
                        print(f"\nwindow kept open (CDP 127.0.0.1:{CDP_PORT}); close the result view to {then}, "
                              "or close the window to exit", flush=True)
                        while ctx.pages and not page.is_closed():
                            try:
                                leave = await page.evaluate("() => window.__simLeave || null")
                            except Exception:  # window closed / navigating
                                leave = None
                            if leave:
                                break
                            await asyncio.sleep(1)
                    battle = (sim or {}).get("battle") or {}
                    if args.play:
                        ok = bool(sim) and sim.get("state") == "done" and not cap.blocked
                    elif args.battle:
                        ok = bool(sim) and sim.get("state") == "done" and (battle.get("compare") or {}).get("ok") and not cap.blocked
                    else:
                        ok = bool(sim) and sim.get("state") == "ready" and not cap.blocked
                    if not (args.setup and leave and not page.is_closed()):
                        break
                    print(f"\n{leave}: back to the setup page\n", flush=True)
                await ctx.close()
                return 0 if ok else 1
    finally:
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
