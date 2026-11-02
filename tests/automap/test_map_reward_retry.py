import sys
from pathlib import Path
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, Mock

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

    async def test_no_retry_when_chests_gone(self):
        context = self.make_context(chests_visible=False)
        state = MapState(reward_followup_click_count=WIN_REWARD_FOLLOWUP_CLICK_COUNT)

        step = await handle_reward_retry(context, state, FRAME)

        self.assertIs(step, MapLifecycleStep.NOT_HANDLED)
        self.click.assert_not_awaited()
        self.wait.assert_not_awaited()

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
        self.assertEqual(self.wait.await_count, retries)
        self.assertEqual(
            {c.args[1:] for c in self.click.await_args_list},
            {WIN_REWARD_FOLLOWUP_CLICK},
        )
        self.assertEqual(state.reward_followup_click_count, WIN_REWARD_MAX_CLICK_COUNT)
        self.assertTrue(state.reward_retry_exhausted_warned)
        self.assertIs(steps[-1], MapLifecycleStep.NOT_HANDLED)

    async def test_stops_once_popup_confirmed(self):
        context = self.make_context(chests_visible=True)
        state = MapState(
            reward_followup_click_count=WIN_REWARD_FOLLOWUP_CLICK_COUNT,
            reward_list_title_seen=True,
        )

        step = await handle_reward_retry(context, state, FRAME)

        self.assertIs(step, MapLifecycleStep.NOT_HANDLED)
        self.click.assert_not_awaited()
