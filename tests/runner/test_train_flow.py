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
from hauntedroom.flows.automap_support.map.model_state import MapRunState
from hauntedroom.core.template_detection import (
    TemplateWaitResult,
    TemplateWaitStatus,
)
from hauntedroom.flows.train import TrainMode, run_train_flow
from hauntedroom.flows.train_support import (
    TRAIN_BATTLE_LOAD_MS,
    TRAIN_ENTRY_SETTLE_MS,
    TRAIN_SELECTION_ROUNDS,
    TRAIN_SELECTION_SETTLE_MS,
    find_train_challenge_click,
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

    @patch("hauntedroom.flows.train.check_and_click_train_challenge", new_callable=AsyncMock)
    async def test_mode_normal_requires_automap_before_entering_train(
        self,
        check_and_click_train_challenge,
    ):
        with self.assertRaisesRegex(
            ValueError,
            "automap_flow is required for normal train mode",
        ):
            await run_train_flow(self.page, mode=TrainMode.NORMAL)

        check_and_click_train_challenge.assert_not_awaited()

    @patch("hauntedroom.flows.train_support.hero_selection.TrainHeroMatcher")
    @patch("hauntedroom.flows.train_support.entry.load_template")
    @patch("hauntedroom.flows.train_support.entry.wait_for_template", new_callable=AsyncMock)
    @patch("hauntedroom.flows.train_support.entry.capture_page_bgr", new_callable=AsyncMock)
    @patch("hauntedroom.flows.train_support.hero_selection.capture_page_bgr", new_callable=AsyncMock)
    async def test_mode_normal_confirms_five_rounds_then_hands_off_to_automap(
        self,
        hero_capture_page_bgr,
        entry_capture_page_bgr,
        wait_for_template,
        load_template,
        matcher_type,
    ):
        """Mode 1: Normal train flow."""
        available = cv2.imread(str(FIXTURES / "train_available.png"))
        entry_capture_page_bgr.return_value = available
        hero_capture_page_bgr.return_value = available
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
        run_state = MapRunState()

        result = await run_train_flow(
            self.page,
            automap_flow,
            stop_event,
            debug=True,
            run_state=run_state,
            mode=TrainMode.NORMAL,
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
            self.page,
            stop_event,
            debug=True,
            run_state=run_state,
        )

    @patch("hauntedroom.flows.train.run_train_ad_exit_cycle", new_callable=AsyncMock)
    async def test_mode_exit_immediately_single_cycle(self, mock_cycle):
        """Mode 2: Exit immediately after match start."""
        mock_cycle.return_value = True
        stop_event = asyncio.Event()

        result = await run_train_flow(
            self.page,
            stop_event=stop_event,
            mode=TrainMode.EXIT_IMMEDIATELY,
            loop=False,
        )
        self.assertTrue(result)
        mock_cycle.assert_awaited_once_with(self.page, stop_event, pet_and_ad=False)

    @patch("hauntedroom.flows.train.run_train_ad_exit_loop", new_callable=AsyncMock)
    async def test_mode_exit_immediately_loop(self, mock_loop):
        """Mode 2 loop: Exit immediately after match start in loop."""
        mock_loop.return_value = True
        stop_event = asyncio.Event()

        result = await run_train_flow(
            self.page,
            stop_event=stop_event,
            mode="exit_immediately",
            loop=True,
        )
        self.assertTrue(result)
        mock_loop.assert_awaited_once_with(self.page, stop_event, debug=False, pet_and_ad=False)

    @patch("hauntedroom.flows.train.run_train_ad_exit_cycle", new_callable=AsyncMock)
    async def test_mode_pet_and_ad_single_cycle(self, mock_cycle):
        """Mode 3: Pet summon, spin dismissal, then exit."""
        mock_cycle.return_value = True
        stop_event = asyncio.Event()

        result = await run_train_flow(
            self.page,
            stop_event=stop_event,
            mode=TrainMode.PET_AND_AD,
            loop=False,
        )
        self.assertTrue(result)
        mock_cycle.assert_awaited_once_with(self.page, stop_event, pet_and_ad=True)

    @patch("hauntedroom.flows.train.run_train_ad_exit_loop", new_callable=AsyncMock)
    async def test_mode_pet_and_ad_loop(self, mock_loop):
        """Mode 3 loop: Pet summon, spin dismissal, then exit in loop."""
        mock_loop.return_value = True
        stop_event = asyncio.Event()

        result = await run_train_flow(
            self.page,
            stop_event=stop_event,
            mode="pet_and_ad",
            loop=True,
        )
        self.assertTrue(result)
        mock_loop.assert_awaited_once_with(self.page, stop_event, debug=False, pet_and_ad=True)
