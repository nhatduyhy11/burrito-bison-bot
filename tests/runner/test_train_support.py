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
CAPTURES = PROJECT_ROOT / "tests" / "fixtures" / "train_ad_exit_screen"
HERO_CAPTURES = PROJECT_ROOT / "tests" / "fixtures" / "hauntedroom-captures"

from hauntedroom.core.runtime import FlowControl
from hauntedroom.flows.automap_support.train_select import TrainChoice
from hauntedroom.flows.train import run_train_flow
from hauntedroom.flows.train_support.entry import (
    check_and_click_train_start,
    start_train_battle,
)
from hauntedroom.flows.train_support.hero_selection import select_train_heroes
from hauntedroom.flows.train_support.pet_and_ad import (
    activate_middle_pet_and_summon,
    run_pet_and_ad_phase,
    wait_and_dismiss_level_spin,
    wait_for_match_start,
)
from hauntedroom.flows.train_support.exit_flow import (
    exit_train_match,
    run_train_ad_exit_cycle,
    run_train_ad_exit_loop,
    wait_for_train_screen,
)
from hauntedroom.flows.train_support.common import (
    TRAIN_BOTTOM_SCAN_INTERVAL_MS,
    TRAIN_SCREEN_TEMPLATE_PATH,
    TrainCycleResult,
)


