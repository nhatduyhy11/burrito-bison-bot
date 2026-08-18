import asyncio
import sys
from pathlib import Path
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, Mock, call, patch

import cv2
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TOOLS_DIR = PROJECT_ROOT / "tools"
FIXTURES_DIR = (
    PROJECT_ROOT / "tests" / "fixtures" / "hauntedroom-captures" / "gear_placement"
)
sys.path.insert(0, str(TOOLS_DIR))

from hauntedroom.flows.automap import AutomapConfig, AutomapFlow
from hauntedroom.flows.automap_support.gear_action import (
    GEAR_DRAG_HOLD_MS,
    GEAR_DRAG_STEP_DELAY_MS,
    GEAR_DRAG_STEPS,
    GEAR_DROP_HOLD_MS,
    GEAR_DROP_SETTLE_MS,
    GEAR_ITEM_POSITION,
    GEAR_MENU_OPEN_ATTEMPTS,
    GEAR_MENU_SETTLE_MS,
    deploy_initial_gear,
)


class GearActionTest(IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.gear_open = cv2.imread(str(FIXTURES_DIR / "gear_open.png"))
        cls.gear_place = cv2.imread(str(FIXTURES_DIR / "gear_place.png"))
        cls.miniboss = cv2.imread(str(FIXTURES_DIR.parent / "miniboss_bar.png"))

    def setUp(self):
        self.page = Mock()
        self.page.evaluate = AsyncMock()
        self.page.wait_for_timeout = AsyncMock()
        self.page.mouse = Mock()
        self.page.mouse.click = AsyncMock()
        self.page.mouse.move = AsyncMock()
        self.page.mouse.down = AsyncMock()
        self.page.mouse.up = AsyncMock()

    @patch(
        "hauntedroom.flows.automap_support.gear_action.capture_page_bgr",
        new_callable=AsyncMock,
    )
    async def test_deploy_drags_and_verifies_both_success_signals(self, capture):
        capture.side_effect = [self.gear_open, self.gear_place]

        placed = await deploy_initial_gear(self.page, self.gear_open)

        self.assertTrue(placed)
        self.page.mouse.click.assert_awaited_once_with(162, 661)
        self.assertEqual(
            self.page.wait_for_timeout.await_args_list,
            [
                call(GEAR_MENU_SETTLE_MS),
                call(GEAR_DRAG_HOLD_MS),
                *[call(GEAR_DRAG_STEP_DELAY_MS)] * GEAR_DRAG_STEPS,
                call(GEAR_DROP_HOLD_MS),
                call(GEAR_DROP_SETTLE_MS),
            ],
        )
        move_calls = self.page.mouse.move.await_args_list
        self.assertEqual(move_calls[0], call(*GEAR_ITEM_POSITION))
        self.assertEqual(move_calls[-1], call(250, 370))
        self.assertEqual(len(move_calls), GEAR_DRAG_STEPS + 1)
        self.assertTrue(
            all(
                previous.args[1] > current.args[1]
                for previous, current in zip(move_calls, move_calls[1:])
            )
        )
        self.page.mouse.down.assert_awaited_once_with()
        self.page.mouse.up.assert_awaited_once_with()

    @patch(
        "hauntedroom.flows.automap_support.gear_action.capture_page_bgr",
        new_callable=AsyncMock,
    )
    async def test_deploy_retries_click_when_menu_does_not_open(self, capture):
        menu_closed = np.zeros_like(self.gear_open)
        capture.side_effect = [menu_closed, self.gear_open, self.gear_place]

        placed = await deploy_initial_gear(self.page, self.gear_open)

        self.assertTrue(placed)
        self.assertEqual(
            self.page.mouse.click.await_args_list,
            [call(162, 661), call(162, 661)],
        )
        self.assertEqual(
            self.page.wait_for_timeout.await_args_list[:2],
            [call(GEAR_MENU_SETTLE_MS), call(GEAR_MENU_SETTLE_MS)],
        )

    @patch(
        "hauntedroom.flows.automap_support.gear_action.find_gear_drop_position",
        return_value=None,
    )
    @patch(
        "hauntedroom.flows.automap_support.gear_action.capture_page_bgr",
        new_callable=AsyncMock,
    )
    async def test_missing_door_anchor_closes_menu_and_soft_fails_as_placed(
        self,
        capture,
        _find_gear_drop_position,
    ):
        capture.side_effect = [self.gear_open, self.gear_place]

        placed = await deploy_initial_gear(self.page, self.gear_open)

        self.assertTrue(placed)
        self.assertEqual(
            self.page.mouse.click.await_args_list,
            [call(162, 661), call(162, 661)],
        )
        self.assertEqual(
            self.page.wait_for_timeout.await_args_list,
            [call(GEAR_MENU_SETTLE_MS), call(GEAR_MENU_SETTLE_MS)],
        )
        self.page.mouse.down.assert_not_awaited()

    @patch(
        "hauntedroom.flows.automap_support.gear_action.capture_page_bgr",
        new_callable=AsyncMock,
    )
    async def test_unverified_drag_closes_open_menu_and_soft_fails_as_placed(
        self,
        capture,
    ):
        capture.side_effect = [
            self.gear_open,
            self.gear_open,
            self.gear_place,
        ]

        placed = await deploy_initial_gear(self.page, self.gear_open)

        self.assertTrue(placed)
        self.assertEqual(
            self.page.mouse.click.await_args_list,
            [call(162, 661), call(162, 661)],
        )
        self.assertEqual(
            self.page.wait_for_timeout.await_args_list[-2:],
            [call(GEAR_DROP_SETTLE_MS), call(GEAR_MENU_SETTLE_MS)],
        )
        self.page.mouse.down.assert_awaited_once_with()
        self.page.mouse.up.assert_awaited_once_with()

    @patch(
        "hauntedroom.flows.automap_support.gear_action.capture_page_bgr",
        new_callable=AsyncMock,
    )
    async def test_unverified_drag_does_not_reopen_closed_menu(self, capture):
        capture.side_effect = [self.gear_open, self.miniboss]

        placed = await deploy_initial_gear(self.page, self.gear_open)

        self.assertTrue(placed)
        self.page.mouse.click.assert_awaited_once_with(162, 661)

    @patch(
        "hauntedroom.flows.automap_support.gear_action.smooth_drag",
        new_callable=AsyncMock,
    )
    @patch(
        "hauntedroom.flows.automap_support.gear_action.capture_page_bgr",
        new_callable=AsyncMock,
    )
    async def test_drag_exception_closes_menu_and_soft_fails_as_placed(
        self,
        capture,
        smooth_drag,
    ):
        capture.side_effect = [
            self.gear_open,
            self.gear_open,
            self.gear_place,
        ]
        smooth_drag.side_effect = RuntimeError("drag failed")

        placed = await deploy_initial_gear(self.page, self.gear_open)

        self.assertTrue(placed)
        self.assertEqual(
            self.page.mouse.click.await_args_list,
            [call(162, 661), call(162, 661)],
        )
        smooth_drag.assert_awaited_once()

    @patch(
        "hauntedroom.flows.automap_support.gear_action.capture_page_bgr",
        new_callable=AsyncMock,
    )
    async def test_menu_retry_limit_soft_fails_as_placed_when_closed(
        self,
        capture,
    ):
        capture.return_value = np.zeros_like(self.gear_open)

        placed = await deploy_initial_gear(self.page, self.gear_open)

        self.assertTrue(placed)
        self.assertEqual(
            self.page.mouse.click.await_count,
            GEAR_MENU_OPEN_ATTEMPTS,
        )
        self.assertEqual(
            self.page.wait_for_timeout.await_args_list,
            [call(GEAR_MENU_SETTLE_MS)] * GEAR_MENU_OPEN_ATTEMPTS,
        )
        self.page.mouse.down.assert_not_awaited()

    @patch("hauntedroom.flows.automap.load_template")
    @patch("hauntedroom.flows.automap.deploy_initial_gear", new_callable=AsyncMock)
    async def test_flow_attempts_gear_only_once_after_unlock(
        self,
        deploy_initial_gear,
        load_template,
    ):
        load_template.return_value = np.zeros((2, 2), dtype=np.uint8)
        deploy_initial_gear.return_value = True
        flow = AutomapFlow(self.page, asyncio.Event(), AutomapConfig())

        self.assertFalse(
            await flow.handle_initial_gear(self.gear_open, np.empty((0, 0)))
        )
        flow.initial_gear_unlocked = True
        self.assertTrue(
            await flow.handle_initial_gear(self.gear_open, np.empty((0, 0)))
        )
        self.assertFalse(
            await flow.handle_initial_gear(self.gear_open, np.empty((0, 0)))
        )
        deploy_initial_gear.assert_awaited_once()
