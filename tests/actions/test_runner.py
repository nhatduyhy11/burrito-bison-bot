import sys
from pathlib import Path
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, Mock, call, patch

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

from hauntedroom.actions.models import (
    ClearBlockersAction,
    ClickAction,
    ClickTemplateAction,
)
from hauntedroom.actions.runner import run_actions
from hauntedroom.core.terminal import BLUE
from hauntedroom.core.template_detection import (
    TemplateWaitResult,
    TemplateWaitStatus,
    wait_for_template,
)


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
    @patch("hauntedroom.actions.runner.wait_for_template", new_callable=AsyncMock)
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
    @patch("hauntedroom.actions.runner.wait_for_template", new_callable=AsyncMock)
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
    @patch("hauntedroom.actions.runner.wait_for_template", new_callable=AsyncMock)
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
    @patch("hauntedroom.actions.runner.wait_for_template", new_callable=AsyncMock)
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
    @patch("hauntedroom.actions.runner.wait_for_template", new_callable=AsyncMock)
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

    @patch(
        "hauntedroom.actions.runner.load_template",
        return_value=np.zeros((1, 1), dtype=np.uint8),
    )
    @patch("hauntedroom.actions.runner.wait_for_template", new_callable=AsyncMock)
    async def test_click_template_skip_if_template_avoids_clicking_stale_step(
        self, wait_for_template, load_template
    ):
        skip_path = Path("home.png")
        self.actions[0] = ClickTemplateAction(
            template_path=self.template_path,
            note="Start",
            delay_ms=0,
            skip_if_template_path=skip_path,
            click_position="mid_left",
            template_scales=(1.0, 0.67, 0.5),
            skip_template_scales=(0.5,),
            region=(10, 20, 300, 400),
        )
        wait_for_template.return_value = TemplateWaitResult(
            TemplateWaitStatus.ALTERNATIVE_MATCHED
        )

        await run_actions(self.page, self.actions, loop_count=1)

        self.assertEqual(load_template.call_count, 2)
        wait_for_template.assert_awaited_once()
        self.assertIs(
            wait_for_template.await_args.kwargs["skip_template"],
            load_template.return_value,
        )
        self.assertEqual(
            wait_for_template.await_args.kwargs["skip_template_name"],
            skip_path.name,
        )
        self.assertEqual(
            wait_for_template.await_args.kwargs["click_position"],
            "mid_left",
        )
        self.assertEqual(
            wait_for_template.await_args.kwargs["template_scales"],
            (1.0, 0.67, 0.5),
        )
        self.assertEqual(
            wait_for_template.await_args.kwargs["skip_template_scales"],
            (0.5,),
        )
        self.assertEqual(
            wait_for_template.await_args.kwargs["region"],
            (10, 20, 300, 400),
        )
        self.page.mouse.click.assert_awaited_once_with(10, 20, button="left")

    @patch(
        "hauntedroom.actions.runner.capture_page_grayscale",
        new_callable=AsyncMock,
    )
    @patch("hauntedroom.actions.runner.find_template")
    @patch(
        "hauntedroom.actions.runner.load_template",
        return_value=np.zeros((1, 1), dtype=np.uint8),
    )
    @patch("hauntedroom.actions.runner.wait_for_template", new_callable=AsyncMock)
    async def test_repeat_click_rechecks_template_and_stops_when_it_disappears(
        self,
        wait_for_template,
        _load_template,
        find_template,
        capture_page_grayscale,
    ):
        action = ClickTemplateAction(
            template_path=Path("start_home.png"),
            template_scales=(1.0,),
            click_position="mid_left",
            click_count=3,
            delay_ms=0,
            repeat_delay_ms=1000,
            recheck_before_repeat=True,
            region=(1, 2, 9, 10),
        )
        wait_for_template.return_value = TemplateWaitResult(
            TemplateWaitStatus.MATCHED,
            (10, 20, 0.95),
        )
        capture_page_grayscale.return_value = np.zeros((10, 10), dtype=np.uint8)
        find_template.side_effect = [(30, 40, 0.96), (0, 0, 0.40)]

        completed = await run_actions(self.page, [action], loop_count=1)

        self.assertTrue(completed)
        self.assertEqual(
            self.page.wait_for_timeout.await_args_list,
            [call(0), call(1000), call(1000)],
        )
        self.assertEqual(capture_page_grayscale.await_count, 2)
        self.assertTrue(
            all(
                match_call.kwargs["region"] == (1, 2, 9, 10)
                for match_call in find_template.call_args_list
            )
        )
        self.assertEqual(
            self.page.mouse.click.await_args_list,
            [
                call(10, 20, button="left"),
                call(30, 40, button="left"),
            ],
        )

    @patch(
        "hauntedroom.actions.runner.load_template",
        return_value=np.zeros((1, 1), dtype=np.uint8),
    )
    @patch("hauntedroom.actions.runner.clear_blockers", new_callable=AsyncMock)
    async def test_clear_blockers_receives_until_template_scales(
        self,
        clear_blockers,
        _load_template,
    ):
        action = ClearBlockersAction(
            blocker_paths=(Path("overlay.png"),),
            until_template_path=Path("start_home.png"),
            until_template_scales=(1.0,),
        )
        clear_blockers.return_value = True

        await run_actions(self.page, [action], loop_count=1)

        clear_blockers.assert_awaited_once()
        self.assertEqual(
            clear_blockers.await_args.kwargs["until_template_scales"],
            (1.0,),
        )

    @patch(
        "hauntedroom.core.template_detection.capture_page_grayscale",
        new_callable=AsyncMock,
    )
    @patch("hauntedroom.core.template_detection.find_template")
    async def test_wait_for_template_returns_alternative_status_when_it_matches(
        self, find_template, capture_page_grayscale
    ):
        capture_page_grayscale.return_value = np.zeros((10, 10), dtype=np.uint8)
        find_template.side_effect = [(0, 0, 0.4), (20, 30, 0.95)]

        result = await wait_for_template(
            self.page,
            np.zeros((1, 1), dtype=np.uint8),
            "exit_back.png",
            0.75,
            1000,
            400,
            skip_template=np.zeros((1, 1), dtype=np.uint8),
            skip_template_name="start_home.png",
        )

        self.assertIs(result.status, TemplateWaitStatus.ALTERNATIVE_MATCHED)
        self.assertIsNone(result.match)
        self.page.wait_for_timeout.assert_not_awaited()
