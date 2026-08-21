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
)
from hauntedroom.flows.automap_support.hero_action import (
    HERO_LEVELUP_OPEN_CLICK,
    choose_hero_levelup_option,
)
from hauntedroom.flows.automap_support.vision.hero_levelup import (
    HERO_LEVELUP_PRICE_REGION,
    HERO_LEVELUP_TEMPLATE_PATHS,
    find_hero_option_centers,
    hero_option_is_purple,
    hero_option_is_yellow,
    load_hero_levelup_templates,
    prepare_hero_levelup_frame,
)
from tests.automap.fakes import fake_automap_templates


def find_choice(frame_bgr, template_paths=None):
    paths = (
        HERO_LEVELUP_TEMPLATE_PATHS
        if template_paths is None
        else template_paths
    )
    return choose_hero_levelup_option(
        paths,
        load_hero_levelup_templates(paths),
        prepare_hero_levelup_frame(frame_bgr),
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
        x1, y1, _, _ = HERO_LEVELUP_PRICE_REGION
        image[y1 : y1 + 2, x1 : x1 + 4] = (255, 255, 255)
        return image

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
        popup = np.zeros((720, 640, 3), dtype=np.uint8)
        popup[610:655, 196:309] = (0, 0, 180)
        popup[610:655, 331:444] = (0, 0, 180)
        template_paths = (
            Path("01_other.png"),
            Path("99_mage_king_upgrade.png"),
        )
        templates = load_hero_levelup_templates(template_paths)

        choice = choose_hero_levelup_option(
            template_paths,
            templates,
            prepare_hero_levelup_frame(popup),
        )

        self.assertIsNotNone(choice)
        self.assertFalse(choice.is_prioritized)
        self.assertEqual((choice.x, choice.y), (387, 632))

    def test_finds_two_visible_options(self):
        popup = cv2.imread(
            str(HERO_SELECT_FIXTURES_DIR / "only_2_option.png")
        )

        choice = find_choice(popup)

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

        choice = find_choice(popup)

        self.assertIsNotNone(choice)
        self.assertFalse(choice.is_prioritized)
        self.assertEqual(choice.fallback_option_count, 1)
        self.assertEqual((choice.x, choice.y), (319, 632))
        self.assertEqual(find_hero_option_centers(popup), [(319, 632)])

    def test_prefers_yellow_over_purple(self):
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
        self.assertTrue(hero_option_is_yellow(popup, centers[2]))

        choice = find_choice(popup, ())

        self.assertIsNotNone(choice)
        self.assertFalse(choice.is_prioritized)
        self.assertEqual(choice.fallback_color, "yellow")
        self.assertEqual(choice.fallback_option_count, 3)
        self.assertEqual((choice.x, choice.y), (446, 632))

    def test_prefers_yellow_over_red(self):
        popup = cv2.imread(
            str(HERO_SELECT_FIXTURES_DIR / "fallback_yellow.png")
        )
        centers = find_hero_option_centers(popup)

        self.assertEqual(
            centers,
            [(193, 632), (319, 632), (446, 632)],
        )
        self.assertFalse(hero_option_is_yellow(popup, centers[0]))
        self.assertTrue(hero_option_is_yellow(popup, centers[1]))
        self.assertFalse(hero_option_is_yellow(popup, centers[2]))

        choice = find_choice(popup)

        self.assertIsNotNone(choice)
        self.assertFalse(choice.is_prioritized)
        self.assertEqual(choice.fallback_color, "yellow")
        self.assertEqual(choice.fallback_option_count, 3)
        self.assertEqual((choice.x, choice.y), (319, 632))

    def test_chooses_purple_even_when_red_is_left(self):
        popup = np.zeros((720, 640, 3), dtype=np.uint8)
        popup[610:655, 196:309] = (0, 0, 180)
        popup[610:655, 331:444] = (180, 0, 120)

        choice = find_choice(popup, ())

        self.assertIsNotNone(choice)
        self.assertFalse(choice.is_prioritized)
        self.assertEqual(choice.fallback_color, "purple")
        self.assertEqual((choice.x, choice.y), (387, 632))

    def test_bridges_narrow_gap_and_finds_purple(self):
        popup = cv2.imread(
            str(WRONG_FALLBACK_FIXTURES_DIR / "wrong_fallback.png")
        )

        centers = find_hero_option_centers(popup)
        choice = find_choice(popup, ())

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
                choice = find_choice(popup)

                self.assertEqual(len(centers), 3)
                self.assertTrue(purple_centers)
                self.assertIsNotNone(choice)
                self.assertFalse(choice.is_prioritized)
                self.assertEqual(choice.fallback_color, "purple")
                self.assertEqual(choice.fallback_option_count, 3)
                self.assertEqual((choice.x, choice.y), purple_centers[0])

    @patch("hauntedroom.flows.automap.capture_page_bgr", new_callable=AsyncMock)
    @patch("hauntedroom.flows.automap.save_fallback_screenshot", new_callable=AsyncMock)
    async def test_no_purple_partial_layout_is_not_captured(
        self,
        save_fallback_screenshot,
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
            AutomapConfig(),
            fake_automap_templates(load_hero_templates=True),
        )

        handled = await flow.hero_levelup(
            initial_frame,
            cv2.cvtColor(initial_frame, cv2.COLOR_BGR2GRAY),
        )

        self.assertTrue(handled)
        save_fallback_screenshot.assert_not_awaited()
        self.assertEqual(
            self.page.mouse.click.await_args_list,
            [call(*HERO_LEVELUP_OPEN_CLICK), call(319, 632)],
        )

    @patch("builtins.print")
    @patch("hauntedroom.flows.automap.capture_page_bgr", new_callable=AsyncMock)
    @patch("hauntedroom.flows.automap.save_fallback_screenshot", new_callable=AsyncMock)
    async def test_no_yellow_or_purple_three_options_saves_fallback_screenshot(
        self,
        save_fallback_screenshot,
        capture_page_bgr,
        print_mock,
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
            fake_automap_templates(),
        )

        handled = await flow.hero_levelup(
            initial_frame,
            cv2.cvtColor(initial_frame, cv2.COLOR_BGR2GRAY),
        )

        self.assertTrue(handled)
        save_fallback_screenshot.assert_awaited_once_with(
            self.page,
            label="hero-fallback-no-priority-no-yellow-or-purple",
        )
        self.assertEqual(
            self.page.mouse.click.await_args_list,
            [call(*HERO_LEVELUP_OPEN_CLICK), call(193, 632)],
        )
        print_mock.assert_any_call(
            "No prioritized hero option matched; falling back to red hero "
            "card at 193,632.",
            flush=True,
        )

    @patch("builtins.print")
    @patch("hauntedroom.flows.automap.capture_page_bgr", new_callable=AsyncMock)
    @patch("hauntedroom.flows.automap.save_fallback_screenshot", new_callable=AsyncMock)
    async def test_yellow_fallback_logs_color_and_clicks_yellow_card(
        self,
        save_fallback_screenshot,
        capture_page_bgr,
        print_mock,
    ):
        popup = cv2.imread(
            str(HERO_SELECT_FIXTURES_DIR / "fallback_yellow.png")
        )
        capture_page_bgr.return_value = popup
        initial_frame = self.make_protect_available(np.zeros_like(popup))
        flow = AutomapFlow(
            self.page,
            asyncio.Event(),
            AutomapConfig(),
            fake_automap_templates(load_hero_templates=True),
        )

        handled = await flow.hero_levelup(
            initial_frame,
            cv2.cvtColor(initial_frame, cv2.COLOR_BGR2GRAY),
        )

        self.assertTrue(handled)
        save_fallback_screenshot.assert_not_awaited()
        print_mock.assert_any_call(
            "No prioritized hero option matched; falling back to yellow "
            "hero card at 319,632.",
            flush=True,
        )
        self.assertEqual(
            self.page.mouse.click.await_args_list,
            [call(*HERO_LEVELUP_OPEN_CLICK), call(319, 632)],
        )

    @patch("hauntedroom.flows.automap.capture_page_bgr", new_callable=AsyncMock)
    @patch("hauntedroom.flows.automap.save_fallback_screenshot", new_callable=AsyncMock)
    async def test_yellow_fallback_with_purple_does_not_save_tracking_screenshot(
        self,
        save_fallback_screenshot,
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
            fake_automap_templates(),
        )

        handled = await flow.hero_levelup(
            initial_frame,
            cv2.cvtColor(initial_frame, cv2.COLOR_BGR2GRAY),
        )

        self.assertTrue(handled)
        save_fallback_screenshot.assert_not_awaited()
        self.assertEqual(
            self.page.mouse.click.await_args_list,
            [call(*HERO_LEVELUP_OPEN_CLICK), call(446, 632)],
        )

    @patch("hauntedroom.flows.automap.capture_page_bgr", new_callable=AsyncMock)
    @patch("hauntedroom.flows.automap.save_fallback_screenshot", new_callable=AsyncMock)
    async def test_hero_fallback_capture_can_be_disabled(
        self,
        save_fallback_screenshot,
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
            AutomapConfig(
                hero_levelup_template_paths=(),
                capture_hero_fallback_screenshots=False,
            ),
            fake_automap_templates(),
        )

        handled = await flow.hero_levelup(
            initial_frame,
            cv2.cvtColor(initial_frame, cv2.COLOR_BGR2GRAY),
        )

        self.assertTrue(handled)
        save_fallback_screenshot.assert_not_awaited()
        self.assertEqual(
            self.page.mouse.click.await_args_list,
            [call(*HERO_LEVELUP_OPEN_CLICK), call(193, 632)],
        )

    @patch("builtins.print")
    @patch("hauntedroom.flows.automap.capture_page_bgr", new_callable=AsyncMock)
    @patch("hauntedroom.flows.automap.save_fallback_screenshot", new_callable=AsyncMock)
    async def test_purple_fallback_does_not_save_tracking_screenshot(
        self,
        save_fallback_screenshot,
        capture_page_bgr,
        print_mock,
    ):
        popup = cv2.imread(
            str(HERO_SELECT_FIXTURES_DIR / "3_option_2lubu.png")
        )
        capture_page_bgr.return_value = popup
        initial_frame = self.make_protect_available(np.zeros_like(popup))
        flow = AutomapFlow(
            self.page,
            asyncio.Event(),
            AutomapConfig(hero_levelup_template_paths=()),
            fake_automap_templates(),
        )

        handled = await flow.hero_levelup(
            initial_frame,
            cv2.cvtColor(initial_frame, cv2.COLOR_BGR2GRAY),
        )

        self.assertTrue(handled)
        save_fallback_screenshot.assert_not_awaited()
        self.assertEqual(
            self.page.mouse.click.await_args_list,
            [call(*HERO_LEVELUP_OPEN_CLICK), call(193, 632)],
        )
        print_mock.assert_any_call(
            "No prioritized hero option matched; falling back to purple "
            "hero card at 193,632.",
            flush=True,
        )

    @patch("hauntedroom.flows.automap.capture_page_bgr", new_callable=AsyncMock)
    @patch("hauntedroom.flows.automap.save_fallback_screenshot", new_callable=AsyncMock)
    async def test_debug_partial_fallback_does_not_save_screenshot(
        self,
        save_fallback_screenshot,
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
            fake_automap_templates(load_hero_templates=True),
        )

        handled = await flow.hero_levelup(
            initial_frame,
            cv2.cvtColor(initial_frame, cv2.COLOR_BGR2GRAY),
        )

        self.assertTrue(handled)
        save_fallback_screenshot.assert_not_awaited()
        self.assertEqual(
            self.page.mouse.click.await_args_list,
            [call(*HERO_LEVELUP_OPEN_CLICK), call(319, 632)],
        )
