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

from hauntedroom.flows.automap import AutomapConfig, AutomapFlow


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

