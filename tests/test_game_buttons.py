import sys
from pathlib import Path
from unittest import TestCase

import numpy as np


TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS_DIR))

from hauntedroom.vision.buttons import (
    ButtonGeometry,
    find_colored_button,
    find_red_yellow_button_pair,
)


class GameButtonVisionTest(TestCase):
    def setUp(self):
        self.geometry = ButtonGeometry(
            min_area=150,
            min_width=15,
            max_width=25,
            min_height=8,
            max_height=12,
            min_fill_ratio=0.8,
        )

    def test_finds_yellow_button_center(self):
        frame = np.zeros((40, 60, 3), dtype=np.uint8)
        frame[15:25, 10:30] = (0, 200, 255)

        button = find_colored_button(
            frame,
            (0, 0, 60, 40),
            "yellow",
            self.geometry,
        )

        self.assertIsNotNone(button)
        self.assertEqual(button.center, (20, 20))

    def test_red_palette_supports_both_hue_ends(self):
        for bgr in ((0, 0, 220), (50, 0, 220)):
            with self.subTest(bgr=bgr):
                frame = np.zeros((40, 60, 3), dtype=np.uint8)
                frame[15:25, 10:30] = bgr

                button = find_colored_button(
                    frame,
                    (0, 0, 60, 40),
                    "red",
                    self.geometry,
                )

                self.assertIsNotNone(button)
                self.assertEqual(button.center, (20, 20))

    def test_rejects_component_outside_button_geometry(self):
        frame = np.zeros((40, 60, 3), dtype=np.uint8)
        frame[15:20, 10:20] = (0, 200, 255)

        self.assertIsNone(
            find_colored_button(
                frame,
                (0, 0, 60, 40),
                "yellow",
                self.geometry,
            )
        )

    def test_finds_adjacent_red_yellow_popup_pair(self):
        frame = np.zeros((50, 100, 3), dtype=np.uint8)
        frame[15:25, 10:30] = (0, 0, 220)
        frame[15:25, 50:70] = (0, 200, 255)

        pair = find_red_yellow_button_pair(
            frame,
            (0, 0, 40, 50),
            (40, 0, 100, 50),
            self.geometry,
            self.geometry,
            min_gap=15,
            max_gap=25,
        )

        self.assertIsNotNone(pair)
        self.assertEqual(pair.red.center, (20, 20))
        self.assertEqual(pair.yellow.center, (60, 20))
