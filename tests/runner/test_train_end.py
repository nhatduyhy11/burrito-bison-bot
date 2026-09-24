"""Tests for train end detection and lifecycle."""

import asyncio
from pathlib import Path
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, Mock

import cv2

from hauntedroom.flows.automap import run_automap_flow
from hauntedroom.flows.automap_support.flow import AutomapFlow
from hauntedroom.flows.automap_support.map.model_state import MapState
from hauntedroom.flows.automap_support.templates import AutomapTemplates
from hauntedroom.flows.automap_support.vision.template_config import AutomapConfig
from hauntedroom.flows.train_support.common import (
    TRAIN_WIN_BUTTON_GEOMETRY,
    TRAIN_WIN_BUTTON_REGION,
    TRAIN_WIN_TEMPLATE_PATH,
    TRAIN_WIN_TEMPLATE_THRESHOLD,
)
from hauntedroom.flows.train_support.train_end import TrainEndLifecycle

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "train_flow"


class TrainEndLifecycleTest(IsolatedAsyncioTestCase):
    """Verify TrainEndLifecycle correctly detects train victory and clicks the red button."""

    async def asyncSetUp(self):
        self.page = Mock()
        self.stop_event = asyncio.Event()
        self.click_mock = AsyncMock()
        self.wait_mock = AsyncMock()

    async def test_detects_train_win_and_clicks_red_button(self):
        img_bgr = cv2.imread(str(FIXTURES / "train_win.png"))
        self.assertIsNotNone(img_bgr, "Fixture train_win.png must exist")
        img_gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)

        state = MapState()
        on_win = Mock(return_value=1)
        lifecycle = TrainEndLifecycle(
            self.page,
            self.stop_event,
            state=state,
            on_win=on_win,
            template_path=TRAIN_WIN_TEMPLATE_PATH,
            template_threshold=TRAIN_WIN_TEMPLATE_THRESHOLD,
            button_region=TRAIN_WIN_BUTTON_REGION,
            button_geometry=TRAIN_WIN_BUTTON_GEOMETRY,
            click_fn=self.click_mock,
            wait_for_flow_timeout_fn=self.wait_mock,
        )

        outcome = await lifecycle.handle_map_end(img_gray, img_bgr)
        self.assertTrue(outcome.handled)
        self.assertTrue(outcome.completed)
        self.assertTrue(state.completed)
        self.assertTrue(state.win_recorded)
        self.assertEqual(state.total_win, 1)
        on_win.assert_called_once()

        self.click_mock.assert_awaited_once_with(self.page, 319, 556)
        self.wait_mock.assert_awaited_once()

    async def test_detects_train_win_empty_and_clicks_red_button(self):
        img_bgr = cv2.imread(str(FIXTURES / "train_win_empty.png"))
        self.assertIsNotNone(img_bgr, "Fixture train_win_empty.png must exist")
        img_gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)

        state = MapState()
        lifecycle = TrainEndLifecycle(
            self.page,
            self.stop_event,
            state=state,
            template_path=TRAIN_WIN_TEMPLATE_PATH,
            template_threshold=TRAIN_WIN_TEMPLATE_THRESHOLD,
            button_region=TRAIN_WIN_BUTTON_REGION,
            button_geometry=TRAIN_WIN_BUTTON_GEOMETRY,
            click_fn=self.click_mock,
            wait_for_flow_timeout_fn=self.wait_mock,
        )

        outcome = await lifecycle.handle_map_end(img_gray, img_bgr)
        self.assertTrue(outcome.handled)
        self.assertTrue(outcome.completed)
        self.assertTrue(state.completed)
        self.assertTrue(state.win_recorded)

        self.click_mock.assert_awaited_once_with(self.page, 319, 508)
        self.wait_mock.assert_awaited_once()

    async def test_returns_not_handled_on_non_win_frame(self):
        img_bgr = cv2.imread(str(FIXTURES / "train_available.png"))
        self.assertIsNotNone(img_bgr, "Fixture train_available.png must exist")
        img_gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)

        state = MapState()
        lifecycle = TrainEndLifecycle(
            self.page,
            self.stop_event,
            state=state,
            template_path=TRAIN_WIN_TEMPLATE_PATH,
            template_threshold=TRAIN_WIN_TEMPLATE_THRESHOLD,
            button_region=TRAIN_WIN_BUTTON_REGION,
            button_geometry=TRAIN_WIN_BUTTON_GEOMETRY,
            click_fn=self.click_mock,
            wait_for_flow_timeout_fn=self.wait_mock,
        )

        outcome = await lifecycle.handle_map_end(img_gray, img_bgr)
        self.assertFalse(outcome.handled)
        self.assertFalse(outcome.completed)
        self.assertFalse(state.completed)
        self.assertFalse(state.win_recorded)
        self.click_mock.assert_not_awaited()

    async def test_automap_flow_with_train_mode_uses_train_end(self):
        img_bgr = cv2.imread(str(FIXTURES / "train_win.png"))
        img_gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)

        config = AutomapConfig()
        templates = AutomapTemplates.load(config)
        state = MapState()

        flow = AutomapFlow(
            self.page,
            self.stop_event,
            config=config,
            templates=templates,
            state=state,
            battle_mode="train",
        )
        self.assertIsInstance(flow.end_lifecycle, TrainEndLifecycle)

        flow.end_lifecycle.click_fn = self.click_mock
        flow.end_lifecycle.wait_for_flow_timeout_fn = self.wait_mock

        handled = await flow.handle_map_end(img_bgr, img_gray)
        self.assertTrue(handled)
        self.assertTrue(state.completed)
        self.click_mock.assert_awaited_once_with(self.page, 319, 556)
