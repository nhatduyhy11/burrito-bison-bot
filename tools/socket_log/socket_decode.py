"""Decode captured Haunted Room WebSocket frames (offline, over a capture dir).

Framing observed on wss://mg-sea-entry.bighost.games/ws:
    request  = [len:2 BE][module:1][cmd:2 BE][seq:1][protobuf body]
    response = [len:2 BE][seq:1][01][01][module:1][cmd:2 BE (=req.cmd+1)][00][protobuf body]
Send/receive frames live in ``<capture_dir>/frames`` with an ``index.jsonl``.

Usage:
    uv run python tools/socket_log/socket_decode.py .tmp/socket-capture/run-mine1 271
    uv run python tools/socket_log/socket_decode.py .tmp/socket-capture/run-mine1 all --dir R
    uv run python tools/socket_log/socket_decode.py .tmp/socket-capture/run-mine1 grep:AEMin
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
