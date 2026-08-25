import sys
from asyncio import Event
from pathlib import Path
from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import AsyncMock, Mock

import cv2
import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

from hauntedroom.actions.hero_select_battle import (
    click_hero_select_battle,
    find_hero_select_battle_button,
)


FIXTURES_DIR = PROJECT_ROOT / "tests" / "fixtures"
HEADER_TEMPLATE = cv2.imread(
    str(PROJECT_ROOT / "tools" / "rooms" / "hero_select_battle_banner_left.png"),
    cv2.IMREAD_GRAYSCALE,
)


class HeroSelectBattleVisionTest(TestCase):
    def test_cn_hero_select_screen_finds_yellow_button_without_reading_text(self):
        image = cv2.imread(
            str(
                FIXTURES_DIR
                / "hauntedroom-captures"
                / "cn_server"
                / "hero_select_screen_bell.png"
            )
        )

        button = find_hero_select_battle_button(image, HEADER_TEMPLATE)

        self.assertIsNotNone(button)
        self.assertEqual(button.center, (319, 689))

    def test_yellow_button_without_top_header_is_rejected(self):
        image = np.zeros((720, 640, 3), dtype=np.uint8)
        image[672:706, 265:374] = (0, 200, 255)

        self.assertIsNone(
            find_hero_select_battle_button(image, HEADER_TEMPLATE)
        )

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

        self.assertIsNone(
            find_hero_select_battle_button(image, HEADER_TEMPLATE)
        )


class HeroSelectBattleActionTest(IsolatedAsyncioTestCase):
    async def test_clicks_detected_button_center(self):
        fixture_path = (
            FIXTURES_DIR
            / "hauntedroom-captures"
            / "cn_server"
            / "hero_select_screen_bell.png"
        )
        page = Mock()
        page.context.pages = [page]
        page.screenshot = AsyncMock(return_value=fixture_path.read_bytes())
        page.wait_for_timeout = AsyncMock()
        page.evaluate = AsyncMock()
        page.mouse.click = AsyncMock()

        completed = await click_hero_select_battle(
            page=page,
            blocker_paths=(),
            header_template_path=Path("header.png"),
            templates={Path("header.png"): HEADER_TEMPLATE},
            threshold=0.9,
            timeout_ms=1_000,
            poll_ms=100,
            delay_ms=0,
            click_positions={},
            label="Start Battle",
            stop_event=Event(),
        )

        self.assertTrue(completed)
        page.mouse.click.assert_awaited_once_with(319, 689)
