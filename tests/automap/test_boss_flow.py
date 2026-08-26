import asyncio
import sys
from pathlib import Path
from unittest import IsolatedAsyncioTestCase
from unittest.mock import ANY, AsyncMock, Mock

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

from hauntedroom.core.runtime import FlowControl
from hauntedroom.flows.automap_support.boss_flow import handle_boss_critical


class BossFlowTest(IsolatedAsyncioTestCase):
    def setUp(self):
        self.page = Mock()
        self.frame_bgr = np.zeros((720, 640, 3), dtype=np.uint8)
        self.frame_gray = np.zeros((720, 640), dtype=np.uint8)
        self.find_health_bar = Mock(return_value=(250, 280, 0.90))
        self.classify_progress = Mock(return_value=False)
        self.find_pause = Mock(return_value=(612, 35, 0.95))
        self.deploy_pet = AsyncMock(return_value=True)
        self.click = AsyncMock()

    async def _handle(
        self,
        stop_event=None,
        *,
        final_boss_pet_deployed=False,
        boss_detection_logged=False,
    ):
        if stop_event is None:
            stop_event = asyncio.Event()
        return await handle_boss_critical(
            self.page,
            stop_event,
            self.frame_bgr,
            self.frame_gray,
            boss_hp_template=np.zeros((2, 2), dtype=np.uint8),
            exit_click_template=np.zeros((2, 2), dtype=np.uint8),
            exit_click_template_name="exit_click.png",
            final_boss_pet_deployed=final_boss_pet_deployed,
            boss_detection_logged=boss_detection_logged,
            find_boss_health_bar_fn=self.find_health_bar,
            boss_progress_is_full_fn=self.classify_progress,
            find_template_fn=self.find_pause,
            deploy_boss_pet_fn=self.deploy_pet,
            click_fn=self.click,
        )

    async def test_mini_boss_is_classified_without_an_armed_pause(self):
        outcome = await self._handle()

        self.assertFalse(outcome.handled)
        self.assertTrue(outcome.boss_detection_logged)
        self.classify_progress.assert_called_once_with(self.frame_bgr)
        self.find_pause.assert_not_called()

    async def test_armed_any_boss_clicks_game_pause_then_pauses_script(self):
        control = FlowControl()
        control.pause_at_next_boss(final_only=False)

        async def assert_script_is_running_when_game_pause_is_clicked(*_args):
            self.assertFalse(control.is_paused)

        self.click.side_effect = assert_script_is_running_when_game_pause_is_clicked

        outcome = await self._handle(control)

        self.assertTrue(outcome.handled)
        self.click.assert_awaited_once_with(self.page, 612, 35)
        self.assertTrue(control.is_paused)
        self.assertIsNone(control.boss_pause_target)

    async def test_armed_final_boss_pauses_before_pet_deploy(self):
        control = FlowControl()
        control.pause_at_next_boss(final_only=True)
        self.classify_progress.return_value = True

        outcome = await self._handle(control)

        self.assertTrue(outcome.handled)
        self.click.assert_awaited_once_with(self.page, 612, 35)
        self.deploy_pet.assert_not_awaited()
        self.assertTrue(control.is_paused)

    async def test_armed_boss_pauses_script_when_game_pause_is_not_found(self):
        control = FlowControl()
        control.pause_at_next_boss(final_only=False)
        self.find_pause.return_value = (612, 35, 0.50)

        outcome = await self._handle(control)

        self.assertTrue(outcome.handled)
        self.assertTrue(control.is_paused)
        self.deploy_pet.assert_not_awaited()
        self.click.assert_not_awaited()

    async def test_final_boss_pause_ignores_mini_boss_and_remains_armed(self):
        control = FlowControl()
        control.pause_at_next_boss(final_only=True)

        outcome = await self._handle(control)

        self.assertFalse(outcome.handled)
        self.assertFalse(control.is_paused)
        self.assertEqual(
            control.boss_pause_target,
            FlowControl.PAUSE_AT_FINAL_BOSS,
        )

    async def test_progress_is_not_classified_without_an_hp_match(self):
        self.find_health_bar.return_value = None

        outcome = await self._handle()

        self.assertFalse(outcome.handled)
        self.assertFalse(outcome.boss_detection_logged)
        self.classify_progress.assert_not_called()

    async def test_final_boss_deploys_pet_and_returns_updated_state(self):
        self.classify_progress.return_value = True

        outcome = await self._handle()

        self.assertTrue(outcome.handled)
        self.deploy_pet.assert_awaited_once_with(
            self.page,
            boss_position=(250, 280),
            frame_bgr=self.frame_bgr,
            stop_event=ANY,
        )
        self.assertTrue(outcome.final_boss_pet_deployed)
        self.assertTrue(outcome.boss_detection_logged)
        self.assertTrue(outcome.final_boss_detected)
