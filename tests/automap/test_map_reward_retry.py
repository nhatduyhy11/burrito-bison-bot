import sys
from pathlib import Path
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, Mock, call, patch

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

from hauntedroom.flows.automap_support.map.model_state import (  # noqa: E402
    MapLifecycleStep,
    MapRewardContext,
    MapState,
)
from hauntedroom.flows.automap_support.map.reward import (  # noqa: E402
    WIN_REWARD_FOLLOWUP_CLICK,
    WIN_REWARD_FOLLOWUP_CLICK_COUNT,
    WIN_REWARD_MAX_CLICK_COUNT,
    WIN_REWARD_RECHECK_MS,
    WIN_REWARD_EMPTY_DELAY_MS,
    handle_reward_retry,
)

FRAME = np.zeros((720, 640), dtype=np.uint8)


class RewardRetryTest(IsolatedAsyncioTestCase):
    def make_context(self, chests_visible: bool):
        self.click = AsyncMock()
        self.wait = AsyncMock(return_value=True)
        return MapRewardContext(
            page=Mock(),
            stop_event=Mock(),
            win_reward_template=np.zeros((2, 2), dtype=np.uint8),
            win_reward_template_path=Path("win_reward.png"),
            reward_list_title_template=np.zeros((2, 2), dtype=np.uint8),
            reward_list_title_template_path=Path("reward_list_title.png"),
            on_win=None,
            find_template_fn=Mock(),
            find_template_matches_fn=Mock(
                return_value=[(305, 466, 0.86)] if chests_visible else []
            ),
            click_fn=self.click,
            wait_for_flow_timeout_fn=self.wait,
        )

    async def test_waits_during_blind_followups(self):
        context = self.make_context(chests_visible=True)
        state = MapState(reward_followup_click_count=1)

        step = await handle_reward_retry(context, state, FRAME)

        self.assertIs(step, MapLifecycleStep.NOT_HANDLED)
        self.click.assert_not_awaited()

    async def test_retries_fixed_point_when_template_is_missing(self):
        context = self.make_context(chests_visible=False)
        state = MapState(reward_followup_click_count=WIN_REWARD_FOLLOWUP_CLICK_COUNT)

        step = await handle_reward_retry(context, state, FRAME)

        self.assertIs(step, MapLifecycleStep.CONTINUE)
        self.click.assert_not_awaited()
        self.wait.assert_awaited_once()

        # A changed frame must not move the pre-calculated click point.
        step = await handle_reward_retry(context, state, FRAME[:360, :320])
        self.assertIs(step, MapLifecycleStep.CONTINUE)
        self.click.assert_awaited_once_with(context.page, 341, 414)
        context.find_template_matches_fn.assert_not_called()

    async def test_retries_until_cap_then_stops(self):
        context = self.make_context(chests_visible=True)
        state = MapState(reward_followup_click_count=WIN_REWARD_FOLLOWUP_CLICK_COUNT)

        steps = []
        for _ in range(100):
            step = await handle_reward_retry(context, state, FRAME)
            steps.append(step)
            if step is MapLifecycleStep.NOT_HANDLED:
                break

        retries = WIN_REWARD_MAX_CLICK_COUNT - WIN_REWARD_FOLLOWUP_CLICK_COUNT
        self.assertEqual(self.click.await_count, retries)
        self.assertEqual(self.wait.await_count, retries * 2)
        self.assertEqual(
            {c.args[1:] for c in self.click.await_args_list},
            {WIN_REWARD_FOLLOWUP_CLICK},
        )
        self.assertEqual(state.reward_followup_click_count, WIN_REWARD_MAX_CLICK_COUNT)
        self.assertTrue(state.reward_retry_exhausted_warned)
        self.assertIs(steps[-1], MapLifecycleStep.NOT_HANDLED)

    async def test_stops_after_popup_when_no_chests_remain(self):
        context = self.make_context(chests_visible=False)
        state = MapState(
            reward_followup_click_count=WIN_REWARD_FOLLOWUP_CLICK_COUNT,
            reward_list_title_seen=True,
        )

        step = await handle_reward_retry(context, state, FRAME)

        self.assertIs(step, MapLifecycleStep.NOT_HANDLED)
        self.click.assert_not_awaited()

    async def test_retries_visible_chests_after_popup_and_waits_after_click(self):
        context = self.make_context(chests_visible=True)
        state = MapState(reward_followup_click_count=2, reward_list_title_seen=True)
        with patch("builtins.print") as log:
            self.assertIs(await handle_reward_retry(context, state, FRAME), MapLifecycleStep.CONTINUE)
            self.click.assert_not_awaited()
            self.assertIs(await handle_reward_retry(context, state, FRAME), MapLifecycleStep.CONTINUE)
        self.click.assert_awaited_once_with(context.page, 341, 414)
        self.assertEqual(self.wait.await_args_list, [
            call(context.page, WIN_REWARD_EMPTY_DELAY_MS, context.stop_event),
            call(context.page, WIN_REWARD_RECHECK_MS, context.stop_event),
        ])
        self.assertEqual(context.find_template_matches_fn.call_count, 2)
        self.assertEqual(state.reward_followup_click_count, 3)
        messages = [c.args[0] for c in log.call_args_list]
        self.assertTrue(any("click begin:" in m and "phase=retry" in m for m in messages))
        self.assertTrue(any("click sent:" in m and "phase=retry" in m for m in messages))

    async def test_cancels_armed_retry_when_chests_disappear_after_popup(self):
        context = self.make_context(chests_visible=True)
        state = MapState(reward_followup_click_count=2, reward_list_title_seen=True)
        await handle_reward_retry(context, state, FRAME)
        context.find_template_matches_fn.return_value = []
        self.assertIs(await handle_reward_retry(context, state, FRAME), MapLifecycleStep.NOT_HANDLED)
        self.click.assert_not_awaited()
        self.assertFalse(state.reward_retry_armed)

    async def test_failed_click_logs_failure_without_claiming_sent(self):
        context = self.make_context(chests_visible=True)
        self.click.side_effect = RuntimeError("mouse disconnected")
        state = MapState(reward_followup_click_count=2, reward_retry_armed=True)
        with patch("builtins.print") as log:
            with self.assertRaisesRegex(RuntimeError, "mouse disconnected"):
                await handle_reward_retry(context, state, FRAME)
        messages = [c.args[0] for c in log.call_args_list]
        self.assertTrue(any("click failed:" in m for m in messages))
        self.assertFalse(any("click sent:" in m for m in messages))
        self.wait.assert_not_awaited()
