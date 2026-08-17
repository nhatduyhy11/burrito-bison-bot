import asyncio
import sys
from pathlib import Path
from unittest import IsolatedAsyncioTestCase
from unittest.mock import ANY, AsyncMock, Mock, call, patch

import cv2
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TOOLS_DIR = PROJECT_ROOT / "tools"
FIXTURES_DIR = PROJECT_ROOT / "tests" / "fixtures"
MAP_WIN_FIXTURES_DIR = FIXTURES_DIR / "hauntedroom-captures" / "map_win"
sys.path.insert(0, str(TOOLS_DIR))

from hauntedroom.core.template import find_template as find_real_template
from hauntedroom.core.template import find_template_matches as find_real_template_matches
from hauntedroom.core.template import load_template as load_real_template
from hauntedroom.flows.automap import (
    AUTOMAP_POLL_MS,
    DAILY_FIRST_WIN_CHECKBOX_TEMPLATE_PATH,
    DAILY_FIRST_WIN_CHECKED_TEMPLATE_PATH,
    DAILY_FIRST_WIN_TEMPLATE_PATH,
    MAP_END_CHECK_INTERVAL_SEC,
    MAP_END_TEMPLATE_THRESHOLD,
    MAP_COMPLETION_BLOCKER_TEMPLATE_PATHS,
    MAP_WIN_TEMPLATE_DIR,
    REWARD_LIST_TITLE_TEMPLATE_PATH,
    REWARD_LIST_TITLE_TEMPLATE_THRESHOLD,
    WIN_REWARD_EMPTY_DELAY_MS,
    WIN_REWARD_FOLLOWUP_CLICK,
    WIN_REWARD_FOLLOWUP_CLICK_COUNT,
    WIN_REWARD_RECHECK_MS,
    WIN_REWARD_TEMPLATE_PATH,
    WIN_REWARD_TEMPLATE_THRESHOLD,
    run_automap_flow,
)
from hauntedroom.flows.automap_support.map_completion import (
    MAP_COMPLETION_BLOCKER_THRESHOLD,
    find_map_completion_blocker,
)
from hauntedroom.flows.automap_support.map_first_win import (
    DAILY_FIRST_WIN_CHECK_DELAY_MS,
    handle_daily_first_win,
)
from hauntedroom.flows import automap
from hauntedroom.flows.automap_support.detectors import (
    HERO_LEVELUP_PRICE_REGION,
)


