"""Read-only text inspection plus an optional entry click; no OCR/MT backend.

Run: uv run python tools/translator_probe.py --enter-game
Artifacts are local, under .tmp/translator-review.
"""

import argparse
import asyncio
import json
from pathlib import Path

from playwright.async_api import async_playwright

HOOK = """
window.__translatorTexts = new Set();
for (const name of ['fillText', 'strokeText']) {
    const original = CanvasRenderingContext2D.prototype[name];
    CanvasRenderingContext2D.prototype[name] = function(text, ...args) {
        if (window.__translatorTexts.size < 3000)
            window.__translatorTexts.add(String(text));
        return original.call(this, text, ...args);
    };
}
"""


async def snapshot(page, output, name):
    await page.screenshot(path=str(output / f"{name}.png"), scale="css")
    frames = []
    for frame in page.frames:
        frames.append(await frame.evaluate("""() => ({
            url: location.origin + location.pathname,
            canvasCount: document.querySelectorAll('canvas').length,
            drawnTexts: [...(window.__translatorTexts || [])]
        })"""))
    (output / f"{name}.json").write_text(
        json.dumps(frames, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return frames


async def main(args):
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            channel=None if args.browser == "chromium" else args.browser,
            headless=not args.headed,
        )
        try:
            context = await browser.new_context(viewport={"width": 640, "height": 720})
            await context.add_init_script(HOOK)
            page = await context.new_page()
            await page.goto(args.url, wait_until="domcontentloaded", timeout=45000)
            await page.wait_for_timeout(15000)
            frames = await snapshot(page, output, "entry")
            if args.enter_game:
                # Verified only for the CN entry screen at this viewport.
                # Require both expected labels before using this fixed coordinate.
                texts = {t for f in frames for t in f["drawnTexts"]}
                if not {"開始遊戲", "選擇伺服器"}.issubset(texts):
                    raise RuntimeError("Unrecognized entry screen; inspect entry.png")
                for frame in page.frames:
                    await frame.evaluate("window.__translatorTexts?.clear()")
                await page.mouse.click(320, 572)
                await page.wait_for_timeout(20000)
                frames = await snapshot(page, output, "after-entry")
            count = sum(len(f["drawnTexts"]) for f in frames)
            print(f"Captured {count} unique draw strings across frames; artifacts: {output}")
            print("Inspection only: this does not establish translation success.")
        finally:
            await browser.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="https://hauntheroesweb.acenetgame.com/")
    parser.add_argument("--browser", choices=["chrome", "msedge", "chromium"], default="chrome")
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--enter-game", action="store_true")
    parser.add_argument("--output", default=".tmp/translator-review")
    asyncio.run(main(parser.parse_args()))
