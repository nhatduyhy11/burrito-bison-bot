import sys
from pathlib import Path
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, Mock, call, patch

import cv2

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TOOLS_DIR = PROJECT_ROOT / "tools"
CAPTURES_DIR = PROJECT_ROOT / "tests" / "fixtures" / "hauntedroom-captures"
sys.path.insert(0, str(TOOLS_DIR))

from hauntedroom.core.terminal import GREEN
from hauntedroom.flows.automap_support.boss_action import (
    SPELL_ACTION_POSITION,
    activate_boss_spell,
    deploy_boss_pet,
)


class BossActionTest(IsolatedAsyncioTestCase):
    def setUp(self):
        self.page = Mock()
        self.page.evaluate = AsyncMock()
        self.page.wait_for_timeout = AsyncMock()
        self.page.mouse = Mock()
        self.page.mouse.click = AsyncMock()

    def _load_capture(self, name: str):
        frame = cv2.imread(str(CAPTURES_DIR / name))
        self.assertIsNotNone(frame)
        return frame

    @patch(
        "hauntedroom.flows.automap_support.boss_action.capture_page_bgr",
        new_callable=AsyncMock,
    )
    async def test_activate_boss_spell_clicks_ready_spell_then_boss(
        self,
        capture_page_bgr,
    ):
        capture_page_bgr.return_value = self._load_capture(
            "boss_screen/pet-spell-ready.png"
        )
        boss_position = (250, 300)

        activated = await activate_boss_spell(self.page, boss_position)

        self.assertTrue(activated)
        self.assertEqual(
            self.page.mouse.click.await_args_list,
            [call(*SPELL_ACTION_POSITION), call(*boss_position)],
        )

    @patch(
        "hauntedroom.flows.automap_support.boss_action.capture_page_bgr",
        new_callable=AsyncMock,
    )
    @patch("hauntedroom.flows.automap_support.boss_action.colorize")
    async def test_deploy_boss_pet_opens_menu_and_clicks_active_summon(
        self,
        colorize_mock,
        capture_page_bgr,
    ):
        colorize_mock.side_effect = lambda message, _color: message
        ready_frame = self._load_capture("boss_screen/pet-spell-ready.png")
        capture_page_bgr.return_value = self._load_capture(
            "boss_screen/pet_menu_open.png"
        )

        deployed = await deploy_boss_pet(self.page, frame_bgr=ready_frame)

        self.assertTrue(deployed)
        self.assertEqual(
            self.page.mouse.click.await_args_list,
            [call(321, 604), call(463, 455)],
        )
        colorize_mock.assert_any_call(
            "Pet summon is active at 463,455, score=1.000; clicking it.",
            GREEN,
        )

    @patch(
        "hauntedroom.flows.automap_support.boss_action.capture_page_bgr",
        new_callable=AsyncMock,
    )
    async def test_deploy_boss_pet_scans_complete_three_pet_cluster(
        self,
        capture_page_bgr,
    ):
        ready_frame = self._load_capture("standby 3 pet.png")
        capture_page_bgr.return_value = self._load_capture(
            "boss_screen/pet_menu_open.png"
        )

        deployed = await deploy_boss_pet(self.page, frame_bgr=ready_frame)

        self.assertTrue(deployed)
        self.assertEqual(
            self.page.mouse.click.await_args_list,
            [call(367, 604), call(463, 455)],
        )

    @patch(
        "hauntedroom.flows.automap_support.boss_action.capture_page_bgr",
        new_callable=AsyncMock,
    )
    async def test_deploy_boss_pet_accepts_different_pet_art(
        self,
        capture_page_bgr,
    ):
        ready_frame = self._load_capture("boss_screen/pet_alt.png")
        capture_page_bgr.return_value = self._load_capture(
            "boss_screen/pet_alt_ready.png"
        )

        deployed = await deploy_boss_pet(self.page, frame_bgr=ready_frame)

        self.assertTrue(deployed)
        self.assertEqual(
            self.page.mouse.click.await_args_list,
            [call(319, 603), call(463, 455)],
        )

    @patch(
        "hauntedroom.flows.automap_support.boss_action.capture_page_bgr",
        new_callable=AsyncMock,
    )
    async def test_deploy_boss_pet_retries_ready_until_active_appears(
        self,
        capture_page_bgr,
    ):
        ready_frame = self._load_capture("boss_screen/pet-spell-ready.png")
        popup_frame = self._load_capture("boss_screen/pet_menu_open.png")
        capture_page_bgr.side_effect = [ready_frame, popup_frame]

        deployed = await deploy_boss_pet(self.page, frame_bgr=ready_frame)

        self.assertTrue(deployed)
        self.assertEqual(
            self.page.mouse.click.await_args_list,
            [
                call(321, 604),
                call(321, 604),
                call(463, 455),
            ],
        )
