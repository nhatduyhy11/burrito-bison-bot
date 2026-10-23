"""Live mine logger: keep a game session open and log raw mine data as JSONL.

Long-running counterpart of the POC pair (socket_capture.py + socket_decode.py).
One instance per profile: a lock file refuses a second run, and SIGTERM/SIGHUP
(closing the terminal) stops it cleanly just like Ctrl+C.
Raw streams written under .tmp/mine-events/ (mine_report.py aggregates them later):
  - mine-events.jsonl  broadcast feed (module 0x13): cmd 0x0004 login replay +
    cmd 0x0007 real-time push, filtered to type 150 (guild-mine events),
    deduplicated by event id across pushes and restarts, optional --webhook;
  - mine-state.jsonl   full map snapshot at each login (0x48/0x0002), one tile per line;
  - mine-tiles.jsonl   live tile deltas (0x48/0x0008) whenever someone enters/leaves
    a slot (--no-tiles skips);
  - player-briefs.jsonl id -> name/guild from every 0x0d/0x0020 the client receives;
  - guild-briefs.jsonl  guild id -> name (0x24/0x0036, id recovered via response seq).

With --fetch-names (default) the logger also injects 0x0d/0x001f brief requests
through the game socket for occupant ids of sectors 2-7, so the report gets a
name for every seated player without any UI clicking.

Usage:
    uv run python tools/socket_log/mine_logger.py --profile .tmp/m535 --snapshot   # one state+names pass, then exit
    uv run python tools/socket_log/mine_logger.py --profile .tmp/m535 --duration 300   # auto-stop after 5 min
    uv run python tools/socket_log/mine_logger.py --profile .tmp/m535 --webhook http://localhost:8000/mine-alerts
"""

import argparse
import asyncio
import datetime
import json
import pathlib
import struct
import sys
from typing import Optional

from playwright.async_api import Page, WebSocket, async_playwright

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from process_guard import (  # noqa: E402
    acquire_profile_lock,
    install_stop_signals,
    release_profile_lock,
)
from socket_decode import decode_proto, read_packed_varints, split_frame  # noqa: E402
from mine_protocol import (  # noqa: E402
    BROADCAST_MODULE,
    BROADCAST_PUSH_CMDS,
    GUILD_BRIEF_CMD,
    GUILD_BRIEF_LIST_CMD,
    GUILD_MODULE,
    MAP_STATE_CMD,
    MINE_MODULE,
    PLAYER_BRIEF_CMD,
    PLAYER_BRIEF_LIST_CMD,
    PLAYER_MODULE,
    TILE_DELTA_CMD,
    build_brief_request,
    frame_is,
    parse_guild_brief,
    parse_mine_event,
    parse_player_briefs,
    parse_tiles,
)

from navigation import navigate_to_game  # noqa: E402
from page_guards import (  # noqa: E402
    install_game_core_frame_guard_after_delay,
    install_profile_popup_guard,
)

sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # cp1252 consoles choke on player names

SECTOR_MIN, SECTOR_MAX = 2, 7  # sector 1 is the flat 124-slot tile — out of scope
BRIEF_CHUNK = 60  # client batches ~59 ids per request
NAME_FETCH_MIN_INTERVAL = 5.0  # seconds between injected batches
SETTLE_SECONDS = 5.0  # grace after the last injected batch for stray replies to land

DEFAULT_DIR = pathlib.Path(".tmp/mine-events")
LOCK_FILENAME = ".mine_logger.lock"

# Captures the game WebSocket instance so Python can inject frames (NameFetcher).
WS_SEND_HOOK_JS = """() => {
    if (window.__mineLoggerHooked) return;
    window.__mineLoggerHooked = true;
    const send = WebSocket.prototype.send;
    WebSocket.prototype.send = function (data) {
        window.__mineLoggerWs = this;
        return send.call(this, data);
    };
}"""

SEND_FRAME_JS = """(bytes) => {
    const ws = window.__mineLoggerWs;
    if (!ws || ws.readyState !== 1) return false;
    ws.send(new Uint8Array(bytes));
    return true;
}"""


