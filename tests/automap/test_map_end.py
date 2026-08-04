import asyncio
import sys
from pathlib import Path
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, Mock, call, patch

import cv2
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TOOLS_DIR = PROJECT_ROOT / "tools"
FIXTURES_DIR = PROJECT_ROOT / "tests" / "fixtures"
sys.path.insert(0, str(TOOLS_DIR))

from hauntedroom.core.vision import find_template as find_real_template
from hauntedroom.core.vision import find_template_matches as find_real_template_matches
from hauntedroom.core.vision import load_template as load_real_template
from hauntedroom.flows.automap import (
    AUTOMAP_POLL_MS,
    MAP_END_CHECK_INTERVAL_SEC,
    MAP_END_TEMPLATE_THRESHOLD,
    REWARD_LIST_TITLE_TEMPLATE_PATH,
    REWARD_LIST_TITLE_TEMPLATE_THRESHOLD,
    WIN_REWARD_EMPTY_DELAY_MS,
    WIN_REWARD_FOLLOWUP_CLICK,
    WIN_REWARD_RECHECK_MS,
    WIN_REWARD_TEMPLATE_PATH,
    WIN_REWARD_TEMPLATE_THRESHOLD,
    run_automap_flow,
)
from hauntedroom.flows.automap_support.detectors import PROTECT_AVAILABLE_REGION


