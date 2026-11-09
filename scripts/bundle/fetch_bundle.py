"""Download the Haunted Room game code bundle and split it into one file per module.

The game is Cocos Creator 2.x; all game code lives in ``assets/main/index.<hash>.js``
(browserify-style: ``window.__require=function e(t,o,i){...}({Name:[fn,deps],...},{},[entries])``).
Splitting is done by evaluating the bundle in a blank browser page with the loader
swapped for a capture stub, so module boundaries come from the JS engine, not a regex.

Output (default ``.tmp/bundle/<bundle-name>/``):
  <bundle-name>.js         raw bundle as served
  modules/<Name>.js        one file per named module (``fn.toString()``)
  modules/_lib/<id>.js     numeric-id modules (npm libs pulled in by browserify)
  index.json               {name: {file, deps, size}} + source URL / fetch time

Usage (from repo root):
  uv run python scripts/bundle/fetch_bundle.py                 # boot game, fetch latest
  uv run python scripts/bundle/fetch_bundle.py --bundle path/to/index.xxx.js
"""

import argparse
import asyncio
import json
import re
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

from playwright.async_api import async_playwright

GAME_URL = "https://hauntedroomvnh5.joynetgame.com/"
BUNDLE_RE = re.compile(r"/assets/main/index\.[0-9a-f]+\.js$")
LOADER_RE = re.compile(r"^window\.__require=function e\(t,o,i\)\{.{0,2000}?return n\}\(", re.S)
CAPTURE_JS = "window.__bundleCapture=function(t){window.__bundleModules=t;return function(){}};"
DUMP_JS = """() => {
  const m = window.__bundleModules;
  if (!m) throw new Error('capture stub was not called');
  return Object.keys(m).map(k => [k, m[k][0].toString(), m[k][1] || {}]);
}"""
SAFE_RE = re.compile(r"[^\w.\-]")


async def find_bundle_url(browser, timeout_s: float) -> str:
    page = await browser.new_page()
    found = asyncio.get_running_loop().create_future()

    def on_response(resp):
        if BUNDLE_RE.search(resp.url.split("?")[0]) and not found.done():
            found.set_result(resp.url)

    page.on("response", on_response)
    try:
        await page.goto(GAME_URL, wait_until="commit", timeout=timeout_s * 1000)
        return await asyncio.wait_for(found, timeout_s)
    finally:
        await page.close()


def download(url: str, dest: Path) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=120) as r:
        dest.write_bytes(r.read())


async def split_modules(browser, source: str) -> list:
    m = LOADER_RE.match(source)
    if not m:
        raise SystemExit("Loader prefix not recognised; bundle format changed?")
    patched = CAPTURE_JS + "window.__bundleCapture(" + source[m.end():]
    page = await browser.new_page()
    try:
        await page.goto("about:blank")
        await page.add_script_tag(content=patched)
        return await page.evaluate(DUMP_JS)
    finally:
        await page.close()


def write_modules(out: Path, modules: list, meta: dict) -> dict:
    mod_dir = out / "modules"
    (mod_dir / "_lib").mkdir(parents=True, exist_ok=True)
    index, seen = {}, set()
    for name, src, deps in modules:
        safe = SAFE_RE.sub("_", name)
        rel = f"modules/_lib/{safe}.js" if name.isdigit() else f"modules/{safe}.js"
        while rel.lower() in seen:  # Windows FS is case-insensitive
            rel = rel[:-3] + "_.js"
        seen.add(rel.lower())
        (out / rel).write_text(src, encoding="utf-8")
        index[name] = {"file": rel, "deps": deps, "size": len(src)}
    (out / "index.json").write_text(
        json.dumps({**meta, "modules": index}, ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    return index


async def run(args) -> int:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, channel=args.browser)
        try:
            if args.bundle:
                bundle_path = args.bundle
                url = None
            else:
                url = await find_bundle_url(browser, args.timeout)
                name = url.rsplit("/", 1)[1].split("?")[0]
                out_dir = args.out / f"main.{name.split('.')[1]}"
                out_dir.mkdir(parents=True, exist_ok=True)
                bundle_path = out_dir / name
                if bundle_path.exists():
                    print(f"cached {bundle_path}")
                else:
                    print(f"download {url}")
                    download(url, bundle_path)
            out = bundle_path.parent if not args.bundle else args.out / bundle_path.stem
            out.mkdir(parents=True, exist_ok=True)
            source = bundle_path.read_text(encoding="utf-8")
            modules = await split_modules(browser, source)
        finally:
            await browser.close()
    meta = {
        "source_url": url,
        "bundle_file": str(bundle_path),
        "fetched_at": datetime.now().isoformat(timespec="seconds"),
        "module_count": len(modules),
    }
    index = write_modules(out, modules, meta)
    named = sum(1 for k in index if not k.isdigit())
    print(f"{len(index)} modules ({named} named) -> {out}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bundle", type=Path, help="Split an already-downloaded bundle, skip browser boot")
    ap.add_argument("--out", type=Path, default=Path(".tmp/bundle"), help="Output root")
    ap.add_argument("--browser", choices=("chrome", "chromium"), default="chrome")
    ap.add_argument("--timeout", type=float, default=90, help="Seconds to wait for bundle URL")
    return asyncio.run(run(ap.parse_args(argv)))


if __name__ == "__main__":
    sys.exit(main())
