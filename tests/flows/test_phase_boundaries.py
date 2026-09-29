"""Regression locks for the lobby -> hero-select -> battle phase boundaries.

Both flows must keep going through the single shared hero-select
implementation in hauntedroom.flows.hero_select:

- Automap (Shift+1): builder composes ClearBlockers -> start_home entry ->
  ClickHeroSelectBattleAction, and the start-auto loop runs those entry
  actions before the automap battle phase. The wrapper's own detection click
  is already locked behaviorally in tests/actions/test_hero_select_battle.py.
- Train: the normal loop runs lobby -> start_train_battle -> card selection
  -> battle, and start_train_battle ends the bottom-strip lobby by clicking
  the battle button found by the real shared detector.

The wait loops stay per caller; each test patches capture_page_bgr at the
caller under test instead of forcing one shared loop.
"""

import ast
import sys
from asyncio import Event
from pathlib import Path
from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import ANY, AsyncMock, Mock, call, patch

import cv2
import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

from hauntedroom.actions.builder import build_start_battle_actions
from hauntedroom.actions.models import (
    ClearBlockersAction,
    ClickHeroSelectBattleAction,
    ClickTemplateAction,
)
from hauntedroom.flows.autotrain import run_normal_train_loop
from hauntedroom.flows.start_auto import run_start_automap_loop
from hauntedroom.flows.train_support.entry import start_train_battle


PACKAGE_DIR = PROJECT_ROOT / "tools" / "hauntedroom"
HERO_SELECT_FIXTURE = (
    PROJECT_ROOT
    / "tests"
    / "fixtures"
    / "hauntedroom-captures"
    / "cn_server"
    / "hero_select_screen_bell.png"
)


def hero_select_importers() -> dict[str, set[str]]:
    """Map hauntedroom modules importing the shared package to imported names."""
    importers: dict[str, set[str]] = {}
    for path in PACKAGE_DIR.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        names = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
            and node.module
            and node.module.startswith("hauntedroom.flows.hero_select")
            for alias in node.names
        }
        if names:
            importers[path.relative_to(PACKAGE_DIR).as_posix()] = names
    return importers


class SharedHeroSelectImplementationTest(TestCase):
    def test_exactly_the_two_phase_callers_use_the_shared_detector(self):
        importers = hero_select_importers()

        self.assertEqual(
            set(importers),
            {
                "actions/hero_select_battle.py",
                "flows/train_support/entry.py",
                "runner/reload.py",
                "flows/hero_select/__init__.py",
            },
        )
        self.assertEqual(
            importers["actions/hero_select_battle.py"],
            {"find_battle_button"},
        )
        self.assertIn(
            "find_battle_button",
            importers["flows/train_support/entry.py"],
        )

    def test_phase_callers_delegate_instead_of_redefining_detection(self):
        for caller in (
            "actions/hero_select_battle.py",
            "flows/train_support/entry.py",
        ):
            tree = ast.parse(
                (PACKAGE_DIR / caller).read_text(encoding="utf-8"),
                filename=caller,
            )
            defined = {
                node.name
                for node in ast.walk(tree)
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            }
            self.assertNotIn("find_battle_button", defined, caller)


class AutomapFlowPhaseOrderTest(IsolatedAsyncioTestCase):
    def test_start_battle_actions_run_lobby_then_shared_hero_select(self):
        actions = build_start_battle_actions()

        self.assertEqual(
            [type(action) for action in actions],
            [ClearBlockersAction, ClickTemplateAction, ClickHeroSelectBattleAction],
        )
        self.assertEqual(actions[1].template_path.name, "start_home.png")
        self.assertEqual(
            actions[2].header_template_path.name,
            "hero_select_battle_banner_top.png",
        )

    async def test_start_auto_runs_entry_actions_before_the_battle_phase(self):
        start_actions = build_start_battle_actions()
        phases = Mock()
        phases.action_runner = AsyncMock(return_value=True)
        phases.automap_flow = AsyncMock(return_value=True)
        page = Mock()
        stop_event = Event()
        run_state = Mock()

        with patch(
            "hauntedroom.flows.start_auto.wait_with_countdown",
            new_callable=AsyncMock,
            return_value=False,
        ), patch(
            "hauntedroom.flows.start_auto.map_was_lost",
            new_callable=AsyncMock,
            return_value=False,
        ):
            completed = await run_start_automap_loop(
                page,
                start_actions,
                phases.automap_flow,
                stop_event,
                phases.action_runner,
                run_state=run_state,
            )

        self.assertFalse(completed)  # loop stops on the first cooldown
        self.assertEqual(
            phases.mock_calls,
            [
                call.action_runner(
                    page,
                    start_actions,
                    loop_count=2,
                    stop_event=stop_event,
                    stop_after_success=True,
                ),
                call.automap_flow(
                    page,
                    stop_event,
                    debug=False,
                    on_win=ANY,
                    run_state=run_state,
                ),
            ],
        )


