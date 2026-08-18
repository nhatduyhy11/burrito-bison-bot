import sys
from pathlib import Path
from unittest import TestCase

import cv2
import numpy as np

TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
sys.path.insert(0, str(TOOLS_DIR))

from hauntedroom.core.template import (
    find_template,
    find_template_in_region,
    find_template_matches,
)
from hauntedroom.core.vision import (
    ColorComponentPattern,
    find_color_component,
    region_has_color_component,
    region_has_enough_white,
)


class ColorComponentTest(TestCase):
    def test_checks_color_geometry_and_fill(self):
        pattern = ColorComponentPattern(
            lower_hsv=(15, 120, 180),
            upper_hsv=(40, 255, 255),
            min_area=200,
            min_width=30,
            max_width=40,
            min_height=8,
            max_height=12,
            min_fill_ratio=0.70,
        )
        frame = np.zeros((40, 60, 3), dtype=np.uint8)
        frame[15:25, 10:46] = (0, 220, 255)

        self.assertTrue(
            region_has_color_component(frame, (0, 0, 60, 40), pattern)
        )
        self.assertEqual(
            find_color_component(frame, (0, 0, 60, 40), pattern).center,
            (28, 20),
        )

        partial = np.zeros_like(frame)
        partial[15:25, 10:34] = (0, 220, 255)
        self.assertFalse(
            region_has_color_component(partial, (0, 0, 60, 40), pattern)
        )


class WhiteRegionTest(TestCase):
    def test_counts_low_saturation_high_value_pixels_in_valid_region(self):
        image = np.zeros((20, 20, 3), dtype=np.uint8)
        image[5:8, 5:8] = (255, 255, 255)

        self.assertTrue(
            region_has_enough_white(
                image,
                (5, 5, 8, 8),
                min_pixels=8,
                max_saturation=50,
                min_value=180,
            )
        )

    def test_rejects_invalid_region(self):
        image = np.zeros((20, 20, 3), dtype=np.uint8)

        self.assertFalse(
            region_has_enough_white(
                image,
                (10, 10, 30, 30),
                min_pixels=1,
                max_saturation=50,
                min_value=180,
            )
        )


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

    def test_region_limits_search_and_returns_absolute_coordinates(self):
        screenshot = np.zeros((100, 120), dtype=np.uint8)
        screenshot[10:40, 10:40] = self.template
        screenshot[50:80, 70:100] = self.template

        x, y, score = find_template(
            screenshot,
            self.template,
            "test.png",
            scales=(1.0,),
            region=(60, 40, 110, 90),
        )

        self.assertEqual((x, y), (85, 65))
        self.assertAlmostEqual(score, 1.0, places=5)

    def test_rejects_region_outside_screenshot(self):
        screenshot = np.zeros((100, 120), dtype=np.uint8)

        with self.assertRaisesRegex(ValueError, "outside screenshot"):
            find_template(
                screenshot,
                self.template,
                "test.png",
                region=(0, 0, 121, 100),
            )

    def test_region_helper_filters_below_threshold_match(self):
        screenshot = np.zeros((100, 120), dtype=np.uint8)

        match = find_template_in_region(
            screenshot,
            self.template,
            "test.png",
            (0, 0, 120, 100),
            threshold=0.99,
            scales=(1.0,),
        )

        self.assertIsNone(match)

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