class MapEndTest(IsolatedAsyncioTestCase):

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

    @patch("hauntedroom.flows.automap.load_template")
    @patch(
        "hauntedroom.flows.automap.find_template",
        side_effect=[
            (0, 0, 0.0),
            (300, 400, 0.91),
            (0, 0, 0.0),
            (138, 37, 0.99),
            (0, 0, 0.20),
            (50, 600, 0.95),
        ],
    )
    @patch("hauntedroom.flows.automap.find_template_matches")
    @patch("hauntedroom.flows.automap.capture_page_bgr", new_callable=AsyncMock)
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
        reward_matches = [
            (305, 466, 1.0),
            (341, 466, 0.98),
        ]
        find_template_matches.return_value = reward_matches

        on_win = Mock(return_value=1)
        with patch("builtins.print") as print_mock:
            completed = await run_automap_flow(
                self.page,
                asyncio.Event(),
                on_win=on_win,
            )

        self.assertTrue(completed)
        self.assertTrue(automap.FIRST_WIN_DONE)
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
        "hauntedroom.flows.automap.load_template",
        return_value=np.zeros((2, 2), dtype=np.uint8),
    )
    @patch("hauntedroom.flows.automap.find_template")
    @patch("hauntedroom.flows.automap.find_template_matches", return_value=[])
    @patch("hauntedroom.flows.automap.capture_page_bgr", new_callable=AsyncMock)
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

    def test_daily_first_win_templates_match_supplied_screens(self):
        label_template = load_real_template(DAILY_FIRST_WIN_TEMPLATE_PATH)
        checkbox_template = load_real_template(
            DAILY_FIRST_WIN_CHECKBOX_TEMPLATE_PATH
        )
        checked_template = load_real_template(
            DAILY_FIRST_WIN_CHECKED_TEMPLATE_PATH
        )

        for fixture_name in (
            "daily_first_win.png",
            "daily_first_win_checked.png",
        ):
            with self.subTest(fixture_name=fixture_name):
                frame = cv2.imread(
                    str(MAP_WIN_FIXTURES_DIR / fixture_name),
                    cv2.IMREAD_GRAYSCALE,
                )
                self.assertIsNotNone(frame)
                _x, _y, label_score = find_real_template(
                    frame,
                    label_template,
                    DAILY_FIRST_WIN_TEMPLATE_PATH.name,
                    scales=(1.0,),
                )
                _x, _y, unchecked_score = find_real_template(
                    frame,
                    checkbox_template,
                    DAILY_FIRST_WIN_CHECKBOX_TEMPLATE_PATH.name,
                    scales=(1.0,),
                )
                _x, _y, checked_score = find_real_template(
                    frame,
                    checked_template,
                    DAILY_FIRST_WIN_CHECKED_TEMPLATE_PATH.name,
                    scales=(1.0,),
                )
                self.assertGreaterEqual(label_score, 0.90)
                if fixture_name == "daily_first_win.png":
                    self.assertGreaterEqual(unchecked_score, 0.95)
                    self.assertLess(checked_score, 0.95)
                else:
                    self.assertLess(unchecked_score, 0.95)
                    self.assertGreaterEqual(checked_score, 0.95)

    async def test_daily_first_win_retries_until_checkbox_is_confirmed(self):
        find_template = Mock()

        checked_scores = iter((0.20, 0.20, 0.99))
        unchecked_scores = iter((0.99, 0.99))

        def match_with_checkbox_state(_frame, _template, name, **_kwargs):
            if name == DAILY_FIRST_WIN_TEMPLATE_PATH.name:
                return (332, 442, 0.99)
            if name == DAILY_FIRST_WIN_CHECKED_TEMPLATE_PATH.name:
                return (10, 10, next(checked_scores))
            return (10, 10, next(unchecked_scores))

        find_template.side_effect = match_with_checkbox_state
        wait = AsyncMock(return_value=True)
        click = AsyncMock()
        capture = AsyncMock(
            return_value=np.zeros((720, 640, 3), dtype=np.uint8)
        )
        checkpoint = AsyncMock(return_value=True)

        handled = await handle_daily_first_win(
            self.page,
            asyncio.Event(),
            np.zeros((720, 640), dtype=np.uint8),
            daily_first_win_template=np.zeros((18, 150), dtype=np.uint8),
            daily_first_win_template_path=DAILY_FIRST_WIN_TEMPLATE_PATH,
            daily_first_win_checkbox_template=np.zeros((19, 19), dtype=np.uint8),
            daily_first_win_checkbox_template_path=(
                DAILY_FIRST_WIN_CHECKBOX_TEMPLATE_PATH
            ),
            daily_first_win_checked_template=np.zeros((19, 19), dtype=np.uint8),
            daily_first_win_checked_template_path=(
                DAILY_FIRST_WIN_CHECKED_TEMPLATE_PATH
            ),
            capture_page_bgr_fn=capture,
            to_grayscale_fn=lambda frame: frame[:, :, 0],
            find_template_fn=find_template,
            click_fn=click,
            wait_for_flow_timeout_fn=wait,
            flow_checkpoint_fn=checkpoint,
            poll_ms=100,
        )

        self.assertTrue(handled)
        self.assertEqual(click.await_count, 3)
        self.assertEqual(click.await_args_list[-1], call(self.page, 377, 478))
        self.assertEqual(
            wait.await_args_list,
            [
                call(self.page, DAILY_FIRST_WIN_CHECK_DELAY_MS, ANY),
                call(self.page, DAILY_FIRST_WIN_CHECK_DELAY_MS, ANY),
            ],
        )

    async def test_daily_first_win_never_toggles_a_checked_checkbox(self):
        frame = cv2.imread(
            str(MAP_WIN_FIXTURES_DIR / "daily_first_win_checked.png"),
            cv2.IMREAD_GRAYSCALE,
        )
        click = AsyncMock()
        wait = AsyncMock(return_value=True)

        handled = await handle_daily_first_win(
            self.page,
            asyncio.Event(),
            frame,
            daily_first_win_template=load_real_template(
                DAILY_FIRST_WIN_TEMPLATE_PATH
            ),
            daily_first_win_template_path=DAILY_FIRST_WIN_TEMPLATE_PATH,
            daily_first_win_checkbox_template=load_real_template(
                DAILY_FIRST_WIN_CHECKBOX_TEMPLATE_PATH
            ),
            daily_first_win_checkbox_template_path=(
                DAILY_FIRST_WIN_CHECKBOX_TEMPLATE_PATH
            ),
            daily_first_win_checked_template=load_real_template(
                DAILY_FIRST_WIN_CHECKED_TEMPLATE_PATH
            ),
            daily_first_win_checked_template_path=(
                DAILY_FIRST_WIN_CHECKED_TEMPLATE_PATH
            ),
            capture_page_bgr_fn=AsyncMock(),
            to_grayscale_fn=lambda image: image,
            find_template_fn=find_real_template,
            click_fn=click,
            wait_for_flow_timeout_fn=wait,
            flow_checkpoint_fn=AsyncMock(return_value=True),
            poll_ms=100,
        )

        self.assertTrue(handled)
        click.assert_awaited_once_with(self.page, 377, 478)
        wait.assert_not_awaited()

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
