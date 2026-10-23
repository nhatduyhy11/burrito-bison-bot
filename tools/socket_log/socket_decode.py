"""Decode captured Haunted Room WebSocket frames (offline, over a capture dir).

Framing observed on wss://mg-sea-entry.bighost.games/ws:
    request  = [len:2 BE][module:1][cmd:2 BE][seq:1][protobuf body]
    response = [len:2 BE][seq:1][01][01][module:1][cmd:2 BE (=req.cmd+1)][00][protobuf body]
Send/receive frames live in ``<capture_dir>/frames`` with an ``index.jsonl``.

Usage:
    uv run python tools/socket_log/socket_decode.py .tmp/socket-capture/run-mine1 271
    uv run python tools/socket_log/socket_decode.py .tmp/socket-capture/run-mine1 all --dir R
    uv run python tools/socket_log/socket_decode.py .tmp/socket-capture/run-mine1 grep:AEMin
    uv run python tools/socket_log/socket_decode.py .tmp/socket-capture/run-mine1 mine-events
    uv run python tools/socket_log/socket_decode.py .tmp/socket-capture/run-mine1 mine-state > state.json
"""

import argparse
import json
import pathlib
import struct
import sys


def read_varint(buf: bytes, pos: int) -> tuple[int, int]:
    result = 0
    shift = 0
    while True:
        b = buf[pos]
        pos += 1
        result |= (b & 0x7F) << shift
        if not b & 0x80:
            return result, pos
        shift += 7


def is_probably_text(buf: bytes) -> bool:
    if not buf:
        return False
    try:
        text = buf.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return sum(ch.isprintable() or ch.isspace() for ch in text) / len(text) > 0.9


def decode_proto(buf: bytes, depth: int = 0) -> list[tuple]:
    """Walk protobuf wire format without a schema; returns [(field, wire, value)]."""
    fields = []
    pos = 0
    try:
        while pos < len(buf):
            key, pos = read_varint(buf, pos)
            field, wire = key >> 3, key & 7
            if field == 0:
                return []  # invalid key; caller falls back to raw bytes
            if wire == 0:
                value, pos = read_varint(buf, pos)
            elif wire == 1:
                if pos + 8 > len(buf):
                    return []
                value = struct.unpack("<Q", buf[pos:pos + 8])[0]
                pos += 8
            elif wire == 2:
                length, pos = read_varint(buf, pos)
                if pos + length > len(buf):
                    return []
                value = buf[pos:pos + length]
                pos += length
            elif wire == 5:
                if pos + 4 > len(buf):
                    return []
                value = struct.unpack("<I", buf[pos:pos + 4])[0]
                pos += 4
            else:
                return []
            fields.append((field, wire, value))
    except (IndexError, struct.error):
        return []
    return fields


def render(value, depth: int, lines: list[str], path: str) -> None:
    pad = "  " * depth
    if isinstance(value, (int, float)):
        extra = ""
        if 1_700_000_000 <= value <= 2_000_000_000:
            import datetime
            extra = f"  # {datetime.datetime.fromtimestamp(value, datetime.timezone.utc):%Y-%m-%d %H:%M:%S}Z"
        lines.append(f"{pad}{path}: {value}{extra}")
    elif isinstance(value, bytes):
        if is_probably_text(value):
            lines.append(f'{pad}{path}: "{value.decode("utf-8")}"')
        else:
            nested = decode_proto(value)
            if nested:
                lines.append(f"{pad}{path}: {{")
                for field, wire, sub in nested:
                    render(sub, depth + 1, lines, f"f{field}(w{wire})")
                lines.append(f"{pad}}}")
            else:
                lines.append(f"{pad}{path}: {value.hex()}")
    else:
        lines.append(f"{pad}{path}: {value!r}")


def split_frame(direction: str, raw: bytes) -> tuple[dict, bytes]:
    (length,) = struct.unpack(">H", raw[:2])
    body = raw[2:2 + length]
    if direction == "S":
        header = {"module": body[0], "cmd": int.from_bytes(body[1:3], "big"), "seq": body[3]}
        return header, body[4:]
    header = {
        "seq": body[0],
        "flags": body[1:3].hex(),
        "module": body[3],
        "cmd": int.from_bytes(body[4:6], "big"),
        "status": body[6],
    }
    return header, body[7:]


MINE_EVENT_TYPE = 150
BROADCAST_MODULE = 0x13
BROADCAST_PUSH_CMD = 0x0004
SEASON_MODULE = 0x48
MAP_STATE_CMD = 0x0002
SEASON_INFO_CMD = 0x0014
MINE_HISTORY_CMD = 0x001B


