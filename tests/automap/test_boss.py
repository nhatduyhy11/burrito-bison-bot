import asyncio
import sys
from pathlib import Path
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, Mock, call, patch

import cv2
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TOOLS_DIR = PROJECT_ROOT / "tools"
FIXTURES_DIR = PROJECT_ROOT / "tests" / "fixtures"
sys.path.insert(0, str(TOOLS_DIR))

from hauntedroom.core.vision import region_has_color_component
from hauntedroom.flows.automap import (
    AutomapConfig,
    AutomapFlow,
    BOSS_HP_TEMPLATE_PATH,
)
from hauntedroom.flows.automap_support.boss_action import (
    PET_ACTIVE_TEMPLATE_PATH,
    SPELL_ACTION_POSITION,
    activate_boss_spell,
    deploy_boss_pet,
)
from hauntedroom.flows.automap_support.boss_detector import (
    BOSS_HP_SEARCH_REGION,
    PET_READY_GLOW_PATTERN,
    PET_READY_REGION,
    SPELL_READY_REGION,
    SPELL_READY_GLOW_PATTERN,
    boss_progress_is_full,
    find_boss_health_bar,
)


class BossTest(IsolatedAsyncioTestCase):

    def setUp(self):
        self.page = Mock()
        self.page.evaluate = AsyncMock()
        self.page.wait_for_timeout = AsyncMock()
        self.page.mouse = Mock()
        self.page.mouse.click = AsyncMock()
        self.page.mouse.move = AsyncMock()
        self.page.mouse.down = AsyncMock()
        self.page.mouse.up = AsyncMock()

    def test_finds_boss_sized_hp_bar_in_upper_region_without_color(self):
        template = cv2.imread(str(BOSS_HP_TEMPLATE_PATH), cv2.IMREAD_GRAYSCALE)
        self.assertIsNotNone(template)
        frame = np.full((720, 640), 80, dtype=np.uint8)
        x, y = 220, 280
        height, width = template.shape
        # Inversion changes every source color/intensity while preserving the
        # narrow vertical stripe geometry used by the detector.
        frame[y : y + height, x : x + width] = 255 - template

        match = find_boss_health_bar(frame, template)

        self.assertIsNotNone(match)
        match_x, match_y, score = match
        self.assertEqual((match_x, match_y), (x + width // 2, y + height // 2))
        self.assertGreaterEqual(score, 0.85)

    def test_rejects_short_hp_signature(self):
        template = cv2.imread(str(BOSS_HP_TEMPLATE_PATH), cv2.IMREAD_GRAYSCALE)
        frame = np.full((720, 640), 80, dtype=np.uint8)
        mini = cv2.resize(template, (40, template.shape[0]), interpolation=cv2.INTER_AREA)
        frame[280 : 280 + mini.shape[0], 220 : 220 + mini.shape[1]] = mini

        self.assertIsNone(find_boss_health_bar(frame, template))

    def test_rejects_partial_bar_even_when_whole_template_score_is_high(self):
        template = cv2.imread(str(BOSS_HP_TEMPLATE_PATH), cv2.IMREAD_GRAYSCALE)
        frame = np.full((720, 640), 80, dtype=np.uint8)
        x, y = 220, 280
        # The old whole-template-only check scored this 45/61-pixel prefix at
        # about 0.71, above the 0.65 acceptance threshold.
        visible_width = 45
        frame[
            y : y + template.shape[0],
            x : x + visible_width,
        ] = 255 - template[:, :visible_width]

        self.assertIsNone(find_boss_health_bar(frame, template))

    def test_accepts_live_full_boss_bar_when_region_contains_it(self):
        template = cv2.imread(str(BOSS_HP_TEMPLATE_PATH), cv2.IMREAD_GRAYSCALE)
        frame = cv2.imread(
            str(
                FIXTURES_DIR
                / "hauntedroom-captures"
                / "boss_screen"
                / "boss_full_bar.png"
            ),
            cv2.IMREAD_GRAYSCALE,
        )

        match = find_boss_health_bar(frame, template)

        self.assertIsNotNone(match)
        self.assertEqual(match[:2], (438, 268))

    def test_accepts_occluded_boss_bar_with_geometry_confirmation(self):
        template = cv2.imread(str(BOSS_HP_TEMPLATE_PATH), cv2.IMREAD_GRAYSCALE)

        for fixture_name, expected_position in (
            ("test_boss_detect.png", (290, 307)),
            ("test_boss_2.png", (306, 237)),
        ):
            with self.subTest(fixture_name=fixture_name):
                frame_bgr = cv2.imread(
                    str(
                        FIXTURES_DIR
                        / "hauntedroom-captures"
                        / "boss_screen"
                        / fixture_name
                    )
                )
                self.assertIsNotNone(frame_bgr)
                frame_gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)

                match = find_boss_health_bar(frame_gray, template)

                self.assertIsNotNone(match)
                self.assertEqual(match[:2], expected_position)

    def test_rejects_live_frame_after_boss_bar_disappears(self):
        template = cv2.imread(str(BOSS_HP_TEMPLATE_PATH), cv2.IMREAD_GRAYSCALE)
        frame = cv2.imread(
            str(
                FIXTURES_DIR
                / "hauntedroom-captures"
                / "boss_screen"
                / "boss_empty_bar.png"
            ),
            cv2.IMREAD_GRAYSCALE,
        )

        self.assertIsNone(find_boss_health_bar(frame, template))

    def test_rejects_boss_bar_below_upper_search_region(self):
        template = cv2.imread(str(BOSS_HP_TEMPLATE_PATH), cv2.IMREAD_GRAYSCALE)
        frame = np.full((720, 640), 80, dtype=np.uint8)
        height, width = template.shape
        x = BOSS_HP_SEARCH_REGION[0]
        y = BOSS_HP_SEARCH_REGION[3]
        frame[y : y + height, x : x + width] = template

        self.assertIsNone(find_boss_health_bar(frame, template))

    def test_final_boss_progress_endpoint_is_yellow_in_live_capture(self):
        frame = cv2.imread(
            str(
                FIXTURES_DIR
                / "hauntedroom-captures"
                / "boss_screen"
                / "boss_full_bar.png"
            )
        )

        self.assertTrue(boss_progress_is_full(frame))

    def test_mini_boss_progress_endpoint_is_not_yellow(self):
        frame = cv2.imread(
            str(
                FIXTURES_DIR
                / "hauntedroom-captures"
                / "boss_screen"
                / "mini_boss_bar.png"
            )
        )

        self.assertFalse(boss_progress_is_full(frame))

    def test_approaching_progress_endpoint_is_not_yellow(self):
        approaching = cv2.imread(
            str(TOOLS_DIR / "rooms" / "boss" / "boss_approaching.png")
        )

        # boss_approaching.png is the global (378, 46)-(430, 89) crop.
        self.assertFalse(
            boss_progress_is_full(
                approaching,
                region=(22, 15, 31, 26),
            )
        )

    async def test_mini_boss_progress_does_not_block_hp_handoff(self):
        with patch(
            "hauntedroom.flows.automap.load_template",
            return_value=np.zeros((2, 2), dtype=np.uint8),
        ):
            flow = AutomapFlow(
                self.page,
                asyncio.Event(),
                AutomapConfig(click_exit_on_boss=True),
            )

        with (
            patch(
                "hauntedroom.flows.automap.find_boss_health_bar",
                return_value=(250, 280, 0.90),
            ),
            patch(
                "hauntedroom.flows.automap.boss_progress_is_full",
                return_value=False,
            ) as classify_progress,
            patch(
                "hauntedroom.flows.automap.find_template",
                return_value=(612, 35, 0.95),
            ),
        ):
            handled = await flow.handle_boss_critical(
                np.zeros((720, 640, 3), dtype=np.uint8),
                np.zeros((720, 640), dtype=np.uint8),
            )

        self.assertTrue(handled)
        classify_progress.assert_called_once()

    @patch(
        "hauntedroom.flows.automap.load_template",
        return_value=np.zeros((2, 2), dtype=np.uint8),
    )
    async def test_click_exit_on_boss_clicks_pause_and_requests_handoff(
        self,
        _load_template,
    ):
        flow = AutomapFlow(
            self.page,
            asyncio.Event(),
            AutomapConfig(click_exit_on_boss=True),
        )
        with (
            patch(
                "hauntedroom.flows.automap.find_boss_health_bar",
                return_value=(250, 280, 0.90),
            ),
            patch(
                "hauntedroom.flows.automap.boss_progress_is_full",
                return_value=False,
            ),
            patch(
                "hauntedroom.flows.automap.find_template",
                return_value=(612, 35, 0.95),
            ),
        ):
            handled = await flow.handle_boss_critical(
                np.zeros((720, 640, 3), dtype=np.uint8),
                np.zeros((720, 640), dtype=np.uint8),
            )

        self.assertTrue(handled)
        self.page.mouse.click.assert_awaited_once_with(612, 35)
        self.assertTrue(flow.boss_handoff_requested)

    @patch(
        "hauntedroom.flows.automap.load_template",
        return_value=np.zeros((2, 2), dtype=np.uint8),
    )
    async def test_click_exit_on_boss_pauses_final_boss_before_pet_deploy(
        self,
        _load_template,
    ):
        flow = AutomapFlow(
            self.page,
            asyncio.Event(),
            AutomapConfig(click_exit_on_boss=True),
        )
        with (
            patch(
                "hauntedroom.flows.automap.find_boss_health_bar",
                return_value=(250, 300, 0.90),
            ),
            patch(
                "hauntedroom.flows.automap.boss_progress_is_full",
                return_value=True,
            ),
            patch(
                "hauntedroom.flows.automap.find_template",
                return_value=(612, 35, 0.95),
            ),
            patch(
                "hauntedroom.flows.automap.deploy_boss_pet",
                new_callable=AsyncMock,
            ) as deploy_pet,
        ):
            handled = await flow.handle_boss_critical(
                np.zeros((720, 640, 3), dtype=np.uint8),
                np.zeros((720, 640), dtype=np.uint8),
            )

        self.assertTrue(handled)
        self.page.mouse.click.assert_awaited_once_with(612, 35)
        deploy_pet.assert_not_awaited()
        self.assertTrue(flow.boss_handoff_requested)

    @patch(
        "hauntedroom.flows.automap.load_template",
        return_value=np.zeros((2, 2), dtype=np.uint8),
    )
    async def test_boss_exit_click_can_be_disabled(
        self,
        _load_template,
    ):
        flow = AutomapFlow(
            self.page,
            asyncio.Event(),
            AutomapConfig(click_exit_on_boss=False),
        )
        with (
            patch(
                "hauntedroom.flows.automap.find_boss_health_bar",
                return_value=(250, 280, 0.90),
            ),
            patch(
                "hauntedroom.flows.automap.boss_progress_is_full",
                return_value=False,
            ),
            patch("hauntedroom.flows.automap.find_template") as find_exit,
            patch("builtins.print") as print_mock,
        ):
            first_handled = await flow.handle_boss_critical(
                np.zeros((720, 640, 3), dtype=np.uint8),
                np.zeros((720, 640), dtype=np.uint8),
            )
            second_handled = await flow.handle_boss_critical(
                np.zeros((720, 640, 3), dtype=np.uint8),
                np.zeros((720, 640), dtype=np.uint8),
            )

        self.assertFalse(first_handled)
        self.assertFalse(second_handled)
        find_exit.assert_not_called()
        self.page.mouse.click.assert_not_awaited()
        self.assertFalse(flow.boss_handoff_requested)
        print_mock.assert_called_once_with(
            "Mini-boss HP entered upper search region at 250,280, "
            "score=0.900; click_exit_on_boss=False.",
            flush=True,
        )

    async def test_progress_is_not_classified_without_an_hp_match(self):
        with patch(
            "hauntedroom.flows.automap.load_template",
            return_value=np.zeros((2, 2), dtype=np.uint8),
        ):
            flow = AutomapFlow(self.page, asyncio.Event(), AutomapConfig())

        with (
            patch(
                "hauntedroom.flows.automap.find_boss_health_bar",
                return_value=None,
            ),
            patch(
                "hauntedroom.flows.automap.boss_progress_is_full",
            ) as classify_progress,
        ):
            handled = await flow.handle_boss_critical(
                np.zeros((720, 640, 3), dtype=np.uint8),
                np.zeros((720, 640), dtype=np.uint8),
            )

        self.assertFalse(handled)
        classify_progress.assert_not_called()

    def test_ready_glow_detector_accepts_supplied_live_capture(self):
        capture = cv2.imread(
            str(
                FIXTURES_DIR
                / "hauntedroom-captures"
                / "boss_screen"
                / "pet-spell-ready.png"
            )
        )
        self.assertIsNotNone(capture)
        self.assertTrue(
            region_has_color_component(
                capture,
                PET_READY_REGION,
                PET_READY_GLOW_PATTERN,
            )
        )
        self.assertTrue(
            region_has_color_component(
                capture,
                SPELL_READY_REGION,
                SPELL_READY_GLOW_PATTERN,
            )
        )

    def test_pet_ready_glow_accepts_different_pet_art(self):
        frame = cv2.imread(
            str(
                FIXTURES_DIR
                / "hauntedroom-captures"
                / "boss_screen"
                / "pet_alt.png"
            )
        )

        self.assertTrue(
            region_has_color_component(
                frame,
                PET_READY_REGION,
                PET_READY_GLOW_PATTERN,
            )
        )

    def test_pet_ready_glow_rejects_partial_width_bar(self):
        frame = cv2.imread(
            str(
                FIXTURES_DIR
                / "hauntedroom-captures"
                / "boss_screen"
                / "test_boss_detect.png"
            )
        )

        self.assertFalse(
            region_has_color_component(
                frame,
                PET_READY_REGION,
                PET_READY_GLOW_PATTERN,
            )
        )

    @patch(
        "hauntedroom.flows.automap_support.boss_action.capture_page_bgr",
        new_callable=AsyncMock,
    )
    async def test_activate_boss_spell_clicks_ready_spell_then_boss(
        self,
        capture_page_bgr,
    ):
        capture_page_bgr.return_value = cv2.imread(
            str(
                FIXTURES_DIR
                / "hauntedroom-captures"
                / "boss_screen"
                / "pet-spell-ready.png"
            )
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
    async def test_deploy_boss_pet_opens_menu_and_clicks_active_summon(
        self,
        capture_page_bgr,
    ):
        ready_frame = cv2.imread(
            str(
                FIXTURES_DIR
                / "hauntedroom-captures"
                / "boss_screen"
                / "pet-spell-ready.png"
            )
        )
        capture_page_bgr.return_value = cv2.imread(
            str(
                FIXTURES_DIR
                / "hauntedroom-captures"
                / "boss_screen"
                / "pet_menu_open.png"
            )
        )

        deployed = await deploy_boss_pet(self.page, frame_bgr=ready_frame)

        self.assertTrue(deployed)
        self.assertEqual(
            self.page.mouse.click.await_args_list,
            [call(321, 604), call(463, 455)],
        )

    @patch(
        "hauntedroom.flows.automap_support.boss_action.capture_page_bgr",
        new_callable=AsyncMock,
    )
    async def test_deploy_boss_pet_accepts_different_pet_art(
        self,
        capture_page_bgr,
    ):
        ready_frame = cv2.imread(
            str(
                FIXTURES_DIR
                / "hauntedroom-captures"
                / "boss_screen"
                / "pet_alt.png"
            )
        )
        capture_page_bgr.return_value = cv2.imread(
            str(
                FIXTURES_DIR
                / "hauntedroom-captures"
                / "boss_screen"
                / "pet_alt_ready.png"
            )
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
        ready_frame = cv2.imread(
            str(
                FIXTURES_DIR
                / "hauntedroom-captures"
                / "boss_screen"
                / "pet-spell-ready.png"
            )
        )
        popup_frame = cv2.imread(
            str(
                FIXTURES_DIR
                / "hauntedroom-captures"
                / "boss_screen"
                / "pet_menu_open.png"
            )
        )
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

    def test_pet_active_template_matches_open_menu_fixture(self):
        frame = cv2.imread(
            str(
                FIXTURES_DIR
                / "hauntedroom-captures"
                / "boss_screen"
                / "pet_menu_open.png"
            ),
            cv2.IMREAD_GRAYSCALE,
        )
        template = cv2.imread(str(PET_ACTIVE_TEMPLATE_PATH), cv2.IMREAD_GRAYSCALE)

        from hauntedroom.core.template import find_template

        x, y, score = find_template(
            frame,
            template,
            PET_ACTIVE_TEMPLATE_PATH.name,
            scales=(1.0,),
        )

        self.assertEqual((x, y), (463, 455))
        self.assertGreaterEqual(score, 0.99)

    @patch(
        "hauntedroom.flows.automap.load_template",
        return_value=np.zeros((2, 2), dtype=np.uint8),
    )
    async def test_final_boss_in_critical_region_is_classified_and_handled(
        self,
        _load_template,
    ):
        flow = AutomapFlow(self.page, asyncio.Event(), AutomapConfig())
        with (
            patch(
                "hauntedroom.flows.automap.find_boss_health_bar",
                return_value=(250, 300, 0.90),
            ),
            patch(
                "hauntedroom.flows.automap.boss_progress_is_full",
                return_value=True,
            ) as classify_progress,
            patch(
                "hauntedroom.flows.automap.find_template",
                return_value=(612, 35, 0.95),
            ),
            patch(
                "hauntedroom.flows.automap.deploy_boss_pet",
                new_callable=AsyncMock,
                return_value=True,
            ) as deploy_pet,
        ):
            handled = await flow.handle_boss_critical(
                np.zeros((720, 640, 3), dtype=np.uint8),
                np.zeros((720, 640), dtype=np.uint8),
            )

        self.assertTrue(handled)
        classify_progress.assert_called_once()
        deploy_pet.assert_awaited_once()
        self.assertTrue(flow.final_boss_pet_deployed)
