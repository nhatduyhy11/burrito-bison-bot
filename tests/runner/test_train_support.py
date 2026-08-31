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

from hauntedroom.core.runtime import FlowControl
from hauntedroom.flows.automap_support.train_select import TrainChoice
from hauntedroom.core.template_detection import (
    TemplateWaitResult,
    TemplateWaitStatus,
)
from hauntedroom.flows.train import run_train_flow
from hauntedroom.flows.train_support.entry import (
    check_and_click_train_challenge,
    wait_and_click_start_battle,
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
    wait_for_train_screen,
)


class TrainSupportTest(IsolatedAsyncioTestCase):
    def setUp(self):
        self.page = Mock()
        self.page.evaluate = AsyncMock()
        self.page.mouse = Mock()
        self.page.mouse.click = AsyncMock()
        self.page.wait_for_timeout = AsyncMock()

    @patch("hauntedroom.flows.train_support.entry.capture_page_bgr", new_callable=AsyncMock)
    async def test_check_and_click_train_challenge_not_available(self, capture_page_bgr):
        # Empty black frame
        capture_page_bgr.return_value = np.zeros((720, 640, 3), dtype=np.uint8)
        self.assertFalse(await check_and_click_train_challenge(self.page))
        self.page.mouse.click.assert_not_called()

    @patch("hauntedroom.flows.train_support.entry.capture_page_bgr", new_callable=AsyncMock)
    async def test_check_and_click_train_challenge_success(self, capture_page_bgr):
        available = cv2.imread(str(FIXTURES / "train_available.png"))
        capture_page_bgr.return_value = available
        self.assertTrue(await check_and_click_train_challenge(self.page))
        self.page.mouse.click.assert_awaited_once_with(400, 646)

    @patch("hauntedroom.flows.train_support.entry.load_template")
    @patch("hauntedroom.flows.train_support.entry.wait_for_template", new_callable=AsyncMock)
    async def test_wait_and_click_start_battle(self, wait_for_template, load_template):
        load_template.return_value = Mock()
        wait_for_template.return_value = TemplateWaitResult(
            TemplateWaitStatus.MATCHED,
            (401, 644, 0.95),
        )
        self.assertTrue(await wait_and_click_start_battle(self.page))
        self.page.mouse.click.assert_awaited_once_with(401, 644)

    @patch("hauntedroom.flows.train_support.entry.load_template")
    @patch("hauntedroom.flows.train_support.entry.wait_for_template", new_callable=AsyncMock)
    async def test_wait_and_click_start_battle_stopped(self, wait_for_template, load_template):
        load_template.return_value = Mock()
        wait_for_template.return_value = TemplateWaitResult(
            TemplateWaitStatus.STOPPED,
            None,
        )
        self.assertFalse(await wait_and_click_start_battle(self.page))
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

    @patch("hauntedroom.flows.train.run_train_ad_exit_cycle", new_callable=AsyncMock)
    async def test_unified_run_train_flow_delegates_to_ad_exit_single_cycle(self, mock_cycle):
        mock_cycle.return_value = True
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
