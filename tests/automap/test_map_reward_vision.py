import asyncio
import sys
from pathlib import Path
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, Mock

import cv2
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FIXTURES_DIR = PROJECT_ROOT / "tests" / "fixtures"
MAP_WIN_FIXTURES_DIR = FIXTURES_DIR / "hauntedroom-captures" / "map_win"
SPECIAL_FLOW_FIXTURES_DIR = FIXTURES_DIR / "special_flow"
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

from hauntedroom.core.template_matching import find_template as find_real_template
from hauntedroom.core.template_matching import (
    find_template_matches as find_real_template_matches,
)
from hauntedroom.core.template_matching import load_template as load_real_template
from hauntedroom.flows.automap import (
    REWARD_LIST_TITLE_TEMPLATE_PATH,
    WIN_REWARD_TEMPLATE_PATH,
)
from hauntedroom.flows.automap_support.map.model_state import (
    MapLifecycleStep,
    MapRewardContext,
    MapState,
)
from hauntedroom.flows.automap_support.map.reward import (
    REWARD_LIST_TITLE_TEMPLATE_THRESHOLD,
    WIN_REWARD_FOLLOWUP_CLICK,
    WIN_REWARD_HOTSPOT_RATIO,
    WIN_REWARD_TEMPLATE_THRESHOLD,
    handle_reward_list,
    relative_position,
    reward_list_popup_visible,
)


class MapRewardVisionTest(IsolatedAsyncioTestCase):
    def setUp(self):
        self.page = Mock()
        self.page.evaluate = AsyncMock()
        self.page.wait_for_timeout = AsyncMock()
        self.page.mouse = Mock()
        self.page.mouse.click = AsyncMock()
        self.page.mouse.move = AsyncMock()
        self.page.mouse.down = AsyncMock()
        self.page.mouse.up = AsyncMock()

    def test_win_reward_template_matches_dynamic_reward_screens(self):
        template = load_real_template(WIN_REWARD_TEMPLATE_PATH)

        fixtures = (
            MAP_WIN_FIXTURES_DIR / "rewards_v1.png",
            MAP_WIN_FIXTURES_DIR / "rewards_v2.png",
            FIXTURES_DIR
            / "hauntedroom-captures"
            / "20260826-125439-709039-live.png",
        )
        for fixture_path in fixtures:
            with self.subTest(fixture_name=fixture_path.name):
                frame = cv2.imread(
                    str(fixture_path),
                    cv2.IMREAD_GRAYSCALE,
                )
                self.assertIsNotNone(frame)
                matches = find_real_template_matches(
                    frame,
                    template,
                    WIN_REWARD_TEMPLATE_PATH.name,
                    threshold=WIN_REWARD_TEMPLATE_THRESHOLD,
                    scales=(1.0,),
                )

                self.assertTrue(matches)

    def test_reward_list_title_template_matches_reward_list_screen(self):
        template = load_real_template(REWARD_LIST_TITLE_TEMPLATE_PATH)
        frame = cv2.imread(
            str(MAP_WIN_FIXTURES_DIR / "reward_list_screen.png"),
            cv2.IMREAD_GRAYSCALE,
        )
        self.assertIsNotNone(frame)

        x, y, score = find_real_template(
            frame,
            template,
            REWARD_LIST_TITLE_TEMPLATE_PATH.name,
            click_position="top_middle",
            scales=(1.0,),
        )

        self.assertGreaterEqual(score, REWARD_LIST_TITLE_TEMPLATE_THRESHOLD)
        self.assertEqual((x, y), (318, 237))

    def test_reward_list_panel_confirmation_does_not_depend_on_title_text(self):
        popup = cv2.imread(
            str(MAP_WIN_FIXTURES_DIR / "reward_list_screen.png"),
            cv2.IMREAD_COLOR,
        )
        missed_reward = cv2.imread(
            str(SPECIAL_FLOW_FIXTURES_DIR / "reward_fail_detect.png"),
            cv2.IMREAD_COLOR,
        )
        self.assertIsNotNone(popup)
        self.assertIsNotNone(missed_reward)

        self.assertTrue(reward_list_popup_visible(popup))
        self.assertFalse(reward_list_popup_visible(missed_reward))

        reward_template = load_real_template(WIN_REWARD_TEMPLATE_PATH)
        missed_reward_gray = cv2.cvtColor(missed_reward, cv2.COLOR_BGR2GRAY)
        self.assertFalse(
            find_real_template_matches(
                missed_reward_gray,
                reward_template,
                WIN_REWARD_TEMPLATE_PATH.name,
                threshold=WIN_REWARD_TEMPLATE_THRESHOLD,
                scales=(1.0,),
            )
        )
        self.assertEqual(
            relative_position(missed_reward, WIN_REWARD_HOTSPOT_RATIO),
            WIN_REWARD_FOLLOWUP_CLICK,
        )

    async def test_red_panel_confirms_win_without_calling_title_matcher(self):
        popup = cv2.imread(
            str(MAP_WIN_FIXTURES_DIR / "reward_list_screen.png"),
            cv2.IMREAD_COLOR,
        )
        popup_gray = cv2.cvtColor(popup, cv2.COLOR_BGR2GRAY)
        on_win = Mock(return_value=7)
        find_template = Mock()
        click = AsyncMock()
        wait = AsyncMock(return_value=True)
        context = MapRewardContext(
            page=self.page,
            stop_event=asyncio.Event(),
            win_reward_template=np.zeros((2, 2), dtype=np.uint8),
            win_reward_template_path=WIN_REWARD_TEMPLATE_PATH,
            reward_list_title_template=np.zeros((2, 2), dtype=np.uint8),
            reward_list_title_template_path=REWARD_LIST_TITLE_TEMPLATE_PATH,
            on_win=on_win,
            find_template_fn=find_template,
            find_template_matches_fn=Mock(),
            click_fn=click,
            wait_for_flow_timeout_fn=wait,
        )
        state = MapState()

        step = await handle_reward_list(context, state, popup, popup_gray)

        self.assertIs(step, MapLifecycleStep.CONTINUE)
        self.assertTrue(state.win_recorded)
        self.assertEqual(state.total_win, 7)
        self.assertFalse(state.first_win_done)
        self.assertTrue(state.reward_list_title_seen)
        on_win.assert_called_once_with()
        find_template.assert_not_called()
        click.assert_awaited_once_with(self.page, 320, 238)
