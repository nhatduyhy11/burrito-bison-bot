"""Live mine-event logger: keep a game session open and log mine changes as JSONL.

Long-running counterpart of the POC pair (socket_capture.py + socket_decode.py).
One instance per profile: a lock file refuses a second run, and SIGTERM/SIGHUP
(closing the terminal) stop it cleanly just like Ctrl+C.
Listens on every WebSocket frame, decodes broadcast pushes (module 0x13 cmd
0x0004) live, filters guild-mine events (type 150) and appends new ones to a
JSONL file, deduplicating by event id across pushes and restarts.

Usage:
    uv run python tools/socket_log/mine_logger.py --profile .tmp/m535
    uv run python tools/socket_log/mine_logger.py --duration 300   # auto-stop after 5 min
    uv run python tools/socket_log/mine_logger.py --webhook http://localhost:8000/mine-alerts
"""

import argparse
import asyncio
import datetime
import json
import os
import pathlib
import signal
import struct
import sys
from typing import Optional

from playwright.async_api import Page, WebSocket, async_playwright

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))  # hauntedroom lives in tools/
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from socket_decode import decode_proto, split_frame  # noqa: E402

from hauntedroom.control_events.new_tab_blocker import (
    install_game_core_frame_guard_after_delay,
    install_profile_popup_guard,
)
from hauntedroom.runner.navigation import navigate_to_game

BROADCAST_MODULE = 0x13
BROADCAST_PUSH_CMD = 0x0004
MINE_EVENT_TYPE = 150
DEFAULT_OUT = pathlib.Path(".tmp/mine-events/mine-events.jsonl")
LOCK_FILENAME = ".mine_logger.lock"


def acquire_profile_lock(profile_dir: pathlib.Path) -> bool:
    """Refuse to start when another live logger process still holds the profile."""
    lock_path = profile_dir / LOCK_FILENAME
    profile_dir.mkdir(parents=True, exist_ok=True)
    if lock_path.exists():
        try:
            pid = int(lock_path.read_text().strip())
            os.kill(pid, 0)  # liveness probe; raises when the PID is gone
        except (ValueError, ProcessLookupError):
            pass  # corrupt or stale lock from a run that died without cleanup
        else:
            print(
                f"[logger] profile {profile_dir} is already held by PID {pid}; exiting.",
                flush=True,
            )
            return False
    lock_path.write_text(str(os.getpid()))
    return True


def release_profile_lock(profile_dir: pathlib.Path) -> None:
    """Drop the lock file only if it still belongs to this process."""
    lock_path = profile_dir / LOCK_FILENAME
    try:
        if lock_path.read_text().strip() == str(os.getpid()):
            lock_path.unlink()
    except OSError:
        pass


def install_stop_signals(stop: asyncio.Event) -> None:
    """Make SIGTERM/SIGHUP (kill, terminal close) stop the logger like Ctrl+C."""
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGHUP):
        try:
            loop.add_signal_handler(sig, stop.set)
        except NotImplementedError:
            pass  # platform without add_signal_handler; Ctrl+C still stops the logger


