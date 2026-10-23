"""Mine protocol layer: module/cmd constants, frame decoders, request encoder.

Pure bytes -> dict functions shared by mine_logger.py (live capture) and any
future decode work (e.g. streak/debuff). No I/O, no playwright, no asyncio —
safe to unit-test against captured frame bytes.
"""

import datetime
import json
import struct
from typing import Optional

from socket_decode import decode_proto, encode_varint, read_packed_varints, split_frame

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
INJECT_SEQ = 0xF0  # seq byte for injected requests; server echoes it, client ignores strays


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


def frame_is(raw: bytes, module: int, cmds: tuple[int, ...]) -> bool:
    try:
        header, _payload = split_frame("R", raw)
    except (IndexError, struct.error):
        return False
    return header["module"] == module and header["cmd"] in cmds
