import sys
import tempfile
from pathlib import Path
from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import AsyncMock, Mock, patch

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from game_translator import Session, WebTranslator, recover_source, retain_current_rows


def png(image):
    return cv2.imencode(".png", image)[1].tobytes()


class RegionFreshnessTests(TestCase):
    def test_animation_outside_text_does_not_discard_text(self):
        before = np.zeros((50, 50), np.uint8)
        after = before.copy()
        after[30:50] = 255
        row = {"box": [[2, 2], [20, 2], [20, 20], [2, 20]]}
        self.assertEqual(retain_current_rows([row], png(before), png(after)), [row])

    def test_changed_text_and_resized_viewport_are_discarded(self):
        before = np.zeros((50, 50), np.uint8)
        after = before.copy()
        after[2:20, 2:20] = 255
        row = {"box": [[2, 2], [20, 2], [20, 20], [2, 20]]}
        self.assertEqual(retain_current_rows([row], png(before), png(after)), [])
        self.assertEqual(retain_current_rows([row], png(before), png(after[:30])), [])

    def test_source_recovery_rejects_ambiguous_and_unrelated_text(self):
        normalize = lambda text: text
        self.assertEqual(recover_source("開始遊", ["開始遊戲"], normalize), "開始遊戲")
        self.assertEqual(recover_source("開始遊", ["開始遊戲", "開始遊玩"], normalize), "開始遊")
        self.assertEqual(recover_source("其他文字", ["開始遊戲"], normalize), "其他文字")


class SessionRetryTests(IsolatedAsyncioTestCase):
    async def test_bot_vision_excludes_translation_overlay(self):
        from hauntedroom.core.vision import capture_page_bgr, capture_page_grayscale

        page = Mock()
        page.screenshot = AsyncMock(return_value=png(np.zeros((20, 20, 3), np.uint8)))
        for capture in (capture_page_bgr, capture_page_grayscale):
            await capture(page)
            style = page.screenshot.call_args.kwargs["style"]
            self.assertIn("#__game_translator", style)
            self.assertIn("visibility: hidden", style)

    def make_session(self):
        page = Mock()
        page.screenshot = AsyncMock(return_value=png(np.zeros((50, 50), np.uint8)))

        async def evaluate(script, *args):
            if script.startswith("[window."):
                return [0, True]
            if script.startswith("[..."):
                return []
            if args:
                return True
            return None

        page.evaluate = AsyncMock(side_effect=evaluate)
        reader = Mock()
        reader.process.return_value = {"rows": []}
        return Session(page, reader)

    async def test_identical_frame_retries_after_ocr_error_then_skips_success(self):
        session = self.make_session()
        session.reader.process.side_effect = [RuntimeError("transient OCR"), {"rows": []}]
        with self.assertRaises(RuntimeError):
            await session.update()
        self.assertIsNone(session.last_hash)
        self.assertTrue((await session.update())["rendered"])
        self.assertIsNone(await session.update())
        self.assertEqual(session.reader.process.call_count, 2)


    async def test_input_during_processing_never_commits_old_result(self):
        session = self.make_session()
        original = session.page.evaluate.side_effect

        async def evaluate(script, *args):
            if args:
                return False  # browser epoch changed while OCR ran
            return await original(script, *args)

        session.page.evaluate.side_effect = evaluate
        self.assertFalse((await session.update())["rendered"])
        self.assertIsNone(session.last_hash)
        await session.update()
        self.assertEqual(session.reader.process.call_count, 2)


class NetworkFallbackTests(TestCase):
    def test_network_failure_uses_local_model_without_poisoning_web_cache(self):
        offline = Mock()
        offline.normalize = lambda text: text
        offline.translate.return_value = ["Bản dịch dự phòng"]
        with tempfile.TemporaryDirectory() as directory:
            translator = WebTranslator(offline, Path(directory) / "cache.json")
            with patch("game_translator.urllib.request.urlopen", side_effect=TimeoutError) as request:
                self.assertEqual(translator.translate(["测试"]), ["Bản dịch dự phòng"])
                self.assertEqual(translator.translate(["测试"]), ["Bản dịch dự phòng"])
                self.assertEqual(request.call_count, 1)
            self.assertEqual(translator.cache, {})
            self.assertEqual(translator.backend, "offline-fallback")
