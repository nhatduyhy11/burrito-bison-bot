import sys
from pathlib import Path
from unittest import TestCase

import cv2


PROJECT_ROOT = Path(__file__).resolve().parents[2]
TOOLS_DIR = PROJECT_ROOT / "tools"
CAPTURES_DIR = PROJECT_ROOT / "tests" / "fixtures" / "hauntedroom-captures"
GEAR_FIXTURES_DIR = CAPTURES_DIR / "gear_placement"
sys.path.insert(0, str(TOOLS_DIR))

from hauntedroom.flows.automap_support.vision.gear import (
    GEAR_MENU_STRIPE_REGION,
    find_gear_button,
    find_gear_drop_position,
    gear_menu_is_open,
)


class GearVisionTest(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.gear_open = cv2.imread(str(GEAR_FIXTURES_DIR / "gear_open.png"))
        cls.gear_place = cv2.imread(str(GEAR_FIXTURES_DIR / "gear_place.png"))
        cls.miniboss = cv2.imread(str(CAPTURES_DIR / "miniboss_bar.png"))
        cls.final_miniboss = cv2.imread(
            str(CAPTURES_DIR / "boss_screen" / "mini_boss_last.png")
        )

    def test_detects_available_plus_only_before_placement(self):
        self.assertEqual(find_gear_button(self.gear_open), (162, 661))
        self.assertIsNone(find_gear_button(self.gear_place))

    def test_derives_drop_point_from_door_hp_bar(self):
        self.assertEqual(find_gear_drop_position(self.gear_open), (250, 370))
        self.assertEqual(find_gear_drop_position(self.gear_place), (250, 370))

    def test_detects_menu_open_and_closed_states(self):
        self.assertTrue(gear_menu_is_open(self.gear_open))
        self.assertFalse(gear_menu_is_open(self.gear_place))
        self.assertFalse(gear_menu_is_open(self.miniboss))
        self.assertFalse(gear_menu_is_open(self.final_miniboss))

    def test_menu_requires_left_warning_stripes(self):
        frame_without_stripes = self.gear_open.copy()
        x1, y1, x2, y2 = GEAR_MENU_STRIPE_REGION
        frame_without_stripes[y1:y2, x1:x2] = 0

        self.assertFalse(gear_menu_is_open(frame_without_stripes))
