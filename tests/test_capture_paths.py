import sys
from pathlib import Path
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, Mock, patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

from hauntedroom.core.runtime import (
    FALLBACK_SCREENSHOT_DIR,
    LIVE_SCREENSHOT_DIR,
    save_fallback_screenshot,
)


class CapturePathTest(IsolatedAsyncioTestCase):
    def test_live_capture_directory_is_inside_test_fixtures(self):
        self.assertEqual(
            LIVE_SCREENSHOT_DIR,
            Path("tests/fixtures/hauntedroom-captures"),
        )

    @patch("hauntedroom.core.runtime.save_screenshot", new_callable=AsyncMock)
    async def test_fallback_screenshot_is_persisted_under_tmp(self, save_screenshot):
        page = Mock()

        await save_fallback_screenshot(page, "hero-fallback")

        self.assertEqual(
            FALLBACK_SCREENSHOT_DIR,
            Path(".tmp/hauntedroom-fallbacks"),
        )
        save_screenshot.assert_awaited_once_with(
            page,
            "hero-fallback",
            FALLBACK_SCREENSHOT_DIR,
            "Fallback",
        )
