import sys
from asyncio import Event
from pathlib import Path
from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import AsyncMock, Mock, call, patch

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
            entry_template_path=Path("entry.png"),
            templates={
                Path("header.png"): HEADER_TEMPLATE,
                Path("entry.png"): np.zeros((2, 2), dtype=np.uint8),
            },
            threshold=0.9,
            timeout_ms=1_000,
            poll_ms=100,
            delay_ms=0,
            click_positions={},
            entry_click_position="mid_left",
            entry_template_scales=(1.0,),
            label="Start Battle",
            stop_event=Event(),
        )

        self.assertTrue(completed)
        page.mouse.click.assert_awaited_once_with(319, 689)

    @patch(
        "hauntedroom.actions.hero_select_battle.close_profile_popup_tabs",
        new_callable=AsyncMock,
    )
    @patch(
        "hauntedroom.actions.hero_select_battle.bot_click",
        new_callable=AsyncMock,
    )
    @patch(
        "hauntedroom.actions.hero_select_battle.click_and_wait",
        new_callable=AsyncMock,
    )
    @patch(
        "hauntedroom.actions.hero_select_battle.wait_for_flow_timeout",
        new_callable=AsyncMock,
    )
    @patch("hauntedroom.actions.hero_select_battle.find_template")
    @patch("hauntedroom.actions.hero_select_battle.find_hero_select_battle_button")
    @patch(
        "hauntedroom.actions.hero_select_battle.capture_page_bgr",
        new_callable=AsyncMock,
    )
    async def test_retries_home_entry_after_blocker_interrupts_transition(
        self,
        capture_page_bgr,
        find_battle_button,
        find_template_mock,
        wait_for_flow_timeout,
        click_and_wait_mock,
        bot_click_mock,
        _close_profile_popup_tabs,
    ):
        blocker_path = Path("lubu_close.png")
        header_path = Path("header.png")
        entry_path = Path("start_home.png")
        frames = [
            np.full((4, 4, 3), 1, dtype=np.uint8),
            np.full((4, 4, 3), 2, dtype=np.uint8),
            np.full((4, 4, 3), 3, dtype=np.uint8),
        ]
        capture_page_bgr.side_effect = frames

        def find_template_for_state(image, _template, name, *_args, **_kwargs):
            state = int(image[0, 0])
            if name == blocker_path.name and state == 1:
                return 483, 182, 0.977
            if name == entry_path.name and state == 2:
                return 296, 562, 0.978
            return 0, 0, 0.0

        find_template_mock.side_effect = find_template_for_state
        battle_button = Mock(center=(319, 689))
        find_battle_button.side_effect = [None, battle_button]
        wait_for_flow_timeout.return_value = True
        click_and_wait_mock.return_value = True
        page = Mock()
        stop_event = Event()

        completed = await click_hero_select_battle(
            page=page,
            blocker_paths=(blocker_path,),
            header_template_path=header_path,
            entry_template_path=entry_path,
            templates={
                blocker_path: np.zeros((2, 2), dtype=np.uint8),
                header_path: np.zeros((2, 2), dtype=np.uint8),
                entry_path: np.zeros((2, 2), dtype=np.uint8),
            },
            threshold=0.9,
            timeout_ms=1_000,
            poll_ms=100,
            delay_ms=0,
            click_positions={},
            entry_click_position="mid_left",
            entry_template_scales=(1.0,),
            label="Start Battle",
            stop_event=stop_event,
        )

        self.assertTrue(completed)
        self.assertEqual(
            click_and_wait_mock.await_args_list,
            [
                call(page, (483, 182), 100, stop_event),
                call(page, (296, 562), 100, stop_event),
            ],
        )
        bot_click_mock.assert_awaited_once_with(page, (319, 689))
