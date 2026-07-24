import sys
from pathlib import Path
from unittest import TestCase

import cv2
import numpy as np

TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS_DIR))

from hauntedroom.cv_pattern_matching import find_template


class FindTemplateScaleTest(TestCase):
    def setUp(self):
        self.template = np.zeros((30, 30), dtype=np.uint8)
        cv2.line(self.template, (3, 4), (25, 21), 220, 3)
        cv2.circle(self.template, (9, 21), 5, 140, -1)

    def test_finds_original_scale(self):
        screenshot = np.zeros((100, 120), dtype=np.uint8)
        screenshot[40:70, 50:80] = self.template

        x, y, score = find_template(screenshot, self.template, "test.png")

        self.assertEqual((x, y), (65, 55))
        self.assertAlmostEqual(score, 1.0, places=5)

    def test_finds_point_67_scale_and_uses_scaled_click_center(self):
        scaled = cv2.resize(
            self.template,
            None,
            fx=0.67,
            fy=0.67,
            interpolation=cv2.INTER_AREA,
        )
        height, width = scaled.shape
        screenshot = np.zeros((100, 120), dtype=np.uint8)
        screenshot[20 : 20 + height, 70 : 70 + width] = scaled

        x, y, score = find_template(screenshot, self.template, "test.png")

        self.assertEqual((x, y), (70 + width // 2, 20 + height // 2))
        self.assertAlmostEqual(score, 1.0, places=5)
