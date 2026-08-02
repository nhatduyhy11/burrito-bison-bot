import sys
from pathlib import Path
from unittest import TestCase

import cv2
import numpy as np

TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
sys.path.insert(0, str(TOOLS_DIR))

from hauntedroom.core.vision import find_template, find_template_matches


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

    def test_uses_bottom_left_click_position(self):
        screenshot = np.zeros((100, 120), dtype=np.uint8)
        screenshot[40:70, 50:80] = self.template

        x, y, score = find_template(
            screenshot,
            self.template,
            "test.png",
            "bottom_left",
        )

        self.assertEqual((x, y), (51, 68))
        self.assertAlmostEqual(score, 1.0, places=5)

    def test_uses_mid_left_click_position(self):
        screenshot = np.zeros((100, 120), dtype=np.uint8)
        screenshot[40:70, 50:80] = self.template

        x, y, score = find_template(
            screenshot,
            self.template,
            "test.png",
            "mid_left",
        )

        self.assertEqual((x, y), (51, 55))
        self.assertAlmostEqual(score, 1.0, places=5)

    def test_finds_distinct_matches_ordered_by_largest_y(self):
        screenshot = np.zeros((140, 120), dtype=np.uint8)
        screenshot[15:45, 20:50] = self.template
        screenshot[90:120, 70:100] = self.template

        matches = find_template_matches(
            screenshot,
            self.template,
            "test.png",
            threshold=0.99,
            scales=(1.0,),
        )

        self.assertEqual(len(matches), 2)
        self.assertEqual(matches[0][:2], (85, 105))
        self.assertEqual(matches[1][:2], (35, 30))

    def test_new_start_home_template_matches_supplied_home_screens(self):
        template_name = "start_home.png"
        template = cv2.imread(
            str(TOOLS_DIR / "rooms" / template_name),
            cv2.IMREAD_GRAYSCALE,
        )
        for fixture_name in ("start_home_block.png", "start_home_clean.png"):
            screenshot = cv2.imread(
                str(FIXTURES_DIR / fixture_name),
                cv2.IMREAD_GRAYSCALE,
            )
            with self.subTest(fixture_name=fixture_name):
                x, y, score = find_template(
                    screenshot,
                    template,
                    template_name,
                    scales=(1.0,),
                )

                self.assertEqual((x, y), (314, 562))
                self.assertGreaterEqual(score, 0.95)
