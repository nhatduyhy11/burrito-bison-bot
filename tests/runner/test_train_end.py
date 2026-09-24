"""Tests for train end detection and lifecycle."""

import asyncio
from pathlib import Path
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, Mock

import cv2

from hauntedroom.flows.automap_support.flow import AutomapFlow
from hauntedroom.flows.automap_support.map.lifecycle import MapLifecycle
from hauntedroom.flows.automap_support.map.model_state import MapState
from hauntedroom.flows.automap_support.templates import AutomapTemplates
from hauntedroom.flows.automap_support.vision.template_config import AutomapConfig
from hauntedroom.flows.train_support.train_end import TrainEndLifecycle

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "train_flow"


def _load_fixture(name: str) -> tuple:
    img_bgr = cv2.imread(str(FIXTURES / name))
    assert img_bgr is not None, f"Fixture {name} must exist"
    return img_bgr, cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)


def _build_lifecycle(page, stop_event, state, **overrides) -> TrainEndLifecycle:
    defaults = dict(
        state=state,
        click_fn=AsyncMock(),
        wait_for_flow_timeout_fn=AsyncMock(),
    )
    defaults.update(overrides)
    return TrainEndLifecycle(page, stop_event, **defaults)


class TrainEndLifecycleTest(IsolatedAsyncioTestCase):
    """Verify TrainEndLifecycle correctly detects train victory and clicks the red button."""

    async def asyncSetUp(self):
        self.page = Mock()
        self.stop_event = asyncio.Event()

    async def test_detects_train_win_and_clicks_red_button(self):
        img_bgr, img_gray = _load_fixture("train_win.png")

        state = MapState()
        on_win = Mock(return_value=1)
        lifecycle = _build_lifecycle(self.page, self.stop_event, state, on_win=on_win)

        outcome = await lifecycle.handle_map_end(img_gray, img_bgr)
        self.assertTrue(outcome.handled)
        self.assertTrue(outcome.completed)
        self.assertTrue(state.completed)
        self.assertTrue(state.win_recorded)
        self.assertEqual(state.total_win, 1)
        on_win.assert_called_once()

        lifecycle.click_fn.assert_awaited_once_with(self.page, 319, 556)
        lifecycle.wait_for_flow_timeout_fn.assert_awaited_once()

    async def test_detects_train_win_empty_and_clicks_red_button(self):
        img_bgr, img_gray = _load_fixture("train_win_empty.png")

        state = MapState()
        lifecycle = _build_lifecycle(self.page, self.stop_event, state)

        outcome = await lifecycle.handle_map_end(img_gray, img_bgr)
        self.assertTrue(outcome.handled)
        self.assertTrue(outcome.completed)
        self.assertTrue(state.completed)
        self.assertTrue(state.win_recorded)

        lifecycle.click_fn.assert_awaited_once_with(self.page, 319, 508)
        lifecycle.wait_for_flow_timeout_fn.assert_awaited_once()

    async def test_keeps_polling_while_red_button_is_missing(self):
        img_bgr, img_gray = _load_fixture("train_win.png")

        state = MapState()
        lifecycle = _build_lifecycle(
            self.page,
            self.stop_event,
            state,
            find_colored_button_fn=Mock(return_value=None),
        )

        outcome = await lifecycle.handle_map_end(img_gray, img_bgr)
        self.assertFalse(outcome.handled)
        self.assertFalse(outcome.completed)
        self.assertFalse(state.completed)
        self.assertFalse(state.win_recorded)
        lifecycle.click_fn.assert_not_awaited()

    async def test_returns_not_handled_on_non_win_frame(self):
        img_bgr, img_gray = _load_fixture("train_available.png")

        state = MapState()
        lifecycle = _build_lifecycle(self.page, self.stop_event, state)

        outcome = await lifecycle.handle_map_end(img_gray, img_bgr)
        self.assertFalse(outcome.handled)
        self.assertFalse(outcome.completed)
        self.assertFalse(state.completed)
        self.assertFalse(state.win_recorded)
        lifecycle.click_fn.assert_not_awaited()

    async def test_automap_flow_with_train_mode_uses_train_end(self):
        img_bgr, img_gray = _load_fixture("train_win.png")

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

        flow.end_lifecycle.click_fn = AsyncMock()
        flow.end_lifecycle.wait_for_flow_timeout_fn = AsyncMock()

        handled = await flow.handle_map_end(img_bgr, img_gray)
        self.assertTrue(handled)
        self.assertTrue(state.completed)
        flow.end_lifecycle.click_fn.assert_awaited_once_with(self.page, 319, 556)

    async def test_automap_flow_default_mode_uses_map_end(self):
        flow = AutomapFlow(
            self.page,
            asyncio.Event(),
            AutomapConfig(),
            AutomapTemplates.load(AutomapConfig()),
        )
        self.assertIsInstance(flow.end_lifecycle, MapLifecycle)
