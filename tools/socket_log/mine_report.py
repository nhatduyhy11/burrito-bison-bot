"""Second-pass aggregator: raw mine_logger JSONL -> sector/mine/point/users report.

Reads from --dir (default .tmp/mine-events, as written by mine_logger.py):
  mine-state.jsonl     login snapshots of the full map (0x48/0x0002), one tile per line
  mine-tiles.jsonl     live tile deltas (0x48/0x0008), applied on top of the last snapshot
  player-briefs.jsonl  id -> name / guild (0x0d/0x0020)
  guild-briefs.jsonl   guild id -> name (0x24/0x0036)

Rebuilds the latest world (snapshot + deltas in logged_at order), groups tiles into
mines of 4 consecutive static ids per sector, and writes mine-report.json plus a
readable tree on stdout. Sector 1 (the flat 124-slot tile) is skipped. A player
sits in exactly one slot — duplicates are collected under "warnings".

Usage:
    uv run python tools/socket_log/mine_report.py
    uv run python tools/socket_log/mine_report.py --dir .tmp/mine-events --json out.json
"""

import argparse
import collections
import datetime
import json
import pathlib
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # player/guild names are CJK-safe here

SECTOR_MIN, SECTOR_MAX = 2, 7  # sector 1 = single 124-slot mega tile, out of scope
SLOTS_PER_POINT = 15
FULL_SNAPSHOT_MIN_TILES = 32  # a real login snapshot carries all 65 tiles; partial pushes don't
SECTOR_NAMES = {
    1: "Khu Mỏ Nguồn Cỏi",
    2: "Mỏ Đường Tắt",
    3: "Mỏ Thanh Tịnh",
    4: "Mỏ Hoang Vu",
    5: "Mỏ Đá Cháy",
    6: "Mỏ Gió Môn",
    7: "Mỏ Huyền Quang",
}
STATE_FILE = "mine-state.jsonl"
TILE_FILE = "mine-tiles.jsonl"
BRIEF_FILE = "player-briefs.jsonl"
GUILD_FILE = "guild-briefs.jsonl"


