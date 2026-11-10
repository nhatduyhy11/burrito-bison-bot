"""Download a Cocos 2.4 asset bundle's config + all import (serialized json) files.

    python battle_sim/tools/fetch_bundle_imports.py battle 78b99 .tmp/battle_research/data/bundle_battle

Bundle hash = the <hash> in assets/<bundle>/config.<hash>.json (from the live page's
resource list). Native files (png/audio) are not fetched.
"""
import concurrent.futures as cf
import json
import sys
import urllib.request
from pathlib import Path

HOST = "https://hauntedroomvnh5.joynetgame.com/assets/"
B64 = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"


def decode_uuid(u: str) -> str:
    """Cocos compressed uuid (22 chars) -> 36-char uuid. Others returned as-is."""
    if len(u) != 22:
        return u
    hexs = u[:2]
    bits = "".join(f"{B64.index(c):06b}" for c in u[2:])
    hexs += "".join(f"{int(bits[i:i + 4], 2):x}" for i in range(0, 120, 4))
    return f"{hexs[:8]}-{hexs[8:12]}-{hexs[12:16]}-{hexs[16:20]}-{hexs[20:]}"


def get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def main() -> None:
    bundle, ver, out = sys.argv[1], sys.argv[2], Path(sys.argv[3])
    out.mkdir(parents=True, exist_ok=True)
    cfg_raw = get(f"{HOST}{bundle}/config.{ver}.json")
    (out / "config.json").write_bytes(cfg_raw)
    cfg = json.loads(cfg_raw)
    uuids = [decode_uuid(u) for u in cfg["uuids"]]
    imp = cfg.get("versions", {}).get("import", [])
    jobs = []
    for i in range(0, len(imp), 2):
        key, h = imp[i], imp[i + 1]
        name = uuids[key] if isinstance(key, int) else key  # pack ids are strings
        jobs.append((name, f"{HOST}{bundle}/import/{name[:2]}/{name}.{h}.json"))

    def fetch(job):
        name, url = job
        dest = out / "import" / f"{name}.json"
        if dest.exists():
            return 0
        dest.parent.mkdir(parents=True, exist_ok=True)
        data = get(url)
        dest.write_bytes(data)
        return len(data)

    with cf.ThreadPoolExecutor(8) as ex:
        total = sum(ex.map(fetch, jobs))
    print(f"{bundle}: {len(jobs)} import files, {total / 1e6:.1f} MB new -> {out}")


if __name__ == "__main__":
    main()
