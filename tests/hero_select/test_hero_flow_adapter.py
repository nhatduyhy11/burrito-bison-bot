import asyncio
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, Mock, patch

import numpy as np

from tests.hero_select.hero_test_helpers import TOOLS_DIR  # noqa: F401
from tests.automap.template_factory import build_test_automap_templates
from hauntedroom.flows.automap import AutomapConfig, AutomapFlow
from hauntedroom.flows.automap_support.hero_action import HeroLevelupOutcome


class HeroFlowAdapterTest(IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.page = Mock()
        self.stop_event = asyncio.Event()
        self.config = AutomapConfig(capture_hero_fallback_screenshots=False)
        self.templates = build_test_automap_templates(self.config)
        self.flow = AutomapFlow(
            self.page,
            self.stop_event,
            self.config,
            self.templates,
        )
        self.frame_bgr = np.zeros((720, 640, 3), dtype=np.uint8)
        self.frame_gray = np.zeros((720, 640), dtype=np.uint8)

    @patch(
        "hauntedroom.flows.automap_support.flow._handle_hero_levelup",
        new_callable=AsyncMock,
    )
    async def test_forwards_dependencies_and_returns_handled(self, handle):
        handle.return_value = HeroLevelupOutcome(True)

        handled = await self.flow.hero_levelup(self.frame_bgr, self.frame_gray)

        self.assertTrue(handled)
        handle.assert_awaited_once()
        args = handle.await_args.args
        kwargs = handle.await_args.kwargs
        self.assertIs(args[0], self.page)
        self.assertIs(args[1], self.stop_event)
        self.assertIs(args[2], self.frame_bgr)
        self.assertIs(
            kwargs["hero_levelup_template_paths"],
            self.config.hero_levelup_template_paths,
        )
        self.assertIs(kwargs["hero_levelup_templates"], self.templates.hero_levelup)
        self.assertFalse(kwargs["capture_fallback_screenshots"])
        for dependency in (
            "hero_levelup_price_is_available_fn",
            "capture_page_bgr_fn",
            "save_fallback_screenshot_fn",
            "click_fn",
            "wait_for_flow_timeout_fn",
            "flow_checkpoint_fn",
        ):
            self.assertTrue(callable(kwargs[dependency]))
        self.assertFalse(self.flow.state.initial_gear_unlocked)

    @patch(
        "hauntedroom.flows.automap_support.flow._handle_hero_levelup",
        new_callable=AsyncMock,
    )
    async def test_maps_initial_gear_outcome_to_flow_state(self, handle):
        handle.return_value = HeroLevelupOutcome(
            handled=True, initial_gear_unlocked=True
        )

        handled = await self.flow.hero_levelup(self.frame_bgr, self.frame_gray)

        self.assertTrue(handled)
        self.assertTrue(self.flow.state.initial_gear_unlocked)

    @patch(
        "hauntedroom.flows.automap_support.flow._handle_hero_levelup",
        new_callable=AsyncMock,
    )
    async def test_debug_mode_preserves_enabled_fallback_capture_policy(self, handle):
        config = AutomapConfig(
            debug=True,
            capture_hero_fallback_screenshots=True,
        )
        flow = AutomapFlow(
            self.page,
            self.stop_event,
            config,
            build_test_automap_templates(config),
        )
        handle.return_value = HeroLevelupOutcome(True)

        handled = await flow.hero_levelup(self.frame_bgr, self.frame_gray)

        self.assertTrue(handled)
        self.assertTrue(handle.await_args.kwargs["capture_fallback_screenshots"])
