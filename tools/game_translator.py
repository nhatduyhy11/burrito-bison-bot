"""Chinese -> Vietnamese screen translator with local OCR and offline fallback.

Setup: uv sync --extra translator && uv run python tools/setup_translator.py
Run: uv run --extra translator python tools/game_translator.py
Shift+D toggles translations. Ctrl+C closes the translator.
"""

import argparse
import asyncio
from difflib import SequenceMatcher
import hashlib
import json
from pathlib import Path
import re
import time
import urllib.parse
import urllib.request

import cv2
import numpy as np
from playwright.async_api import async_playwright

CHINESE = re.compile(r"[\u3400-\u9fff]")
OVERLAY_ID = "__game_translator"
INIT = """
window.__translationEpoch = Date.now();
window.__translationEnabled = true;
window.__gameSourceTexts = new Set();
for (const method of ['fillText','strokeText']) {
    const original = CanvasRenderingContext2D.prototype[method];
    CanvasRenderingContext2D.prototype[method] = function(text, ...args) {
        if (window.__gameSourceTexts.size < 10000) window.__gameSourceTexts.add(String(text));
        return original.call(this, text, ...args);
    };
}
function invalidateTranslation() {
    window.__translationEpoch++;
    document.getElementById('__game_translator')?.remove();
}
for (const event of ['pointerdown', 'wheel', 'resize'])
    window.addEventListener(event, invalidateTranslation, {capture:true, passive:true});
window.addEventListener('keydown', event => {
    if (event.shiftKey && event.code === 'KeyD' && !event.repeat &&
        !event.ctrlKey && !event.altKey && !event.metaKey) {
        window.__translationEnabled = !window.__translationEnabled;
        event.preventDefault();
    }
    invalidateTranslation();
}, true);
"""
RENDER = """
({rows, epoch}) => {
    if (window.__translationEpoch !== epoch || !window.__translationEnabled) return false;
    document.getElementById('__game_translator')?.remove();
    const layer = document.createElement('div');
    layer.id = '__game_translator';
    Object.assign(layer.style, {position:'fixed', inset:'0', zIndex:'2147483647',
        pointerEvents:'none', overflow:'hidden'});
    for (const row of rows) {
        const label = document.createElement('div');
        label.textContent = row.vi;
        label.title = row.source;
        const xs = row.box.map(p => p[0]), ys = row.box.map(p => p[1]);
        const x = Math.min(...xs), y = Math.min(...ys);
        const width = Math.max(75, Math.max(...xs)-x);
        Object.assign(label.style, {position:'absolute',
            left: Math.max(0, Math.min(x, innerWidth - width))+'px', top:y+'px',
            width: Math.min(width + 30, innerWidth - x - 2)+'px',
            color:'#fff', background:'rgba(12,20,32,.94)', border:'1px solid #4dd9b4',
            borderRadius:'3px', padding:'2px 3px', boxSizing:'border-box',
            font:'12px/1.25 Arial, sans-serif', overflowWrap:'anywhere'});
        layer.appendChild(label);
    }
    document.documentElement.appendChild(layer);
    return true;
}
"""


class OfflineTranslator:
    """Batched CPU translation using the Argos 1.9 Chinese/English/Vietnamese models."""

    def __init__(self, models, cache_path):
        import ctranslate2
        import sentencepiece
        from opencc import OpenCC

        self.normalize = OpenCC("t2s").convert
        self.stages = []
        for pair in ("zh_en", "en_vi"):
            root = Path(models) / pair
            if not (root / "model/model.bin").is_file():
                raise RuntimeError("Missing models. Run: uv run python tools/setup_translator.py")
            tokenizer = sentencepiece.SentencePieceProcessor(
                model_file=str(root / "sentencepiece.model")
            )
            engine = ctranslate2.Translator(
                str(root / "model"), device="cpu", compute_type="int8", intra_threads=4
            )
            self.stages.append((tokenizer, engine))
        self.cache_path = Path(cache_path)
        self.cache = {}
        if self.cache_path.exists():
            try:
                self.cache = json.loads(self.cache_path.read_text(encoding="utf-8"))
            except (ValueError, OSError):
                pass
        self.model_batches = 0

    def translate(self, texts):
        normalized = [self.normalize(t.strip()) for t in texts]
        missing = list(dict.fromkeys(t for t in normalized if t not in self.cache))
        if missing:
            translated = missing
            for tokenizer, engine in self.stages:
                tokens = [tokenizer.encode(t, out_type=str) for t in translated]
                result = engine.translate_batch(
                    tokens, beam_size=3, max_batch_size=16, max_decoding_length=256
                )
                translated = [
                    tokenizer.decode(r.hypotheses[0]).replace("\u2581", " ").strip()
                    for r in result
                ]
            if any(not t.strip() for t in translated):
                raise RuntimeError("Translation returned empty text")
            self.cache.update(zip(missing, translated))
            self.model_batches += 1
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.cache_path.with_suffix(".tmp")
            temporary.write_text(json.dumps(self.cache, ensure_ascii=False, indent=2), encoding="utf-8")
            temporary.replace(self.cache_path)
        return [self.cache[t] for t in normalized]


