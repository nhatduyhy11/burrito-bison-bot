import sys
import asyncio
from pathlib import Path
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, Mock, call


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

from hauntedroom.core.mouse import (
    SUPPORTED_MOUSE_BUTTONS,
    bot_click,
    click_and_wait,
    smooth_drag,
)


class ClickTest(IsolatedAsyncioTestCase):
    def setUp(self):
        self.page = Mock()
        self.page.evaluate = AsyncMock()
        self.page.wait_for_timeout = AsyncMock()
        self.page.mouse = Mock()
        self.page.mouse.click = AsyncMock()

    def test_supported_buttons_match_browser_mouse_contract(self):
        self.assertEqual(
            SUPPORTED_MOUSE_BUTTONS,
            frozenset({"left", "middle", "right"}),
        )

    async def test_bot_click_suppresses_logging_and_forwards_button(self):
        await bot_click(self.page, (10, 20), button="right")

        self.page.evaluate.assert_awaited_once()
        self.page.mouse.click.assert_awaited_once_with(10, 20, button="right")

    async def test_click_and_wait_returns_flow_wait_result(self):
        stop_event = asyncio.Event()
        stop_event.set()

        continued = await click_and_wait(self.page, (30, 40), 250, stop_event)

        self.assertFalse(continued)
        self.page.mouse.click.assert_awaited_once_with(30, 40)
        self.page.wait_for_timeout.assert_awaited_once_with(250)

    async def test_click_and_wait_repeats_click_and_wait(self):
        continued = await click_and_wait(
            self.page,
            (30, 40),
            250,
            click_count=3,
        )

        self.assertTrue(continued)
        self.assertEqual(self.page.mouse.click.await_count, 3)
        self.assertEqual(self.page.wait_for_timeout.await_count, 3)

    async def test_click_and_wait_stops_before_next_repeat(self):
        stop_event = asyncio.Event()

        async def stop_after_first_wait(_ms):
            stop_event.set()

        self.page.wait_for_timeout.side_effect = stop_after_first_wait

        continued = await click_and_wait(
            self.page,
            (30, 40),
            250,
            stop_event,
            click_count=3,
        )

        self.assertFalse(continued)
        self.page.mouse.click.assert_awaited_once_with(30, 40)

    async def test_click_and_wait_normalizes_non_positive_click_count(self):
        continued = await click_and_wait(
            self.page, (30, 40), 250, click_count=0
        )

        self.assertTrue(continued)
        self.page.mouse.click.assert_awaited_once_with(30, 40)
        self.page.wait_for_timeout.assert_awaited_once_with(250)


class SmoothDragTest(IsolatedAsyncioTestCase):
    def setUp(self):
        self.page = Mock()
        self.page.wait_for_timeout = AsyncMock()
        self.page.mouse = Mock()
        self.page.mouse.move = AsyncMock()
        self.page.mouse.down = AsyncMock()
        self.page.mouse.up = AsyncMock()

    async def test_interpolates_path_and_applies_timing(self):
        await smooth_drag(
            self.page,
            (10, 20),
            (30, 50),
            hold_before_move_ms=100,
            steps=2,
            step_delay_ms=25,
            hold_before_release_ms=75,
        )

        self.assertEqual(
            self.page.mouse.move.await_args_list,
            [call(10, 20), call(20, 35), call(30, 50)],
        )
        self.assertEqual(
            self.page.wait_for_timeout.await_args_list,
            [call(100), call(25), call(25), call(75)],
        )
        self.page.mouse.down.assert_awaited_once_with()
        self.page.mouse.up.assert_awaited_once_with()

    async def test_releases_mouse_when_movement_fails(self):
        self.page.mouse.move.side_effect = [None, RuntimeError("move failed")]

        with self.assertRaisesRegex(RuntimeError, "move failed"):
            await smooth_drag(self.page, (0, 0), (10, 10), steps=1)

        self.page.mouse.up.assert_awaited_once_with()

    async def test_rejects_invalid_options_before_mouse_input(self):
        with self.assertRaisesRegex(ValueError, "steps"):
            await smooth_drag(self.page, (0, 0), (10, 10), steps=0)

        self.page.mouse.move.assert_not_awaited()
        self.page.mouse.down.assert_not_awaited()