class JsonlSink:
    """Append dicts as JSONL lines; every push is new data (no dedupe)."""

    def __init__(self, out_path: pathlib.Path, tag: str) -> None:
        self.out_path = out_path
        self.tag = tag
        self.count = 0
        out_path.parent.mkdir(parents=True, exist_ok=True)

    async def add(self, rows: list[dict]) -> None:
        if not rows:
            return
        logged_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        with self.out_path.open("a", encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps({**row, "logged_at": logged_at}, ensure_ascii=False) + "\n")
        self.count += len(rows)
        print(f"[{self.tag}] {len(rows)} rows (total {self.count})", flush=True)


class MineEventSink:
    """Dedupe by event id, append fresh events to JSONL, optional webhook."""

    def __init__(self, out_path: pathlib.Path, webhook: Optional[str]) -> None:
        self.out_path = out_path
        self.webhook = webhook
        self.seen_ids: set[int] = set()
        self.new_count = 0
        out_path.parent.mkdir(parents=True, exist_ok=True)
        if out_path.exists():
            for line in out_path.read_text(encoding="utf-8").splitlines():
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


class NameFetcher:
    """Inject 0x0d/0x001f brief requests through the game socket for unknown ids.

    Frames go out via page JS (window.__mineLoggerWs, captured by WS_SEND_HOOK_JS);
    responses arrive on the normal receive path and are logged by the brief sink.
    """

    def __init__(self) -> None:
        self.page: Optional[Page] = None
        self.pending: set[int] = set()
        self.requested: set[int] = set()
        self.last_flush = 0.0
        self.last_attempt = 0.0
        self._lock = asyncio.Lock()

    def queue(self, ids) -> None:
        self.pending.update(i for i in ids if i not in self.requested)

    def settled(self) -> bool:
        """All queued ids sent and enough time passed for the last replies to land."""
        if self.pending or not self.requested:
            return False
        return asyncio.get_running_loop().time() - self.last_flush > SETTLE_SECONDS

    async def flush(self, force: bool = False) -> None:
        if not self.pending or self.page is None:
            return
        now = asyncio.get_running_loop().time()
        self.last_attempt = now
        if not force and now - self.last_flush < NAME_FETCH_MIN_INTERVAL:
            return
        async with self._lock:
            if not self.pending:
                return
            while self.pending:
                ids = sorted(self.pending)[:BRIEF_CHUNK]
                try:
                    sent = await self.page.evaluate(SEND_FRAME_JS, list(build_brief_request(ids)))
                except Exception as exc:  # noqa: BLE001 — page closing etc. must not kill the logger
                    print(f"[names] inject failed: {exc}", flush=True)
                    return
                if not sent:
                    print("[names] game socket not ready; will retry on next trigger", flush=True)
                    return
                self.requested.update(ids)
                self.pending.difference_update(ids)
                print(f"[names] requested briefs for {len(ids)} ids", flush=True)
                if self.pending:
                    await asyncio.sleep(0.5)  # pace multi-chunk batches
            self.last_flush = asyncio.get_running_loop().time()