class TrainFlowPhaseOrderTest(IsolatedAsyncioTestCase):
    async def test_train_loop_runs_lobby_then_hero_select_then_cards_then_battle(
        self,
    ):
        phases = Mock()
        phases.wait_for_train_screen = AsyncMock(side_effect=[True, False])
        phases.wait_for_train_start_available = AsyncMock(return_value=True)
        phases.start_train_battle = AsyncMock(return_value=True)
        phases.select_train_heroes = AsyncMock(return_value=True)
        phases.automap_flow = AsyncMock(return_value=True)
        page = Mock()
        stop_event = Event()
        run_state = Mock()

        with patch(
            "hauntedroom.flows.autotrain.wait_for_train_screen",
            new=phases.wait_for_train_screen,
        ), patch(
            "hauntedroom.flows.autotrain.wait_for_train_start_available",
            new=phases.wait_for_train_start_available,
        ), patch(
            "hauntedroom.flows.autotrain.start_train_battle",
            new=phases.start_train_battle,
        ), patch(
            "hauntedroom.flows.autotrain.select_train_heroes",
            new=phases.select_train_heroes,
        ):
            completed = await run_normal_train_loop(
                page,
                phases.automap_flow,
                stop_event,
                debug=False,
                run_state=run_state,
            )

        self.assertFalse(completed)  # second cycle stops at the screen wait
        self.assertEqual(
            phases.mock_calls,
            [
                call.wait_for_train_screen(page, stop_event),
                call.wait_for_train_start_available(page, stop_event),
                call.start_train_battle(page, stop_event),
                call.select_train_heroes(page, stop_event, raise_on_timeout=False),
                call.automap_flow(
                    page,
                    stop_event,
                    debug=False,
                    run_state=run_state,
                    battle_mode="train",
                ),
                call.wait_for_train_screen(page, stop_event),
            ],
        )


class TrainLobbyHandoffTest(IsolatedAsyncioTestCase):
    async def test_train_lobby_ends_at_the_shared_hero_select_detector(self):
        page = Mock()
        lobby_click = (274, 662)
        lobby_frame = np.full((4, 4, 3), 1, dtype=np.uint8)
        hero_select_frame = cv2.imread(str(HERO_SELECT_FIXTURE))

        with patch(
            "hauntedroom.flows.train_support.entry.capture_page_bgr",
            new_callable=AsyncMock,
            side_effect=[lobby_frame, lobby_frame, lobby_frame, hero_select_frame],
        ), patch(
            "hauntedroom.flows.train_support.entry.find_train_bottom_button_click",
            side_effect=[lobby_click, lobby_click, None],
        ), patch(
            "hauntedroom.flows.train_support.entry.train_is_available",
            return_value=True,
        ), patch(
            "hauntedroom.flows.train_support.entry.wait_for_flow_timeout",
            new_callable=AsyncMock,
            return_value=True,
        ), patch(
            "hauntedroom.flows.train_support.entry.click_and_wait",
            new_callable=AsyncMock,
            return_value=True,
        ) as click_and_wait_mock:
            completed = await start_train_battle(page)

        self.assertTrue(completed)
        # The lobby click comes first; the battle click coordinates come from
        # the real shared detector reading the hero-select fixture.
        self.assertEqual(
            click_and_wait_mock.await_args_list,
            [
                call(page, lobby_click, ANY, None),
                call(page, (319, 689), ANY, None),
            ],
        )
