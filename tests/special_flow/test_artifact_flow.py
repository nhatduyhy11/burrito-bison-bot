import sys
from pathlib import Path
from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import AsyncMock, Mock, call, patch

import cv2
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

from hauntedroom.core.template import load_template
from hauntedroom.flows.artifact import (
    ARTIFACT_CLOSE_TEMPLATE_PATH,
    ARTIFACT_MARK_TEMPLATE_PATH,
    find_artifact_activation,
    find_artifact_item,
    find_artifact_popup_close,
    find_artifact_tabs,
    run_artifact_flow,
)


FIXTURE_DIR = PROJECT_ROOT / "tests" / "fixtures" / "special_flow"


class ArtifactDetectorTest(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mark_template = load_template(ARTIFACT_MARK_TEMPLATE_PATH)
        cls.close_template = load_template(ARTIFACT_CLOSE_TEMPLATE_PATH)

    def _fixture(self, name: str) -> np.ndarray:
        frame = cv2.imread(str(FIXTURE_DIR / name), cv2.IMREAD_GRAYSCALE)
        self.assertIsNotNone(frame)
        return frame

    def test_first_available_fixture_finds_tabs_and_content_click(self):
        frame = self._fixture("artifact_avail.png")

        tabs = find_artifact_tabs(frame, self.mark_template)
        item = find_artifact_item(frame, self.mark_template)

        self.assertEqual([match[0] for match in tabs], [0, 1, 2])
        self.assertEqual((tabs[0][1], tabs[0][2]), (225, 361))
        self.assertIsNotNone(item)
        self.assertEqual(item[:2], (417, 411))

    def test_second_available_fixture_finds_tabs_and_content_click(self):
        frame = self._fixture("artifact_avail_2.png")

        tabs = find_artifact_tabs(frame, self.mark_template)
        item = find_artifact_item(frame, self.mark_template)

        self.assertEqual([match[0] for match in tabs], [0, 1, 2])
        self.assertEqual((tabs[0][1], tabs[0][2]), (225, 361))
        self.assertIsNotNone(item)
        self.assertEqual(item[:2], (186, 411))

    def test_active_fixture_reuses_mark_and_lubu_close_templates(self):
        frame = self._fixture("artifact_active.png")

        activation = find_artifact_activation(frame, self.mark_template)
        close = find_artifact_popup_close(frame, self.close_template)

        self.assertIsNotNone(activation)
        self.assertEqual(activation[:2], (364, 587))
        self.assertGreaterEqual(activation[2], 0.60)
        self.assertIsNotNone(close)
        self.assertEqual(close[:2], (491, 87))
        self.assertGreaterEqual(close[2], 0.90)


class ArtifactFlowTest(IsolatedAsyncioTestCase):
    @patch(
        "hauntedroom.flows.artifact.load_template",
        return_value=np.zeros((2, 2), dtype=np.uint8),
    )
    @patch(
        "hauntedroom.flows.artifact.capture_page_grayscale",
        new_callable=AsyncMock,
        return_value=np.zeros((720, 640), dtype=np.uint8),
    )
    @patch("hauntedroom.flows.artifact.find_artifact_popup_close")
    @patch("hauntedroom.flows.artifact.find_artifact_activation")
    @patch("hauntedroom.flows.artifact.find_artifact_item")
    @patch("hauntedroom.flows.artifact.find_artifact_tabs")
    async def test_flow_opens_activates_closes_and_finishes(
        self,
        find_tabs,
        find_item,
        find_activation,
        find_close,
        _capture,
        _load,
    ):
        page = Mock()
        page.evaluate = AsyncMock()
        page.wait_for_timeout = AsyncMock()
        page.mouse = Mock()
        page.mouse.click = AsyncMock()
        find_tabs.side_effect = [[(0, 225, 361, 0.84)], [], []]
        find_item.side_effect = [(417, 411, 0.90), None, None, None]
        find_close.side_effect = [
            (491, 87, 0.98),
            (491, 87, 0.98),
            (491, 87, 0.98),
            (491, 87, 0.98),
            None,
        ]
        find_activation.side_effect = [(364, 587, 0.64), None]

        completed = await run_artifact_flow(
            page, delay_ms=0, idle_confirm_ms=0
        )

        self.assertTrue(completed)
        self.assertEqual(
            page.mouse.click.await_args_list,
            [
                call(225, 361),
                call(417, 411),
                call(364, 587),
                call(364, 587),
                call(364, 587),
                call(491, 87),
            ],
        )
        self.assertEqual(
            page.wait_for_timeout.await_args_list,
            [call(0), call(0), call(1000), call(1000), call(1000), call(0)],
        )

    @patch(
        "hauntedroom.flows.artifact.load_template",
        return_value=np.zeros((2, 2), dtype=np.uint8),
    )
    @patch(
        "hauntedroom.flows.artifact.capture_page_grayscale",
        new_callable=AsyncMock,
        return_value=np.zeros((720, 640), dtype=np.uint8),
    )
    @patch(
        "hauntedroom.flows.artifact.find_artifact_activation",
        return_value=None,
    )
    @patch(
        "hauntedroom.flows.artifact.find_artifact_item",
        return_value=None,
    )
    @patch(
        "hauntedroom.flows.artifact.find_artifact_tabs",
        return_value=[],
    )
    @patch("hauntedroom.flows.artifact.find_artifact_popup_close")
    async def test_idle_confirmation_reclicks_close_then_observes_two_seconds(
        self,
        find_close,
        _find_tabs,
        _find_item,
        _find_activation,
        _capture,
        _load,
    ):
        page = Mock()
        page.evaluate = AsyncMock()
        page.wait_for_timeout = AsyncMock()
        page.mouse = Mock()
        page.mouse.click = AsyncMock()
        find_close.side_effect = [(491, 87, 0.98), None, None, None, None]

        completed = await run_artifact_flow(page)

        self.assertTrue(completed)
        page.mouse.click.assert_awaited_once_with(491, 87)
        self.assertEqual(
            page.wait_for_timeout.await_args_list,
            [call(800), call(800), call(800), call(800)],
        )
        _find_activation.assert_called_once()

    @patch(
        "hauntedroom.flows.artifact.load_template",
        return_value=np.zeros((2, 2), dtype=np.uint8),
    )
    @patch(
        "hauntedroom.flows.artifact.capture_page_grayscale",
        new_callable=AsyncMock,
        return_value=np.zeros((720, 640), dtype=np.uint8),
    )
    @patch("hauntedroom.flows.artifact.find_artifact_activation")
    @patch(
        "hauntedroom.flows.artifact.find_artifact_popup_close",
        return_value=None,
    )
    @patch(
        "hauntedroom.flows.artifact.find_artifact_item",
        return_value=None,
    )
    @patch(
        "hauntedroom.flows.artifact.find_artifact_tabs",
        return_value=[],
    )
    async def test_list_state_never_scans_popup_activation_region(
        self,
        _find_tabs,
        _find_item,
        _find_close,
        find_activation,
        _capture,
        _load,
    ):
        page = Mock()
        page.evaluate = AsyncMock()
        page.wait_for_timeout = AsyncMock()
        page.mouse = Mock()
        page.mouse.click = AsyncMock()

        completed = await run_artifact_flow(
            page, delay_ms=0, idle_confirm_ms=0
        )

        self.assertTrue(completed)
        find_activation.assert_not_called()
        page.mouse.click.assert_not_awaited()

    @patch(
        "hauntedroom.flows.artifact.load_template",
        return_value=np.zeros((2, 2), dtype=np.uint8),
    )
    @patch(
        "hauntedroom.flows.artifact.capture_page_grayscale",
        new_callable=AsyncMock,
        return_value=np.zeros((720, 640), dtype=np.uint8),
    )
    @patch("hauntedroom.flows.artifact.find_artifact_popup_close")
    @patch("hauntedroom.flows.artifact.find_artifact_item")
    @patch("hauntedroom.flows.artifact.find_artifact_tabs")
    async def test_flow_retries_card_click_until_popup_appears(
        self,
        find_tabs,
        find_item,
        find_close,
        _capture,
        _load,
    ):
        page = Mock()
        page.evaluate = AsyncMock()
        page.wait_for_timeout = AsyncMock()
        page.mouse = Mock()
        page.mouse.click = AsyncMock()
        find_tabs.return_value = [(0, 225, 361, 0.84)]
        find_item.return_value = (417, 411, 0.90)
        find_close.return_value = None

        completed = await run_artifact_flow(page, delay_ms=0)

        self.assertFalse(completed)
        self.assertEqual(
            page.mouse.click.await_args_list,
            [call(225, 361)] + [call(417, 411)] * 4,
        )
