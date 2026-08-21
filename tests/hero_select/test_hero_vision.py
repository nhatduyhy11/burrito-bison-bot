import unittest

import cv2

from tests.hero_select.hero_test_helpers import (
    CAPTURES_DIR,
    TOOLS_DIR,
    WRONG_FALLBACK_FIXTURES_DIR,
    load_hero_fixture,
)
from hauntedroom.flows.automap_support.vision.hero_levelup import (
    HERO_ASCEND_TEMPLATE_NAME,
    HERO_LEVELUP_SEARCH_TOP,
    HERO_LEVELUP_TEMPLATE_PATHS,
    find_hero_ascend_options,
    find_hero_option_centers,
    hero_option_color,
    hero_option_is_purple,
    load_hero_levelup_templates,
)


class HeroVisionTest(unittest.TestCase):
    def test_template_catalog_and_search_region_cover_current_heroes(self):
        self.assertEqual(HERO_LEVELUP_SEARCH_TOP, 460)
        self.assertEqual(
            [path.name for path in HERO_LEVELUP_TEMPLATE_PATHS],
            [
                "00_hero_ascend.png",
                "00_mage_king.png",
                "01_dark_lubu.png",
                "02_hanuman.png",
                "03_soul_spear.png",
                "04_thunder_trident.png",
                "09_pinocchio.png",
                "10_prayer_box.png",
                "11_death.png",
                "11_underworld.png",
                "12_soul_reaper.png",
                "99_mage_king.png",
            ],
        )
        self.assertEqual(
            set(load_hero_levelup_templates()),
            set(HERO_LEVELUP_TEMPLATE_PATHS),
        )

    def test_finds_two_visible_options(self):
        popup = load_hero_fixture("only_2_option.png")
        self.assertEqual(find_hero_option_centers(popup), [(252, 632), (387, 632)])

    def test_finds_only_visible_option(self):
        popup = load_hero_fixture("only_1_option.png")
        self.assertEqual(find_hero_option_centers(popup), [(319, 632)])

    def test_detects_yellow_and_purple_cards(self):
        popup = load_hero_fixture("3 lvup option.png")
        centers = find_hero_option_centers(popup)

        self.assertEqual(centers, [(193, 632), (319, 632), (446, 632)])
        self.assertEqual(
            [hero_option_color(popup, center) for center in centers],
            ["purple", "purple", "yellow"],
        )

    def test_detects_yellow_between_red_cards(self):
        popup = load_hero_fixture("fallback_yellow.png")
        centers = find_hero_option_centers(popup)

        self.assertEqual(centers, [(193, 632), (319, 632), (446, 632)])
        self.assertEqual(
            [hero_option_color(popup, center) for center in centers],
            ["red", "yellow", "red"],
        )

    def test_bridges_narrow_gap_and_finds_purple(self):
        popup = cv2.imread(str(WRONG_FALLBACK_FIXTURES_DIR / "wrong_fallback.png"))
        centers = find_hero_option_centers(popup)

        self.assertEqual(centers, [(193, 632), (319, 632), (446, 632)])
        self.assertTrue(hero_option_is_purple(popup, centers[0]))

    def test_all_wrong_captures_now_find_a_purple_option(self):
        fixture_paths = sorted(WRONG_FALLBACK_FIXTURES_DIR.glob("*.png"))

        self.assertGreater(len(fixture_paths), 1)
        for fixture_path in fixture_paths:
            with self.subTest(fixture=fixture_path.name):
                popup = cv2.imread(str(fixture_path))
                centers = find_hero_option_centers(popup)
                self.assertEqual(len(centers), 3)
                self.assertTrue(
                    any(hero_option_is_purple(popup, center) for center in centers)
                )

    def test_hero_ascend_crop_matches_both_new_options(self):
        popup = cv2.imread(str(CAPTURES_DIR / "ascend_2_option.png"))
        template = cv2.imread(
            str(
                TOOLS_DIR
                / "rooms"
                / "automap"
                / "hero_levelup"
                / HERO_ASCEND_TEMPLATE_NAME
            ),
            cv2.IMREAD_GRAYSCALE,
        )

        options = find_hero_ascend_options(
            cv2.cvtColor(popup, cv2.COLOR_BGR2GRAY), template
        )

        self.assertEqual(
            [(x, y) for x, y, _score in options], [(320, 632), (447, 632)]
        )
        self.assertGreaterEqual(min(score for _x, _y, score in options), 0.97)