def parse_mine_event(payload: bytes) -> list[dict]:
    """Extract type-150 entries from one broadcast push frame."""
    events = []
    for _field, _wire, value in decode_proto(payload):
        if not isinstance(value, bytes):
            continue
        entry: dict[int, object] = {}
        args_text: Optional[str] = None
        for f2, _w2, v2 in decode_proto(value):
            if isinstance(v2, bytes):
                args_text = v2.decode("utf-8", "replace")
            else:
                entry[f2] = v2
        if entry.get(7) != MINE_EVENT_TYPE:
            continue
        try:
            args = json.loads(args_text or "[]")
        except json.JSONDecodeError:
            args = [args_text]
        events.append(
            {
                "id": entry.get(1),
                "time": datetime.datetime.fromtimestamp(
                    entry.get(3, 0), datetime.timezone.utc
                ).isoformat(),
                "player": args[0][0] if args and args[0] else None,
                "pos": args[2][0] if len(args) > 2 and args[2] else None,
                "action": args[3][0] if len(args) > 3 and args[3] else None,
                "logged_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            }
        )
    return events


class MineEventSink:
    """Dedupe by event id, append fresh events to JSONL, optional webhook."""

    def __init__(self, out_path: pathlib.Path, webhook: Optional[str]) -> None:
        self.out_path = out_path
        self.webhook = webhook
        self.seen_ids: set[int] = set()
        self.new_count = 0
        out_path.parent.mkdir(parents=True, exist_ok=True)
        if out_path.exists():
            for line in out_path.read_text().splitlines():
                try:
                    self.seen_ids.add(json.loads(line)["id"])
                except (json.JSONDecodeError, KeyError):
                    continue
        print(f"[sink] {len(self.seen_ids)} known events from {out_path}", flush=True)

    async def add(self, events: list[dict]) -> None:
        fresh = [e for e in events if e["id"] not in self.seen_ids]
        if not fresh:
            return
        with self.out_path.open("a", encoding="utf-8") as fh:
            for event in fresh:
                self.seen_ids.add(event["id"])
                fh.write(json.dumps(event, ensure_ascii=False) + "\n")
        self.new_count += len(fresh)
        for event in fresh:
            print(
                f"[mine] #{event['id']} {event['time'][11:19]}Z "
                f"{event['player']} pos={event['pos']} action={event['action']}",
                flush=True,
            )
        if self.webhook:
            await self._post(fresh)

    async def _post(self, events: list[dict]) -> None:
        import urllib.request

        def post() -> None:
            request = urllib.request.Request(
                self.webhook,
                data=json.dumps(events, ensure_ascii=False).encode(),
                headers={"Content-Type": "application/json"},
            )
            urllib.request.urlopen(request, timeout=5)

        try:
            await asyncio.to_thread(post)
        except OSError as exc:
            print(f"[webhook] failed: {exc}")


def frame_is_broadcast_push(raw: bytes) -> bool:
    try:
        header, _payload = split_frame("R", raw)
    except (IndexError, struct.error):
        return False
    return header["module"] == BROADCAST_MODULE and header["cmd"] == BROADCAST_PUSH_CMD


def on_websocket(ws: WebSocket, page: Page, sink: MineEventSink) -> None:
    print(f"[ws open] {ws.url}", flush=True)
    # The :19005 handshake socket always closes right after redirecting to the
    # game socket — only the game socket closing means we lost the session.
    is_game_socket = "nodeName=" in ws.url

    def on_frame(payload) -> None:
        if not isinstance(payload, bytes) or not frame_is_broadcast_push(payload):
            return
        _header, body = split_frame("R", payload)
        asyncio.ensure_future(sink.add(parse_mine_event(body)))

    def on_close() -> None:
        if not is_game_socket:
            return
        print("[ws close] game socket dropped; reloading page in 10s...", flush=True)
        asyncio.ensure_future(reload_later(page))

    ws.on("framereceived", on_frame)
    ws.on("close", on_close)


async def reload_later(page: Page, delay: float = 10.0) -> None:
    await asyncio.sleep(delay)
    try:
        await page.reload(wait_until="commit", timeout=15_000)
        print("[ws close] page reloaded")
    except Exception as exc:  # noqa: BLE001 — any reload failure just gets logged
        print(f"[ws close] reload failed: {exc}")


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", default=".tmp/m535")
    parser.add_argument("--url", default="https://hauntedroomvnh5.joynetgame.com/")
    parser.add_argument("--out", type=pathlib.Path, default=DEFAULT_OUT)
    parser.add_argument("--webhook", default=None, help="POST JSON for each fresh event batch")
    parser.add_argument("--duration", type=float, default=None, help="Seconds to run (default: forever)")
    args = parser.parse_args()

    profile_dir = pathlib.Path(args.profile)
    if not acquire_profile_lock(profile_dir):
        raise SystemExit(1)
    sink = MineEventSink(args.out, args.webhook)
    stop = asyncio.Event()
    install_stop_signals(stop)

    async with async_playwright() as playwright:
        context = await playwright.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            channel="chrome",
            headless=False,
            viewport={"width": 640, "height": 720},
            args=[
                "--disable-blink-features=AutomationControlled",
                "--hide-crash-restore-bubble",
            ],
            service_workers="block",
        )
        try:
            page = context.pages[0] if context.pages else await context.new_page()
            page = await navigate_to_game(
                context, page, args.url, prepare_page=install_profile_popup_guard
            )
            guard_task = asyncio.create_task(install_game_core_frame_guard_after_delay(page))

            def hook(new_page: Page) -> None:
                new_page.on(
                    "websocket",
                    lambda ws: on_websocket(ws, new_page, sink),
                )

            hook(page)
            context.on("page", hook)

            if args.duration:
                print(f"[logger] running for {args.duration}s...")
                try:
                    await asyncio.wait_for(stop.wait(), timeout=args.duration)
                except asyncio.TimeoutError:
                    pass
            else:
                print("[logger] running forever — Ctrl+C or closing the terminal stops it")
                await stop.wait()
            guard_task.cancel()
        finally:
            await context.close()
            release_profile_lock(profile_dir)
    print(f"[logger] done — {sink.new_count} new events -> {args.out}")


if __name__ == "__main__":
    asyncio.run(main())
