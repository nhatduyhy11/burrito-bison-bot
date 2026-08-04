import asyncio
import sys
from pathlib import Path
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, Mock, call, patch

import cv2
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TOOLS_DIR = PROJECT_ROOT / "tools"
HERO_SELECT_FIXTURES_DIR = (
    PROJECT_ROOT
    / "tests"
    / "fixtures"
    / "hauntedroom-captures"
    / "hero_select"
)
sys.path.insert(0, str(TOOLS_DIR))

from hauntedroom.flows.automap import (
    AutomapConfig,
    AutomapFlow,
    HERO_FALLBACK_SCREENSHOT_DIR,
    HERO_LEVELUP_OPEN_CLICK,
    HERO_LEVELUP_OPTION_SETTLE_MS,
    HERO_LEVELUP_SELECTION_SETTLE_MS,
)
from hauntedroom.flows.automap_support.detectors import PROTECT_AVAILABLE_REGION
from hauntedroom.flows.automap_support.hero_levelup import (
    HERO_ASCEND_TEMPLATE_NAME,
    HERO_LEVELUP_SEARCH_TOP,
    HERO_LEVELUP_TEMPLATE_PATHS,
    HeroLevelupMatcher,
    find_hero_ascend_options,
    find_hero_option_centers,
)


class HeroSelectTest(IsolatedAsyncioTestCase):
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

    @patch("hauntedroom.flows.automap.capture_page_bgr", new_callable=AsyncMock)
    async def test_hero_levelup_uses_priority_2_hanuman_from_lower_region(
        self,
        capture_page_bgr,
    ):
        popup = cv2.imread(
            str(HERO_SELECT_FIXTURES_DIR / "3_option_hanu_xlubu.png")
        )
        capture_page_bgr.return_value = popup
        initial_frame = self.make_protect_available(np.zeros_like(popup))
        flow = AutomapFlow(self.page, asyncio.Event(), AutomapConfig())

        handled = await flow.hero_levelup(
            initial_frame,
            cv2.cvtColor(initial_frame, cv2.COLOR_BGR2GRAY),
        )

        self.assertTrue(handled)
        self.assertEqual(
            self.page.mouse.click.await_args_list,
            [call(*HERO_LEVELUP_OPEN_CLICK), call(347, 597)],
        )
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
                "99_mage_king.png",
            ],
        )
        self.assertEqual(
            self.page.wait_for_timeout.await_args_list,
            [
                call(HERO_LEVELUP_OPTION_SETTLE_MS),
                call(HERO_LEVELUP_SELECTION_SETTLE_MS),
            ],
        )

    @patch("hauntedroom.flows.automap.save_screenshot", new_callable=AsyncMock)
    async def test_hero_levelup_does_not_fallback_before_opening_picker(
        self,
        save_screenshot,
    ):
        battle_frame = np.zeros((720, 640, 3), dtype=np.uint8)
        battle_frame[610:655, 120:520] = (80, 20, 60)
        self.assertIsNotNone(HeroLevelupMatcher().find_choice(battle_frame))
        flow = AutomapFlow(self.page, asyncio.Event(), AutomapConfig())

        handled = await flow.hero_levelup(
            battle_frame,
            cv2.cvtColor(battle_frame, cv2.COLOR_BGR2GRAY),
        )

        self.assertFalse(handled)
        save_screenshot.assert_not_awaited()
        self.page.mouse.click.assert_not_awaited()
        self.page.wait_for_timeout.assert_not_awaited()

    def test_hero_ascend_pattern_always_uses_priority_zero(self):
        popup = cv2.imread(
            str(HERO_SELECT_FIXTURES_DIR / "hero_ascend_option.png")
        )

        choice = HeroLevelupMatcher().find_choice(popup)

        self.assertIsNotNone(choice)
        self.assertEqual(choice.template_name, HERO_ASCEND_TEMPLATE_NAME)
        self.assertEqual(choice.priority, 0.0)
        self.assertEqual((choice.x, choice.y), (194, 632))

    def test_hero_ascend_crop_matches_both_new_options(self):
        popup = cv2.imread(
            str(
                PROJECT_ROOT
                / "tests"
                / "fixtures"
                / "hauntedroom-captures"
                / "ascend_2_option.png"
            )
        )
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
            cv2.cvtColor(popup, cv2.COLOR_BGR2GRAY),
            template,
        )

        self.assertEqual(
            [(x, y) for x, y, _score in options],
            [(320, 632), (447, 632)],
        )
        self.assertGreaterEqual(min(score for _x, _y, score in options), 0.97)

        choice = HeroLevelupMatcher().find_choice(popup)
        self.assertEqual(choice.template_name, HERO_ASCEND_TEMPLATE_NAME)
        self.assertEqual((choice.x, choice.y), (320, 632))

    @patch("hauntedroom.flows.automap.capture_page_bgr", new_callable=AsyncMock)
    async def test_hero_levelup_waits_for_flash_to_settle_before_first_capture(
        self,
        capture_page_bgr,
    ):
        popup = cv2.imread(
            str(HERO_SELECT_FIXTURES_DIR / "test-vps-lubu.png")
        )

        async def capture_after_settle(_page):
            self.assertEqual(
                self.page.wait_for_timeout.await_args_list,
                [call(HERO_LEVELUP_OPTION_SETTLE_MS)],
            )
            return popup

        capture_page_bgr.side_effect = capture_after_settle
        initial_frame = self.make_protect_available(np.zeros_like(popup))
        flow = AutomapFlow(self.page, asyncio.Event(), AutomapConfig())

        handled = await flow.hero_levelup(
            initial_frame,
            cv2.cvtColor(initial_frame, cv2.COLOR_BGR2GRAY),
        )

        self.assertTrue(handled)
        self.assertEqual(
            self.page.mouse.click.await_args_list,
            [call(*HERO_LEVELUP_OPEN_CLICK), call(192, 597)],
        )
        self.assertEqual(
            self.page.wait_for_timeout.await_args_list,
            [
                call(HERO_LEVELUP_OPTION_SETTLE_MS),
                call(HERO_LEVELUP_SELECTION_SETTLE_MS),
            ],
        )
        capture_page_bgr.assert_awaited_once_with(self.page)

    def test_hero_levelup_priority_1_dark_lubu_wins(self):
        popup = cv2.imread(
            str(HERO_SELECT_FIXTURES_DIR / "3_option_2lubu.png")
        )

        choice = HeroLevelupMatcher().find_choice(popup)

        self.assertIsNotNone(choice)
        self.assertEqual(choice.template_name, "01_dark_lubu.png")
        self.assertEqual((choice.x, choice.y), (473, 597))

    def test_hero_levelup_name_only_dark_lubu_beats_hanuman(self):
        popup = cv2.imread(
            str(HERO_SELECT_FIXTURES_DIR / "lubu and hanu.png")
        )

        choice = HeroLevelupMatcher().find_choice(popup)

        self.assertIsNotNone(choice)
        self.assertEqual(choice.template_name, "01_dark_lubu.png")
        self.assertEqual(choice.priority, 1.0)
        self.assertEqual((choice.x, choice.y), (447, 597))

    def test_hero_levelup_new_mage_king_overrides_priorities_1_and_2(self):
        popup = cv2.imread(
            str(HERO_SELECT_FIXTURES_DIR / "start_with_vps.png")
        )

        choice = HeroLevelupMatcher().find_choice(popup)

        self.assertIsNotNone(choice)
        self.assertEqual(choice.template_name, "00_mage_king.png")
        self.assertEqual(choice.priority, 0.0)
        self.assertEqual((choice.x, choice.y), (192, 597))

    def test_hero_levelup_vps_lubu_fixture_selects_mage_king(self):
        popup = cv2.imread(
            str(HERO_SELECT_FIXTURES_DIR / "test-vps-lubu.png")
        )

        choice = HeroLevelupMatcher().find_choice(popup)

        self.assertIsNotNone(choice)
        self.assertEqual(choice.template_name, "00_mage_king.png")
        self.assertEqual(choice.priority, 0.0)
        self.assertEqual((choice.x, choice.y), (192, 597))

    @patch(
        "hauntedroom.flows.automap_support.hero_levelup.load_template",
        return_value=np.zeros((2, 2), dtype=np.uint8),
    )
    @patch(
        "hauntedroom.flows.automap_support.hero_levelup.find_template",
        side_effect=[(0, 0, 0.1), (252, 137, 0.95)],
    )
    def test_hero_levelup_priority_99_is_excluded_from_fallback(
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

    def test_hero_levelup_fallback_finds_two_visible_options(self):
        popup = cv2.imread(
            str(HERO_SELECT_FIXTURES_DIR / "only_2_option.png")
        )

        choice = HeroLevelupMatcher().find_choice(popup)

        self.assertIsNotNone(choice)
        self.assertFalse(choice.is_prioritized)
        self.assertEqual((choice.x, choice.y), (252, 632))
        self.assertEqual(
            find_hero_option_centers(popup),
            [(252, 632), (387, 632)],
        )

    def test_hero_levelup_fallback_finds_only_visible_option(self):
        popup = cv2.imread(
            str(HERO_SELECT_FIXTURES_DIR / "only_1_option.png")
        )

        choice = HeroLevelupMatcher().find_choice(popup)

        self.assertIsNotNone(choice)
        self.assertFalse(choice.is_prioritized)
        self.assertEqual((choice.x, choice.y), (319, 632))
        self.assertEqual(find_hero_option_centers(popup), [(319, 632)])

    @patch("hauntedroom.flows.automap.capture_page_bgr", new_callable=AsyncMock)
    @patch("hauntedroom.flows.automap.save_screenshot", new_callable=AsyncMock)
    async def test_hero_levelup_fallback_saves_screenshot_before_click(
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
        save_screenshot.assert_awaited_once_with(
            self.page,
            "no-prioritized-hero-option",
            HERO_FALLBACK_SCREENSHOT_DIR,
            "Hero fallback",
        )
        self.assertEqual(
            self.page.mouse.click.await_args_list,
            [call(*HERO_LEVELUP_OPEN_CLICK), call(319, 632)],
        )
