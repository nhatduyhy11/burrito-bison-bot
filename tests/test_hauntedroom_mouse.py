import sys
from pathlib import Path
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, Mock, call


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

from hauntedroom.core.mouse import smooth_drag


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
