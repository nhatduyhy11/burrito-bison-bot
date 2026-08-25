import sys
from pathlib import Path
from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import AsyncMock, Mock, call, patch

import cv2
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

from hauntedroom.core.template_matching import find_template, load_template
from hauntedroom.flows.research import (
    RESEARCH_ACTIVE_TEMPLATE_PATH,
    run_research_flow,
)


class ResearchFlowTest(IsolatedAsyncioTestCase):

    @patch(
        "hauntedroom.flows.research.load_template",
        return_value=np.zeros((2, 2), dtype=np.uint8),
    )
    @patch(
        "hauntedroom.flows.research.capture_page_grayscale",
        new_callable=AsyncMock,
    )
    @patch("hauntedroom.flows.research.find_template")
    async def test_research_flow_returns_to_available_after_active_is_gone(
        self,
        find_template,
        capture_page_grayscale,
        _load_template,
    ):
        page = Mock()
        page.evaluate = AsyncMock()
        page.wait_for_timeout = AsyncMock()
        page.mouse = Mock()
        page.mouse.click = AsyncMock()
        capture_page_grayscale.return_value = np.zeros((10, 10), dtype=np.uint8)
        find_template.side_effect = [
            (11, 22, 0.61),
            (270, 420, 0.62),
            (0, 0, 0.40),
            (270, 420, 0.63),
            (0, 0, 0.41),
            (0, 0, 0.42),
            (0, 0, 0.43),
            (0, 0, 0.44),
            (0, 0, 0.45),
            (0, 0, 0.46),
            (0, 0, 0.47),
            (0, 0, 0.48),
        ]

        completed = await run_research_flow(page)

        self.assertTrue(completed)
        self.assertEqual(find_template.call_count, 12)
        self.assertEqual(find_template.call_args_list[0].args[-1], "bottom_left")
        self.assertEqual(find_template.call_args_list[0].kwargs["scales"], (1.0,))
        self.assertEqual(len(find_template.call_args_list[1].args), 3)
        self.assertEqual(find_template.call_args_list[1].kwargs["scales"], (1.0,))
        self.assertEqual(find_template.call_args_list[8].args[-1], "bottom_left")
        self.assertEqual(
            page.mouse.click.await_args_list,
            [call(11, 22), call(230, 425), call(230, 425)],
        )

    @patch(
        "hauntedroom.flows.research.load_template",
        return_value=np.zeros((2, 2), dtype=np.uint8),
    )
    @patch(
        "hauntedroom.flows.research.capture_page_grayscale",
        new_callable=AsyncMock,
    )
    @patch("hauntedroom.flows.research.find_template")
    async def test_research_flow_checks_available_four_times_before_ending(
        self,
        find_template,
        capture_page_grayscale,
        _load_template,
    ):
        page = Mock()
        page.evaluate = AsyncMock()
        page.wait_for_timeout = AsyncMock()
        page.mouse = Mock()
        page.mouse.click = AsyncMock()
        capture_page_grayscale.return_value = np.zeros((10, 10), dtype=np.uint8)
        find_template.side_effect = [
            (0, 0, score) for score in (0.40, 0.41, 0.42, 0.43)
        ]

        completed = await run_research_flow(page)

        self.assertTrue(completed)
        self.assertEqual(find_template.call_count, 4)
        self.assertEqual(page.wait_for_timeout.await_count, 3)
        page.mouse.click.assert_not_awaited()


class ResearchActiveTemplateTest(TestCase):

    def test_language_neutral_active_template_ignores_standalone_badge(self):
        fixture_path = (
            PROJECT_ROOT
            / "tests"
            / "fixtures"
            / "hauntedroom-captures"
            / "cn_server"
            / "research_available_cn.png"
        )
        screenshot = cv2.imread(str(fixture_path), cv2.IMREAD_GRAYSCALE)
        self.assertIsNotNone(screenshot)
        active_template = load_template(RESEARCH_ACTIVE_TEMPLATE_PATH)

        x, y, score = find_template(
            screenshot,
            active_template,
            RESEARCH_ACTIVE_TEMPLATE_PATH.name,
            scales=(1.0,),
        )

        self.assertEqual((x, y), (270, 420))
        self.assertGreater(score, 0.98)

        # Remove the popup-button anchor. The standalone badge on the selected
        # research node must stay below the production threshold.
        without_popup_anchor = screenshot.copy()
        without_popup_anchor[400:440, 258:282] = 128
        _, _, standalone_badge_score = find_template(
            without_popup_anchor,
            active_template,
            RESEARCH_ACTIVE_TEMPLATE_PATH.name,
            scales=(1.0,),
        )
        self.assertLess(standalone_badge_score, 0.6)
