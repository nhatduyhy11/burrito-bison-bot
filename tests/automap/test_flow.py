import asyncio
import sys
from pathlib import Path
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, Mock, patch

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TOOLS_DIR = PROJECT_ROOT / "tools"
FIXTURES_DIR = PROJECT_ROOT / "tests" / "fixtures"
sys.path.insert(0, str(TOOLS_DIR))

from hauntedroom.flows.automap import (
    MAP_BLOCKER_TEMPLATE_PATHS,
    AutomapConfig,
    AutomapFlow,
)
from hauntedroom.flows.automap_support.flow import (
    BOSS_RECHECK_INTERVAL_MS,
    LUBU_CLOSE_TEMPLATE_THRESHOLD,
)
from hauntedroom.flows.automap_support.map.model_state import MapRunState, MapState
from hauntedroom.flows.automap_support.templates import AutomapTemplates
from hauntedroom.flows.automap_support.upgrade_action import (
    AUTOMAP_ACTION_DELAY_MS,
    UpgradeOutcome,
)

from tests.automap.template_factory import build_test_automap_templates


class AutomapFlowTest(IsolatedAsyncioTestCase):
    def setUp(self):
        self.page = Mock()
        self.page.evaluate = AsyncMock()
        self.page.wait_for_timeout = AsyncMock()
        self.page.mouse = Mock()
        self.page.mouse.click = AsyncMock()
        self.page.mouse.move = AsyncMock()
        self.page.mouse.down = AsyncMock()
        self.page.mouse.up = AsyncMock()

    @patch("hauntedroom.flows.automap_support.templates.load_template")
    async def test_template_owner_loads_all_templates_once(self, load_template):
        load_template.return_value = np.zeros((2, 2), dtype=np.uint8)

        config = AutomapConfig()
        AutomapTemplates.load(config)

        self.assertEqual(
            load_template.call_count,
            12
            + len(MAP_BLOCKER_TEMPLATE_PATHS)
            + len(config.hero_levelup_template_paths),
        )

    @patch("hauntedroom.flows.automap_support.templates.load_template")
    async def test_automap_flow_uses_injected_templates_and_state(
        self,
        load_template,
    ):
        image = np.zeros((2, 2), dtype=np.uint8)
        templates = AutomapTemplates(
            lv_up=image,
            built=image,
            lv_spin=image,
            map_end=image,
            win_reward=image,
            reward_list_title=image,
            daily_first_win=image,
            daily_first_win_checkbox=image,
            daily_first_win_checked=image,
            boss_hp=image,
            start_home=image,
            exit_click=image,
            map_blockers=(),
            hero_levelup={},
        )
        state = MapState(initial_gear_unlocked=True)
        run_state = MapRunState(daily_first_win_done=True)

        flow = AutomapFlow(
            self.page,
            asyncio.Event(),
            AutomapConfig(),
            templates=templates,
            state=state,
            run_state=run_state,
        )

        self.assertIs(flow.templates, templates)
        self.assertIs(flow.state, state)
        self.assertIs(flow.run_state, run_state)
        self.assertTrue(flow.run_state.daily_first_win_done)
        self.assertTrue(flow.state.initial_gear_unlocked)
        load_template.assert_not_called()

    async def test_on_win_is_an_invocation_dependency(self):
        on_win = Mock(return_value=3)
        outcome = Mock(
            completed=True,
            win_recorded=True,
            total_win=3,
            first_win_done=True,
        )
        run_state = MapRunState(
            daily_first_win_done=True,
            new_account_lubu_popup_active=True,
        )
        flow = AutomapFlow(
            self.page,
            asyncio.Event(),
            AutomapConfig(),
            build_test_automap_templates(),
            state=MapState(map_end_armed=True),
            on_win=on_win,
            run_state=run_state,
        )

        with patch(
            "hauntedroom.flows.automap_support.map.lifecycle.finish_map",
            new_callable=AsyncMock,
            return_value=outcome,
        ) as finish_map:
            with patch(
                "hauntedroom.flows.automap_support.map.lifecycle.find_template",
                return_value=(10, 20, 0.99),
            ):
                result = await flow.map_lifecycle.handle_map_end(
                    np.zeros((2, 2), dtype=np.uint8)
                )

        self.assertTrue(result.completed)
        self.assertIs(finish_map.await_args.kwargs["on_win"], on_win)
        self.assertTrue(flow.state.win_recorded)
        self.assertEqual(flow.state.total_win, 3)
        self.assertTrue(flow.run_state.daily_first_win_done)
        self.assertFalse(flow.run_state.new_account_lubu_popup_active)

    async def test_new_account_map_end_waits_for_an_upgrade_or_final_boss(self):
        flow = AutomapFlow(
            self.page,
            asyncio.Event(),
            AutomapConfig(),
            build_test_automap_templates(),
            run_state=MapRunState(new_account_lubu_popup_active=True),
        )
        map_end_detector = Mock(return_value=(334, 645, 0.903))
        flow.map_lifecycle.find_template_fn = map_end_detector

        outcome = await flow.map_lifecycle.handle_map_end(
            np.zeros((720, 640), dtype=np.uint8)
        )

        self.assertFalse(outcome.handled)
        map_end_detector.assert_not_called()

    @patch(
        "hauntedroom.flows.automap_support.flow.capture_page_bgr",
        new_callable=AsyncMock,
    )
    @patch("hauntedroom.flows.automap_support.flow.find_template")
    async def test_new_account_lubu_close_is_clicked_and_confirmed(
        self,
        find_template,
        capture_page_bgr,
    ):
        templates = build_test_automap_templates()
        templates.map_blockers = (
            (Path("lubu_close.png"), np.zeros((2, 2), dtype=np.uint8)),
        )
        find_template.side_effect = [
            (420, 180, LUBU_CLOSE_TEMPLATE_THRESHOLD + 0.1),
            (0, 0, LUBU_CLOSE_TEMPLATE_THRESHOLD - 0.1),
        ]
        capture_page_bgr.return_value = np.zeros((720, 640, 3), dtype=np.uint8)
        flow = AutomapFlow(
            self.page,
            asyncio.Event(),
            AutomapConfig(),
            templates,
            run_state=MapRunState(new_account_lubu_popup_active=True),
        )

        handled = await flow.handle_new_account_lubu_close(
            np.zeros((720, 640, 3), dtype=np.uint8),
            np.zeros((720, 640), dtype=np.uint8),
        )

        self.assertTrue(handled)
        self.page.mouse.click.assert_awaited_once_with(420, 180)
        self.page.wait_for_timeout.assert_awaited_once_with(AUTOMAP_ACTION_DELAY_MS)
        capture_page_bgr.assert_awaited_once_with(self.page)
        self.assertEqual(find_template.call_count, 2)

    @patch("hauntedroom.flows.automap_support.flow._handle_level_up")
    async def test_first_level_up_keeps_new_account_lubu_close_armed(
        self, handle_level_up
    ):
        handle_level_up.return_value = UpgradeOutcome(handled=True)
        templates = build_test_automap_templates()
        templates.map_blockers = (
            (Path("lubu_close.png"), np.zeros((2, 2), dtype=np.uint8)),
        )
        flow = AutomapFlow(
            self.page,
            asyncio.Event(),
            AutomapConfig(),
            templates,
            run_state=MapRunState(new_account_lubu_popup_active=True),
        )

        self.assertTrue(
            await flow.handle_level_up(
                np.zeros((720, 640, 3), dtype=np.uint8),
                np.zeros((720, 640), dtype=np.uint8),
            )
        )
        self.assertTrue(flow.state.map_end_armed)
        self.assertTrue(flow.run_state.new_account_lubu_popup_active)

        with patch(
            "hauntedroom.flows.automap_support.flow.find_template",
            return_value=(0, 0, 0.0),
        ) as find_template:
            handled = await flow.handle_new_account_lubu_close(
                np.zeros((720, 640, 3), dtype=np.uint8),
                np.zeros((720, 640), dtype=np.uint8),
            )

        self.assertFalse(handled)
        find_template.assert_called_once()

    async def test_normal_automap_does_not_check_new_account_lubu_close(self):
        templates = build_test_automap_templates()
        templates.map_blockers = (
            (Path("lubu_close.png"), np.zeros((2, 2), dtype=np.uint8)),
        )
        flow = AutomapFlow(
            self.page,
            asyncio.Event(),
            AutomapConfig(),
            templates,
        )

        with patch(
            "hauntedroom.flows.automap_support.flow.find_template"
        ) as find_template:
            handled = await flow.handle_new_account_lubu_close(
                np.zeros((720, 640, 3), dtype=np.uint8),
                np.zeros((720, 640), dtype=np.uint8),
            )

        self.assertFalse(handled)
        find_template.assert_not_called()

    @patch(
        "hauntedroom.flows.automap_support.flow.capture_page_bgr",
        new_callable=AsyncMock,
    )
    async def test_boss_handler_throttles_next_capture(
        self,
        capture_page_bgr,
    ):
        capture_page_bgr.return_value = np.zeros((720, 640, 3), dtype=np.uint8)
        stop_event = asyncio.Event()
        self.page.wait_for_timeout.side_effect = lambda _ms: stop_event.set()
        flow = AutomapFlow(
            self.page,
            stop_event,
            AutomapConfig(),
            build_test_automap_templates(),
        )
        flow.handle_level_spin_interrupt = AsyncMock(return_value=False)
        flow.handle_map_end = AsyncMock(return_value=False)
        flow.handle_initial_gear = AsyncMock(return_value=False)
        flow.handle_boss_critical = AsyncMock(return_value=True)
        flow.handle_level_up = AsyncMock(return_value=False)
        flow.handle_build_structure = AsyncMock(return_value=False)
        flow.hero_levelup = AsyncMock(return_value=False)

        await flow.run()

        self.page.wait_for_timeout.assert_awaited_once_with(BOSS_RECHECK_INTERVAL_MS)
        capture_page_bgr.assert_awaited_once_with(self.page)
