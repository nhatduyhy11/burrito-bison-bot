import asyncio
import sys
from pathlib import Path
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, Mock, call, patch

import cv2
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FIXTURES_DIR = PROJECT_ROOT / "tests" / "fixtures"
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

from hauntedroom.core.template import find_template as find_real_template
from hauntedroom.core.template import load_template as load_real_template
from hauntedroom.flows import automap
from hauntedroom.flows.automap import (
    MAP_COMPLETION_BLOCKER_TEMPLATE_PATHS,
    WIN_REWARD_FOLLOWUP_CLICK,
    WIN_REWARD_FOLLOWUP_CLICK_COUNT,
    run_automap_flow,
)
from hauntedroom.flows.automap_support.completion_flow.blocker import (
    MAP_COMPLETION_BLOCKER_THRESHOLD,
    find_map_completion_blocker,
)
from hauntedroom.flows.automap_support.vision.hero_levelup import (
    HERO_LEVELUP_PRICE_REGION,
)


class MapCompletionBlockerTest(IsolatedAsyncioTestCase):
    def setUp(self):
        automap.FIRST_WIN_DONE = False
        self.page = Mock()
        self.page.evaluate = AsyncMock()
        self.page.wait_for_timeout = AsyncMock()
        self.page.mouse = Mock()
        self.page.mouse.click = AsyncMock()
        self.page.mouse.move = AsyncMock()
        self.page.mouse.down = AsyncMock()
        self.page.mouse.up = AsyncMock()

    @staticmethod
    def make_protect_available(image):
        x1, y1, _, _ = HERO_LEVELUP_PRICE_REGION
        image[y1 : y1 + 2, x1 : x1 + 4] = (255, 255, 255)
        return image

    def test_newbie_screen_matches_map_completion_blocker(self):
        frame = cv2.imread(
            str(FIXTURES_DIR / "hauntedroom-captures" / "newbie_block_screen.png"),
            cv2.IMREAD_GRAYSCALE,
        )
        self.assertIsNotNone(frame)
        blocker_templates = tuple(
            (path, load_real_template(path))
            for path in MAP_COMPLETION_BLOCKER_TEMPLATE_PATHS
        )

        match = find_map_completion_blocker(
            frame,
            blocker_templates,
            find_real_template,
        )

        self.assertIsNotNone(match)
        x, y, score, path = match
        self.assertEqual(path.name, "overlay_newbie.png")
        self.assertEqual((x, y), (345, 75))
        self.assertGreaterEqual(score, MAP_COMPLETION_BLOCKER_THRESHOLD)

    @patch(
        "hauntedroom.flows.automap.load_template",
        return_value=np.zeros((2, 2), dtype=np.uint8),
    )
    @patch("hauntedroom.flows.automap.find_template")
    @patch("hauntedroom.flows.automap.find_template_matches", return_value=[])
    @patch("hauntedroom.flows.automap.capture_page_bgr", new_callable=AsyncMock)
    async def test_map_end_clears_newbie_blocker_after_two_followup_clicks(
        self,
        capture_page_bgr,
        _find_template_matches,
        find_template,
        _load_template,
    ):
        blocker_cleared = False

        def match_by_name(_frame, _template, name, **_kwargs):
            if name == "map_end.png":
                return 300, 400, 0.91
            if name == "overlay_newbie.png" and not blocker_cleared:
                return 345, 75, 0.99
            if name == "start_home.png" and blocker_cleared:
                return 50, 600, 0.95
            return 0, 0, 0.0

        def record_click(x, y):
            nonlocal blocker_cleared
            if (x, y) == (345, 75):
                blocker_cleared = True

        find_template.side_effect = match_by_name
        self.page.mouse.click.side_effect = record_click
        capture_page_bgr.return_value = self.make_protect_available(
            np.zeros((720, 640, 3), dtype=np.uint8)
        )

        completed = await run_automap_flow(self.page, asyncio.Event())

        self.assertTrue(completed)
        self.assertEqual(
            self.page.mouse.click.await_args_list,
            [
                call(300, 400),
                *[
                    call(*WIN_REWARD_FOLLOWUP_CLICK)
                    for _ in range(WIN_REWARD_FOLLOWUP_CLICK_COUNT)
                ],
                call(345, 75),
            ],
        )
