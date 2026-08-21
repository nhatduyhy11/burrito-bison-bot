import asyncio
import sys
from pathlib import Path
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, Mock, patch

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

from hauntedroom.flows.automap import (
    AUTOMAP_POLL_MS,
    DAILY_FIRST_WIN_CHECKBOX_TEMPLATE_PATH,
    DAILY_FIRST_WIN_CHECKED_TEMPLATE_PATH,
    DAILY_FIRST_WIN_TEMPLATE_PATH,
    MAP_END_CHECK_INTERVAL_SEC,
    MAP_END_TEMPLATE_THRESHOLD,
    REWARD_LIST_TITLE_TEMPLATE_PATH,
    WIN_REWARD_TEMPLATE_PATH,
    run_automap_flow,
)
from hauntedroom.flows.automap_support.vision.template_config import (
    MAP_WIN_TEMPLATE_DIR,
)


class MapEndAutomapAdapterTest(IsolatedAsyncioTestCase):
    def setUp(self):
        self.page = Mock()
        self.page.evaluate = AsyncMock()
        self.page.wait_for_timeout = AsyncMock()
        self.page.mouse = Mock()
        self.page.mouse.click = AsyncMock()

    def test_map_win_templates_are_grouped_in_map_win_directory(self):
        template_paths = (
            WIN_REWARD_TEMPLATE_PATH,
            REWARD_LIST_TITLE_TEMPLATE_PATH,
            DAILY_FIRST_WIN_TEMPLATE_PATH,
            DAILY_FIRST_WIN_CHECKBOX_TEMPLATE_PATH,
            DAILY_FIRST_WIN_CHECKED_TEMPLATE_PATH,
        )

        self.assertTrue(MAP_WIN_TEMPLATE_DIR.is_dir())
        for template_path in template_paths:
            with self.subTest(template_path=template_path):
                self.assertEqual(template_path.parent, MAP_WIN_TEMPLATE_DIR)
                self.assertTrue(template_path.is_file())

    @patch(
        "hauntedroom.flows.automap_support.templates.load_template",
        return_value=np.zeros((2, 2), dtype=np.uint8),
    )
    @patch("hauntedroom.flows.automap_support.flow.find_template", return_value=(0, 0, 0.0))
    @patch("hauntedroom.flows.automap_support.flow.find_template_matches", return_value=[])
    @patch("hauntedroom.flows.automap_support.flow.capture_page_bgr", new_callable=AsyncMock)
    async def test_map_end_is_checked_at_most_once_per_interval(
        self,
        capture_page_bgr,
        find_template_matches,
        find_template,
        _load_template,
    ):
        capture_page_bgr.return_value = np.zeros((720, 640, 3), dtype=np.uint8)
        stop_event = asyncio.Event()

        async def stop_after_second_poll(*_args, **_kwargs):
            if self.page.wait_for_timeout.await_count == 2:
                stop_event.set()

        self.page.wait_for_timeout.side_effect = stop_after_second_poll

        completed = await run_automap_flow(self.page, stop_event)

        self.assertFalse(completed)
        self.assertGreater(MAP_END_CHECK_INTERVAL_SEC, AUTOMAP_POLL_MS / 1000)
        self.assertGreater(MAP_END_TEMPLATE_THRESHOLD, 0.80)
        self.assertEqual(
            [
                call_args.args[2]
                for call_args in find_template.call_args_list
                if call_args.args[2] == "map_end.png"
            ],
            ["map_end.png"],
        )
        matched_template_names = [
            call_args.args[2] for call_args in find_template_matches.call_args_list
        ]
        self.assertEqual(matched_template_names.count("lv_up.png"), 2)
        self.assertEqual(matched_template_names.count("built.png"), 2)
