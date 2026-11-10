"""Extract Tiled maps / tilesets (cc.JsonAsset) from the downloaded `battle` bundle pack.

    python battle_sim/tools/extract_maps.py .tmp/battle_research/data/bundle_battle .tmp/battle_research/data/maps

Writes <name>.json for every map (has layers+tilesets) and tileset (has tiles).
Duplicate names (e.g. brush/_empty/brush_xx vs brush/xx/brush_xx): the one with
more tiles wins; the other is kept as <name>.<n>.json.
"""
import json
import sys
from pathlib import Path


def main() -> None:
    src, out = Path(sys.argv[1]), Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    found = {}
    for f in (src / "import").glob("*.json"):
        data = json.loads(f.read_text(encoding="utf8"))
        if not (isinstance(data, list) and len(data) > 5 and isinstance(data[5], list)):
            continue
        for entry in data[5]:
            try:
                name, payload = entry[0][0][1], entry[0][0][2]
            except (TypeError, IndexError, KeyError):
                continue
            if not isinstance(payload, dict):
                continue
            if "layers" in payload and "tilesets" in payload:
                kind, size = "map", 0
            elif "tiles" in payload:
                kind, size = "tileset", len(payload.get("tiles") or [])
            else:
                continue
            found.setdefault(name, []).append((size, kind, payload))
    for name, items in sorted(found.items()):
        items.sort(key=lambda t: -t[0])
        for i, (_size, kind, payload) in enumerate(items):
            fn = f"{name}.json" if i == 0 else f"{name}.{i}.json"
            (out / fn).write_text(json.dumps(payload, ensure_ascii=False), encoding="utf8")
    print(f"{sum(len(v) for v in found.values())} assets -> {out}")


if __name__ == "__main__":
    main()
