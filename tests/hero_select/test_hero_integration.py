import asyncio
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, Mock, call, patch

import cv2
import numpy as np

from tests.hero_select.hero_test_helpers import (
    TOOLS_DIR,  # noqa: F401
    find_choice,
    load_hero_fixture,
    make_levelup_available,
)
from tests.automap.template_factory import build_test_automap_templates
from hauntedroom.flows.automap import AutomapConfig, AutomapFlow
from hauntedroom.flows.automap_support.hero_action import (
    HERO_LEVELUP_OPEN_CLICK,
    HERO_LEVELUP_OPTION_SETTLE_MS,
    HERO_LEVELUP_SELECTION_SETTLE_MS,
)


class HeroFlowIntegrationRegressionTest(IsolatedAsyncioTestCase):
    def setUp(self):
        self.page = Mock()
        self.page.evaluate = AsyncMock()
        self.page.wait_for_timeout = AsyncMock()
        self.page.mouse = Mock()
        self.page.mouse.click = AsyncMock()

    def make_flow(self, config, *, load_templates):
        return AutomapFlow(
            self.page,
            asyncio.Event(),
            config,
            build_test_automap_templates(
                config,
                load_hero_templates=load_templates,
            ),
        )

    @patch("builtins.print")
    @patch(
        "hauntedroom.flows.automap_support.flow.save_fallback_screenshot",
        new_callable=AsyncMock,
    )
    @patch(
        "hauntedroom.flows.automap_support.flow.capture_page_bgr",
        new_callable=AsyncMock,
    )
    async def test_real_fixtures_preserve_click_and_capture_behavior(
        self,
        capture_page_bgr,
        save_fallback_screenshot,
        print_mock,
    ):
        cases = [
            ("3_option_hanu_xlubu.png", AutomapConfig(), True, (347, 597), False, None),
            ("only_1_option.png", AutomapConfig(), True, (319, 632), False, "red"),
            (
                "only_1_option.png", AutomapConfig(debug=True), True,
                (319, 632), False, "red",
            ),
            (
                "lubu and hanu.png", AutomapConfig(hero_levelup_template_paths=()),
                False, (193, 632), True, "red",
            ),
            (
                "fallback_yellow.png", AutomapConfig(), True,
                (319, 632), False, "yellow",
            ),
            (
                "3 lvup option.png", AutomapConfig(hero_levelup_template_paths=()),
                False, (446, 632), False, "yellow",
            ),
            (
                "3_option_2lubu.png", AutomapConfig(hero_levelup_template_paths=()),
                False, (193, 632), False, "purple",
            ),
            (
                "lubu and hanu.png",
                AutomapConfig(
                    hero_levelup_template_paths=(),
                    capture_hero_fallback_screenshots=False,
                ),
                False, (193, 632), False, "red",
            ),
        ]

        for fixture, config, load_templates, expected_click, capture, color in cases:
            with self.subTest(fixture=fixture, config=config):
                popup = load_hero_fixture(fixture)
                capture_page_bgr.return_value = popup
                initial_frame = make_levelup_available(np.zeros_like(popup))
                flow = self.make_flow(config, load_templates=load_templates)

                handled = await flow.hero_levelup(
                    initial_frame,
                    cv2.cvtColor(initial_frame, cv2.COLOR_BGR2GRAY),
                )

                self.assertTrue(handled)
                self.assertEqual(
                    self.page.mouse.click.await_args_list,
                    [call(*HERO_LEVELUP_OPEN_CLICK), call(*expected_click)],
                )
                self.assertEqual(
                    self.page.wait_for_timeout.await_args_list,
                    [
                        call(HERO_LEVELUP_OPTION_SETTLE_MS),
                        call(HERO_LEVELUP_SELECTION_SETTLE_MS),
                    ],
                )
                if capture:
                    save_fallback_screenshot.assert_awaited_once_with(
                        self.page,
                        label="hero-fallback-no-priority-no-yellow-or-purple",
                    )
                else:
                    save_fallback_screenshot.assert_not_awaited()
                if color is not None:
                    x, y = expected_click
                    print_mock.assert_any_call(
                        "No prioritized hero option matched; falling back to "
                        f"{color} hero card at {x},{y}.",
                        flush=True,
                    )

                capture_page_bgr.reset_mock()
                save_fallback_screenshot.reset_mock()
                print_mock.reset_mock()
                self.page.mouse.click.reset_mock()
                self.page.wait_for_timeout.reset_mock()

    @patch(
        "hauntedroom.flows.automap_support.flow.save_fallback_screenshot",
        new_callable=AsyncMock,
    )
    async def test_battle_frame_that_resembles_options_is_not_inspected(
        self,
        save_fallback_screenshot,
    ):
        battle_frame = np.zeros((720, 640, 3), dtype=np.uint8)
        battle_frame[610:655, 120:520] = (80, 20, 60)
        self.assertIsNotNone(find_choice(battle_frame))
        flow = self.make_flow(AutomapConfig(), load_templates=True)

        handled = await flow.hero_levelup(
            battle_frame,
            cv2.cvtColor(battle_frame, cv2.COLOR_BGR2GRAY),
        )

        self.assertFalse(handled)
        save_fallback_screenshot.assert_not_awaited()
        self.page.mouse.click.assert_not_awaited()
        self.page.wait_for_timeout.assert_not_awaited()

    @patch(
        "hauntedroom.flows.automap_support.flow.capture_page_bgr",
        new_callable=AsyncMock,
    )
    async def test_real_fixture_is_captured_only_after_picker_settles(
        self,
        capture_page_bgr,
    ):
        popup = load_hero_fixture("test-vps-lubu.png")

        async def capture_after_settle(_page):
            self.assertEqual(
                self.page.wait_for_timeout.await_args_list,
                [call(HERO_LEVELUP_OPTION_SETTLE_MS)],
            )
            return popup

        capture_page_bgr.side_effect = capture_after_settle
        initial_frame = make_levelup_available(np.zeros_like(popup))
        flow = self.make_flow(AutomapConfig(), load_templates=True)

        handled = await flow.hero_levelup(
            initial_frame,
            cv2.cvtColor(initial_frame, cv2.COLOR_BGR2GRAY),
        )

        self.assertTrue(handled)
        self.assertEqual(
            self.page.mouse.click.await_args_list,
            [call(*HERO_LEVELUP_OPEN_CLICK), call(192, 597)],
        )
        self.assertEqual(
            self.page.wait_for_timeout.await_args_list,
            [
                call(HERO_LEVELUP_OPTION_SETTLE_MS),
                call(HERO_LEVELUP_SELECTION_SETTLE_MS),
            ],
        )
        capture_page_bgr.assert_awaited_once_with(self.page)
