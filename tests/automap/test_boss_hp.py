import sys
from pathlib import Path
from unittest import TestCase

import cv2
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TOOLS_DIR = PROJECT_ROOT / "tools"
CAPTURES_DIR = PROJECT_ROOT / "tests" / "fixtures" / "hauntedroom-captures"
sys.path.insert(0, str(TOOLS_DIR))

from hauntedroom.flows.automap import BOSS_HP_TEMPLATE_PATH
from hauntedroom.flows.automap_support.vision.boss_hp import (
    BOSS_HP_SEARCH_REGION,
    find_boss_health_bar,
)


class BossHealthBarTest(TestCase):
    def setUp(self):
        self.template = cv2.imread(
            str(BOSS_HP_TEMPLATE_PATH),
            cv2.IMREAD_GRAYSCALE,
        )
        self.assertIsNotNone(self.template)

    def _load_boss_capture(self, name: str):
        frame = cv2.imread(str(CAPTURES_DIR / "boss_screen" / name))
        self.assertIsNotNone(frame)
        return frame

    def test_finds_boss_sized_hp_bar_in_upper_region_without_color(self):
        frame = np.full((720, 640), 80, dtype=np.uint8)
        x, y = 220, 280
        height, width = self.template.shape
        # Inversion changes every source intensity while preserving the narrow
        # vertical stripe geometry used by the detector.
        frame[y : y + height, x : x + width] = 255 - self.template

        match = find_boss_health_bar(frame, self.template)

        self.assertIsNotNone(match)
        match_x, match_y, score = match
        self.assertEqual((match_x, match_y), (x + width // 2, y + height // 2))
        self.assertGreaterEqual(score, 0.85)

    def test_rejects_short_hp_signature(self):
        frame = np.full((720, 640), 80, dtype=np.uint8)
        mini = cv2.resize(
            self.template,
            (40, self.template.shape[0]),
            interpolation=cv2.INTER_AREA,
        )
        frame[280 : 280 + mini.shape[0], 220 : 220 + mini.shape[1]] = mini

        self.assertIsNone(find_boss_health_bar(frame, self.template))

    def test_rejects_partial_bar_even_when_whole_template_score_is_high(self):
        frame = np.full((720, 640), 80, dtype=np.uint8)
        x, y = 220, 280
        # The old whole-template-only check scored this 45/61-pixel prefix at
        # about 0.71, above the 0.65 acceptance threshold.
        visible_width = 45
        frame[
            y : y + self.template.shape[0],
            x : x + visible_width,
        ] = 255 - self.template[:, :visible_width]

        self.assertIsNone(find_boss_health_bar(frame, self.template))

    def test_accepts_live_full_boss_bar_when_region_contains_it(self):
        frame = cv2.cvtColor(
            self._load_boss_capture("boss_full_bar.png"),
            cv2.COLOR_BGR2GRAY,
        )

        match = find_boss_health_bar(frame, self.template)

        self.assertIsNotNone(match)
        self.assertEqual(match[:2], (438, 268))

    def test_accepts_occluded_boss_bar_with_geometry_confirmation(self):
        for fixture_name, expected_position in (
            ("test_boss_detect.png", (290, 307)),
            ("test_boss_2.png", (306, 237)),
        ):
            with self.subTest(fixture_name=fixture_name):
                frame_gray = cv2.cvtColor(
                    self._load_boss_capture(fixture_name),
                    cv2.COLOR_BGR2GRAY,
                )

                match = find_boss_health_bar(frame_gray, self.template)

                self.assertIsNotNone(match)
                self.assertEqual(match[:2], expected_position)

    def test_rejects_live_frame_after_boss_bar_disappears(self):
        frame = cv2.cvtColor(
            self._load_boss_capture("boss_empty_bar.png"),
            cv2.COLOR_BGR2GRAY,
        )

        self.assertIsNone(find_boss_health_bar(frame, self.template))

    def test_rejects_boss_bar_below_upper_search_region(self):
        frame = np.full((720, 640), 80, dtype=np.uint8)
        height, width = self.template.shape
        x = BOSS_HP_SEARCH_REGION[0]
        y = BOSS_HP_SEARCH_REGION[3]
        frame[y : y + height, x : x + width] = self.template

        self.assertIsNone(find_boss_health_bar(frame, self.template))
