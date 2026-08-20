import asyncio
import sys
from pathlib import Path
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, Mock, call, patch

import cv2


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "tools"))
FIXTURES = PROJECT_ROOT / "tests" / "fixtures" / "train_flow"

from hauntedroom.flows.automap_support.train_select import TrainChoice
from hauntedroom.core.template_detection import (
    TemplateWaitResult,
    TemplateWaitStatus,
)
from hauntedroom.flows.train import (
    TRAIN_BATTLE_LOAD_MS,
    TRAIN_ENTRY_SETTLE_MS,
    TRAIN_SELECTION_ROUNDS,
    TRAIN_SELECTION_SETTLE_MS,
    find_train_challenge_click,
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

    def test_available_fixture_is_detected(self):
        frame = cv2.imread(str(FIXTURES / "train_available.png"))
        self.assertTrue(train_is_available(frame))

    def test_finds_live_train_challenge_button_center(self):
        frame = cv2.imread(str(FIXTURES / "train_available.png"))

        self.assertEqual(find_train_challenge_click(frame), (400, 646))

    def test_does_not_invent_click_when_challenge_button_is_absent(self):
        frame = cv2.imread(str(FIXTURES / "train_available.png"))
        frame[620:680, 320:480] = 0

        self.assertIsNone(find_train_challenge_click(frame))

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
        wait_for_template.return_value = TemplateWaitResult(
            TemplateWaitStatus.MATCHED,
            (401, 644, 0.95),
        )
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
            automap_flow,
            stop_event,
            debug=True,
        )

        self.assertTrue(result)
        self.assertEqual(
            self.page.mouse.click.await_args_list[:2],
            [call(400, 646), call(401, 644)],
        )
        confirm_clicks = [
            click_args
            for click_args in self.page.mouse.click.await_args_list
            if click_args == call(319, 670)
        ]
        self.assertEqual(len(confirm_clicks), TRAIN_SELECTION_ROUNDS)
        self.assertEqual(
            self.page.wait_for_timeout.await_args_list,
            [call(TRAIN_ENTRY_SETTLE_MS), call(TRAIN_BATTLE_LOAD_MS)]
            + [call(TRAIN_SELECTION_SETTLE_MS)] * 15,
        )
        self.assertEqual(
            wait_for_template.await_args.kwargs["template_scales"],
            (1.0, 0.67),
        )
        automap_flow.assert_awaited_once_with(
            self.page, stop_event, debug=True
        )