class TrainSupportTest(IsolatedAsyncioTestCase):
    def setUp(self):
        self.page = Mock()
        self.page.evaluate = AsyncMock()
        self.page.mouse = Mock()
        self.page.mouse.click = AsyncMock()
        self.page.wait_for_timeout = AsyncMock()

    def test_train_screen_template_is_a_runtime_asset(self):
        self.assertTrue(TRAIN_SCREEN_TEMPLATE_PATH.is_file())
        self.assertNotIn("tests", TRAIN_SCREEN_TEMPLATE_PATH.parts)

    async def _run_composite_cycle(self, *, pet_and_ad: bool):
        phases = {
            "wait_for_train_start_available": AsyncMock(return_value=True),
            "start_train_battle": AsyncMock(return_value=True),
            "select_train_heroes": AsyncMock(return_value=True),
            "wait_for_match_start": AsyncMock(return_value=True),
            "run_pet_and_ad_phase": AsyncMock(return_value=True),
            "exit_train_match": AsyncMock(return_value=True),
            "wait_for_train_screen": AsyncMock(return_value=True),
        }
        stop_event = asyncio.Event()
        with patch.multiple(
            "hauntedroom.flows.train_support.exit_flow",
            **phases,
        ):
            result = await run_train_ad_exit_cycle(
                self.page,
                stop_event,
                pet_and_ad=pet_and_ad,
            )
        return result, stop_event, phases

    @patch("hauntedroom.flows.train_support.entry.capture_page_bgr", new_callable=AsyncMock)
    async def test_check_and_click_train_start_not_available(self, capture_page_bgr):
        # Empty black frame
        capture_page_bgr.return_value = np.zeros((720, 640, 3), dtype=np.uint8)
        self.assertFalse(await check_and_click_train_start(self.page))
        self.page.mouse.click.assert_not_called()

    @patch("hauntedroom.flows.train_support.entry.capture_page_bgr", new_callable=AsyncMock)
    async def test_check_and_click_train_start_success(self, capture_page_bgr):
        available = cv2.imread(str(FIXTURES / "train_available.png"))
        capture_page_bgr.return_value = available
        self.assertTrue(await check_and_click_train_start(self.page))
        self.page.mouse.click.assert_awaited_once_with(400, 646)

    @patch("hauntedroom.flows.train_support.entry.capture_page_bgr", new_callable=AsyncMock)
    async def test_start_train_battle_clicks_strip_then_battle_button(
        self,
        capture_page_bgr,
    ):
        available = cv2.imread(str(FIXTURES / "train_available.png"))
        hero_select = cv2.imread(str(HERO_CAPTURES / "hero_select_screen_vn.png"))
        capture_page_bgr.side_effect = [
            available,
            available,
            np.zeros((720, 640, 3), dtype=np.uint8),
            hero_select,
        ]

        self.assertTrue(await start_train_battle(self.page))

        self.assertEqual(
            self.page.mouse.click.await_args_list,
            [call(400, 646), call(319, 689)],
        )
        self.assertEqual(
            self.page.wait_for_timeout.await_args_list,
            [call(TRAIN_BOTTOM_SCAN_INTERVAL_MS)] * 3,
        )

    @patch("hauntedroom.flows.train_support.entry.capture_page_bgr", new_callable=AsyncMock)
    async def test_start_train_battle_claims_reward_button_first(self, capture_page_bgr):
        reward = cv2.imread(str(FIXTURES / "train_reward.png"))
        hero_select = cv2.imread(str(HERO_CAPTURES / "hero_select_screen_vn.png"))
        capture_page_bgr.side_effect = [
            reward,
            reward,
            np.zeros((720, 640, 3), dtype=np.uint8),
            hero_select,
        ]

        self.assertTrue(await start_train_battle(self.page))

        self.assertEqual(self.page.mouse.click.await_args_list[0], call(319, 646))

    @patch("hauntedroom.flows.train_support.entry.capture_page_bgr", new_callable=AsyncMock)
    async def test_start_train_battle_clicks_dimmed_button_behind_popup(
        self,
        capture_page_bgr,
    ):
        collect = cv2.imread(str(FIXTURES / "train_reward_collect.png"))
        hero_select = cv2.imread(str(HERO_CAPTURES / "hero_select_screen_vn.png"))
        capture_page_bgr.side_effect = [
            collect,
            collect,
            np.zeros((720, 640, 3), dtype=np.uint8),
            hero_select,
        ]

        self.assertTrue(await start_train_battle(self.page))

        self.assertEqual(self.page.mouse.click.await_args_list[0], call(405, 645))

    @patch(
        "hauntedroom.flows.train_support.entry.save_timeout_screenshot",
        new_callable=AsyncMock,
    )
    @patch("hauntedroom.flows.train_support.entry.capture_page_bgr", new_callable=AsyncMock)
    async def test_start_train_battle_times_out_when_battle_button_is_missing(
        self,
        capture_page_bgr,
        save_timeout_screenshot,
    ):
        capture_page_bgr.return_value = np.zeros((720, 640, 3), dtype=np.uint8)
        save_timeout_screenshot.return_value = None

        with self.assertRaises(TimeoutError):
            await start_train_battle(
                self.page,
                screen_timeout_ms=30,
                screen_poll_ms=10,
            )

        save_timeout_screenshot.assert_awaited_once()

    @patch("hauntedroom.flows.train_support.entry.capture_page_bgr", new_callable=AsyncMock)
    async def test_start_train_battle_returns_false_when_stopped_during_hero_wait(
        self,
        capture_page_bgr,
    ):
        stop_event = asyncio.Event()
        zeros = np.zeros((720, 640, 3), dtype=np.uint8)

        def _capture_and_stop(_page):
            stop_event.set()
            return zeros

        capture_page_bgr.side_effect = _capture_and_stop

        self.assertFalse(await start_train_battle(self.page, stop_event))
        self.page.mouse.click.assert_not_called()

    async def test_start_train_battle_respects_stop_event(self):
        stop_event = asyncio.Event()
        stop_event.set()

        self.assertFalse(await start_train_battle(self.page, stop_event))
        self.page.mouse.click.assert_not_called()

    @patch("hauntedroom.flows.train_support.hero_selection.capture_page_bgr", new_callable=AsyncMock)
    async def test_select_train_heroes_timeout_raising(self, capture_page_bgr):
        capture_page_bgr.return_value = np.zeros((720, 640, 3), dtype=np.uint8)
        matcher = Mock()
        matcher.find_choice.return_value = None
        with self.assertRaises(TimeoutError):
            await select_train_heroes(
                self.page,
                rounds=1,
                timeout_ms=10,
                poll_ms=5,
                raise_on_timeout=True,
                matcher=matcher,
            )

    @patch("hauntedroom.flows.train_support.hero_selection.capture_page_bgr", new_callable=AsyncMock)
    async def test_select_train_heroes_timeout_suppressed(self, capture_page_bgr):
        capture_page_bgr.return_value = np.zeros((720, 640, 3), dtype=np.uint8)
        matcher = Mock()
        matcher.find_choice.return_value = None
        result = await select_train_heroes(
            self.page,
            rounds=1,
            timeout_ms=10,
            poll_ms=5,
            raise_on_timeout=False,
            matcher=matcher,
        )
        self.assertFalse(result)

    @patch("hauntedroom.flows.train_support.pet_and_ad.load_template")
    @patch("hauntedroom.flows.train_support.pet_and_ad.find_template")
    @patch("hauntedroom.flows.train_support.pet_and_ad.capture_page_bgr", new_callable=AsyncMock)
    async def test_wait_for_match_start(self, capture_page_bgr, find_template, load_template):
        capture_page_bgr.return_value = np.zeros((720, 640, 3), dtype=np.uint8)
        load_template.return_value = Mock()
        find_template.return_value = (233, 654, 0.85)
        self.assertTrue(await wait_for_match_start(self.page))

    @patch("hauntedroom.flows.train_support.pet_and_ad.load_template")
    @patch("hauntedroom.flows.train_support.common.find_template")
    @patch("hauntedroom.flows.train_support.pet_and_ad.capture_page_bgr", new_callable=AsyncMock)
    async def test_activate_middle_pet_and_summon(self, capture_page_bgr, common_find_template, load_template):
        capture_page_bgr.return_value = np.zeros((720, 640, 3), dtype=np.uint8)
        load_template.return_value = Mock()
        # 1: menu open check (True), 2: click loop check 1 (open), 3: click loop check 2 (closed)
        common_find_template.side_effect = [
            (444, 525, 0.90),
            (444, 525, 0.90),
            (444, 525, 0.20),
        ]
        self.assertTrue(await activate_middle_pet_and_summon(self.page))
        self.assertIn(call(320, 610), self.page.mouse.click.await_args_list)
        self.assertIn(call(450, 458), self.page.mouse.click.await_args_list)

    @patch("hauntedroom.flows.train_support.pet_and_ad.load_template")
    @patch("hauntedroom.flows.train_support.pet_and_ad.find_template")
    @patch("hauntedroom.flows.train_support.pet_and_ad.capture_page_bgr", new_callable=AsyncMock)
    async def test_wait_and_dismiss_level_spin(self, capture_page_bgr, find_template, load_template):
        capture_page_bgr.return_value = np.zeros((720, 640, 3), dtype=np.uint8)
        load_template.return_value = Mock()
        find_template.side_effect = [
            (285, 125, 0.90),  # appeared
            (285, 125, 0.90),  # click 1
            (285, 125, 0.20),  # disappeared
        ]
        self.assertTrue(await wait_and_dismiss_level_spin(self.page))
        self.assertIn(call(285, 665), self.page.mouse.click.await_args_list)

    @patch("hauntedroom.flows.train_support.exit_flow.load_template")
    @patch("hauntedroom.flows.train_support.exit_flow.click_pause_exit", new_callable=AsyncMock)
    async def test_exit_train_match(self, click_pause_exit, load_template):
        load_template.return_value = Mock()
        click_pause_exit.return_value = True
        self.assertTrue(await exit_train_match(self.page))
        click_pause_exit.assert_awaited_once()

    @patch("hauntedroom.flows.train_support.exit_flow.load_template")
    @patch("hauntedroom.flows.train_support.exit_flow.find_template")
    @patch("hauntedroom.flows.train_support.exit_flow.capture_page_bgr", new_callable=AsyncMock)
    async def test_wait_for_train_screen(self, capture_page_bgr, find_template, load_template):
        capture_page_bgr.return_value = np.zeros((720, 640, 3), dtype=np.uint8)
        load_template.return_value = Mock()
        find_template.side_effect = [
            (100, 100, 0.20),  # not visible
            (100, 100, 0.95),  # visible
        ]
        self.assertTrue(await wait_for_train_screen(self.page))
        self.page.mouse.click.assert_awaited_once_with(251, 633)

    async def test_pet_and_ad_cycle_runs_every_phase(self):
        result, stop_event, phases = await self._run_composite_cycle(
            pet_and_ad=True
        )

        self.assertIs(result, TrainCycleResult.COMPLETED)
        phases["wait_for_train_start_available"].assert_awaited_once_with(
            self.page, stop_event
        )
        phases["start_train_battle"].assert_awaited_once_with(
            self.page, stop_event
        )
        phases["select_train_heroes"].assert_awaited_once_with(
            self.page,
            stop_event,
            raise_on_timeout=False,
        )
        phases["wait_for_match_start"].assert_awaited_once_with(
            self.page, stop_event
        )
        phases["run_pet_and_ad_phase"].assert_awaited_once_with(
            self.page, stop_event
        )
        phases["exit_train_match"].assert_awaited_once_with(self.page, stop_event)
        phases["wait_for_train_screen"].assert_awaited_once_with(
            self.page, stop_event
        )

    async def test_immediate_exit_cycle_skips_pet_and_ad_phase(self):
        result, stop_event, phases = await self._run_composite_cycle(
            pet_and_ad=False
        )

        self.assertIs(result, TrainCycleResult.COMPLETED)
        phases["wait_for_train_start_available"].assert_awaited_once_with(
            self.page, stop_event
        )
        phases["start_train_battle"].assert_awaited_once_with(
            self.page, stop_event
        )
        phases["select_train_heroes"].assert_awaited_once_with(
            self.page,
            stop_event,
            raise_on_timeout=False,
        )
        phases["wait_for_match_start"].assert_awaited_once_with(
            self.page, stop_event
        )
        phases["run_pet_and_ad_phase"].assert_not_awaited()
        phases["exit_train_match"].assert_awaited_once_with(self.page, stop_event)
        phases["wait_for_train_screen"].assert_awaited_once_with(
            self.page, stop_event
        )

    @patch("hauntedroom.flows.train_support.exit_flow.wait_for_train_screen", new_callable=AsyncMock)
    @patch("hauntedroom.flows.train_support.exit_flow.run_train_ad_exit_cycle", new_callable=AsyncMock)
    async def test_loop_recovers_and_retries_after_temporary_timeout(
        self,
        run_cycle,
        wait_for_train_screen,
    ):
        stop_event = asyncio.Event()
        run_cycle.side_effect = [
            TrainCycleResult.RETRYABLE_FAILURE,
            TrainCycleResult.STOPPED,
        ]
        wait_for_train_screen.return_value = True

        self.assertFalse(
            await run_train_ad_exit_loop(self.page, stop_event, pet_and_ad=False)
        )

        self.assertEqual(run_cycle.await_count, 2)
        wait_for_train_screen.assert_awaited_once_with(self.page, stop_event)

    @patch("hauntedroom.flows.train_support.exit_flow.wait_for_train_screen", new_callable=AsyncMock)
    @patch("hauntedroom.flows.train_support.exit_flow.run_train_ad_exit_cycle", new_callable=AsyncMock)
    async def test_loop_stops_immediately_for_stop_event(
        self,
        run_cycle,
        wait_for_train_screen,
    ):
        run_cycle.return_value = TrainCycleResult.STOPPED
        stop_event = asyncio.Event()
        stop_event.set()

        self.assertFalse(
            await run_train_ad_exit_loop(self.page, stop_event, pet_and_ad=False)
        )

        run_cycle.assert_not_awaited()
        wait_for_train_screen.assert_not_awaited()

    @patch("hauntedroom.flows.train.run_train_ad_exit_cycle", new_callable=AsyncMock)
    async def test_unified_run_train_flow_delegates_to_ad_exit_single_cycle(self, mock_cycle):
        mock_cycle.return_value = TrainCycleResult.COMPLETED
        stop_event = asyncio.Event()

        result = await run_train_flow(self.page, stop_event=stop_event, pet_and_ad=False, loop=False)
        self.assertTrue(result)
        mock_cycle.assert_awaited_once_with(self.page, stop_event, pet_and_ad=False)

    @patch("hauntedroom.flows.train.run_train_ad_exit_loop", new_callable=AsyncMock)
    async def test_unified_run_train_flow_delegates_to_ad_exit_loop(self, mock_loop):
        mock_loop.return_value = True
        stop_event = asyncio.Event()

        result = await run_train_flow(self.page, stop_event=stop_event, pet_and_ad=True, loop=True)
        self.assertTrue(result)
        mock_loop.assert_awaited_once_with(self.page, stop_event, debug=False, pet_and_ad=True)
