import sys
from pathlib import Path
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, Mock, call, patch

import cv2

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "tools"))
FIXTURES = PROJECT_ROOT / "tests" / "fixtures" / "train_flow"
CAPTURES = PROJECT_ROOT / "tests" / "fixtures" / "train_ad_exit_screen"

from hauntedroom.core.runtime import FlowControl
from hauntedroom.flows.automap_support.train_select import TrainChoice
from hauntedroom.core.template_detection import (
    TemplateWaitResult,
    TemplateWaitStatus,
)
from hauntedroom.flows.train_common import (
    TRAIN_SELECTION_ROUNDS,
)
from hauntedroom.flows.train_ad_exit import run_train_ad_exit_flow


class TrainAdExitFlowTest(IsolatedAsyncioTestCase):
    def setUp(self):
        self.page = Mock()
        self.page.evaluate = AsyncMock()
        self.page.mouse = Mock()
        self.page.mouse.click = AsyncMock()
        self.page.wait_for_timeout = AsyncMock()

    @patch("hauntedroom.flows.train_ad_exit.TrainHeroMatcher")
    @patch("hauntedroom.flows.train_ad_exit.load_template")
    @patch("hauntedroom.flows.train_ad_exit.wait_for_template", new_callable=AsyncMock)
    @patch("hauntedroom.flows.train_ad_exit.capture_page_bgr", new_callable=AsyncMock)
    @patch("hauntedroom.flows.train_ad_exit.find_template")
    @patch("hauntedroom.flows.train_ad_exit.click_pause_exit", new_callable=AsyncMock)
    async def test_train_ad_exit_flow_one_loop(
        self,
        click_pause_exit,
        find_template,
        capture_page_bgr,
        wait_for_template,
        load_template,
        matcher_type,
    ):
        stop_event = FlowControl()
        available = cv2.imread(str(FIXTURES / "train_available.png"))
        a4 = cv2.imread(str(CAPTURES / "a_new_4.png"))
        a5 = cv2.imread(str(CAPTURES / "a_new_5.png"))
        
        # We need capture_page_bgr to return:
        # 1. train_is_available check -> available
        # 2-16. TrainHeroMatcher selection rounds -> available
        # 17. Money template check -> a4
        # 18. Wait for pet menu to open -> a5
        # 19. First check inside pet menu click loop -> a5 (still open)
        # 20. Second check inside pet menu click loop -> a4 (closed)
        # 21-23. Subsequent checks (spin, etc.) -> a4
        # 24. Wait train screen check 1 -> a4
        # 25. Wait train screen check 2 -> available
        # 26+. Loop 2 starts -> trigger stop event to terminate flow
        call_count = 0
        def capture_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 16:
                return available
            elif call_count == 17:
                return a4
            elif call_count == 18:
                return a5
            elif call_count == 19:
                return a5
            elif call_count == 20:
                return a4
            elif call_count <= 24:
                return a4
            elif call_count == 25:
                return available
            else:
                stop_event.set()
                return a4
        capture_page_bgr.side_effect = capture_side_effect
        
        # Wait for template results
        wait_for_template.side_effect = [
            # First wait is start battle button
            TemplateWaitResult(TemplateWaitStatus.MATCHED, (401, 644, 0.95)),
        ]
        
        load_template.return_value = Mock()
        
        # Hero selection (5 rounds)
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
        
        # money template matching, pet_active matching, lv_spin matching, and a_new_1 matching
        find_template.side_effect = [
            (233, 654, 0.85),  # money template match (match started)
            (444, 525, 0.90),  # pet_active check (menu open check, present)
            (444, 525, 0.90),  # pet_active check (click loop check 1, menu still open)
            (444, 525, 0.20),  # pet_active check (click loop check 2, closed)
            (285, 125, 0.90),  # lv_spin template match (appeared)
            (285, 125, 0.90),  # lv_spin check (still present to click)
            (285, 125, 0.20),  # lv_spin check (disappeared)
            (100, 100, 0.20),  # wait train screen check 1 (not visible)
            (100, 100, 0.95),  # wait train screen check 2 (visible)
        ]
        
        click_pause_exit.return_value = True

        result = await run_train_ad_exit_flow(
            self.page,
            stop_event,
            debug=True,
        )

        self.assertFalse(result)
        
        # Verify clicks occurred
        clicks = self.page.mouse.click.await_args_list
        self.assertIn(call(400, 646), clicks)
        self.assertIn(call(401, 644), clicks)
        self.assertIn(call(320, 610), clicks)
        
        # First triệu hồi fingerprint button (450, 458) should be clicked twice
        # because the first check was still open, and second check was closed.
        triệu_hồi_clicks = [c for c in clicks if c == call(450, 458)]
        self.assertEqual(len(triệu_hồi_clicks), 2)
        
        # level spin dismiss click
        self.assertIn(call(285, 665), clicks)

        # overlay close click
        self.assertIn(call(251, 633), clicks)
        
        click_pause_exit.assert_awaited_once()
