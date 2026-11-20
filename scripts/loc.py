"""Line-count report for project source files.

Writes two reports, sorted by line count (high to low), listing only files
above the threshold (default 120 lines):
  - loc_py.<timestamp>.txt     : *.py
  - loc_web_md.<timestamp>.txt : *.js, *.css, *.md
Reports land next to this script (scripts/) and are gitignored.

Files come from git (tracked + untracked-not-ignored), so .venv, .tmp,
node_modules etc. are skipped automatically. Line count = physical lines.

Usage:
  python scripts/loc.py                 # reports -> scripts/
  python scripts/loc.py --min 200
"""
from __future__ import annotations

import argparse
import subprocess
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
GROUPS = {
    "loc_py": (".py",),
    "loc_web_md": (".js", ".css", ".md"),
}


def list_files() -> list[str]:
    out = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=ROOT, capture_output=True, check=True,
    ).stdout.decode("utf-8")
    return [p for p in out.split("\0") if p]


def count_lines(path: Path) -> int:
    with path.open("rb") as f:
        data = f.read()
    if not data:
        return 0
    return data.count(b"\n") + (0 if data.endswith(b"\n") else 1)


def write_report(dest: Path, rows: list[tuple[str, str, int]], min_loc: int, exts) -> None:
    rows.sort(key=lambda r: (-r[2], r[1], r[0]))
    w_name = max([len("file")] + [len(r[0]) for r in rows])
    w_dir = max([len("folder")] + [len(r[1]) for r in rows])
    lines = [
        f"# {', '.join('*' + e for e in exts)} | > {min_loc} loc | {len(rows)} files",
        f"{'file':<{w_name}}  {'folder':<{w_dir}}  loc",
        f"{'-' * w_name}  {'-' * w_dir}  -----",
    ]
    lines += [f"{n:<{w_name}}  {d:<{w_dir}}  {c}" for n, d, c in rows]
    dest.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--min", type=int, default=120, help="only list files with more lines than this")
    args = ap.parse_args()

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    files = list_files()

    for report, exts in GROUPS.items():
        rows = []
        for rel in files:
            if not rel.lower().endswith(exts):
                continue
            path = ROOT / rel
            if not path.is_file():  # deleted in working tree
                continue
            n = count_lines(path)
            if n > args.min:
                folder = str(Path(rel).parent).replace("\\", "/")
                rows.append((Path(rel).name, "." if folder == "." else folder, n))
        dest = HERE / f"{report}.{stamp}.txt"
        write_report(dest, rows, args.min, exts)
        print(f"{dest}  ({len(rows)} files)")


if __name__ == "__main__":
    main()
