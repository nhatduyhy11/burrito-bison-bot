import sys
from pathlib import Path
from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import AsyncMock, Mock, call, patch

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

from hauntedroom.actions.models import (
    ClearBlockersAction,
    ClickAction,
    ClickTemplateAction,
)
from hauntedroom.actions.runner_executor import action_label, execute_action
from hauntedroom.core.template_detection import TemplateWaitResult, TemplateWaitStatus


class ActionLabelTest(TestCase):

    def test_includes_note_when_present(self):
        self.assertEqual(action_label(2, 3, "Start"), "2.3 (Start)")

    def test_omits_parentheses_without_note(self):
        self.assertEqual(action_label(2, 3, None), "2.3")


class ActionRunnerExecutorTest(IsolatedAsyncioTestCase):

    def setUp(self):
        self.page = Mock()
        self.page.evaluate = AsyncMock()
        self.page.wait_for_timeout = AsyncMock()
        self.page.mouse = Mock()
        self.page.mouse.click = AsyncMock()

    async def test_click_action_dispatches_to_mouse(self):
        completed = await execute_action(
            self.page,
            ClickAction(x=10, y=20),
            {},
            loop_index=1,
            action_index=2,
            stop_event=None,
        )
        self.assertTrue(completed)
        self.page.mouse.click.assert_awaited_once_with(10, 20, button="left")

    @patch(
        "hauntedroom.actions.runner_executor.wait_for_template",
        new_callable=AsyncMock,
    )
    async def test_click_template_skip_if_template_avoids_clicking_stale_step(
        self, wait_for_template
    ):
        template_path = Path("start.png")
        skip_path = Path("home.png")
        template = np.zeros((1, 1), dtype=np.uint8)
        skip_template = np.ones((1, 1), dtype=np.uint8)
        action = ClickTemplateAction(
            template_path=template_path,
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
        completed = await execute_action(
            self.page,
            action,
            {template_path: template, skip_path: skip_template},
            loop_index=1,
            action_index=1,
            stop_event=None,
        )
        self.assertTrue(completed)
        wait_for_template.assert_awaited_once()
        self.assertIs(
            wait_for_template.await_args.kwargs["skip_template"],
            skip_template,
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
        self.page.mouse.click.assert_not_awaited()

    @patch(
        "hauntedroom.actions.runner_executor.capture_page_grayscale",
        new_callable=AsyncMock,
    )
    @patch("hauntedroom.actions.runner_executor.find_template")
    @patch(
        "hauntedroom.actions.runner_executor.wait_for_template",
        new_callable=AsyncMock,
    )
    async def test_repeat_click_rechecks_template_and_stops_when_it_disappears(
        self,
        wait_for_template,
        find_template,
        capture_page_grayscale,
    ):
        template_path = Path("start_home.png")
        action = ClickTemplateAction(
            template_path=template_path,
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
        completed = await execute_action(
            self.page,
            action,
            {template_path: np.zeros((1, 1), dtype=np.uint8)},
            loop_index=1,
            action_index=1,
            stop_event=None,
        )
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
        "hauntedroom.actions.runner_executor.clear_blockers",
        new_callable=AsyncMock,
    )
    async def test_clear_blockers_receives_until_template_scales(
        self,
        clear_blockers,
    ):
        blocker_path = Path("overlay.png")
        until_template_path = Path("start_home.png")
        action = ClearBlockersAction(
            blocker_paths=(blocker_path,),
            until_template_path=until_template_path,
            until_template_scales=(1.0,),
        )
        clear_blockers.return_value = True
        completed = await execute_action(
            self.page,
            action,
            {
                blocker_path: np.zeros((1, 1), dtype=np.uint8),
                until_template_path: np.zeros((1, 1), dtype=np.uint8),
            },
            loop_index=1,
            action_index=1,
            stop_event=None,
        )
        self.assertTrue(completed)
        clear_blockers.assert_awaited_once()
        self.assertEqual(
            clear_blockers.await_args.kwargs["until_template_scales"],
            (1.0,),
        )
