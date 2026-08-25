import asyncio
import sys
from pathlib import Path
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, Mock, call, patch

import cv2


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

from hauntedroom.flows.new_account import (  # noqa: E402
    NEW_ACCOUNT_ACTION_CLICK,
    NEW_ACCOUNT_CLICK_DELAY_MS,
    run_new_account_flow,
)


class NewAccountFlowTest(IsolatedAsyncioTestCase):
    def setUp(self):
        self.page = Mock()
        self.page.evaluate = AsyncMock()
        self.page.wait_for_timeout = AsyncMock()
        self.page.mouse = Mock()
        self.page.mouse.click = AsyncMock()

    @patch(
        "hauntedroom.flows.new_account.capture_page_bgr",
        new_callable=AsyncMock,
    )
    async def test_clicks_both_steps_at_one_point_then_starts_automap(
        self,
        capture_page_bgr,
    ):
        fixture_dir = PROJECT_ROOT / "tests" / "fixtures" / "special_flow"
        step1 = cv2.imread(str(fixture_dir / "new_acc_step1.png"))
        step2 = cv2.imread(str(fixture_dir / "new_acc_step2.png"))
        automap = cv2.imread(
            str(
                PROJECT_ROOT
                / "tests"
                / "fixtures"
                / "hauntedroom-captures"
                / "boss_screen"
                / "final_boss_miss.png"
            )
        )
        capture_page_bgr.side_effect = [step1, step2, automap]
        automap_flow = AsyncMock(return_value=True)
        stop_event = asyncio.Event()
        run_state = object()

        completed = await run_new_account_flow(
            self.page,
            automap_flow,
            stop_event,
            True,
            run_state=run_state,
        )

        self.assertTrue(completed)
        self.assertEqual(
            self.page.mouse.click.await_args_list,
            [call(*NEW_ACCOUNT_ACTION_CLICK), call(*NEW_ACCOUNT_ACTION_CLICK)],
        )
        self.assertEqual(
            self.page.wait_for_timeout.await_args_list,
            [call(NEW_ACCOUNT_CLICK_DELAY_MS), call(NEW_ACCOUNT_CLICK_DELAY_MS)],
        )
        automap_flow.assert_awaited_once_with(
            self.page,
            stop_event,
            debug=True,
            run_state=run_state,
            new_account_lubu_popup_active=True,
        )

    @patch(
        "hauntedroom.flows.new_account.capture_page_bgr",
        new_callable=AsyncMock,
    )
    async def test_stopped_flow_does_not_capture_or_click(self, capture_page_bgr):
        stop_event = asyncio.Event()
        stop_event.set()

        completed = await run_new_account_flow(
            self.page,
            AsyncMock(),
            stop_event,
        )

        self.assertFalse(completed)
        capture_page_bgr.assert_not_awaited()
        self.page.mouse.click.assert_not_awaited()
