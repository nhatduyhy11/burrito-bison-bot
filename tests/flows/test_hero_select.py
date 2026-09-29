import sys
from pathlib import Path
from unittest import TestCase

import cv2
import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

from hauntedroom.flows.hero_select import find_battle_button


FIXTURES_DIR = PROJECT_ROOT / "tests" / "fixtures"
HEADER_TEMPLATE = cv2.imread(
    str(PROJECT_ROOT / "tools" / "rooms" / "hero_select_battle_banner_top.png"),
    cv2.IMREAD_GRAYSCALE,
)


class HeroSelectBattleVisionTest(TestCase):
    def test_vn_hero_select_screen_finds_yellow_button_without_reading_text(self):
        image = cv2.imread(
            str(
                FIXTURES_DIR
                / "hauntedroom-captures"
                / "hero_select_screen_vn.png"
            )
        )

        button = find_battle_button(image, HEADER_TEMPLATE)

        self.assertIsNotNone(button)
        self.assertEqual(button.center, (319, 689))

    def test_cn_hero_select_screen_finds_yellow_button_without_reading_text(self):
        image = cv2.imread(
            str(
                FIXTURES_DIR
                / "hauntedroom-captures"
                / "cn_server"
                / "hero_select_screen_bell.png"
            )
        )

        button = find_battle_button(image, HEADER_TEMPLATE)

        self.assertIsNotNone(button)
        self.assertEqual(button.center, (319, 689))

    def test_yellow_button_without_top_header_is_rejected(self):
        image = np.zeros((720, 640, 3), dtype=np.uint8)
        image[672:706, 265:374] = (0, 200, 255)

        self.assertIsNone(find_battle_button(image, HEADER_TEMPLATE))

    def test_top_header_without_yellow_button_is_rejected(self):
        image = cv2.imread(
            str(
                FIXTURES_DIR
                / "hauntedroom-captures"
                / "cn_server"
                / "hero_select_screen_bell.png"
            )
        )
        image[650:719, 230:410] = 0

        self.assertIsNone(find_battle_button(image, HEADER_TEMPLATE))