class WebTranslator:
    """Best-effort Google web endpoint, cached; local fallback on network errors.

    This is not the supported Google Cloud API and has no availability guarantee.
    """

    def __init__(self, offline, cache_path):
        self.offline = offline
        self.normalize = offline.normalize
        self.cache_path = Path(cache_path)
        self.cache = {}
        if self.cache_path.is_file():
            try:
                self.cache = json.loads(self.cache_path.read_text(encoding="utf-8"))
            except (ValueError, OSError):
                pass
        self.model_batches = 0
        self.retry_after = 0
        self.backend = "google-web"

    def translate(self, texts):
        normalized = [self.normalize(t.strip()) for t in texts]
        missing = list(dict.fromkeys(t for t in normalized if t not in self.cache))
        if missing:
            if time.monotonic() < self.retry_after:
                self.backend = "offline-fallback"
                self.model_batches += 1
                return self.offline.translate(texts)
            try:
                # Keep batches small enough for GET and preserve one OCR line per result.
                for offset in range(0, len(missing), 8):
                    batch = missing[offset:offset + 8]
                    query = urllib.parse.urlencode({
                        "client": "gtx", "sl": "zh-CN", "tl": "vi", "dt": "t",
                        "q": "\n".join(batch),
                    })
                    request = urllib.request.Request(
                        "https://translate.google.com/translate_a/single?" + query,
                        headers={"User-Agent": "Mozilla/5.0"},
                    )
                    with urllib.request.urlopen(request, timeout=12) as response:
                        payload = json.load(response)
                    lines = "".join(part[0] for part in payload[0] if part[0]).split("\n")
                    if len(lines) != len(batch) or any(not line.strip() for line in lines):
                        raise ValueError("Translation line alignment failed")
                    self.cache.update(zip(batch, (line.strip() for line in lines)))
                    self.model_batches += 1
                self.cache_path.parent.mkdir(parents=True, exist_ok=True)
                temporary = self.cache_path.with_suffix(".tmp")
                temporary.write_text(json.dumps(self.cache, ensure_ascii=False, indent=2), encoding="utf-8")
                temporary.replace(self.cache_path)
            except Exception as error:
                print(f"Web MT unavailable ({type(error).__name__}); using offline for 60s.", flush=True)
                self.retry_after = time.monotonic() + 60
                self.backend = "offline-fallback"
                self.model_batches += 1
                return self.offline.translate(texts)
        self.backend = "google-web"
        return [self.cache[t] for t in normalized]


def recover_source(text, candidates, normalize):
    """Use captured game strings only when they closely match visible OCR."""
    normalized = normalize(text).replace(" ", "")
    if len(normalized) < 3:
        return text
    unique = {normalize(c).replace(" ", ""): c for c in candidates}
    scored = sorted(
        ((SequenceMatcher(None, normalized, key).ratio(), c)
         for key, c in unique.items() if abs(len(key) - len(normalized)) <= 2),
        reverse=True,
    )
    if scored and scored[0][0] >= 0.72:
        best = scored[0]
        if best[0] == 1 or len(scored) == 1 or best[0] - scored[1][0] >= 0.08:
            return best[1]
    return text


