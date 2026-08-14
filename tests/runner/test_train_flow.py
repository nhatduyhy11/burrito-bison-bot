import asyncio
import sys
from pathlib import Path
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, Mock, call, patch

import cv2


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "tools"))
FIXTURES = PROJECT_ROOT / "tests" / "fixtures" / "train_select"

from hauntedroom.flows.automap_support.train_select import TrainChoice
from hauntedroom.actions.models import ClickTemplateAction
from hauntedroom.flows.train import (
    TRAIN_BATTLE_LOAD_MS,
    TRAIN_ENTRY_CLICK,
    TRAIN_SELECTION_ROUNDS,
    TRAIN_SELECTION_SETTLE_MS,
    get_start_battle_action,
    run_train_flow,
    train_is_available,
)


class TrainFlowTest(IsolatedAsyncioTestCase):
    def setUp(self):
        self.page = Mock()
        self.page.evaluate = AsyncMock()
        self.page.mouse = Mock()
        self.page.mouse.click = AsyncMock()
        self.page.wait_for_timeout = AsyncMock()
        self.start_battle_path = Path("rooms/start_battle.png")
        self.actions = [
            ClickTemplateAction(
                self.start_battle_path,
                threshold=0.91,
                template_scales=(1.0, 0.67),
            )
        ]

    def test_available_fixture_is_detected(self):
        frame = cv2.imread(str(FIXTURES / "train_available.png"))
        self.assertTrue(train_is_available(frame))

    def test_reuses_start_battle_action_configuration(self):
        self.assertIs(get_start_battle_action(self.actions), self.actions[0])

    @patch("hauntedroom.flows.train.TrainHeroMatcher")
    @patch("hauntedroom.flows.train.load_template")
    @patch("hauntedroom.flows.train.wait_for_template", new_callable=AsyncMock)
    @patch("hauntedroom.flows.train.capture_page_bgr", new_callable=AsyncMock)
    async def test_confirms_five_rounds_then_hands_off_to_automap(
        self,
        capture_page_bgr,
        wait_for_template,
        load_template,
        matcher_type,
    ):
        available = cv2.imread(str(FIXTURES / "train_available.png"))
        capture_page_bgr.return_value = available
        wait_for_template.return_value = (401, 644, 0.95)
        load_template.return_value = Mock()
        matcher = matcher_type.return_value
        choices = []
        for _ in range(TRAIN_SELECTION_ROUNDS):
            choices.extend(
                [
                    TrainChoice(172, 566),
                    TrainChoice(271, 566),
                    TrainChoice(319, 670, confirm=True),
                ]
            )
        matcher.find_choice.side_effect = choices
        automap_flow = AsyncMock(return_value=True)
        stop_event = asyncio.Event()

        result = await run_train_flow(
            self.page,
            self.actions,
            automap_flow,
            stop_event,
            debug=True,
        )

        self.assertTrue(result)
        self.assertEqual(
            self.page.mouse.click.await_args_list[:2],
            [call(*TRAIN_ENTRY_CLICK), call(401, 644)],
        )
        confirm_clicks = [
            click_args
            for click_args in self.page.mouse.click.await_args_list
            if click_args == call(319, 670)
        ]
        self.assertEqual(len(confirm_clicks), TRAIN_SELECTION_ROUNDS)
        self.assertEqual(
            self.page.wait_for_timeout.await_args_list,
            [call(TRAIN_BATTLE_LOAD_MS)]
            + [call(TRAIN_SELECTION_SETTLE_MS)] * 15,
        )
        automap_flow.assert_awaited_once_with(
            self.page, stop_event, debug=True
        )
        self.assertEqual(wait_for_template.await_args.kwargs["template_scales"], (1.0, 0.67))