def on_websocket(
    ws: WebSocket,
    page: Page,
    sink: MineEventSink,
    state_sink: JsonlSink,
    tile_sink: Optional[JsonlSink],
    brief_sink: JsonlSink,
    guild_sink: JsonlSink,
    name_fetcher: NameFetcher,
) -> None:
    print(f"[ws open] {ws.url}", flush=True)
    # The :19005 handshake socket always closes right after redirecting to the
    # game socket — only the game socket closing means we lost the session.
    is_game_socket = "nodeName=" in ws.url
    pending_guild_requests: dict[int, int] = {}  # seq -> guild id asked via 0x24/0x0035

    def occupant_ids(tiles: list[dict]) -> set[int]:
        return {
            player_id
            for tile in tiles
            if tile["sector"] is None or SECTOR_MIN <= tile["sector"] <= SECTOR_MAX
            for player_id in tile["occupied"].values()
        }

    def on_sent(payload) -> None:
        if not isinstance(payload, bytes):
            return
        try:
            header, body = split_frame("S", payload)
        except (IndexError, struct.error):
            return
        if header["module"] == GUILD_MODULE and header["cmd"] == GUILD_BRIEF_CMD:
            for f, _w, v in decode_proto(body):
                if f == 1 and isinstance(v, bytes):
                    ids = read_packed_varints(v)
                    if ids:
                        pending_guild_requests[header["seq"]] = ids[0]
        elif header["module"] == PLAYER_MODULE and header["cmd"] == PLAYER_BRIEF_CMD:
            # the client fetched names itself — don't re-request those ids
            for f, _w, v in decode_proto(body):
                if f == 1 and isinstance(v, bytes):
                    client_ids = set(read_packed_varints(v))
                    name_fetcher.requested.update(client_ids)
                    name_fetcher.pending.difference_update(client_ids)

    def on_frame(payload) -> None:
        if not isinstance(payload, bytes):
            return
        if frame_is(payload, BROADCAST_MODULE, BROADCAST_PUSH_CMDS):
            _header, body = split_frame("R", payload)
            asyncio.ensure_future(sink.add(parse_mine_event(body)))
        elif frame_is(payload, MINE_MODULE, (MAP_STATE_CMD,)):
            header, body = split_frame("R", payload)
            tiles = parse_tiles(body)
            asyncio.ensure_future(state_sink.add(tiles))
            name_fetcher.queue(occupant_ids(tiles))
            asyncio.ensure_future(name_fetcher.flush(force=True))
        elif tile_sink is not None and frame_is(payload, MINE_MODULE, (TILE_DELTA_CMD,)):
            _header, body = split_frame("R", payload)
            tiles = parse_tiles(body)
            asyncio.ensure_future(tile_sink.add(tiles))
            name_fetcher.queue(occupant_ids(tiles))
            asyncio.ensure_future(name_fetcher.flush())
        elif frame_is(payload, PLAYER_MODULE, (PLAYER_BRIEF_LIST_CMD,)):
            _header, body = split_frame("R", payload)
            asyncio.ensure_future(brief_sink.add(parse_player_briefs(body)))
        elif frame_is(payload, GUILD_MODULE, (GUILD_BRIEF_LIST_CMD,)):
            header, body = split_frame("R", payload)
            info = parse_guild_brief(body)
            asyncio.ensure_future(guild_sink.add([{**info, "guild_id": pending_guild_requests.pop(header["seq"], None)}]))

    def on_close() -> None:
        if not is_game_socket:
            return
        print("[ws close] game socket dropped; reloading page in 10s...", flush=True)
        asyncio.ensure_future(reload_later(page))

    ws.on("framereceived", on_frame)
    ws.on("framesent", on_sent)
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
    parser.add_argument(
        "--dir",
        type=pathlib.Path,
        default=DEFAULT_DIR,
        help="Base dir for the raw JSONL streams (use a timestamped dir for one-off runs)",
    )
    parser.add_argument("--out", type=pathlib.Path, default=None, help="default <dir>/mine-events.jsonl")
    parser.add_argument("--state", type=pathlib.Path, default=None, help="default <dir>/mine-state.jsonl")
    parser.add_argument("--tiles", type=pathlib.Path, default=None, help="default <dir>/mine-tiles.jsonl")
    parser.add_argument("--briefs", type=pathlib.Path, default=None, help="default <dir>/player-briefs.jsonl")
    parser.add_argument("--guilds", type=pathlib.Path, default=None, help="default <dir>/guild-briefs.jsonl")
    parser.add_argument("--no-tiles", action="store_true", help="Skip tile-delta logging")
    parser.add_argument(
        "--no-fetch-names",
        action="store_true",
        help="Don't inject 0x0d/0x001f brief requests for occupant ids (passive only)",
    )
    parser.add_argument("--webhook", default=None, help="POST JSON for each fresh event batch")
    parser.add_argument(
        "--snapshot",
        action="store_true",
        help="Exit once one map state + all occupant names are captured (overrides --duration)",
    )
    parser.add_argument(
        "--snapshot-timeout",
        type=float,
        default=120.0,
        help="Hard time limit for --snapshot mode (default: 120s)",
    )
    parser.add_argument("--duration", type=float, default=None, help="Seconds to run (default: forever)")
    args = parser.parse_args()

    out_path = args.out or args.dir / "mine-events.jsonl"
    state_path = args.state or args.dir / "mine-state.jsonl"
    tiles_path = args.tiles or args.dir / "mine-tiles.jsonl"
    briefs_path = args.briefs or args.dir / "player-briefs.jsonl"
    guilds_path = args.guilds or args.dir / "guild-briefs.jsonl"

    profile_dir = pathlib.Path(args.profile)
    if not acquire_profile_lock(profile_dir, LOCK_FILENAME):
        raise SystemExit(1)
    sink = MineEventSink(out_path, args.webhook)
    state_sink = JsonlSink(state_path, "state")
    tile_sink = None if args.no_tiles else JsonlSink(tiles_path, "tile")
    brief_sink = JsonlSink(briefs_path, "brief")
    guild_sink = JsonlSink(guilds_path, "guild")
    name_fetcher = NameFetcher()
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
        await context.add_init_script(WS_SEND_HOOK_JS)  # covers pages opened later
        try:
            page = context.pages[0] if context.pages else await context.new_page()

            async def prepare(new_page: Page) -> None:
                await install_profile_popup_guard(new_page)
                # page-level init script: context-level ones don't reach the pre-existing
                # page of a persistent profile (seen 2026-10-23: hook never ran)
                await new_page.add_init_script(WS_SEND_HOOK_JS)

            page = await navigate_to_game(context, page, args.url, prepare_page=prepare)
            try:
                await page.evaluate(WS_SEND_HOOK_JS)  # belt & suspenders for the current doc
            except Exception as exc:  # noqa: BLE001 — frame not ready yet; heartbeats retrigger send hook
                print(f"[names] send-hook evaluate skipped: {exc}", flush=True)
            name_fetcher.page = page
            if args.no_fetch_names:
                name_fetcher.flush = lambda **_kw: asyncio.sleep(0)  # type: ignore[method-assign]
            guard_task = asyncio.create_task(install_game_core_frame_guard_after_delay(page))

            def hook(new_page: Page) -> None:
                name_fetcher.page = new_page
                new_page.on(
                    "websocket",
                    lambda ws: on_websocket(
                        ws, new_page, sink, state_sink, tile_sink, brief_sink, guild_sink, name_fetcher
                    ),
                )

            hook(page)
            context.on("page", hook)

            if args.snapshot:
                loop = asyncio.get_running_loop()
                deadline = loop.time() + args.snapshot_timeout
                print(f"[logger] snapshot mode — stop when state+names complete (max {args.snapshot_timeout:.0f}s)")
                last_retry = 0.0
                while loop.time() < deadline:
                    await asyncio.sleep(1)
                    if state_sink.count == 0:
                        continue  # map state not pushed yet
                    if args.no_fetch_names:
                        break  # state is all we wanted
                    if name_fetcher.pending:
                        now = loop.time()
                        if now - last_retry > 3.0:
                            last_retry = now
                            await name_fetcher.flush(force=True)
                        continue
                    if name_fetcher.settled():
                        break
                else:
                    print("[logger] snapshot timeout — exiting with partial data")
            elif args.duration:
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
            release_profile_lock(profile_dir, LOCK_FILENAME)
    done = f"[logger] done — {sink.new_count} new events -> {out_path}"
    done += f", {state_sink.count} state tiles -> {state_path}"
    if tile_sink is not None:
        done += f", {tile_sink.count} tile deltas -> {tiles_path}"
    done += f", {brief_sink.count} briefs -> {briefs_path}, {guild_sink.count} guild briefs -> {guilds_path}"
    print(done)


if __name__ == "__main__":
    asyncio.run(main())
