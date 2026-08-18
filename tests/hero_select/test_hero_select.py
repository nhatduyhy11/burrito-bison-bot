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
)
from hauntedroom.flows.automap_support.hero_action import (
    HERO_LEVELUP_OPEN_CLICK,
    HERO_LEVELUP_OPTION_SETTLE_MS,
    HERO_LEVELUP_SELECTION_SETTLE_MS,
    choose_hero_levelup_option,
)
from hauntedroom.flows.automap_support.vision.hero_levelup import (
    HERO_LEVELUP_PRICE_REGION,
    HERO_ASCEND_TEMPLATE_NAME,
    HERO_LEVELUP_SEARCH_TOP,
    HERO_LEVELUP_TEMPLATE_PATHS,
    find_hero_ascend_options,
    load_hero_levelup_templates,
    prepare_hero_levelup_frame,
)


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


class HeroSelectTest(IsolatedAsyncioTestCase):
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
                "09_pinocchio.png",
                "10_prayer_box.png",
                "11_death.png",
                "11_underworld.png",
                "12_soul_reaper.png",
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
        self.assertIsNotNone(find_choice(battle_frame))
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

        choice = find_choice(popup)

        self.assertIsNotNone(choice)
        self.assertEqual(choice.template_name, HERO_ASCEND_TEMPLATE_NAME)
        self.assertEqual(choice.priority, 0.0)
        self.assertEqual((choice.x, choice.y), (194, 632))

    def test_action_policy_selects_ascend_before_name_priorities(self):
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
        self.assertEqual((choice.x, choice.y), (320, 632))
        find_ascend.assert_called_once_with(frame, templates[ascend_path])
        find_template.assert_not_called()
        find_options.assert_not_called()

    def test_action_policy_selects_numeric_priority_independent_of_match_order(
        self,
    ):
        frame = Mock()
        priority_1 = Path("01_dark_lubu.png")
        priority_2 = Path("02_hanuman.png")
        templates = {priority_1: Mock(), priority_2: Mock()}
        find_ascend = Mock(return_value=[])
        find_template = Mock(
            side_effect=lambda _frame, path, _template: {
                priority_1: (193, 597, 0.91),
                priority_2: (446, 597, 0.99),
            }[path]
        )
        find_options = Mock()

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
        find_template.assert_called_once_with(
            frame,
            priority_1,
            templates[priority_1],
        )
        find_options.assert_not_called()

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

        choice = find_choice(popup)
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

        choice = find_choice(popup)

        self.assertIsNotNone(choice)
        self.assertEqual(choice.template_name, "01_dark_lubu.png")
        self.assertEqual((choice.x, choice.y), (473, 597))

    def test_hero_levelup_name_only_dark_lubu_beats_hanuman(self):
        popup = cv2.imread(
            str(HERO_SELECT_FIXTURES_DIR / "lubu and hanu.png")
        )

        choice = find_choice(popup)

        self.assertIsNotNone(choice)
        self.assertEqual(choice.template_name, "01_dark_lubu.png")
        self.assertEqual(choice.priority, 1.0)
        self.assertEqual((choice.x, choice.y), (447, 597))

    def test_hero_levelup_new_mage_king_overrides_priorities_1_and_2(self):
        popup = cv2.imread(
            str(HERO_SELECT_FIXTURES_DIR / "start_with_vps.png")
        )

        choice = find_choice(popup)

        self.assertIsNotNone(choice)
        self.assertEqual(choice.template_name, "00_mage_king.png")
        self.assertEqual(choice.priority, 0.0)
        self.assertEqual((choice.x, choice.y), (192, 597))

    def test_hero_levelup_vps_lubu_fixture_selects_mage_king(self):
        popup = cv2.imread(
            str(HERO_SELECT_FIXTURES_DIR / "test-vps-lubu.png")
        )

        choice = find_choice(popup)

        self.assertIsNotNone(choice)
        self.assertEqual(choice.template_name, "00_mage_king.png")
        self.assertEqual(choice.priority, 0.0)
        self.assertEqual((choice.x, choice.y), (192, 597))

    def test_hero_levelup_priority_11_selects_underworld_once(self):
        popup = cv2.imread(
            str(HERO_SELECT_FIXTURES_DIR / "prio_9start.png")
        )

        choice = find_choice(popup)

        self.assertIsNotNone(choice)
        self.assertEqual(choice.template_name, "11_underworld.png")
        self.assertEqual(choice.priority, 11.0)
        self.assertEqual((choice.x, choice.y), (193, 597))

    def test_hero_levelup_priority_11_death_beats_priority_12_soul_reaper(self):
        popup = cv2.imread(str(HERO_SELECT_FIXTURES_DIR / "prio_910.png"))

        choice = find_choice(popup)

        self.assertIsNotNone(choice)
        self.assertEqual(choice.template_name, "11_death.png")
        self.assertEqual(choice.priority, 11.0)
        self.assertEqual((choice.x, choice.y), (447, 597))

    def test_hero_levelup_priority_12_soul_reaper_template_matches(self):
        popup = cv2.imread(str(HERO_SELECT_FIXTURES_DIR / "prio_910.png"))
        soul_reaper_path = next(
            path
            for path in HERO_LEVELUP_TEMPLATE_PATHS
            if path.name == "12_soul_reaper.png"
        )

        choice = find_choice(popup, (soul_reaper_path,))

        self.assertIsNotNone(choice)
        self.assertEqual(choice.template_name, "12_soul_reaper.png")
        self.assertEqual(choice.priority, 12.0)
        self.assertEqual((choice.x, choice.y), (319, 598))

    def test_hero_levelup_priority_9_pinocchio_beats_priority_10_prayer_box(self):
        popup = cv2.imread(str(HERO_SELECT_FIXTURES_DIR / "prio_1112.png"))
        priority_9_and_10_paths = tuple(
            path
            for path in HERO_LEVELUP_TEMPLATE_PATHS
            if path.name in {"09_pinocchio.png", "10_prayer_box.png"}
        )

        choice = find_choice(popup, priority_9_and_10_paths)

        self.assertIsNotNone(choice)
        self.assertEqual(choice.template_name, "09_pinocchio.png")
        self.assertEqual(choice.priority, 9.0)
        self.assertEqual((choice.x, choice.y), (218, 597))

    def test_hero_levelup_new_fixture_prefers_priority_9_pinocchio_over_death(self):
        popup = cv2.imread(str(HERO_SELECT_FIXTURES_DIR / "prio_1112.png"))

        choice = find_choice(popup)

        self.assertIsNotNone(choice)
        self.assertEqual(choice.template_name, "09_pinocchio.png")
        self.assertEqual(choice.priority, 9.0)
        self.assertEqual((choice.x, choice.y), (218, 597))

    def test_hero_levelup_priority_10_prayer_box_template_matches(self):
        popup = cv2.imread(str(HERO_SELECT_FIXTURES_DIR / "prio_1112.png"))
        prayer_box_path = next(
            path
            for path in HERO_LEVELUP_TEMPLATE_PATHS
            if path.name == "10_prayer_box.png"
        )

        choice = find_choice(popup, (prayer_box_path,))

        self.assertIsNotNone(choice)
        self.assertEqual(choice.template_name, "10_prayer_box.png")
        self.assertEqual(choice.priority, 10.0)
        self.assertEqual((choice.x, choice.y), (446, 598))
