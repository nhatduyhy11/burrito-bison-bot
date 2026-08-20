import asyncio
import sys
from pathlib import Path
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, Mock, patch

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

from hauntedroom.flows.automap import AutomapConfig, AutomapFlow
from hauntedroom.flows.automap_support.boss_flow import BossCriticalOutcome


class BossAutomapAdapterTest(IsolatedAsyncioTestCase):
    @patch(
        "hauntedroom.flows.automap.load_template",
        return_value=np.zeros((2, 2), dtype=np.uint8),
    )
    async def test_boss_outcome_updates_automap_state(self, _load_template):
        page = Mock()
        outcome = BossCriticalOutcome(
            handled=True,
            final_boss_pet_deployed=True,
            boss_detection_logged=True,
        )
        flow = AutomapFlow(page, asyncio.Event(), AutomapConfig())

        with patch(
            "hauntedroom.flows.automap._handle_boss_critical",
            new_callable=AsyncMock,
            return_value=outcome,
        ) as handle_boss:
            handled = await flow.handle_boss_critical(
                np.zeros((720, 640, 3), dtype=np.uint8),
                np.zeros((720, 640), dtype=np.uint8),
            )

        self.assertTrue(handled)
        self.assertTrue(flow.state.final_boss_pet_deployed)
        self.assertTrue(flow.state.boss_detection_logged)
        handle_boss.assert_awaited_once()
