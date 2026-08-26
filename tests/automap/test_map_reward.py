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
SPECIAL_FLOW_FIXTURES_DIR = FIXTURES_DIR / "special_flow"
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
from hauntedroom.flows.automap_support.map.model_state import (
    MapLifecycleStep,
    MapRewardContext,
    MapRunState,
    MapState,
)
from hauntedroom.flows.automap_support.map.reward import (
    REWARD_LIST_TITLE_TEMPLATE_THRESHOLD,
    WIN_REWARD_EMPTY_DELAY_MS,
    WIN_REWARD_FOLLOWUP_CLICK,
    WIN_REWARD_HOTSPOT_RATIO,
    WIN_REWARD_RECHECK_MS,
    WIN_REWARD_TEMPLATE_THRESHOLD,
    handle_reward_list,
    relative_position,
    reward_list_popup_visible,
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
    @patch("hauntedroom.flows.automap_support.flow.find_template")
    @patch("hauntedroom.flows.automap_support.flow.find_template_matches")
    @patch("hauntedroom.flows.automap_support.flow.capture_page_bgr", new_callable=AsyncMock)
    async def test_map_end_clicks_fixed_card_and_records_confirmed_popup(
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
        title_scores = iter((0.99, 0.20))

        def match_by_name(_frame, _template, name, **_kwargs):
            if name == "map_end.png":
                return 300, 400, 0.91
            if name == "reward_list_title.png":
                return 138, 37, next(title_scores)
            if name == "start_home.png":
                return 50, 600, 0.95
            return 0, 0, 0.0

        find_template.side_effect = match_by_name
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
        self.assertIn("Reward popup confirmed; win recorded.", messages)
        self.assertEqual(
            self.page.mouse.click.await_args_list,
            [
                call(300, 400),
                call(*WIN_REWARD_FOLLOWUP_CLICK),
                call(318, 237),
            ],
        )
        self.assertTrue(
            any(call_args.args[2] == "map_end.png" for call_args in find_template.call_args_list)
        )
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
            ],
        )
        self.assertEqual(find_template_matches.call_count, 1)

    @patch("hauntedroom.flows.automap_support.templates.load_template")
    @patch("hauntedroom.flows.automap_support.flow.find_template")
    @patch("hauntedroom.flows.automap_support.flow.find_template_matches")
    @patch("hauntedroom.flows.automap_support.flow.capture_page_bgr", new_callable=AsyncMock)
    async def test_first_win_remains_active_after_home_reward_click(
        self,
        capture_page_bgr,
        find_template_matches,
        find_template,
        load_template,
    ):
        load_template.return_value = np.zeros((2, 2), dtype=np.uint8)
        capture_page_bgr.return_value = np.zeros((720, 640, 3), dtype=np.uint8)
        daily_scores = iter((0.0, 0.0, 0.99, 0.99))
        title_scores = iter((0.99, 0.0, 0.0))
        home_scores = iter((0.0, 0.95))

        def match_by_name(_frame, _template, name, **_kwargs):
            if name == "map_end.png":
                return 300, 400, 0.91
            if name == "daily_first_win.png":
                return 332, 442, next(daily_scores)
            if name == "daily_first_win_checked.png":
                return 10, 10, 0.99
            if name == "reward_list_title.png":
                return 138, 37, next(title_scores)
            if name == "start_home.png":
                return 50, 600, next(home_scores)
            return 0, 0, 0.0

        find_template.side_effect = match_by_name
        find_template_matches.return_value = []

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
        self.assertEqual(
            self.page.mouse.click.await_args_list,
            [
                call(300, 400),
                call(318, 237),
                call(*WIN_REWARD_FOLLOWUP_CLICK),
                call(377, 478),
            ],
        )
        messages = [print_call.args[0] for print_call in print_mock.call_args_list]
        self.assertTrue(
            any(message.startswith("Daily first-win prompt at ") for message in messages)
        )

    def test_win_reward_template_matches_dynamic_reward_screens(self):
        template = load_real_template(WIN_REWARD_TEMPLATE_PATH)

        fixtures = (
            MAP_WIN_FIXTURES_DIR / "rewards_v1.png",
            MAP_WIN_FIXTURES_DIR / "rewards_v2.png",
            FIXTURES_DIR
            / "hauntedroom-captures"
            / "20260826-125439-709039-live.png",
        )
        for fixture_path in fixtures:
            with self.subTest(fixture_name=fixture_path.name):
                frame = cv2.imread(
                    str(fixture_path),
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

    def test_reward_list_panel_confirmation_does_not_depend_on_title_text(self):
        popup = cv2.imread(
            str(MAP_WIN_FIXTURES_DIR / "reward_list_screen.png"),
            cv2.IMREAD_COLOR,
        )
        missed_reward = cv2.imread(
            str(SPECIAL_FLOW_FIXTURES_DIR / "reward_fail_detect.png"),
            cv2.IMREAD_COLOR,
        )
        self.assertIsNotNone(popup)
        self.assertIsNotNone(missed_reward)

        self.assertTrue(reward_list_popup_visible(popup))
        self.assertFalse(reward_list_popup_visible(missed_reward))

        reward_template = load_real_template(WIN_REWARD_TEMPLATE_PATH)
        missed_reward_gray = cv2.cvtColor(missed_reward, cv2.COLOR_BGR2GRAY)
        self.assertFalse(
            find_real_template_matches(
                missed_reward_gray,
                reward_template,
                WIN_REWARD_TEMPLATE_PATH.name,
                threshold=WIN_REWARD_TEMPLATE_THRESHOLD,
                scales=(1.0,),
            )
        )
        self.assertEqual(
            relative_position(missed_reward, WIN_REWARD_HOTSPOT_RATIO),
            WIN_REWARD_FOLLOWUP_CLICK,
        )

    async def test_red_panel_confirms_win_without_calling_title_matcher(self):
        popup = cv2.imread(
            str(MAP_WIN_FIXTURES_DIR / "reward_list_screen.png"),
            cv2.IMREAD_COLOR,
        )
        popup_gray = cv2.cvtColor(popup, cv2.COLOR_BGR2GRAY)
        on_win = Mock(return_value=7)
        find_template = Mock()
        click = AsyncMock()
        wait = AsyncMock(return_value=True)
        context = MapRewardContext(
            page=self.page,
            stop_event=asyncio.Event(),
            win_reward_template=np.zeros((2, 2), dtype=np.uint8),
            win_reward_template_path=WIN_REWARD_TEMPLATE_PATH,
            reward_list_title_template=np.zeros((2, 2), dtype=np.uint8),
            reward_list_title_template_path=REWARD_LIST_TITLE_TEMPLATE_PATH,
            on_win=on_win,
            find_template_fn=find_template,
            find_template_matches_fn=Mock(),
            click_fn=click,
            wait_for_flow_timeout_fn=wait,
        )
        state = MapState()

        step = await handle_reward_list(context, state, popup, popup_gray)

        self.assertIs(step, MapLifecycleStep.CONTINUE)
        self.assertTrue(state.win_recorded)
        self.assertEqual(state.total_win, 7)
        self.assertFalse(state.first_win_done)
        self.assertTrue(state.reward_list_title_seen)
        on_win.assert_called_once_with()
        find_template.assert_not_called()
        click.assert_awaited_once_with(self.page, 320, 238)

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
        self.assertTrue(
            any(call_args.args[2] == "map_end.png" for call_args in find_template.call_args_list)
        )
        self.assertEqual(find_template_matches.call_count, 3)
        self.assertEqual(
            self.page.wait_for_timeout.await_args_list,
            [
                call(WIN_REWARD_EMPTY_DELAY_MS),
                call(WIN_REWARD_EMPTY_DELAY_MS),
            ],
        )

    @patch("hauntedroom.flows.automap_support.templates.load_template")
    @patch("hauntedroom.flows.automap_support.flow.find_template")
    @patch("hauntedroom.flows.automap_support.flow.find_template_matches")
    @patch("hauntedroom.flows.automap_support.flow.capture_page_bgr", new_callable=AsyncMock)
    async def test_map_end_reclicks_reward_list_title_until_it_disappears(
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
        title_scores = iter((0.99, 0.98, 0.20))

        def match_by_name(_frame, _template, name, **_kwargs):
            if name == "map_end.png":
                return 300, 400, 0.91
            if name == "reward_list_title.png":
                return 138, 37, next(title_scores)
            if name == "start_home.png":
                return 50, 600, 0.95
            return 0, 0, 0.0

        find_template.side_effect = match_by_name
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
                call(*WIN_REWARD_FOLLOWUP_CLICK),
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
