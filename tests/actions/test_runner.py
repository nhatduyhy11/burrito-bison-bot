import asyncio
import sys
from pathlib import Path
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, Mock, call, patch

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

from hauntedroom.actions.models import ClickAction, ClickTemplateAction
from hauntedroom.actions.runner import log_action_timeout, run_actions
from hauntedroom.core.template_detection import TemplateWaitResult, TemplateWaitStatus
from hauntedroom.core.terminal import BLUE, ORANGE


class ActionRunnerTest(IsolatedAsyncioTestCase):

    def setUp(self):
        self.page = Mock()
        self.page.evaluate = AsyncMock()
        self.page.wait_for_timeout = AsyncMock()
        self.page.mouse = Mock()
        self.page.mouse.click = AsyncMock()
        self.template_path = Path("start.png")
        self.actions = [
            ClickTemplateAction(
                template_path=self.template_path,
                note="Start",
                delay_ms=0,
            ),
            ClickAction(x=10, y=20),
        ]

    @patch("hauntedroom.actions.runner.print")
    @patch("hauntedroom.actions.runner.colorize")
    async def test_timeout_and_skip_logs_are_orange(self, colorize, print_mock):
        colorize.side_effect = lambda message, _color: f"orange:{message}"
        log_action_timeout(
            TimeoutError("timed out"),
            loop_index=1,
            loop_total="infinite",
            label="1.3 (Start Battle)",
            timeout_count=1,
            loop_count=None,
            loop_label="spawn_exit_lvup loop",
        )
        colorize.assert_has_calls(
            [
                call(
                    "1.3 (Start Battle): timeout count=1/2: timed out",
                    ORANGE,
                ),
                call(
                    "Skipping the rest of spawn_exit_lvup loop 1/infinite; "
                    "retrying from the first action on the next loop.",
                    ORANGE,
                ),
            ]
        )
        emitted_messages = [args[0] for args, _kwargs in print_mock.call_args_list]
        self.assertTrue(
            all(message.startswith("orange:") for message in emitted_messages)
        )

    @patch("hauntedroom.actions.runner.print")
    @patch("hauntedroom.actions.runner.colorize")
    async def test_loop_count_logs_are_blue_and_support_custom_label(
        self, colorize, print_mock
    ):
        colorize.side_effect = lambda message, _color: f"blue:{message}"
        await run_actions(
            self.page,
            [ClickAction(x=10, y=20)],
            loop_count=1,
            loop_label="spawn_exit_lvup loop",
        )
        colorize.assert_has_calls(
            [
                call("spawn_exit_lvup loop 1/1 start", BLUE),
                call("spawn_exit_lvup loop 1/1 finish", BLUE),
            ]
        )
        emitted_messages = [args[0] for args, _kwargs in print_mock.call_args_list]
        self.assertIn("blue:spawn_exit_lvup loop 1/1 start", emitted_messages)
        self.assertIn("blue:spawn_exit_lvup loop 1/1 finish", emitted_messages)
        self.assertFalse(
            any("Action loop" in message for message in emitted_messages)
        )

    @patch(
        "hauntedroom.actions.runner.load_template",
        return_value=np.zeros((1, 1), dtype=np.uint8),
    )
    @patch(
        "hauntedroom.actions.runner_executor.wait_for_template",
        new_callable=AsyncMock,
    )
    async def test_first_timeout_skips_rest_of_loop_then_retries(
        self, wait_for_template, _load_template
    ):
        wait_for_template.side_effect = [
            TimeoutError("first timeout"),
            TemplateWaitResult(TemplateWaitStatus.MATCHED, (30, 40, 0.95)),
        ]
        await run_actions(self.page, self.actions, loop_count=2)
        self.assertEqual(wait_for_template.await_count, 2)
        self.assertEqual(self.page.mouse.click.await_count, 2)

    @patch(
        "hauntedroom.actions.runner.load_template",
        return_value=np.zeros((1, 1), dtype=np.uint8),
    )
    @patch(
        "hauntedroom.actions.runner_executor.wait_for_template",
        new_callable=AsyncMock,
    )
    async def test_finite_loop_returns_false_when_final_attempt_times_out(
        self, wait_for_template, _load_template
    ):
        wait_for_template.side_effect = TimeoutError("only timeout")
        completed = await run_actions(self.page, self.actions, loop_count=1)
        self.assertFalse(completed)
        wait_for_template.assert_awaited_once()
        self.page.mouse.click.assert_not_awaited()

    @patch(
        "hauntedroom.actions.runner.load_template",
        return_value=np.zeros((1, 1), dtype=np.uint8),
    )
    @patch(
        "hauntedroom.actions.runner_executor.wait_for_template",
        new_callable=AsyncMock,
    )
    async def test_stop_after_success_does_not_repeat_successful_actions(
        self, wait_for_template, _load_template
    ):
        wait_for_template.return_value = TemplateWaitResult(
            TemplateWaitStatus.MATCHED,
            (30, 40, 0.95),
        )
        completed = await run_actions(
            self.page,
            self.actions,
            loop_count=2,
            stop_after_success=True,
        )
        self.assertTrue(completed)
        wait_for_template.assert_awaited_once()
        self.assertEqual(self.page.mouse.click.await_count, 2)

    @patch(
        "hauntedroom.actions.runner.load_template",
        return_value=np.zeros((1, 1), dtype=np.uint8),
    )
    @patch(
        "hauntedroom.actions.runner_executor.wait_for_template",
        new_callable=AsyncMock,
    )
    async def test_second_timeout_stops_runner(
        self, wait_for_template, _load_template
    ):
        wait_for_template.side_effect = [
            TimeoutError("first timeout"),
            TimeoutError("second timeout"),
        ]
        with self.assertRaisesRegex(TimeoutError, "second timeout"):
            await run_actions(self.page, self.actions, loop_count=3)
        self.assertEqual(wait_for_template.await_count, 2)
        self.page.mouse.click.assert_not_awaited()

    @patch(
        "hauntedroom.actions.runner.load_template",
        return_value=np.zeros((1, 1), dtype=np.uint8),
    )
    @patch(
        "hauntedroom.actions.runner_executor.wait_for_template",
        new_callable=AsyncMock,
    )
    async def test_successful_loop_resets_timeout_count(
        self, wait_for_template, _load_template
    ):
        wait_for_template.side_effect = [
            TimeoutError("first timeout"),
            TemplateWaitResult(TemplateWaitStatus.MATCHED, (30, 40, 0.95)),
            TimeoutError("timeout after recovery"),
            TimeoutError("consecutive timeout"),
        ]
        with self.assertRaisesRegex(TimeoutError, "consecutive timeout"):
            await run_actions(self.page, self.actions, loop_count=4)
        self.assertEqual(wait_for_template.await_count, 4)
        self.assertEqual(self.page.mouse.click.await_count, 2)

    async def test_pre_set_stop_event_ends_flow_without_clicking(self):
        stop_event = asyncio.Event()
        stop_event.set()
        completed = await run_actions(
            self.page,
            [ClickAction(x=10, y=20)],
            loop_count=None,
            stop_event=stop_event,
        )
        self.assertFalse(completed)
        self.page.mouse.click.assert_not_awaited()
