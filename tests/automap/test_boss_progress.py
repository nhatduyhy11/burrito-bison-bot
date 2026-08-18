import sys
from pathlib import Path
from unittest import TestCase

import cv2
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TOOLS_DIR = PROJECT_ROOT / "tools"
CAPTURES_DIR = (
    PROJECT_ROOT / "tests" / "fixtures" / "hauntedroom-captures"
)
sys.path.insert(0, str(TOOLS_DIR))

from hauntedroom.flows.automap_support.vision.boss_progress import (
    boss_progress_is_full,
    find_boss_progress_anchor,
    progress_end_region_from_anchor,
)


class BossProgressTest(TestCase):
    def _load_capture(self, name: str):
        frame = cv2.imread(str(CAPTURES_DIR / "boss_screen" / name))
        self.assertIsNotNone(frame)
        return frame

    def test_full_progress_is_detected_from_standard_icon_position(self):
        frame = self._load_capture("boss_full_bar.png")

        anchor = find_boss_progress_anchor(frame)

        self.assertIsNotNone(anchor)
        self.assertEqual((anchor.x, anchor.y), (410, 58))
        self.assertEqual(
            progress_end_region_from_anchor(anchor),
            (400, 61, 409, 72),
        )
        self.assertTrue(boss_progress_is_full(frame))

    def test_full_progress_tracks_shifted_icon_position(self):
        frame = self._load_capture("final_boss_miss.png")

        anchor = find_boss_progress_anchor(frame)

        self.assertIsNotNone(anchor)
        self.assertEqual((anchor.x, anchor.y), (408, 56))
        self.assertEqual(
            progress_end_region_from_anchor(anchor),
            (398, 59, 407, 70),
        )
        self.assertTrue(boss_progress_is_full(frame))

    def test_mini_boss_progress_endpoint_is_not_yellow(self):
        frame = self._load_capture("mini_boss_bar.png")

        self.assertFalse(boss_progress_is_full(frame))

    def test_missing_boss_icon_does_not_fall_back_to_fixed_coordinates(self):
        frame = np.zeros((720, 640, 3), dtype=np.uint8)

        self.assertIsNone(find_boss_progress_anchor(frame))
        self.assertFalse(boss_progress_is_full(frame))

    def test_approaching_progress_endpoint_is_not_yellow(self):
        approaching = cv2.imread(
            str(TOOLS_DIR / "rooms" / "boss" / "boss_approaching.png")
        )
        self.assertIsNotNone(approaching)

        # boss_approaching.png is the global (378, 46)-(430, 89) crop.
        anchor = find_boss_progress_anchor(
            approaching,
            region=(17, 0, 52, 43),
        )

        self.assertIsNotNone(anchor)
        endpoint = progress_end_region_from_anchor(anchor)
        self.assertEqual(endpoint, (22, 15, 31, 26))
        self.assertFalse(boss_progress_is_full(approaching, region=endpoint))
