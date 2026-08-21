import asyncio
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, Mock, call, patch

import numpy as np

from tests.hero_select.hero_test_helpers import make_levelup_available
from hauntedroom.flows.automap_support.hero_action import (
    HERO_LEVELUP_OPEN_CLICK,
    HERO_LEVELUP_OPTION_SETTLE_MS,
    HERO_LEVELUP_SELECTION_SETTLE_MS,
    HeroLevelupChoice,
    handle_hero_levelup,
)


class HeroActionTest(IsolatedAsyncioTestCase):
    def setUp(self):
        self.page = Mock()
        self.stop_event = asyncio.Event()
        self.initial_frame = make_levelup_available(
            np.zeros((720, 640, 3), dtype=np.uint8)
        )
        self.option_frame = np.zeros_like(self.initial_frame)
        self.price_is_available = Mock(return_value=True)
        self.capture_page_bgr = AsyncMock(return_value=self.option_frame)
        self.save_fallback_screenshot = AsyncMock()
        self.click = AsyncMock()
        self.wait_for_flow_timeout = AsyncMock(return_value=True)
        self.flow_checkpoint = AsyncMock(return_value=True)

    async def handle(self, *, capture_fallback_screenshots=True):
        return await handle_hero_levelup(
            self.page,
            self.stop_event,
            self.initial_frame,
            hero_levelup_template_paths=(),
            hero_levelup_templates={},
            hero_levelup_price_is_available_fn=self.price_is_available,
            capture_page_bgr_fn=self.capture_page_bgr,
            save_fallback_screenshot_fn=self.save_fallback_screenshot,
            click_fn=self.click,
            wait_for_flow_timeout_fn=self.wait_for_flow_timeout,
            flow_checkpoint_fn=self.flow_checkpoint,
            capture_fallback_screenshots=capture_fallback_screenshots,
        )

    @patch(
        "hauntedroom.flows.automap_support.hero_action.choose_hero_levelup_option"
    )
    async def test_unavailable_levelup_does_not_open_or_inspect_picker(self, choose):
        self.price_is_available.return_value = False

        outcome = await self.handle()

        self.assertFalse(outcome.handled)
        self.assertFalse(outcome.initial_gear_unlocked)
        choose.assert_not_called()
        self.capture_page_bgr.assert_not_awaited()
        self.click.assert_not_awaited()
        self.wait_for_flow_timeout.assert_not_awaited()

    @patch(
        "hauntedroom.flows.automap_support.hero_action.choose_hero_levelup_option",
        return_value=HeroLevelupChoice(
            347,
            597,
            template_name="02_hanuman.png",
            score=0.95,
            priority=2.0,
        ),
    )
    async def test_prioritized_choice_opens_waits_captures_and_clicks(self, _choose):
        async def capture_after_settle(_page):
            self.assertEqual(
                self.wait_for_flow_timeout.await_args_list,
                [call(self.page, HERO_LEVELUP_OPTION_SETTLE_MS, self.stop_event)],
            )
            return self.option_frame

        self.capture_page_bgr.side_effect = capture_after_settle

        outcome = await self.handle()

        self.assertTrue(outcome.handled)
        self.assertTrue(outcome.initial_gear_unlocked)
        self.assertEqual(
            self.click.await_args_list,
            [call(self.page, *HERO_LEVELUP_OPEN_CLICK), call(self.page, 347, 597)],
        )
        self.assertEqual(
            self.wait_for_flow_timeout.await_args_list,
            [
                call(self.page, HERO_LEVELUP_OPTION_SETTLE_MS, self.stop_event),
                call(self.page, HERO_LEVELUP_SELECTION_SETTLE_MS, self.stop_event),
            ],
        )
        self.capture_page_bgr.assert_awaited_once_with(self.page)
        self.save_fallback_screenshot.assert_not_awaited()

    @patch("builtins.print")
    @patch(
        "hauntedroom.flows.automap_support.hero_action.choose_hero_levelup_option",
        return_value=HeroLevelupChoice(
            193,
            632,
            fallback_color="red",
            fallback_option_count=3,
            fallback_has_yellow=False,
            fallback_has_purple=False,
        ),
    )
    async def test_complete_red_fallback_is_captured_logged_and_clicked(
        self, _choose, print_mock
    ):
        outcome = await self.handle()

        self.assertTrue(outcome.handled)
        self.assertTrue(outcome.initial_gear_unlocked)
        self.save_fallback_screenshot.assert_awaited_once_with(
            self.page,
            label="hero-fallback-no-priority-no-yellow-or-purple",
        )
        print_mock.assert_any_call(
            "No prioritized hero option matched; falling back to red hero "
            "card at 193,632.",
            flush=True,
        )
        self.assertEqual(
            self.click.await_args_list,
            [call(self.page, *HERO_LEVELUP_OPEN_CLICK), call(self.page, 193, 632)],
        )

    @patch("builtins.print")
    @patch(
        "hauntedroom.flows.automap_support.hero_action.choose_hero_levelup_option"
    )
    async def test_partial_or_colored_fallback_is_logged_clicked_not_captured(
        self, choose, print_mock
    ):
        cases = [
            HeroLevelupChoice(
                319,
                632,
                fallback_color="red",
                fallback_option_count=1,
                fallback_has_yellow=False,
                fallback_has_purple=False,
            ),
            HeroLevelupChoice(
                446,
                632,
                fallback_color="yellow",
                fallback_option_count=3,
                fallback_has_yellow=True,
                fallback_has_purple=True,
            ),
            HeroLevelupChoice(
                193,
                632,
                fallback_color="purple",
                fallback_option_count=3,
                fallback_has_yellow=False,
                fallback_has_purple=True,
            ),
        ]

        for choice in cases:
            with self.subTest(choice=choice):
                choose.return_value = choice
                await self.handle()
                self.save_fallback_screenshot.assert_not_awaited()
                print_mock.assert_any_call(
                    "No prioritized hero option matched; falling back to "
                    f"{choice.fallback_color} hero card at {choice.x},{choice.y}.",
                    flush=True,
                )
                self.assertEqual(
                    self.click.await_args_list,
                    [
                        call(self.page, *HERO_LEVELUP_OPEN_CLICK),
                        call(self.page, choice.x, choice.y),
                    ],
                )
                self.save_fallback_screenshot.reset_mock()
                print_mock.reset_mock()
                self.click.reset_mock()
                self.wait_for_flow_timeout.reset_mock()
                self.capture_page_bgr.reset_mock()
                self.flow_checkpoint.reset_mock()

    @patch(
        "hauntedroom.flows.automap_support.hero_action.choose_hero_levelup_option",
        return_value=HeroLevelupChoice(
            193,
            632,
            fallback_color="red",
            fallback_option_count=3,
            fallback_has_yellow=False,
            fallback_has_purple=False,
        ),
    )
    async def test_fallback_capture_can_be_disabled(self, _choose):
        outcome = await self.handle(capture_fallback_screenshots=False)

        self.assertTrue(outcome.handled)
        self.save_fallback_screenshot.assert_not_awaited()
        self.assertEqual(
            self.click.await_args_list,
            [call(self.page, *HERO_LEVELUP_OPEN_CLICK), call(self.page, 193, 632)],
        )

    @patch(
        "hauntedroom.flows.automap_support.hero_action.choose_hero_levelup_option"
    )
    async def test_stop_during_picker_settle_returns_handled_without_capture(
        self, choose
    ):
        self.wait_for_flow_timeout.return_value = False

        outcome = await self.handle()

        self.assertTrue(outcome.handled)
        self.assertFalse(outcome.initial_gear_unlocked)
        self.assertEqual(
            self.click.await_args_list, [call(self.page, *HERO_LEVELUP_OPEN_CLICK)]
        )
        choose.assert_not_called()
        self.capture_page_bgr.assert_not_awaited()
