import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import cv2
import numpy as np

from tests.hero_select.hero_test_helpers import (
    CAPTURES_DIR,
    WRONG_FALLBACK_FIXTURES_DIR,
    find_choice,
    load_hero_fixture,
)
from hauntedroom.flows.automap_support.hero_action import (
    choose_hero_levelup_option,
)
from hauntedroom.flows.automap_support.vision.hero_levelup import (
    HERO_ASCEND_TEMPLATE_NAME,
    HERO_LEVELUP_TEMPLATE_PATHS,
    find_hero_option_centers,
    hero_option_is_purple,
    load_hero_levelup_templates,
    prepare_hero_levelup_frame,
)


class HeroChoicePolicyTest(unittest.TestCase):
    def test_selects_ascend_before_name_priorities(self):
        frame = Mock()
        ascend_path = Path(HERO_ASCEND_TEMPLATE_NAME)
        templates = {ascend_path: Mock()}
        find_ascend = Mock(return_value=[(320, 632, 0.95)])
        find_template = Mock()
        find_options = Mock()

        choice = choose_hero_levelup_option(
            (ascend_path,),
            templates,
            frame,
            find_ascend_fn=find_ascend,
            find_template_fn=find_template,
            find_options_fn=find_options,
        )

        self.assertEqual(choice.template_name, HERO_ASCEND_TEMPLATE_NAME)
        self.assertEqual(choice.priority, 0.0)
        self.assertEqual((choice.x, choice.y), (320, 632))
        find_ascend.assert_called_once_with(frame, templates[ascend_path])
        find_template.assert_not_called()
        find_options.assert_not_called()

    def test_selects_numeric_priority_independent_of_match_order(self):
        frame = Mock()
        priority_1 = Path("01_dark_lubu.png")
        priority_2 = Path("02_hanuman.png")
        templates = {priority_1: Mock(), priority_2: Mock()}
        find_ascend = Mock(return_value=[])
        find_options = Mock()
        find_template = Mock(
            side_effect=lambda _frame, path, _template: {
                priority_1: (193, 597, 0.91),
                priority_2: (446, 597, 0.99),
            }[path]
        )

        choice = choose_hero_levelup_option(
            (priority_2, priority_1),
            templates,
            frame,
            find_ascend_fn=find_ascend,
            find_template_fn=find_template,
            find_options_fn=find_options,
        )

        self.assertEqual(choice.template_name, "01_dark_lubu.png")
        self.assertEqual(choice.priority, 1.0)
        find_ascend.assert_not_called()
        find_template.assert_called_once_with(frame, priority_1, templates[priority_1])
        find_options.assert_not_called()

    @patch(
        "hauntedroom.flows.automap_support.vision.hero_levelup.load_template",
        return_value=np.zeros((2, 2), dtype=np.uint8),
    )
    @patch(
        "hauntedroom.flows.automap_support.vision.hero_levelup.find_template",
        side_effect=[(0, 0, 0.1), (252, 137, 0.95)],
    )
    def test_priority_99_is_excluded_from_fallback(
        self,
        _find_template,
        _load_template,
    ):
        normal_path = Path("01_other.png")
        ignored_path = Path("99_mage_king_upgrade.png")
        template_paths = (normal_path, ignored_path)
        popup = np.zeros((720, 640, 3), dtype=np.uint8)
        popup[610:655, 196:309] = (0, 0, 180)
        popup[610:655, 331:444] = (0, 0, 180)

        choice = choose_hero_levelup_option(
            template_paths,
            load_hero_levelup_templates(template_paths),
            prepare_hero_levelup_frame(popup),
        )

        self.assertIsNotNone(choice)
        self.assertFalse(choice.is_prioritized)
        self.assertEqual((choice.x, choice.y), (387, 632))

    def test_fallback_color_order_is_yellow_then_purple_then_red(self):
        cases = [
            (
                [(193, 632, "purple"), (319, 632, "red"), (446, 632, "yellow")],
                "yellow",
                (446, 632),
            ),
            ([(193, 632, "red"), (319, 632, "purple")], "purple", (319, 632)),
            ([(193, 632, "red")], "red", (193, 632)),
        ]

        for options, expected_color, expected_position in cases:
            with self.subTest(options=options):
                choice = choose_hero_levelup_option(
                    (),
                    {},
                    Mock(),
                    find_options_fn=Mock(return_value=options),
                )
                self.assertEqual(choice.fallback_color, expected_color)
                self.assertEqual((choice.x, choice.y), expected_position)
                self.assertEqual(choice.fallback_option_count, len(options))

    def test_real_fallback_fixtures_follow_color_priority(self):
        cases = [
            ("3 lvup option.png", (), "yellow", (446, 632)),
            ("fallback_yellow.png", None, "yellow", (319, 632)),
            ("3_option_2lubu.png", (), "purple", (193, 632)),
        ]

        for fixture, template_paths, expected_color, expected_position in cases:
            with self.subTest(fixture=fixture):
                choice = find_choice(
                    load_hero_fixture(fixture),
                    template_paths,
                )

                self.assertIsNotNone(choice)
                self.assertFalse(choice.is_prioritized)
                self.assertEqual(choice.fallback_color, expected_color)
                self.assertEqual(choice.fallback_option_count, 3)
                self.assertEqual((choice.x, choice.y), expected_position)

    def test_real_detection_chooses_purple_when_red_is_left(self):
        popup = np.zeros((720, 640, 3), dtype=np.uint8)
        popup[610:655, 196:309] = (0, 0, 180)
        popup[610:655, 331:444] = (180, 0, 120)

        choice = find_choice(popup, ())

        self.assertIsNotNone(choice)
        self.assertFalse(choice.is_prioritized)
        self.assertEqual(choice.fallback_color, "purple")
        self.assertEqual((choice.x, choice.y), (387, 632))

    def test_ascend_fixture_uses_leftmost_option_at_priority_zero(self):
        choice = find_choice(load_hero_fixture("hero_ascend_option.png"))

        self.assertEqual(choice.template_name, HERO_ASCEND_TEMPLATE_NAME)
        self.assertEqual(choice.priority, 0.0)
        self.assertEqual((choice.x, choice.y), (194, 632))

    def test_two_ascend_options_choose_leftmost(self):
        popup = cv2.imread(str(CAPTURES_DIR / "ascend_2_option.png"))

        choice = find_choice(popup)

        self.assertEqual(choice.template_name, HERO_ASCEND_TEMPLATE_NAME)
        self.assertEqual(choice.priority, 0.0)
        self.assertEqual((choice.x, choice.y), (320, 632))

    def test_partial_layout_fixtures_produce_expected_fallback_choices(self):
        cases = [
            ("only_2_option.png", 2, (252, 632)),
            ("only_1_option.png", 1, (319, 632)),
        ]

        for fixture, option_count, position in cases:
            with self.subTest(fixture=fixture):
                choice = find_choice(load_hero_fixture(fixture))
                self.assertFalse(choice.is_prioritized)
                self.assertEqual(choice.fallback_option_count, option_count)
                self.assertEqual((choice.x, choice.y), position)

    def test_wrong_fallback_fixtures_choose_first_detected_purple(self):
        fixture_paths = sorted(WRONG_FALLBACK_FIXTURES_DIR.glob("*.png"))

        self.assertGreater(len(fixture_paths), 1)
        for fixture_path in fixture_paths:
            with self.subTest(fixture=fixture_path.name):
                popup = cv2.imread(str(fixture_path))
                purple_centers = [
                    center
                    for center in find_hero_option_centers(popup)
                    if hero_option_is_purple(popup, center)
                ]
                choice = find_choice(popup)
                self.assertFalse(choice.is_prioritized)
                self.assertEqual(choice.fallback_color, "purple")
                self.assertEqual(choice.fallback_option_count, 3)
                self.assertEqual((choice.x, choice.y), purple_centers[0])

    def test_lubu_near_threshold_captures_choose_lubu(self):
        fixture_dir = CAPTURES_DIR / "retest"

        for index in range(1, 5):
            fixture_path = fixture_dir / f"lubu_miss_{index}.png"
            with self.subTest(fixture=fixture_path.name):
                popup = cv2.imread(str(fixture_path))
                self.assertIsNotNone(popup)

                choice = find_choice(popup)

                self.assertEqual(choice.template_name, "01_dark_lubu.png")
                self.assertEqual(choice.priority, 1.0)
                self.assertEqual((choice.x, choice.y), (331, 597))
                self.assertGreaterEqual(choice.score, 0.69)
                self.assertLess(choice.score, 0.70)

    def test_current_fixture_choices_follow_template_priorities(self):
        cases = [
            ("3_option_hanu_xlubu.png", None, "02_hanuman.png", 2.0, (347, 597)),
            ("3_option_2lubu.png", None, "01_dark_lubu.png", 1.0, (484, 597)),
            ("lubu and hanu.png", None, "01_dark_lubu.png", 1.0, (458, 597)),
            ("start_with_vps.png", None, "00_mage_king.png", 0.0, (192, 597)),
            ("test-vps-lubu.png", None, "00_mage_king.png", 0.0, (192, 597)),
            ("prio_9start.png", None, "11_underworld.png", 11.0, (193, 597)),
            ("prio_910.png", None, "11_death.png", 11.0, (447, 597)),
            ("prio_1112.png", None, "09_pinocchio.png", 9.0, (218, 597)),
            (
                "prio_910.png",
                {"12_soul_reaper.png"},
                "12_soul_reaper.png",
                12.0,
                (319, 598),
            ),
            (
                "prio_1112.png",
                {"09_pinocchio.png", "10_prayer_box.png"},
                "09_pinocchio.png",
                9.0,
                (218, 597),
            ),
            (
                "prio_1112.png",
                {"10_prayer_box.png"},
                "10_prayer_box.png",
                10.0,
                (446, 598),
            ),
        ]

        for fixture, names, template_name, priority, position in cases:
            with self.subTest(fixture=fixture, templates=names):
                paths = (
                    None
                    if names is None
                    else tuple(
                        path for path in HERO_LEVELUP_TEMPLATE_PATHS if path.name in names
                    )
                )
                choice = find_choice(load_hero_fixture(fixture), paths)
                self.assertEqual(choice.template_name, template_name)
                self.assertEqual(choice.priority, priority)
                self.assertEqual((choice.x, choice.y), position)
