import asyncio
import sys
from pathlib import Path
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, Mock, call, patch

import cv2
import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "tools"))
FIXTURES = PROJECT_ROOT / "tests" / "fixtures" / "train_flow"
HERO_CAPTURES = PROJECT_ROOT / "tests" / "fixtures" / "hauntedroom-captures"
HEADER_TEMPLATE_PATH = (
    PROJECT_ROOT / "tools" / "rooms" / "hero_select_battle_banner_top.png"
)

from hauntedroom.flows.automap_support.train_select import TrainChoice
from hauntedroom.flows.automap_support.map.model_state import MapRunState
from hauntedroom.flows.autotrain import TrainMode, run_train_flow
from hauntedroom.flows.train_support.common import TrainCycleResult
from hauntedroom.flows.train_support import (
    TRAIN_BOTTOM_BUTTON_REGION,
    TRAIN_BOTTOM_SCAN_INTERVAL_MS,
    TRAIN_ENTRY_SETTLE_MS,
    TRAIN_SELECTION_ROUNDS,
    TRAIN_SELECTION_SETTLE_MS,
    find_hero_select_battle_click,
    find_train_bottom_button_click,
    train_is_available,
)


class TrainFlowTest(IsolatedAsyncioTestCase):
    def setUp(self):
        self.page = Mock()
        self.page.evaluate = AsyncMock()
        self.page.mouse = Mock()
        self.page.mouse.click = AsyncMock()
        self.page.wait_for_timeout = AsyncMock()

    def test_available_fixture_is_detected(self):
        frame = cv2.imread(str(FIXTURES / "train_available.png"))
        self.assertTrue(train_is_available(frame))

    def test_unavailable_fixture_keeps_yellow_button_but_rejects_entry(self):
        frame = cv2.imread(str(FIXTURES / "train_unavailable.png"))
        self.assertEqual(find_train_bottom_button_click(frame), (400, 646))
        self.assertFalse(train_is_available(frame))

    def test_reward_actions_remain_available(self):
        for name in ("train_reward.png", "train_reward_collect.png", "train_screen_station22.png"):
            with self.subTest(name=name):
                self.assertTrue(train_is_available(cv2.imread(str(FIXTURES / name))))

    def test_other_notifications_cannot_enable_an_unmarked_challenge(self):
        frame = cv2.imread(str(FIXTURES / "train_unavailable.png"))
        available = cv2.imread(str(FIXTURES / "train_available.png"))
        # Give the exhausted lobby the available screenshot's AFK badge.
        frame[260:295, 490:520] = available[260:295, 490:520]
        self.assertFalse(train_is_available(frame))

    def test_finds_challenge_button_center_in_bottom_strip(self):
        frame = cv2.imread(str(FIXTURES / "train_available.png"))

        self.assertEqual(find_train_bottom_button_click(frame), (400, 646))

    def test_finds_reward_claim_button_center_in_bottom_strip(self):
        frame = cv2.imread(str(FIXTURES / "train_reward.png"))

        self.assertEqual(find_train_bottom_button_click(frame), (319, 646))

    def test_finds_dimmed_challenge_button_behind_reward_popup(self):
        frame = cv2.imread(str(FIXTURES / "train_reward_collect.png"))

        self.assertEqual(find_train_bottom_button_click(frame), (405, 645))

    def test_does_not_invent_click_when_bottom_strip_is_clear(self):
        frame = cv2.imread(str(FIXTURES / "train_available.png"))
        left, top, right, bottom = TRAIN_BOTTOM_BUTTON_REGION
        frame[top:bottom, left:right] = 0

        self.assertIsNone(find_train_bottom_button_click(frame))

    def test_bottom_scan_rejects_empty_frame(self):
        frame = np.zeros((720, 640, 3), dtype=np.uint8)

        self.assertIsNone(find_train_bottom_button_click(frame))

    def test_finds_battle_button_on_hero_select_screen(self):
        frame = cv2.imread(str(HERO_CAPTURES / "hero_select_screen_vn.png"))
        header = cv2.imread(str(HEADER_TEMPLATE_PATH), cv2.IMREAD_GRAYSCALE)

        self.assertEqual(find_hero_select_battle_click(frame, header), (319, 689))

    def test_battle_button_requires_hero_select_banner(self):
        frame = np.zeros((720, 640, 3), dtype=np.uint8)
        frame[672:706, 265:374] = (0, 200, 255)
        header = cv2.imread(str(HEADER_TEMPLATE_PATH), cv2.IMREAD_GRAYSCALE)

        self.assertIsNone(find_hero_select_battle_click(frame, header))

    def test_hero_select_without_battle_button_is_rejected(self):
        frame = cv2.imread(str(HERO_CAPTURES / "hero_select_screen_vn.png"))
        frame[650:719, 230:410] = 0
        header = cv2.imread(str(HEADER_TEMPLATE_PATH), cv2.IMREAD_GRAYSCALE)

        self.assertIsNone(find_hero_select_battle_click(frame, header))

    @patch("hauntedroom.flows.autotrain.check_and_click_train_start", new_callable=AsyncMock)
    async def test_mode_normal_requires_automap_before_entering_train(
        self,
        check_and_click_train_start,
    ):
        with self.assertRaisesRegex(
            ValueError,
            "automap_flow is required for normal train mode",
        ):
            await run_train_flow(self.page, mode=TrainMode.NORMAL)

        check_and_click_train_start.assert_not_awaited()

    @patch("hauntedroom.flows.train_support.hero_selection.TrainHeroMatcher")
    @patch("hauntedroom.flows.train_support.entry.capture_page_bgr", new_callable=AsyncMock)
    @patch("hauntedroom.flows.train_support.hero_selection.capture_page_bgr", new_callable=AsyncMock)
    async def test_mode_normal_confirms_five_rounds_then_hands_off_to_automap(
        self,
        hero_capture_page_bgr,
        entry_capture_page_bgr,
        matcher_type,
    ):
        """Mode 1: Normal train flow."""
        available = cv2.imread(str(FIXTURES / "train_available.png"))
        clear = np.zeros((720, 640, 3), dtype=np.uint8)
        hero_select = cv2.imread(str(HERO_CAPTURES / "hero_select_screen_vn.png"))
        entry_capture_page_bgr.side_effect = [
            available,
            available,
            available,
            clear,
            hero_select,
        ]
        hero_capture_page_bgr.return_value = available
        matcher = matcher_type.return_value
        choices = []
        for _ in range(TRAIN_SELECTION_ROUNDS):
            choices.extend(
                [
                    TrainChoice(172, 566),
                    TrainChoice(271, 566),
                    TrainChoice(319, 670, confirm=True),
                ]
            )
        matcher.find_choice.side_effect = choices
        automap_flow = AsyncMock(return_value=True)
        stop_event = asyncio.Event()
        run_state = MapRunState()

        result = await run_train_flow(
            self.page,
            automap_flow,
            stop_event,
            debug=True,
            run_state=run_state,
            mode=TrainMode.NORMAL,
        )

        self.assertTrue(result)
        self.assertEqual(
            self.page.mouse.click.await_args_list[:3],
            [call(400, 646), call(400, 646), call(319, 689)],
        )
        confirm_clicks = [
            click_args
            for click_args in self.page.mouse.click.await_args_list
            if click_args == call(319, 670)
        ]
        self.assertEqual(len(confirm_clicks), TRAIN_SELECTION_ROUNDS)
        self.assertEqual(
            self.page.wait_for_timeout.await_args_list,
            [
                call(TRAIN_ENTRY_SETTLE_MS),
                call(TRAIN_BOTTOM_SCAN_INTERVAL_MS),
                call(TRAIN_BOTTOM_SCAN_INTERVAL_MS),
                call(TRAIN_BOTTOM_SCAN_INTERVAL_MS),
            ]
            + [call(TRAIN_SELECTION_SETTLE_MS)] * 15,
        )
        automap_flow.assert_awaited_once_with(
            self.page,
            stop_event,
            debug=True,
            run_state=run_state,
            battle_mode="train",
        )

    @patch("hauntedroom.flows.autotrain.select_train_heroes", new_callable=AsyncMock)
    @patch("hauntedroom.flows.autotrain.start_train_battle", new_callable=AsyncMock)
    @patch(
        "hauntedroom.flows.autotrain.wait_for_train_start_available",
        new_callable=AsyncMock,
    )
    @patch("hauntedroom.flows.autotrain.wait_for_train_screen", new_callable=AsyncMock)
    async def test_mode_normal_loop_repeats_until_entry_waits_fail(
        self,
        wait_for_train_screen,
        wait_for_train_start_available,
        start_train_battle,
        select_train_heroes,
    ):
        """Mode 1 loop: wins back to back, then keeps waiting for attempts."""
        wait_for_train_screen.return_value = True
        wait_for_train_start_available.side_effect = [True, True, False]
        start_train_battle.return_value = True
        select_train_heroes.return_value = True
        automap_flow = AsyncMock(return_value=True)
        stop_event = asyncio.Event()
        run_state = MapRunState()

        result = await run_train_flow(
            self.page,
            automap_flow,
            stop_event,
            debug=False,
            run_state=run_state,
            mode=TrainMode.NORMAL,
            loop=True,
        )

        self.assertFalse(result)
        self.assertEqual(automap_flow.await_count, 2)
        self.assertEqual(start_train_battle.await_count, 2)
        self.assertEqual(select_train_heroes.await_count, 2)
        self.assertEqual(wait_for_train_start_available.await_count, 3)
        self.assertEqual(
            automap_flow.await_args_list,
            [
                call(
                    self.page,
                    stop_event,
                    debug=False,
                    run_state=run_state,
                    battle_mode="train",
                ),
                call(
                    self.page,
                    stop_event,
                    debug=False,
                    run_state=run_state,
                    battle_mode="train",
                ),
            ],
        )

    @patch("hauntedroom.flows.autotrain.select_train_heroes", new_callable=AsyncMock)
    @patch("hauntedroom.flows.autotrain.start_train_battle", new_callable=AsyncMock)
    @patch(
        "hauntedroom.flows.autotrain.wait_for_train_start_available",
        new_callable=AsyncMock,
    )
    @patch("hauntedroom.flows.autotrain.wait_for_train_screen", new_callable=AsyncMock)
    async def test_mode_normal_loop_stops_when_battle_reports_stop(
        self,
        wait_for_train_screen,
        wait_for_train_start_available,
        start_train_battle,
        select_train_heroes,
    ):
        """Mode 1 loop: a stopped auto-battle ends the whole train loop."""
        wait_for_train_screen.return_value = True
        wait_for_train_start_available.return_value = True
        start_train_battle.return_value = True
        select_train_heroes.return_value = True
        automap_flow = AsyncMock(return_value=False)

        result = await run_train_flow(
            self.page,
            automap_flow,
            asyncio.Event(),
            mode=TrainMode.NORMAL,
            loop=True,
        )

        self.assertFalse(result)
        automap_flow.assert_awaited_once()
        wait_for_train_start_available.assert_awaited_once()

    @patch("hauntedroom.flows.autotrain.select_train_heroes", new_callable=AsyncMock)
    @patch("hauntedroom.flows.autotrain.start_train_battle", new_callable=AsyncMock)
    @patch(
        "hauntedroom.flows.autotrain.wait_for_train_start_available",
        new_callable=AsyncMock,
    )
    @patch("hauntedroom.flows.autotrain.wait_for_train_screen", new_callable=AsyncMock)
    async def test_mode_normal_loop_stops_on_hero_selection_failure(
        self,
        wait_for_train_screen,
        wait_for_train_start_available,
        start_train_battle,
        select_train_heroes,
    ):
        """Mode 1 loop: hero selection must not raise mid-loop; stop instead."""
        wait_for_train_screen.return_value = True
        wait_for_train_start_available.return_value = True
        start_train_battle.return_value = True
        select_train_heroes.return_value = False
        automap_flow = AsyncMock()

        result = await run_train_flow(
            self.page,
            automap_flow,
            asyncio.Event(),
            mode=TrainMode.NORMAL,
            loop=True,
        )

        self.assertFalse(result)
        automap_flow.assert_not_awaited()
        self.assertEqual(
            select_train_heroes.await_args.kwargs, {"raise_on_timeout": False}
        )

    @patch("hauntedroom.flows.autotrain.run_train_ad_exit_cycle", new_callable=AsyncMock)
    async def test_mode_exit_immediately_single_cycle(self, mock_cycle):
        """Mode 2: Exit immediately after match start."""
        mock_cycle.return_value = TrainCycleResult.COMPLETED
        stop_event = asyncio.Event()

        result = await run_train_flow(
            self.page,
            stop_event=stop_event,
            mode=TrainMode.EXIT_IMMEDIATELY,
            loop=False,
        )
        self.assertTrue(result)
        mock_cycle.assert_awaited_once_with(self.page, stop_event, pet_and_ad=False)

    @patch("hauntedroom.flows.autotrain.run_train_ad_exit_loop", new_callable=AsyncMock)
    async def test_mode_exit_immediately_loop(self, mock_loop):
        """Mode 2 loop: Exit immediately after match start in loop."""
        mock_loop.return_value = True
        stop_event = asyncio.Event()

        result = await run_train_flow(
            self.page,
            stop_event=stop_event,
            mode="exit_immediately",
            loop=True,
        )
        self.assertTrue(result)
        mock_loop.assert_awaited_once_with(self.page, stop_event, debug=False, pet_and_ad=False)

    @patch("hauntedroom.flows.autotrain.run_train_ad_exit_cycle", new_callable=AsyncMock)
    async def test_mode_pet_and_ad_single_cycle(self, mock_cycle):
        """Mode 3: Pet summon, spin dismissal, then exit."""
        mock_cycle.return_value = TrainCycleResult.COMPLETED
        stop_event = asyncio.Event()

        result = await run_train_flow(
            self.page,
            stop_event=stop_event,
            mode=TrainMode.PET_AND_AD,
            loop=False,
        )
        self.assertTrue(result)
        mock_cycle.assert_awaited_once_with(self.page, stop_event, pet_and_ad=True)

    @patch("hauntedroom.flows.autotrain.run_train_ad_exit_loop", new_callable=AsyncMock)
    async def test_mode_pet_and_ad_loop(self, mock_loop):
        """Mode 3 loop: Pet summon, spin dismissal, then exit in loop."""
        mock_loop.return_value = True
        stop_event = asyncio.Event()

        result = await run_train_flow(
            self.page,
            stop_event=stop_event,
            mode="pet_and_ad",
            loop=True,
        )
        self.assertTrue(result)
        mock_loop.assert_awaited_once_with(self.page, stop_event, debug=False, pet_and_ad=True)
