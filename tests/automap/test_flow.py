import asyncio
import sys
from pathlib import Path
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, Mock, patch

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TOOLS_DIR = PROJECT_ROOT / "tools"
FIXTURES_DIR = PROJECT_ROOT / "tests" / "fixtures"
sys.path.insert(0, str(TOOLS_DIR))

from hauntedroom.flows.automap import (
    BOSS_RECHECK_INTERVAL_MS,
    MAP_COMPLETION_BLOCKER_TEMPLATE_PATHS,
    AutomapConfig,
    AutomapFlow,
    AutomapState,
    AutomapTemplates,
)
from hauntedroom.flows.automap_support.state import AutomapRunContext


class AutomapFlowTest(IsolatedAsyncioTestCase):
    def setUp(self):
        self.page = Mock()
        self.page.evaluate = AsyncMock()
        self.page.wait_for_timeout = AsyncMock()
        self.page.mouse = Mock()
        self.page.mouse.click = AsyncMock()
        self.page.mouse.move = AsyncMock()
        self.page.mouse.down = AsyncMock()
        self.page.mouse.up = AsyncMock()

    @patch("hauntedroom.flows.automap.load_template")
    async def test_automap_flow_loads_all_templates_once_per_run(self, load_template):
        load_template.return_value = np.zeros((2, 2), dtype=np.uint8)

        AutomapFlow(self.page, asyncio.Event(), AutomapConfig())

        self.assertEqual(
            load_template.call_count,
            12 + len(MAP_COMPLETION_BLOCKER_TEMPLATE_PATHS),
        )

    @patch("hauntedroom.flows.automap.load_template")
    async def test_automap_flow_uses_injected_templates_and_state(
        self,
        load_template,
    ):
        image = np.zeros((2, 2), dtype=np.uint8)
        templates = AutomapTemplates(
            lv_up=image,
            built=image,
            lv_spin=image,
            map_end=image,
            win_reward=image,
            reward_list_title=image,
            daily_first_win=image,
            daily_first_win_checkbox=image,
            daily_first_win_checked=image,
            boss_hp=image,
            start_home=image,
            exit_click=image,
            map_completion_blockers=(),
            hero_levelup={},
        )
        state = AutomapState(initial_gear_unlocked=True)
        run_context = AutomapRunContext(daily_first_win_done=True)

        flow = AutomapFlow(
            self.page,
            asyncio.Event(),
            AutomapConfig(),
            templates=templates,
            state=state,
            run_context=run_context,
        )

        self.assertIs(flow.templates, templates)
        self.assertIs(flow.state, state)
        self.assertIs(flow.run_context, run_context)
        self.assertTrue(flow.run_context.daily_first_win_done)
        self.assertTrue(flow.state.initial_gear_unlocked)
        load_template.assert_not_called()

    @patch("hauntedroom.flows.automap.capture_page_bgr", new_callable=AsyncMock)
    @patch("hauntedroom.flows.automap.load_template")
    async def test_boss_handler_throttles_next_capture(
        self,
        load_template,
        capture_page_bgr,
    ):
        load_template.return_value = np.zeros((2, 2), dtype=np.uint8)
        capture_page_bgr.return_value = np.zeros((720, 640, 3), dtype=np.uint8)
        stop_event = asyncio.Event()
        self.page.wait_for_timeout.side_effect = lambda _ms: stop_event.set()
        flow = AutomapFlow(
            self.page,
            stop_event,
            AutomapConfig(),
        )
        flow.handle_level_spin_interrupt = AsyncMock(return_value=False)
        flow.handle_map_end = AsyncMock(return_value=False)
        flow.handle_initial_gear = AsyncMock(return_value=False)
        flow.handle_boss_critical = AsyncMock(return_value=True)
        flow.handle_level_up = AsyncMock(return_value=False)
        flow.handle_build_structure = AsyncMock(return_value=False)
        flow.hero_levelup = AsyncMock(return_value=False)

        await flow.run()

        self.page.wait_for_timeout.assert_awaited_once_with(BOSS_RECHECK_INTERVAL_MS)
        capture_page_bgr.assert_awaited_once_with(self.page)
