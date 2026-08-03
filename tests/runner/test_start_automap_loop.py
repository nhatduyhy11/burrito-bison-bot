import asyncio
import sys
from pathlib import Path
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, Mock, call, patch


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

from hauntedroom_runner import (
    BETWEEN_MAPS_WAIT_MS,
    get_start_battle_actions,
    map_was_lost,
    run_start_automap_loop,
)


class StartAutomapLoopTest(IsolatedAsyncioTestCase):
    def setUp(self):
        self.start_home = {
            "type": "click_template",
            "_template_path": Path("rooms/start_home.png"),
        }
        self.start_battle = {
            "type": "click_template",
            "_template_path": Path("rooms/start_battle.png"),
        }
        self.exit_click = {
            "type": "click_template",
            "_template_path": Path("rooms/exit_click.png"),
        }
        self.actions = [self.start_home, self.start_battle, self.exit_click]

    def test_start_actions_reuse_prefix_and_exclude_exit_actions(self):
        self.assertEqual(
            get_start_battle_actions(self.actions),
            [self.start_home, self.start_battle],
        )

    def test_start_actions_require_start_battle_checkpoint(self):
        with self.assertRaisesRegex(ValueError, "start_battle.png"):
            get_start_battle_actions([self.start_home])

    async def test_loss_detector_is_currently_a_false_placeholder(self):
        self.assertFalse(await map_was_lost(Mock()))

    @patch(
        "hauntedroom_runner.wait_with_countdown",
        new_callable=AsyncMock,
    )
    @patch(
        "hauntedroom_runner.map_was_lost",
        new_callable=AsyncMock,
    )
    @patch(
        "hauntedroom_runner.run_actions",
        new_callable=AsyncMock,
    )
    async def test_loops_start_then_automap_until_loss(
        self,
        run_actions,
        map_was_lost_mock,
        wait_with_countdown_mock,
    ):
        page = Mock()
        stop_event = asyncio.Event()
        automap_flow = AsyncMock(return_value=True)
        run_actions.return_value = True
        map_was_lost_mock.side_effect = [False, True]
        wait_with_countdown_mock.return_value = True

        completed = await run_start_automap_loop(
            page,
            self.actions,
            automap_flow,
            stop_event,
        )

        self.assertTrue(completed)
        self.assertEqual(run_actions.await_count, 2)
        self.assertEqual(
            run_actions.await_args_list,
            [
                call(
                    page,
                    [self.start_home, self.start_battle],
                    loop_count=1,
                    stop_event=stop_event,
                ),
                call(
                    page,
                    [self.start_home, self.start_battle],
                    loop_count=1,
                    stop_event=stop_event,
                ),
            ],
        )
        self.assertEqual(
            automap_flow.await_args_list,
            [call(page, stop_event), call(page, stop_event)],
        )
        wait_with_countdown_mock.assert_awaited_once_with(
            page,
            BETWEEN_MAPS_WAIT_MS,
            "Start-auto loop 1 cooldown",
            stop_event,
        )

    @patch(
        "hauntedroom_runner.map_was_lost",
        new_callable=AsyncMock,
    )
    @patch(
        "hauntedroom_runner.run_actions",
        new_callable=AsyncMock,
    )
    async def test_stops_when_automap_does_not_complete(
        self,
        run_actions,
        map_was_lost_mock,
    ):
        run_actions.return_value = True
        automap_flow = AsyncMock(return_value=False)

        completed = await run_start_automap_loop(
            Mock(),
            self.actions,
            automap_flow,
            asyncio.Event(),
        )

        self.assertFalse(completed)
        map_was_lost_mock.assert_not_awaited()