class ScreenReader:
    def __init__(self, translator):
        from rapidocr_onnxruntime import RapidOCR

        self.ocr = RapidOCR()
        self.translator = translator
        self.glossary = json.loads(
            Path(__file__).with_name("translator_glossary.json").read_text(encoding="utf-8")
        )

    def process(self, png, candidates=()):
        started = time.perf_counter()
        image = cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError("Invalid screenshot")
        scale = 1.5
        result, _ = self.ocr(cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC))
        rows = [
            {"box": (np.asarray(box) / scale).tolist(), "ocr": text,
             "source": recover_source(text, candidates, self.translator.normalize),
             "confidence": float(confidence)}
            for box, text, confidence in (result or [])
            if confidence >= 0.65 and CHINESE.search(text)
        ]
        ocr_ms = (time.perf_counter() - started) * 1000
        before = self.translator.model_batches
        missing = []
        for row in rows:
            key = self.translator.normalize(row["source"]).replace(" ", "")
            if key in self.glossary:
                row["vi"] = self.glossary[key]
                row["translation_source"] = "glossary"
            else:
                missing.append(row)
        translated = self.translator.translate([r["source"] for r in missing])
        for row, vi in zip(missing, translated):
            row["vi"] = vi
            row["translation_source"] = getattr(self.translator, "backend", "offline")
        return {
            "rows": rows, "ocr_ms": round(ocr_ms, 1),
            "processing_ms": round((time.perf_counter() - started) * 1000, 1),
            "model_batches": self.translator.model_batches - before,
            "backend": getattr(self.translator, "backend", "offline"),
        }


def retain_current_rows(rows, source_png, current_png):
    """Discard regions that changed while OCR/translation ran (including animation)."""
    source = cv2.imdecode(np.frombuffer(source_png, np.uint8), cv2.IMREAD_GRAYSCALE)
    current = cv2.imdecode(np.frombuffer(current_png, np.uint8), cv2.IMREAD_GRAYSCALE)
    if source is None or current is None or source.shape != current.shape:
        return []
    height, width = source.shape
    kept = []
    for row in rows:
        box = np.asarray(row["box"])
        x0, y0 = np.maximum(box.min(axis=0).astype(int), 0)
        x1, y1 = np.minimum(np.ceil(box.max(axis=0)).astype(int), [width, height])
        if x1 <= x0 or y1 <= y0:
            continue
        diff = cv2.absdiff(source[y0:y1, x0:x1], current[y0:y1, x0:x1])
        if float(diff.mean()) < 12 and float((diff > 40).mean()) < 0.12:
            kept.append(row)
    return kept


class Session:
    def __init__(self, page, reader):
        self.page, self.reader = page, reader
        self.last_hash = None
        self.last_epoch = None
        self.last_result = None
        self.last_png = None

    async def update(self, force=False):
        epoch, enabled = await self.page.evaluate(
            "[window.__translationEpoch, window.__translationEnabled]"
        )
        if not enabled:
            return None
        started = time.perf_counter()
        png = await self.page.screenshot(
            scale="css", style=f"#{OVERLAY_ID} {{ visibility: hidden !important; }}"
        )
        digest = hashlib.sha256(png).hexdigest()
        if not force and digest == self.last_hash and epoch == self.last_epoch:
            return None
        # Keep only labels whose source pixels are still present, avoiding flicker.
        retained = []
        if self.last_result and self.last_png and epoch == self.last_epoch:
            retained = retain_current_rows(self.last_result["rows"], self.last_png, png)
        await self.page.evaluate(RENDER, {"rows": retained, "epoch": epoch})
        candidates = await self.page.evaluate("[...(window.__gameSourceTexts || [])]")
        result = await asyncio.to_thread(self.reader.process, png, candidates)
        current_png = await self.page.screenshot(
            scale="css", style=f"#{OVERLAY_ID} {{ visibility: hidden !important; }}"
        )
        rows = retain_current_rows(result["rows"], png, current_png)
        result["discarded_regions"] = len(result["rows"]) - len(rows)
        result["rows"] = rows
        rendered = await self.page.evaluate(RENDER, {"rows": result["rows"], "epoch": epoch})
        result["rendered"] = rendered
        result["total_ms"] = round((time.perf_counter() - started) * 1000, 1)
        if rendered:
            # Commit only successful work; errors and input during OCR retry next iteration.
            self.last_hash = digest if not result["discarded_regions"] else None
            self.last_epoch = epoch
            self.last_result = result
            self.last_png = current_png
        return result