def read_jsonl(path: pathlib.Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def load_world(directory: pathlib.Path) -> tuple[dict[int, dict], str | None]:
    """Replay state snapshots + deltas in logged_at order -> {pos: tile}.

    0x48/0x0002 arrives both as a full 65-tile snapshot at login AND as small
    partial updates mid-session — rows of one frame share logged_at, so they are
    grouped into bursts; only a full-sized burst resets the map.
    """
    bursts: list[tuple[str, str, list[dict]]] = []
    for filename, kind in ((STATE_FILE, "state"), (TILE_FILE, "delta")):
        grouped: dict[str, list[dict]] = collections.OrderedDict()
        for row in read_jsonl(directory / filename):
            grouped.setdefault(row["logged_at"], []).append(row)
        bursts += [(ts, kind, rows) for ts, rows in grouped.items()]
    bursts.sort(key=lambda item: item[0])  # ISO stamps sort lexicographically
    world: dict[int, dict] = {}
    for _ts, kind, rows in bursts:
        if kind == "state" and len(rows) >= FULL_SNAPSHOT_MIN_TILES:
            world = {}  # login snapshot replaces the whole map
        for row in rows:
            world[row["pos"]] = row
    return world, (bursts[-1][0] if bursts else None)


def group_mines(world: dict[int, dict]) -> dict[int, list[list[dict]]]:
    """Tiles -> per sector, mines of 4 tiles in ascending static-id order = point 1-4.

    Static ids run consecutively across whole sectors (2002-2021 = 5 mines), so
    mines are NOT id-gap separated — the chunk of 4 IS the mine. The level
    pattern confirms the cut: points 1-3 share the lower level, point 4 is the
    upper one (verified on all 16 mines, incl. the scrambled sector 4/5 ids).
    """
    by_sector: dict[int, list[dict]] = collections.defaultdict(list)
    for tile in world.values():
        if tile.get("sector"):
            by_sector[tile["sector"]].append(tile)
    mines: dict[int, list[list[dict]]] = {}
    for sector, tiles in by_sector.items():
        tiles.sort(key=lambda t: t["pos"])
        mines[sector] = [tiles[i : i + 4] for i in range(0, len(tiles), 4)]
    return mines


def build_report(directory: pathlib.Path) -> dict:
    world, as_of = load_world(directory)
    mines = group_mines(world)

    names: dict[int, dict] = {}  # player id -> {name, guild_id, guild_name}; latest brief wins
    guilds: dict[int, str] = {}  # guild id -> name
    for brief in read_jsonl(directory / BRIEF_FILE):
        if brief.get("id"):
            names[brief["id"]] = brief
            # every brief carries the player's guild (f11: id + name) — free claim-name source
            if brief.get("guild_id") and brief.get("guild_name"):
                guilds.setdefault(brief["guild_id"], brief["guild_name"])
    for brief in read_jsonl(directory / GUILD_FILE):
        if brief.get("guild_id") and brief.get("name"):
            guilds[brief["guild_id"]] = brief["name"]

    warnings: list[str] = []
    seen: dict[int, list[str]] = collections.defaultdict(list)
    unnamed: set[int] = set()

    sectors_out = []
    for sector in sorted(s for s in mines if SECTOR_MIN <= s <= SECTOR_MAX):
        sector_out = {"sector": sector, "name": SECTOR_NAMES.get(sector), "mines": []}
        for mine_no, run in enumerate(mines[sector], 1):
            if len(run) != 4:
                warnings.append(
                    f"s{sector}/m{mine_no}: expected 4 consecutive tiles, got {len(run)}: {[t['pos'] for t in run]}"
                )
            elif not (
                run[0]["level"] == run[1]["level"] == run[2]["level"]
                and (run[3]["level"] or 0) > (run[0]["level"] or 0)
            ):
                warnings.append(
                    f"s{sector}/m{mine_no}: unexpected level pattern "
                    f"{[t['level'] for t in run]} (expected 3x lower + 1x upper)"
                )
            points_out = []
            for point_no, tile in enumerate(run, 1):
                users = []
                for slot_no, player_id in sorted(
                    tile["occupied"].items(), key=lambda kv: int(kv[0])
                ):
                    location = f"s{sector}/m{mine_no}/p{point_no}/slot{slot_no}"
                    seen[player_id].append(location)
                    info = names.get(player_id)
                    if info is None:
                        unnamed.add(player_id)
                    users.append(
                        {
                            "slot": int(slot_no),
                            "id": player_id,
                            "name": info.get("name") if info else None,
                            "guild": info.get("guild_name") if info else None,
                        }
                    )
                claim_id = tile.get("claim")
                claim = None
                if claim_id:
                    claim = {"guild_id": claim_id, "guild_name": guilds.get(claim_id)}
                points_out.append(
                    {
                        "point": point_no,
                        "tile": tile["pos"],
                        "level": tile.get("level"),
                        "claim": claim,
                        "occupied": len(users),
                        "slots": SLOTS_PER_POINT,
                        "users": users,
                    }
                )
            sector_out["mines"].append(
                {
                    "mine": mine_no,
                    "tiles": [t["pos"] for t in run],
                    "points": points_out,
                }
            )
        sectors_out.append(sector_out)

    for player_id, locations in seen.items():
        if len(locations) > 1:
            warnings.append(f"player {player_id} sits in {len(locations)} slots: {', '.join(locations)}")
    if unnamed:
        warnings.append(
            f"{len(unnamed)} players without a name (no brief captured): "
            + ", ".join(str(i) for i in sorted(unnamed))
        )

    return {
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "as_of": as_of,
        "sectors": sectors_out,
        "warnings": warnings,
    }


def print_tree(report: dict) -> None:
    total_players = {
        u["id"] for s in report["sectors"] for m in s["mines"] for p in m["points"] for u in p["users"]
    }
    print(f"Báo cáo khu mỏ (tại {report['as_of']}) — {len(total_players)} người trong {len(total_players)} slot")
    for sector in report["sectors"]:
        print(f"\nSector {sector['sector']} — {sector['name']}")
        for mine in sector["mines"]:
            lo, hi = mine["tiles"][0], mine["tiles"][-1]
            print(f"  Mỏ {mine['mine']} (tile {lo}–{hi})")
            for point in mine["points"]:
                claim = point["claim"]
                claim_text = (
                    f"claim {claim['guild_name'] or '?'} ({claim['guild_id']})"
                    if claim
                    else "unclaimed"
                )
                print(f"    Điểm {point['point']} · tile {point['tile']} · lv{point['level']} · {claim_text} · {point['occupied']}/{point['slots']} người")
                for user in point["users"]:
                    name = user["name"] or "(chưa có tên)"
                    guild = f" [{user['guild']}]" if user["guild"] else ""
                    print(f"      slot {user['slot']:>4}: {user['id']}  {name}{guild}")
    if report["warnings"]:
        print("\nCảnh báo:")
        for warning in report["warnings"]:
            print(f"  - {warning}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dir", type=pathlib.Path, default=pathlib.Path(".tmp/mine-events"))
    parser.add_argument("--json", type=pathlib.Path, default=None, help="Output path (default <dir>/mine-report.json)")
    args = parser.parse_args()

    report = build_report(args.dir)
    out_path = args.json or (args.dir / "mine-report.json")
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[report] {out_path}")
    print_tree(report)


if __name__ == "__main__":
    main()
