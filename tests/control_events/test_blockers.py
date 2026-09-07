import sys
from asyncio import Event
from pathlib import Path
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, Mock, patch

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

from hauntedroom.control_events.blockers import clear_blockers


class ClearBlockersTest(IsolatedAsyncioTestCase):
    @patch(
        "hauntedroom.control_events.blockers.close_profile_popup_tabs",
        new_callable=AsyncMock,
    )
    @patch(
        "hauntedroom.control_events.blockers.click_and_wait",
        new_callable=AsyncMock,
    )
    @patch(
        "hauntedroom.control_events.blockers.wait_for_flow_timeout",
        new_callable=AsyncMock,
    )
    @patch("hauntedroom.control_events.blockers.find_template")
    @patch(
        "hauntedroom.control_events.blockers.capture_page_grayscale",
        new_callable=AsyncMock,
    )
    async def test_newbie_blocker_uses_fixed_top_left_click(
        self,
        capture_page_grayscale,
        find_template,
        wait_for_flow_timeout,
        click_and_wait,
        _close_profile_popup_tabs,
    ):
        blocker_path = Path("overlay_newbie.png")
        until_path = Path("start_home.png")
        capture_page_grayscale.side_effect = [
            np.zeros((4, 4), dtype=np.uint8),
            np.zeros((4, 4), dtype=np.uint8),
        ]
        find_template.side_effect = [
            (405, 506, 0.99),
            (0, 0, 0.0),
            (20, 30, 0.95),
        ]
        wait_for_flow_timeout.return_value = True
        click_and_wait.return_value = True
        page = Mock()
        stop_event = Event()

        completed = await clear_blockers(
            page=page,
            blocker_paths=[blocker_path],
            until_template_path=until_path,
            templates={
                blocker_path: np.zeros((2, 2), dtype=np.uint8),
                until_path: np.zeros((2, 2), dtype=np.uint8),
            },
            threshold=0.9,
            timeout_ms=1_000,
            poll_ms=100,
            delay_ms=0,
            click_positions={"overlay_newbie.png": "center"},
            label="Clear blockers",
            stop_event=stop_event,
        )

        self.assertTrue(completed)
        click_and_wait.assert_awaited_once_with(
            page,
            (157, 54),
            100,
            stop_event,
        )
        self.assertEqual(
            find_template.call_args_list[0].args[2:],
            ("overlay_newbie.png", "center"),
        )
