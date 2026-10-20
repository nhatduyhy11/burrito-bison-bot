"""Deterministic browser regression with real OCR/MT, in addition to live CN demo."""

import asyncio
import json
from pathlib import Path

from playwright.async_api import async_playwright

from game_translator import INIT, OVERLAY_ID, OfflineTranslator, ScreenReader, Session, WebTranslator


async def main():
    output = Path(".tmp/translator-regression")
    output.mkdir(parents=True, exist_ok=True)
    offline = OfflineTranslator(".tmp/translator-models", ".tmp/translator-models/zh-vi-argos19-cache.json")
    translator = WebTranslator(offline, ".tmp/translator-models/zh-vi-google-web-cache.json")
    reader = ScreenReader(translator)
    async with async_playwright() as p:
        browser = await p.chromium.launch(channel="chrome", headless=True)
        try:
            page = await browser.new_page(viewport={"width": 640, "height": 720})
            await page.set_content("""
                <style>body{margin:0;background:#172335}canvas{display:block}</style>
                <canvas width="640" height="720"></canvas>
            """)
            await page.evaluate(INIT)
            await page.evaluate("""() => {
                window.panel = 0; window.clicks = 0;
                window.draw = () => {
                    const ctx = document.querySelector('canvas').getContext('2d');
                    ctx.fillStyle = '#172335'; ctx.fillRect(0,0,640,720);
                    ctx.fillStyle = 'white'; ctx.font = '24px sans-serif';
                    const lines = window.panel
                        ? ['升級技能可以提高傷害。', '點擊按鈕返回上一頁。']
                        : ['滿星英雄加神器即可獲得', '終極形態英雄！'];
                    lines.forEach((line,i) => ctx.fillText(line,40,200+i*65));
                };
                document.querySelector('canvas').addEventListener('click', () => window.clicks++);
                document.querySelector('canvas').addEventListener('wheel', () => {
                    window.panel = 1; draw();
                });
                draw();
            }""")
            session = Session(page, reader)
            first = await session.update()
            assert first["rendered"] and len(first["rows"]) == 2
            assert any(r["translation_source"] == "google-web" for r in first["rows"])
            assert all(r["source"] != r["vi"] for r in first["rows"])
            await page.screenshot(path=str(output / "long-description.png"))
            assert await session.update() is None, "Unchanged frame should skip OCR"
            cached = await session.update(force=True)
            assert cached["model_batches"] == 0, "Repeated text should use cache"
            await page.mouse.click(100, 200)
            assert await page.evaluate("window.clicks") == 1
            assert await page.locator(f"#{OVERLAY_ID}").count() == 0
            await page.mouse.wheel(0, 240)
            await page.wait_for_function("window.panel === 1")
            second = await session.update()
            assert second["rendered"] and len(second["rows"]) == 2
            assert {r["source"] for r in first["rows"]}.isdisjoint(
                {r["source"] for r in second["rows"]}
            )
            await page.screenshot(path=str(output / "after-scroll.png"))
            # Real local inference, never a glossary-only test.
            local = await asyncio.to_thread(offline.translate, [
                "升級技能可以提高傷害。", "點擊按鈕返回上一頁。"
            ])
            assert all(local) and all(not any("\u3400" <= c <= "\u9fff" for c in t) for t in local)
            report = {"first": first, "cached": cached, "after_scroll": second, "offline": local}
            (output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            print("PASS: real MT on new sentences, unchanged frame skip, cache, click-through, scrolling, offline inference.")
        finally:
            await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