class MapEndTest(IsolatedAsyncioTestCase):

    def setUp(self):
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
        x1, y1, _, _ = PROTECT_AVAILABLE_REGION
        image[y1 : y1 + 2, x1 : x1 + 4] = (255, 255, 255)
        return image

    @patch("hauntedroom.flows.automap.load_template")
    @patch(
        "hauntedroom.flows.automap.find_template",
        side_effect=[
            (0, 0, 0.0),
            (300, 400, 0.91),
            (0, 0, 0.0),
            (0, 0, 0.0),
            (50, 600, 0.95),
        ],
    )
    @patch("hauntedroom.flows.automap.find_template_matches")
    @patch("hauntedroom.flows.automap.capture_page_bgr", new_callable=AsyncMock)
    async def test_map_end_reclicks_first_reward_top_middle_until_no_match(
        self,
        capture_page_bgr,
        find_template_matches,
        find_template,
        load_template,
    ):
        load_template.side_effect = lambda path: np.zeros(
            (42, 34) if path.name == "win_reward.png" else (2, 2),
            dtype=np.uint8,
        )
        capture_page_bgr.return_value = self.make_protect_available(
            np.zeros((720, 640, 3), dtype=np.uint8)
        )
        reward_matches = [
            (305, 466, 1.0),
            (341, 466, 0.98),
        ]
        find_template_matches.side_effect = [
            reward_matches,
            reward_matches,
            [],
            [],
        ]

        on_win = Mock(return_value=1)
        with patch("builtins.print") as print_mock:
            completed = await run_automap_flow(
                self.page,
                asyncio.Event(),
                on_win=on_win,
            )

        self.assertTrue(completed)
        on_win.assert_called_once_with()
        messages = [print_call.args[0] for print_call in print_mock.call_args_list]
        self.assertLess(
            messages.index(">>> [1] win"),
            messages.index("Auto-map flow completed; runner is idle."),
        )
        self.assertEqual(
            self.page.mouse.click.await_args_list,
            [
                call(300, 400),
                call(305, 446),
                call(305, 446),
                call(*WIN_REWARD_FOLLOWUP_CLICK),
            ],
        )
        self.assertEqual(find_template.call_args_list[1].args[2], "map_end.png")
        reward_call = find_template_matches.call_args_list[0]
        self.assertEqual(reward_call.args[2], "win_reward.png")
        self.assertEqual(
            reward_call.kwargs["threshold"],
            WIN_REWARD_TEMPLATE_THRESHOLD,
        )
        self.assertEqual(
            self.page.wait_for_timeout.await_args_list,
            [
                call(WIN_REWARD_RECHECK_MS),
                call(WIN_REWARD_RECHECK_MS),
                call(WIN_REWARD_EMPTY_DELAY_MS),
            ],
        )

    def test_win_reward_template_matches_dynamic_reward_screens(self):
        template = load_real_template(WIN_REWARD_TEMPLATE_PATH)

        for fixture_name in ("rewards_v1.png", "rewards_v2.png"):
            with self.subTest(fixture_name=fixture_name):
                frame = cv2.imread(
                    str(
                        FIXTURES_DIR
                        / "hauntedroom-captures"
                        / fixture_name
                    ),
                    cv2.IMREAD_GRAYSCALE,
                )
                self.assertIsNotNone(frame)
                matches = find_real_template_matches(
                    frame,
                    template,
                    WIN_REWARD_TEMPLATE_PATH.name,
                    threshold=WIN_REWARD_TEMPLATE_THRESHOLD,
                    scales=(1.0,),
                )

                self.assertTrue(matches)

    def test_reward_list_title_template_matches_reward_list_screen(self):
        template = load_real_template(REWARD_LIST_TITLE_TEMPLATE_PATH)
        frame = cv2.imread(
            str(
                FIXTURES_DIR
                / "hauntedroom-captures"
                / "reward_list_screen.png"
            ),
            cv2.IMREAD_GRAYSCALE,
        )
        self.assertIsNotNone(frame)

        x, y, score = find_real_template(
            frame,
            template,
            REWARD_LIST_TITLE_TEMPLATE_PATH.name,
            click_position="top_middle",
            scales=(1.0,),
        )

        self.assertGreaterEqual(score, REWARD_LIST_TITLE_TEMPLATE_THRESHOLD)
        self.assertEqual((x, y), (318, 237))

    @patch(
        "hauntedroom.flows.automap.load_template",
        return_value=np.zeros((2, 2), dtype=np.uint8),
    )
    @patch(
        "hauntedroom.flows.automap.find_template",
        side_effect=[
            (0, 0, 0.0),
            (300, 400, 0.91),
            (0, 0, 0.0),
            (0, 0, 0.0),
            (50, 600, 0.95),
        ],
    )
    @patch("hauntedroom.flows.automap.find_template_matches", return_value=[])
    @patch("hauntedroom.flows.automap.capture_page_bgr", new_callable=AsyncMock)
    async def test_map_end_clicks_followup_once_before_checking_home(
        self,
        capture_page_bgr,
        find_template_matches,
        find_template,
        _load_template,
    ):
        capture_page_bgr.return_value = self.make_protect_available(
            np.zeros((720, 640, 3), dtype=np.uint8)
        )

        completed = await run_automap_flow(self.page, asyncio.Event())

        self.assertTrue(completed)
        self.assertEqual(
            self.page.mouse.click.await_args_list,
            [call(300, 400), call(*WIN_REWARD_FOLLOWUP_CLICK)],
        )
        self.assertEqual(find_template.call_args_list[1].args[2], "map_end.png")
        self.assertEqual(find_template_matches.call_count, 2)
        self.page.wait_for_timeout.assert_awaited_once_with(
            WIN_REWARD_EMPTY_DELAY_MS
        )

    @patch("hauntedroom.flows.automap.load_template")
    @patch(
        "hauntedroom.flows.automap.find_template",
        side_effect=[
            (0, 0, 0.0),
            (300, 400, 0.91),
            (138, 37, 0.99),
            (138, 37, 0.98),
            (0, 0, 0.20),
            (50, 600, 0.95),
        ],
    )
    @patch("hauntedroom.flows.automap.find_template_matches")
    @patch("hauntedroom.flows.automap.capture_page_bgr", new_callable=AsyncMock)
    async def test_map_end_reclicks_reward_list_title_until_it_disappears(
        self,
        capture_page_bgr,
        find_template_matches,
        _find_template,
        load_template,
    ):
        load_template.side_effect = lambda path: np.zeros(
            (42, 34) if path.name == "win_reward.png" else (2, 2),
            dtype=np.uint8,
        )
        capture_page_bgr.return_value = self.make_protect_available(
            np.zeros((720, 640, 3), dtype=np.uint8)
        )
        find_template_matches.side_effect = [
            [(305, 466, 1.0)],
            [],
            [],
            [],
        ]

        completed = await run_automap_flow(self.page, asyncio.Event())

        self.assertTrue(completed)
        self.assertEqual(
            self.page.mouse.click.await_args_list,
            [
                call(300, 400),
                call(305, 446),
                call(318, 237),
                call(318, 237),
            ],
        )
        self.assertEqual(
            self.page.wait_for_timeout.await_args_list,
            [
                call(WIN_REWARD_RECHECK_MS),
                call(WIN_REWARD_RECHECK_MS),
                call(WIN_REWARD_RECHECK_MS),
            ],
        )

    @patch(
        "hauntedroom.flows.automap.load_template",
        return_value=np.zeros((2, 2), dtype=np.uint8),
    )
    @patch("hauntedroom.flows.automap.find_template", return_value=(0, 0, 0.0))
    @patch("hauntedroom.flows.automap.find_template_matches", return_value=[])
    @patch("hauntedroom.flows.automap.capture_page_bgr", new_callable=AsyncMock)
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
            call_args.args[2]
            for call_args in find_template_matches.call_args_list
        ]
        self.assertEqual(matched_template_names.count("lv_up.png"), 2)
        self.assertEqual(matched_template_names.count("built.png"), 2)