def read_packed_varints(buf: bytes) -> list[int]:
    """All varints in a packed repeated field."""
    values, pos = [], 0
    while pos < len(buf):
        value, pos = read_varint(buf, pos)
        values.append(value)
    return values


def extract_mine_state(capture_dir: pathlib.Path) -> dict:
    """Dump the full guild-mine state (module 0x48) from a capture dir.

    The client requests all three at login, before any navigation:
      0x48/0x0001 -> 0x0002  full map state (summary + repeated tile f2)
      0x48/0x0013 -> 0x0014  season window + packed season tile-id list
      0x48/0x001a -> 0x001b  mine history feed: {f2: JSON string, f1: type code} —
                             type 1 = "[pos, value, ts]", type 4 = "[player_id, pos, action, ts]"
    Tile entry: f1=pos (map*1000+tile), f2/f3=type-ish (1-7 / 1-9),
    f4=0 or 513xxxx, f7=repeated {f1: action, f2: count} season stats,
    f5=repeated slot {f1: player id, f2: slot no, f5: packed [start, end?]}
    where timestamps only appear on slots being mined right now.
    """
    import datetime

    def fmt_ts(value):
        if not value:
            return None
        return datetime.datetime.fromtimestamp(value, datetime.timezone.utc).isoformat()

    frames: dict[int, bytes] = {}
    for line in (capture_dir / "index.jsonl").read_text().splitlines():
        record = json.loads(line)
        if record.get("dir") != "R" or not record.get("n"):
            continue
        raw = (capture_dir / record["file"]).read_bytes()
        try:
            header, payload = split_frame("R", raw)
        except (IndexError, struct.error):
            continue
        if header["module"] != SEASON_MODULE or header["status"] != 0:
            continue
        # each cmd arrives once per session; keep the largest body
        if header["cmd"] not in frames or len(payload) > len(frames[header["cmd"]]):
            frames[header["cmd"]] = payload

    state: dict = {"season": None, "map_state": None, "history": []}

    if SEASON_INFO_CMD in frames:
        info: dict = {}
        for field, _wire, value in decode_proto(frames[SEASON_INFO_CMD]):
            if field == 3 and isinstance(value, bytes):
                info["tile_ids"] = read_packed_varints(value)
            elif field == 5:
                info["start"] = fmt_ts(value)
            elif field == 4:
                info["end"] = fmt_ts(value)
            elif field in (1, 2):
                info[f"f{field}"] = value
        state["season"] = info

    if MAP_STATE_CMD in frames:
        summary = None
        tiles = []
        for field, _wire, value in decode_proto(frames[MAP_STATE_CMD]):
            if field == 3 and isinstance(value, bytes):
                sub = {f: v for f, _w, v in decode_proto(value)}
                summary = {
                    "f1_pos": sub.get(1),
                    "f2": sub.get(2),
                    "f4": sub.get(4),
                    "f5": sub.get(5),
                    "f8": sub.get(8),
                    "f9": {f: v for f, _w, v in decode_proto(sub[9])} if isinstance(sub.get(9), bytes) else sub.get(9),
                    "f6_time": fmt_ts(sub.get(6)),
                    "f7_time": fmt_ts(sub.get(7)),
                    "f10_time": fmt_ts(sub.get(10)),
                }
            elif field == 2 and isinstance(value, bytes):
                tile: dict = {"pos": None, "slots": [], "stats": {}}
                for f, _w, v in decode_proto(value):
                    if f == 1:
                        tile["pos"] = v
                    elif f in (2, 3, 4, 8, 9):
                        tile[f"f{f}"] = v
                    elif f == 6 and isinstance(v, bytes):
                        tile["f6"] = {sf: sv for sf, _sw, sv in decode_proto(v)}
                    elif f == 7 and isinstance(v, bytes):
                        sub = {sf: sv for sf, _sw, sv in decode_proto(v)}
                        tile["stats"][sub.get(1)] = sub.get(2)
                    elif f == 5 and isinstance(v, bytes):
                        slot: dict = {"slot": None, "player_id": None, "times": []}
                        for sf, _sw, sv in decode_proto(v):
                            if sf == 1:
                                slot["player_id"] = sv
                            elif sf == 2:
                                slot["slot"] = sv
                            elif sf == 3:
                                slot["f3"] = sv
                            elif sf == 5:
                                slot["times"] = [fmt_ts(x) for x in read_packed_varints(sv)] if sv else []
                        tile["slots"].append(slot)
                tile["map"], tile["tile_idx"] = divmod(tile["pos"], 1000)
                tiles.append(tile)
        state["map_state"] = {"summary": summary, "tiles": tiles}

    if MINE_HISTORY_CMD in frames:
        events = []
        for field, _wire, value in decode_proto(frames[MINE_HISTORY_CMD]):
            if field != 2 or not isinstance(value, bytes):
                continue
            # each entry = {f2: JSON string, f1: entry type (1 or 4)}
            entry_type = None
            args = None
            for sf, _sw, sv in decode_proto(value):
                if isinstance(sv, bytes):
                    try:
                        args = json.loads(sv.decode("utf-8"))
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        pass
                else:
                    entry_type = sv
            if not isinstance(args, list):
                continue
            if len(args) >= 4:
                events.append(
                    {
                        "type": entry_type,
                        "player_id": args[0],
                        "pos": args[1],
                        "action": args[2],
                        "time": fmt_ts(args[3]),
                    }
                )
            elif len(args) == 3:
                events.append(
                    {"type": entry_type, "pos": args[0], "value": args[1], "time": fmt_ts(args[2])}
                )
        state["history"] = events

    return state


