import asyncio
import sys
from pathlib import Path
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, Mock, call, patch

import cv2
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TOOLS_DIR = PROJECT_ROOT / "tools"
CAPTURES_DIR = (
    PROJECT_ROOT / "tests" / "fixtures" / "hauntedroom-captures"
)
HERO_SELECT_FIXTURES_DIR = CAPTURES_DIR / "hero_select"
WRONG_FALLBACK_FIXTURES_DIR = CAPTURES_DIR / "wrong_fallback"
sys.path.insert(0, str(TOOLS_DIR))

from hauntedroom.flows.automap import (
    AutomapConfig,
    AutomapFlow,
    HERO_FALLBACK_SCREENSHOT_DIR,
    HERO_LEVELUP_OPEN_CLICK,
)
from hauntedroom.flows.automap_support.detectors import PROTECT_AVAILABLE_REGION
from hauntedroom.flows.automap_support.hero_levelup import (
    HeroLevelupMatcher,
    find_hero_option_centers,
    hero_option_is_purple,
)


class HeroFallbackTest(IsolatedAsyncioTestCase):
    def setUp(self):
        self.page = Mock()
        self.page.evaluate = AsyncMock()
        self.page.wait_for_timeout = AsyncMock()
        self.page.mouse = Mock()
        self.page.mouse.click = AsyncMock()

    @staticmethod
    def make_protect_available(image):
        x1, y1, _, _ = PROTECT_AVAILABLE_REGION
        image[y1 : y1 + 2, x1 : x1 + 4] = (255, 255, 255)
        return image

    @patch(
        "hauntedroom.flows.automap_support.hero_levelup.load_template",
        return_value=np.zeros((2, 2), dtype=np.uint8),
    )
    @patch(
        "hauntedroom.flows.automap_support.hero_levelup.find_template",
        side_effect=[(0, 0, 0.1), (252, 137, 0.95)],
    )
    def test_priority_99_is_excluded_from_fallback(
        self,
        _find_template,
        _load_template,
    ):
        popup = np.zeros((720, 640, 3), dtype=np.uint8)
        popup[610:655, 196:309] = (0, 0, 180)
        popup[610:655, 331:444] = (0, 0, 180)
        matcher = HeroLevelupMatcher(
            (
                Path("01_other.png"),
                Path("99_mage_king_upgrade.png"),
            )
        )

        choice = matcher.find_choice(popup)

        self.assertIsNotNone(choice)
        self.assertFalse(choice.is_prioritized)
        self.assertEqual((choice.x, choice.y), (387, 632))

    def test_finds_two_visible_options(self):
        popup = cv2.imread(
            str(HERO_SELECT_FIXTURES_DIR / "only_2_option.png")
        )

        choice = HeroLevelupMatcher().find_choice(popup)

        self.assertIsNotNone(choice)
        self.assertFalse(choice.is_prioritized)
        self.assertEqual(choice.fallback_option_count, 2)
        self.assertEqual((choice.x, choice.y), (252, 632))
        self.assertEqual(
            find_hero_option_centers(popup),
            [(252, 632), (387, 632)],
        )

    def test_finds_only_visible_option(self):
        popup = cv2.imread(
            str(HERO_SELECT_FIXTURES_DIR / "only_1_option.png")
        )

        choice = HeroLevelupMatcher().find_choice(popup)

        self.assertIsNotNone(choice)
        self.assertFalse(choice.is_prioritized)
        self.assertEqual(choice.fallback_option_count, 1)
        self.assertEqual((choice.x, choice.y), (319, 632))
        self.assertEqual(find_hero_option_centers(popup), [(319, 632)])

    def test_prefers_purple_over_red(self):
        popup = cv2.imread(
            str(HERO_SELECT_FIXTURES_DIR / "3 lvup option.png")
        )
        centers = find_hero_option_centers(popup)

        self.assertEqual(
            centers,
            [(193, 632), (319, 632), (446, 632)],
        )
        self.assertTrue(hero_option_is_purple(popup, centers[0]))
        self.assertTrue(hero_option_is_purple(popup, centers[1]))
        self.assertFalse(hero_option_is_purple(popup, centers[2]))

        choice = HeroLevelupMatcher(()).find_choice(popup)

        self.assertIsNotNone(choice)
        self.assertFalse(choice.is_prioritized)
        self.assertEqual(choice.fallback_color, "purple")
        self.assertEqual(choice.fallback_option_count, 3)
        self.assertEqual((choice.x, choice.y), (193, 632))

    def test_chooses_purple_even_when_red_is_left(self):
        popup = np.zeros((720, 640, 3), dtype=np.uint8)
        popup[610:655, 196:309] = (0, 0, 180)
        popup[610:655, 331:444] = (180, 0, 120)

        choice = HeroLevelupMatcher(()).find_choice(popup)

        self.assertIsNotNone(choice)
        self.assertFalse(choice.is_prioritized)
        self.assertEqual(choice.fallback_color, "purple")
        self.assertEqual((choice.x, choice.y), (387, 632))

    def test_bridges_narrow_gap_and_finds_purple(self):
        popup = cv2.imread(
            str(WRONG_FALLBACK_FIXTURES_DIR / "wrong_fallback.png")
        )

        centers = find_hero_option_centers(popup)
        choice = HeroLevelupMatcher(()).find_choice(popup)

        self.assertEqual(centers, [(193, 632), (319, 632), (446, 632)])
        self.assertTrue(hero_option_is_purple(popup, centers[0]))
        self.assertIsNotNone(choice)
        self.assertEqual(choice.fallback_color, "purple")
        self.assertEqual((choice.x, choice.y), (193, 632))

    def test_all_wrong_captures_now_find_a_purple_option(self):
        fixture_paths = sorted(WRONG_FALLBACK_FIXTURES_DIR.glob("*.png"))

        self.assertGreater(len(fixture_paths), 1)
        for fixture_path in fixture_paths:
            with self.subTest(fixture=fixture_path.name):
                popup = cv2.imread(str(fixture_path))
                centers = find_hero_option_centers(popup)
                purple_centers = [
                    center
                    for center in centers
                    if hero_option_is_purple(popup, center)
                ]
                choice = HeroLevelupMatcher().find_choice(popup)

                self.assertEqual(len(centers), 3)
                self.assertTrue(purple_centers)
                self.assertIsNotNone(choice)
                self.assertFalse(choice.is_prioritized)
                self.assertEqual(choice.fallback_color, "purple")
                self.assertEqual(choice.fallback_option_count, 3)
                self.assertEqual((choice.x, choice.y), purple_centers[0])

    @patch("hauntedroom.flows.automap.capture_page_bgr", new_callable=AsyncMock)
    @patch("hauntedroom.flows.automap.save_screenshot", new_callable=AsyncMock)
    async def test_no_purple_partial_layout_is_not_captured(
        self,
        save_screenshot,
        capture_page_bgr,
    ):
        popup = cv2.imread(
            str(HERO_SELECT_FIXTURES_DIR / "only_1_option.png")
        )
        capture_page_bgr.return_value = popup
        initial_frame = self.make_protect_available(np.zeros_like(popup))
        flow = AutomapFlow(self.page, asyncio.Event(), AutomapConfig())

        handled = await flow.hero_levelup(
            initial_frame,
            cv2.cvtColor(initial_frame, cv2.COLOR_BGR2GRAY),
        )

        self.assertTrue(handled)
        save_screenshot.assert_not_awaited()
        self.assertEqual(
            self.page.mouse.click.await_args_list,
            [call(*HERO_LEVELUP_OPEN_CLICK), call(319, 632)],
        )

    @patch("hauntedroom.flows.automap.capture_page_bgr", new_callable=AsyncMock)
    @patch("hauntedroom.flows.automap.save_screenshot", new_callable=AsyncMock)
    async def test_no_purple_three_options_saves_tracking_screenshot(
        self,
        save_screenshot,
        capture_page_bgr,
    ):
        popup = cv2.imread(
            str(HERO_SELECT_FIXTURES_DIR / "lubu and hanu.png")
        )
        capture_page_bgr.return_value = popup
        initial_frame = self.make_protect_available(np.zeros_like(popup))
        flow = AutomapFlow(
            self.page,
            asyncio.Event(),
            AutomapConfig(hero_levelup_template_paths=()),
        )

        handled = await flow.hero_levelup(
            initial_frame,
            cv2.cvtColor(initial_frame, cv2.COLOR_BGR2GRAY),
        )

        self.assertTrue(handled)
        save_screenshot.assert_awaited_once_with(
            self.page,
            "no-priority-no-purple-hero-option",
            HERO_FALLBACK_SCREENSHOT_DIR,
            "Hero fallback tracking",
        )
        self.assertEqual(
            self.page.mouse.click.await_args_list,
            [call(*HERO_LEVELUP_OPEN_CLICK), call(193, 632)],
        )

    @patch("hauntedroom.flows.automap.capture_page_bgr", new_callable=AsyncMock)
    @patch("hauntedroom.flows.automap.save_screenshot", new_callable=AsyncMock)
    async def test_purple_fallback_does_not_save_tracking_screenshot(
        self,
        save_screenshot,
        capture_page_bgr,
    ):
        popup = cv2.imread(
            str(HERO_SELECT_FIXTURES_DIR / "3 lvup option.png")
        )
        capture_page_bgr.return_value = popup
        initial_frame = self.make_protect_available(np.zeros_like(popup))
        flow = AutomapFlow(
            self.page,
            asyncio.Event(),
            AutomapConfig(hero_levelup_template_paths=()),
        )

        handled = await flow.hero_levelup(
            initial_frame,
            cv2.cvtColor(initial_frame, cv2.COLOR_BGR2GRAY),
        )

        self.assertTrue(handled)
        save_screenshot.assert_not_awaited()
        self.assertEqual(
            self.page.mouse.click.await_args_list,
            [call(*HERO_LEVELUP_OPEN_CLICK), call(193, 632)],
        )

    @patch("hauntedroom.flows.automap.capture_page_bgr", new_callable=AsyncMock)
    @patch("hauntedroom.flows.automap.save_screenshot", new_callable=AsyncMock)
    async def test_debug_partial_fallback_does_not_save_screenshot(
        self,
        save_screenshot,
        capture_page_bgr,
    ):
        popup = cv2.imread(
            str(HERO_SELECT_FIXTURES_DIR / "only_1_option.png")
        )
        capture_page_bgr.return_value = popup
        initial_frame = self.make_protect_available(np.zeros_like(popup))
        flow = AutomapFlow(
            self.page,
            asyncio.Event(),
            AutomapConfig(debug=True),
        )

        handled = await flow.hero_levelup(
            initial_frame,
            cv2.cvtColor(initial_frame, cv2.COLOR_BGR2GRAY),
        )

        self.assertTrue(handled)
        save_screenshot.assert_not_awaited()
        self.assertEqual(
            self.page.mouse.click.await_args_list,
            [call(*HERO_LEVELUP_OPEN_CLICK), call(319, 632)],
        )
