import sys
from pathlib import Path
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, Mock, patch

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

from hauntedroom.core.template_detection import (
    TemplateWaitStatus,
    wait_for_template,
)


class TemplateDetectionTest(IsolatedAsyncioTestCase):

    def setUp(self):
        self.page = Mock()
        self.page.wait_for_timeout = AsyncMock()

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
