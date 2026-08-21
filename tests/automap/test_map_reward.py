import asyncio
import sys
from pathlib import Path
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, Mock, call, patch

import cv2
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FIXTURES_DIR = PROJECT_ROOT / "tests" / "fixtures"
MAP_WIN_FIXTURES_DIR = FIXTURES_DIR / "hauntedroom-captures" / "map_win"
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

from hauntedroom.core.template_matching import find_template as find_real_template
from hauntedroom.core.template_matching import (
    find_template_matches as find_real_template_matches,
)
from hauntedroom.core.template_matching import load_template as load_real_template
from hauntedroom.flows.automap import (
    REWARD_LIST_TITLE_TEMPLATE_PATH,
    WIN_REWARD_TEMPLATE_PATH,
    run_automap_flow,
)
from hauntedroom.flows.automap_support.map.model_state import MapRunState
from hauntedroom.flows.automap_support.map.reward import (
    REWARD_LIST_TITLE_TEMPLATE_THRESHOLD,
    WIN_REWARD_EMPTY_DELAY_MS,
    WIN_REWARD_FOLLOWUP_CLICK,
    WIN_REWARD_RECHECK_MS,
    WIN_REWARD_TEMPLATE_THRESHOLD,
)
from hauntedroom.flows.automap_support.vision.hero_levelup import (
    HERO_LEVELUP_PRICE_REGION,
)


class MapRewardTest(IsolatedAsyncioTestCase):
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
        x1, y1, _, _ = HERO_LEVELUP_PRICE_REGION
        image[y1 : y1 + 2, x1 : x1 + 4] = (255, 255, 255)
        return image

    @patch("hauntedroom.flows.automap_support.templates.load_template")
    @patch(
        "hauntedroom.flows.automap_support.flow.find_template",
        side_effect=[
            (0, 0, 0.0),
            (300, 400, 0.91),
            (0, 0, 0.0),
            (138, 37, 0.99),
            (0, 0, 0.20),
            (50, 600, 0.95),
        ],
    )
    @patch("hauntedroom.flows.automap_support.flow.find_template_matches")
    @patch("hauntedroom.flows.automap_support.flow.capture_page_bgr", new_callable=AsyncMock)
    async def test_map_end_reclicks_reward_position_until_title_appears(
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
        find_template_matches.return_value = [
            (305, 466, 1.0),
            (341, 466, 0.98),
        ]

        on_win = Mock(return_value=1)
        run_state = MapRunState()
        with patch("builtins.print") as print_mock:
            completed = await run_automap_flow(
                self.page,
                asyncio.Event(),
                on_win=on_win,
                run_state=run_state,
            )

        self.assertTrue(completed)
        self.assertTrue(run_state.daily_first_win_done)
        on_win.assert_called_once_with()
        messages = [print_call.args[0] for print_call in print_mock.call_args_list]
        self.assertLess(
            messages.index(">>> [1] win"),
            messages.index("Auto-map flow completed; runner is idle."),
        )
        self.assertIn(
            "Reward list title not found; clicking previous win reward "
            "position at 305,446 and checking again in 2s.",
            messages,
        )
        self.assertEqual(
            self.page.mouse.click.await_args_list,
            [
                call(300, 400),
                call(305, 446),
                call(305, 446),
                call(318, 237),
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
                call(WIN_REWARD_RECHECK_MS),
            ],
        )
        self.assertEqual(find_template_matches.call_count, 1)

    def test_win_reward_template_matches_dynamic_reward_screens(self):
        template = load_real_template(WIN_REWARD_TEMPLATE_PATH)

        for fixture_name in ("rewards_v1.png", "rewards_v2.png"):
            with self.subTest(fixture_name=fixture_name):
                frame = cv2.imread(
                    str(MAP_WIN_FIXTURES_DIR / fixture_name),
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
            str(MAP_WIN_FIXTURES_DIR / "reward_list_screen.png"),
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
        "hauntedroom.flows.automap_support.templates.load_template",
        return_value=np.zeros((2, 2), dtype=np.uint8),
    )
    @patch("hauntedroom.flows.automap_support.flow.find_template")
    @patch("hauntedroom.flows.automap_support.flow.find_template_matches", return_value=[])
    @patch("hauntedroom.flows.automap_support.flow.capture_page_bgr", new_callable=AsyncMock)
    async def test_map_end_clicks_followup_twice_before_checking_home(
        self,
        capture_page_bgr,
        find_template_matches,
        find_template,
        _load_template,
    ):
        def match_by_name(_frame, _template, name, **_kwargs):
            if name == "map_end.png":
                return 300, 400, 0.91
            if name == "start_home.png":
                return 50, 600, 0.95
            return 0, 0, 0.0

        find_template.side_effect = match_by_name
        capture_page_bgr.return_value = self.make_protect_available(
            np.zeros((720, 640, 3), dtype=np.uint8)
        )

        completed = await run_automap_flow(self.page, asyncio.Event())

        self.assertTrue(completed)
        self.assertEqual(
            self.page.mouse.click.await_args_list,
            [
                call(300, 400),
                call(*WIN_REWARD_FOLLOWUP_CLICK),
                call(*WIN_REWARD_FOLLOWUP_CLICK),
            ],
        )
        self.assertEqual(find_template.call_args_list[1].args[2], "map_end.png")
        self.assertEqual(find_template_matches.call_count, 3)
        self.assertEqual(
            self.page.wait_for_timeout.await_args_list,
            [
                call(WIN_REWARD_EMPTY_DELAY_MS),
                call(WIN_REWARD_EMPTY_DELAY_MS),
            ],
        )

    @patch("hauntedroom.flows.automap_support.templates.load_template")
    @patch(
        "hauntedroom.flows.automap_support.flow.find_template",
        side_effect=[
            (0, 0, 0.0),
            (300, 400, 0.91),
            (138, 37, 0.99),
            (138, 37, 0.98),
            (0, 0, 0.20),
            (50, 600, 0.95),
        ],
    )
    @patch("hauntedroom.flows.automap_support.flow.find_template_matches")
    @patch("hauntedroom.flows.automap_support.flow.capture_page_bgr", new_callable=AsyncMock)
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
