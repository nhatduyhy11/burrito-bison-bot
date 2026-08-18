import sys
from pathlib import Path
from unittest import TestCase

import cv2

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TOOLS_DIR = PROJECT_ROOT / "tools"
CAPTURES_DIR = PROJECT_ROOT / "tests" / "fixtures" / "hauntedroom-captures"
sys.path.insert(0, str(TOOLS_DIR))

from hauntedroom.flows.automap_support.boss_action import PET_ACTIVE_TEMPLATE_PATH
from hauntedroom.flows.automap_support.vision.boss_controls import (
    boss_spell_is_ready,
    find_active_pet_summon,
    find_ready_boss_pet,
)


class BossControlsTest(TestCase):
    def _load_boss_capture(self, name: str):
        frame = cv2.imread(str(CAPTURES_DIR / "boss_screen" / name))
        self.assertIsNotNone(frame)
        return frame

    def test_ready_detectors_accept_supplied_live_capture(self):
        frame = self._load_boss_capture("pet-spell-ready.png")

        self.assertIsNotNone(find_ready_boss_pet(frame))
        self.assertTrue(boss_spell_is_ready(frame))

    def test_pet_ready_glow_accepts_different_pet_art(self):
        frame = self._load_boss_capture("pet_alt.png")

        self.assertIsNotNone(find_ready_boss_pet(frame))

    def test_pet_ready_glow_rejects_partial_width_bar(self):
        frame = self._load_boss_capture("test_boss_detect.png")

        self.assertIsNone(find_ready_boss_pet(frame))

    def test_pet_active_template_matches_open_menu_fixture(self):
        frame = self._load_boss_capture("pet_menu_open.png")
        reference = cv2.imread(str(PET_ACTIVE_TEMPLATE_PATH))
        self.assertIsNotNone(reference)

        match = find_active_pet_summon(
            frame,
            reference,
            PET_ACTIVE_TEMPLATE_PATH.name,
        )

        self.assertIsNotNone(match)
        x, y, score = match
        self.assertEqual((x, y), (463, 455))
        self.assertGreaterEqual(score, 0.99)