def create_reader(models=".tmp/translator-models", offline=False):
    print("Loading OCR and offline translation models...", flush=True)
    try:
        translator = OfflineTranslator(models, Path(models) / "zh-vi-argos19-cache.json")
        if not offline:
            translator = WebTranslator(translator, Path(models) / "zh-vi-google-web-cache.json")
        return ScreenReader(translator)
    except ImportError as error:
        raise RuntimeError(
            "Translator dependencies missing. Run with: uv run --extra translator python ..."
        ) from error


async def translate_page(page, reader, output=".tmp/translator-result"):
    """Run on an existing runner page; cancellation is owned by the runner."""
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    session = Session(page, reader)
    print("Translator ON in this game window. Shift+D: toggle.", flush=True)
    while not page.is_closed():
        try:
            result = await session.update()
            if result is not None:
                (output / "latest.json").write_text(
                    json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
                )
        except Exception as error:
            if page.is_closed():
                break
            print(f"Retrying after {type(error).__name__}: {error}", flush=True)
            await asyncio.sleep(1)
        await asyncio.sleep(0.5)


async def run(args):
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    reader = await asyncio.to_thread(create_reader, args.models, args.offline)
    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            args.profile, channel=None if args.browser == "chromium" else args.browser,
            headless=args.headless, viewport={"width": 640, "height": 720},
        )
        try:
            await context.add_init_script(INIT)
            page = context.pages[0] if context.pages else await context.new_page()
            await page.goto(args.url, wait_until="domcontentloaded", timeout=45000)
            session = Session(page, reader)
            if args.demo:
                await demo(session, output)
                return
            await translate_page(page, reader, output)
        finally:
            await context.close()


async def demo(session, output):
    """Actual game capture -> OCR -> offline MT -> DOM overlay evidence."""
    page = session.page
    report = []

    async def record(name):
        result = None
        for attempt in range(6):
            result = await session.update(force=True)
            if result and result["rows"] and result["rendered"]:
                break
            await page.wait_for_timeout(700)
        if not result or not result["rows"] or not result["rendered"]:
            raise RuntimeError(f"No translated screen at {name}")
        await page.screenshot(path=str(output / f"{name}-source.png"), scale="css",
                              style=f"#{OVERLAY_ID} {{ visibility:hidden !important; }}")
        await page.screenshot(path=str(output / f"{name}-translated.png"), scale="css")
        report.append({"screen": name, **result})
        (output / "report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"{name}: {len(result['rows'])} translated regions; {result['total_ms']} ms", flush=True)
        return result

    await page.wait_for_timeout(15000)
    await record("01-entry")
    # Verify the translation layer does not receive clicks.
    assert await page.locator(f"#{OVERLAY_ID}").evaluate(
        "el => getComputedStyle(el).pointerEvents"
    ) == "none"
    await page.mouse.click(320, 572)
    assert await page.locator(f"#{OVERLAY_ID}").count() == 0
    await page.wait_for_timeout(20000)
    await record("02-story")
    await page.mouse.click(464, 50)
    await page.wait_for_timeout(8000)
    await record("03-game")
    # Wheel must invalidate labels even when the scene itself does not scroll.
    await page.mouse.wheel(0, 160)
    await page.wait_for_timeout(150)
    assert await page.locator(f"#{OVERLAY_ID}").count() == 0
    await record("04-after-wheel")
    await page.keyboard.press("Shift+KeyD")
    assert await page.locator(f"#{OVERLAY_ID}").count() == 0
    assert await session.update() is None
    await page.keyboard.press("Shift+KeyD")
    await record("05-enabled")
    await page.mouse.click(320, 642)
    await page.wait_for_timeout(8000)
    await record("06-tutorial")
    print("PASS: real OCR/MT/render, click-through, wheel invalidation and toggle.", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="https://hauntheroesweb.acenetgame.com/")
    parser.add_argument("--profile", default=".tmp/translator-profile")
    parser.add_argument("--models", default=".tmp/translator-models")
    parser.add_argument("--output", default=".tmp/translator-result")
    parser.add_argument("--browser", choices=["chrome", "msedge", "chromium"], default="chrome")
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--offline", action="store_true", help="Never send recognized text to web MT")
    parser.add_argument("--demo", action="store_true")
    try:
        asyncio.run(run(parser.parse_args()))
    except KeyboardInterrupt:
        pass
