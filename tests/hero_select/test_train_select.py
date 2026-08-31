import sys
from pathlib import Path
from unittest import TestCase

import cv2


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "tools"))
FIXTURES = PROJECT_ROOT / "tests" / "fixtures" / "train_select"
TRAIN_FLOW_FIXTURES = PROJECT_ROOT / "tests" / "fixtures" / "train_flow"

from hauntedroom.flows.automap_support.train_select import (
    TRAIN_CONFIRM_CLICK,
    TrainHeroMatcher,
)
from hauntedroom.flows.automap_support.vision.train import (
    TRAIN_TEMPLATE_SCALE,
    find_train_cards,
)


class TrainSelectTest(TestCase):
    def setUp(self):
        self.matcher = TrainHeroMatcher()

    def load(self, name):
        image = cv2.imread(str(FIXTURES / name))
        self.assertIsNotNone(image)
        return image

    def test_uses_one_fixed_downscale_for_copied_priority_templates(self):
        self.assertEqual(TRAIN_TEMPLATE_SCALE, 0.8)

    def test_priority_selects_soul_spear_before_purple_fallback(self):
        choice = self.matcher.find_choice(self.load("select_2.png"))

        self.assertIsNotNone(choice)
        self.assertEqual(choice.template_name, "03_soul_spear.png")
        self.assertEqual((choice.x, choice.y), (369, 566))
        self.assertGreaterEqual(choice.score, 0.65)

    def test_one_selected_card_is_counted_from_one_yellow_corner(self):
        image = self.load("1_select_left.png")
        cards = find_train_cards(image)

        self.assertEqual([card.index for card in cards if card.is_selected], [1])
        choice = self.matcher.find_choice(image)
        self.assertEqual((choice.x, choice.y), (172, 566))
        self.assertFalse(choice.confirm)

    def test_two_selected_cards_confirm_without_tracking_grayout(self):
        choice = self.matcher.find_choice(self.load("2_selected.png"))

        self.assertIsNotNone(choice)
        self.assertTrue(choice.confirm)
        self.assertEqual((choice.x, choice.y), TRAIN_CONFIRM_CLICK)

    def test_lubu_priority_then_leftmost_purple_fallback(self):
        choice = self.matcher.find_choice(self.load("lub_and_purple.png"))
        self.assertEqual(choice.template_name, "01_dark_lubu.png")
        self.assertEqual((choice.x, choice.y), (369, 566))

        selected_choice = self.matcher.find_choice(
            self.load("lubu_and_purple_selected.png")
        )
        self.assertTrue(selected_choice.confirm)

    def test_non_picker_frame_is_rejected(self):
        frame = cv2.imread(str(TRAIN_FLOW_FIXTURES / "train_available.png"))
        self.assertIsNotNone(frame)

        self.assertEqual(find_train_cards(frame), [])
        self.assertIsNone(self.matcher.find_choice(frame))

    def test_red_card_fallback_when_no_purple_available(self):
        choice = self.matcher.find_choice(self.load("train_3red.png"))
        self.assertIsNotNone(choice)
        self.assertEqual((choice.x, choice.y), (271, 566))
        self.assertIsNone(choice.template_name)
