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
from socket_decode import decode_proto, encode_varint, read_packed_varints, split_frame  # noqa: E402

from navigation import navigate_to_game  # noqa: E402
from page_guards import (  # noqa: E402
    install_game_core_frame_guard_after_delay,
    install_profile_popup_guard,
)

sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # cp1252 consoles choke on player names

BROADCAST_MODULE = 0x13
BROADCAST_PUSH_CMDS = (0x0004, 0x0007)  # login replay + real-time pushes
MINE_EVENT_TYPE = 150
MINE_MODULE = 0x48
MAP_STATE_CMD = 0x0002  # full snapshot at login
TILE_DELTA_CMD = 0x0008  # live single-tile pushes
PLAYER_MODULE = 0x0D
PLAYER_BRIEF_CMD = 0x001F  # request: packed player ids
PLAYER_BRIEF_LIST_CMD = 0x0020  # response: repeated brief
GUILD_MODULE = 0x24
GUILD_BRIEF_CMD = 0x0035  # request: one guild id
GUILD_BRIEF_LIST_CMD = 0x0036  # response: f3 = guild info; guild id only via request seq

SECTOR_MIN, SECTOR_MAX = 2, 7  # sector 1 is the flat 124-slot tile — out of scope
BRIEF_CHUNK = 60  # client batches ~59 ids per request
INJECT_SEQ = 0xF0  # seq byte for injected requests; server echoes it, client ignores strays
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


def parse_tile(value: bytes) -> dict:
    """One tile — login state (0x48/0x0002) and delta (0x48/0x0008) share the layout.

    f1=pos (static server table id), f2=sector 1-7, f3=point level 1-9,
    f4=claiming guild id (5XX00YY) or 0, f5=slot {f1: player id, f2: slot no} —
    player id 0 means the slot is free.
    """
    tile: dict = {
        "pos": None,
        "sector": None,
        "level": None,
        "claim": None,
        "occupied": {},
        "free": [],
    }
    for f, _wire, v in decode_proto(value):
        if f == 1 and not isinstance(v, bytes):
            tile["pos"] = v
        elif f == 2 and not isinstance(v, bytes):
            tile["sector"] = v
        elif f == 3 and not isinstance(v, bytes):
            tile["level"] = v
        elif f == 4 and not isinstance(v, bytes):
            tile["claim"] = v or None
        elif f == 5 and isinstance(v, bytes):
            slot = {sf: sv for sf, _sw, sv in decode_proto(v)}
            player_id = slot.get(1) or 0
            slot_no = slot.get(2)
            if player_id and slot_no is not None:
                tile["occupied"][str(slot_no)] = player_id
            elif slot_no is not None:
                tile["free"].append(slot_no)
    return tile


def parse_tiles(payload: bytes) -> list[dict]:
    """Repeated f2 = tile snapshots (works for both map state and tile deltas)."""
    return [parse_tile(v) for f, _wire, v in decode_proto(payload) if f == 2 and isinstance(v, bytes)]


def parse_player_briefs(payload: bytes) -> list[dict]:
    """0x0d/0x0020: repeated f2 = brief {f1: id, f2: name, f4: power, f9: server,
    f11: guild {f1: guild id, f2: guild name}}."""
    briefs = []
    for field, _wire, value in decode_proto(payload):
        if field != 2 or not isinstance(value, bytes):
            continue
        sub = {f: v for f, _w, v in decode_proto(value)}
        guild = {g: gv for g, _gw, gv in decode_proto(sub[11])} if isinstance(sub.get(11), bytes) else {}
        name = sub.get(2)
        guild_name = guild.get(2)
        briefs.append(
            {
                "id": sub.get(1),
                "name": name.decode("utf-8", "replace") if isinstance(name, bytes) else None,
                "power": sub.get(4),
                "server": sub.get(9),
                "guild_id": guild.get(1) or None,
                "guild_name": guild_name.decode("utf-8", "replace") if isinstance(guild_name, bytes) else None,
            }
        )
    return briefs


def parse_guild_brief(payload: bytes) -> dict:
    """0x24/0x0036: f3 = {f2: name, f3: description, f10: member count}."""
    sub = {f: v for f, _w, v in decode_proto(payload)}
    info = {f: v for f, _w, v in decode_proto(sub[3])} if isinstance(sub.get(3), bytes) else {}
    name = info.get(2)
    description = info.get(3)
    return {
        "name": name.decode("utf-8", "replace") if isinstance(name, bytes) else None,
        "members": info.get(10),
        "description": description.decode("utf-8", "replace") if isinstance(description, bytes) else None,
    }


def build_brief_request(ids: list[int]) -> bytes:
    """0x0d/0x001f request frame: [len:2][module:1][cmd:2][seq:1][f1 = packed ids]."""
    packed = b"".join(encode_varint(i) for i in ids)
    body = b"\x0a" + encode_varint(len(packed)) + packed
    return struct.pack(">HBHB", 4 + len(body), PLAYER_MODULE, PLAYER_BRIEF_CMD, INJECT_SEQ) + body


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


def frame_is(raw: bytes, module: int, cmds: tuple[int, ...]) -> bool:
    try:
        header, _payload = split_frame("R", raw)
    except (IndexError, struct.error):
        return False
    return header["module"] == module and header["cmd"] in cmds


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
