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
    AutomapConfig,
    AutomapFlow,
)


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

        self.assertEqual(load_template.call_count, 9)

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
            AutomapConfig(click_exit_on_boss=False),
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
