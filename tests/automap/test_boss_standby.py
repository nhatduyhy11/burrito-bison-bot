import asyncio
import sys
from pathlib import Path
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, Mock, call, patch

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))

from hauntedroom.core.runtime import FlowControl
from hauntedroom.flows.automap import AutomapConfig, AutomapFlow
from hauntedroom.flows.automap_support.upgrade_action import AUTOMAP_POLL_MS
from tests.automap.template_factory import build_test_automap_templates


class BossStandbyTest(IsolatedAsyncioTestCase):
    async def test_standby_polls_without_actions_then_pauses_at_any_boss(self):
        for final_boss, progress_only in ((False, False), (True, False), (True, True)):
            with self.subTest(final_boss=final_boss, progress_only=progress_only):
                control = FlowControl()
                control.standby_at_next_boss()
                page = Mock()
                page.evaluate = AsyncMock()
                page.mouse.click = AsyncMock()
                page.wait_for_timeout = AsyncMock()
                flow = AutomapFlow(
                    page, control, AutomapConfig(), build_test_automap_templates(),
                )
                gameplay_handlers = (
                    "handle_new_account_lubu_close", "handle_level_spin_interrupt",
                    "handle_map_end", "handle_initial_gear", "handle_level_up",
                    "handle_build_structure", "hero_levelup",
                )
                for name in gameplay_handlers:
                    setattr(flow, name, AsyncMock(return_value=False))
                frame = np.zeros((720, 640, 3), dtype=np.uint8)
                with (
                    patch("hauntedroom.flows.automap_support.flow.capture_page_bgr",
                          AsyncMock(return_value=frame)) as capture,
                    patch("hauntedroom.flows.automap_support.flow.find_boss_health_bar",
                          side_effect=[None, None, None if progress_only else (250, 280, 0.99)]),
                    patch("hauntedroom.flows.automap_support.flow.boss_progress_is_full",
                          side_effect=[False, False, final_boss]),
                    patch("hauntedroom.flows.automap_support.flow.find_pause_exit_button",
                          side_effect=[None, (100, 100)]),
                    patch("hauntedroom.flows.automap_support.flow.find_template",
                          return_value=(612, 35, 0.99)),
                    patch("hauntedroom.flows.automap_support.flow.deploy_boss_pet",
                          new_callable=AsyncMock) as deploy_pet,
                ):
                    task = asyncio.create_task(flow.run())
                    try:
                        for _ in range(50):
                            if control.is_paused or task.done():
                                break
                            await asyncio.sleep(0)
                        self.assertTrue(control.is_paused)
                        self.assertFalse(control.is_boss_standby)
                        self.assertEqual(flow.state.map_end_armed, final_boss and not progress_only)
                        page.mouse.click.assert_awaited_once_with(612, 35)
                        self.assertEqual(capture.await_count, 4)
                        self.assertEqual(
                            page.wait_for_timeout.await_args_list[:2],
                            [call(AUTOMAP_POLL_MS), call(AUTOMAP_POLL_MS)],
                        )
                        for name in gameplay_handlers:
                            getattr(flow, name).assert_not_awaited()
                        deploy_pet.assert_not_awaited()
                    finally:
                        control.set()
                        await asyncio.wait_for(task, 1)

    async def test_standby_interrupts_an_inflight_action_sequence(self):
        control = FlowControl()
        flow = AutomapFlow(
            Mock(), control, AutomapConfig(), build_test_automap_templates(),
        )
        started = asyncio.Event()
        cleaned_up = asyncio.Event()
        click_after_wait = AsyncMock()

        async def handler(*_frames):
            started.set()
            try:
                await asyncio.Event().wait()
                await click_after_wait()
            finally:
                cleaned_up.set()

        frame = np.zeros((2, 2, 3), dtype=np.uint8)
        task = asyncio.create_task(flow.run_interruptible_handler(handler, frame, frame))
        await started.wait()
        control.standby_at_next_boss()
        self.assertFalse(await asyncio.wait_for(task, 1))
        self.assertTrue(cleaned_up.is_set())
        click_after_wait.assert_not_awaited()