def extract_mine_events(capture_dir: pathlib.Path) -> list[dict]:
    """Pull guild-mine history events (broadcast type 150) from a capture dir.

    Feed arrives as server pushes of module 0x13 cmd 0x0004 right after login;
    each entry: f1=msg id, f3=unix ts, f7=type (150 = mine), f9=template args
    like '[["AEMìn"],[28000],[5047],[9001]]' → player, template, pos, action.
    """
    import datetime

    events = []
    for line in (capture_dir / "index.jsonl").read_text().splitlines():
        record = json.loads(line)
        if record.get("dir") != "R" or not record.get("n"):
            continue
        raw = (capture_dir / record["file"]).read_bytes()
        try:
            header, payload = split_frame("R", raw)
        except (IndexError, struct.error):
            continue
        if header["module"] != BROADCAST_MODULE or header["cmd"] != BROADCAST_PUSH_CMD:
            continue
        for field, wire, value in decode_proto(payload):
            if not isinstance(value, bytes):
                continue
            entry = {}
            args_text = None
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
                        entry[3], datetime.timezone.utc
                    ).isoformat(),
                    "player": args[0][0] if args and args[0] else None,
                    "pos": args[2][0] if len(args) > 2 and args[2] else None,
                    "action": args[3][0] if len(args) > 3 and args[3] else None,
                    "raw_args": args,
                }
            )
    events.sort(key=lambda e: (e["time"], e["id"] or 0))
    return events


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture_dir", type=pathlib.Path)
    parser.add_argument("selector", help="frame number, 'all', or 'grep:STRING'")
    parser.add_argument("--dir", choices=("S", "R"), default="R", help="Direction for 'all'")
    args = parser.parse_args()

    # player/guild names contain CJK — never die on the Windows console codepage
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    rows = [
        json.loads(line)
        for line in (args.capture_dir / "index.jsonl").read_text().splitlines()
        if line.strip()
    ]
    frames = {
        r["n"]: r
        for r in rows
        if r["dir"] in "SR"
    }

    selected = []
    if args.selector == "mine-events":
        print(json.dumps(extract_mine_events(args.capture_dir), ensure_ascii=False, indent=2))
        return
    if args.selector == "mine-state":
        print(json.dumps(extract_mine_state(args.capture_dir), ensure_ascii=False, indent=1))
        return
    if args.selector.startswith("grep:"):
        needle = args.selector[5:].encode()
        for n, r in frames.items():
            if needle in pathlib.Path(args.capture_dir / r["file"]).read_bytes():
                selected.append(n)
    elif args.selector == "all":
        selected = [n for n, r in frames.items() if r["dir"] == args.dir]
    else:
        selected = [int(args.selector)]

    for n in sorted(selected):
        r = frames[n]
        raw = pathlib.Path(args.capture_dir / r["file"]).read_bytes()
        header, payload = split_frame(r["dir"], raw)
        print(f'--- #{n:03d} t={r["t"]}ms dir={r["dir"]} size={r["size"]}B')
        print(f"    header={header} payload={len(payload)}B")
        lines: list[str] = []
        for field, wire, value in decode_proto(payload):
            render(value, 1, lines, f"f{field}(w{wire})")
        print("\n".join(lines) or "    <unparseable>")
        print()


if __name__ == "__main__":
    main()
