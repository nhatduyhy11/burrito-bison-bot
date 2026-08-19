import asyncio
import sys
from pathlib import Path
from unittest import IsolatedAsyncioTestCase
from unittest.mock import ANY, AsyncMock, Mock, call

import cv2
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MAP_WIN_FIXTURES_DIR = (
    PROJECT_ROOT
    / "tests"
    / "fixtures"
    / "hauntedroom-captures"
    / "map_win"
)
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

from hauntedroom.core.template_matching import find_template as find_real_template
from hauntedroom.core.template_matching import load_template as load_real_template
from hauntedroom.flows.automap import (
    DAILY_FIRST_WIN_CHECKBOX_TEMPLATE_PATH,
    DAILY_FIRST_WIN_CHECKED_TEMPLATE_PATH,
    DAILY_FIRST_WIN_TEMPLATE_PATH,
)
from hauntedroom.flows.automap_support.completion_flow.first_win import (
    DAILY_FIRST_WIN_CHECK_DELAY_MS,
    handle_daily_first_win,
)
from hauntedroom.flows.automap_support.completion_flow.state import (
    FirstWinContext,
)


class DailyFirstWinTest(IsolatedAsyncioTestCase):
    def setUp(self):
        self.page = Mock()

    def test_daily_first_win_templates_match_supplied_screens(self):
        label_template = load_real_template(DAILY_FIRST_WIN_TEMPLATE_PATH)
        checkbox_template = load_real_template(
            DAILY_FIRST_WIN_CHECKBOX_TEMPLATE_PATH
        )
        checked_template = load_real_template(
            DAILY_FIRST_WIN_CHECKED_TEMPLATE_PATH
        )

        for fixture_name in (
            "daily_first_win.png",
            "daily_first_win_checked.png",
        ):
            with self.subTest(fixture_name=fixture_name):
                frame = cv2.imread(
                    str(MAP_WIN_FIXTURES_DIR / fixture_name),
                    cv2.IMREAD_GRAYSCALE,
                )
                self.assertIsNotNone(frame)
                _x, _y, label_score = find_real_template(
                    frame,
                    label_template,
                    DAILY_FIRST_WIN_TEMPLATE_PATH.name,
                    scales=(1.0,),
                )
                _x, _y, unchecked_score = find_real_template(
                    frame,
                    checkbox_template,
                    DAILY_FIRST_WIN_CHECKBOX_TEMPLATE_PATH.name,
                    scales=(1.0,),
                )
                _x, _y, checked_score = find_real_template(
                    frame,
                    checked_template,
                    DAILY_FIRST_WIN_CHECKED_TEMPLATE_PATH.name,
                    scales=(1.0,),
                )
                self.assertGreaterEqual(label_score, 0.90)
                if fixture_name == "daily_first_win.png":
                    self.assertGreaterEqual(unchecked_score, 0.95)
                    self.assertLess(checked_score, 0.95)
                else:
                    self.assertLess(unchecked_score, 0.95)
                    self.assertGreaterEqual(checked_score, 0.95)

    async def test_daily_first_win_retries_until_checkbox_is_confirmed(self):
        find_template = Mock()

        checked_scores = iter((0.20, 0.20, 0.99))
        unchecked_scores = iter((0.99, 0.99))

        def match_with_checkbox_state(_frame, _template, name, **_kwargs):
            if name == DAILY_FIRST_WIN_TEMPLATE_PATH.name:
                return (332, 442, 0.99)
            if name == DAILY_FIRST_WIN_CHECKED_TEMPLATE_PATH.name:
                return (10, 10, next(checked_scores))
            return (10, 10, next(unchecked_scores))

        find_template.side_effect = match_with_checkbox_state
        wait = AsyncMock(return_value=True)
        click = AsyncMock()
        capture = AsyncMock(
            return_value=np.zeros((720, 640, 3), dtype=np.uint8)
        )
        checkpoint = AsyncMock(return_value=True)

        handled = await handle_daily_first_win(
            FirstWinContext(
                page=self.page,
                stop_event=asyncio.Event(),
                daily_first_win_template=np.zeros((18, 150), dtype=np.uint8),
                daily_first_win_template_path=DAILY_FIRST_WIN_TEMPLATE_PATH,
                daily_first_win_checkbox_template=np.zeros(
                    (19, 19), dtype=np.uint8
                ),
                daily_first_win_checkbox_template_path=(
                    DAILY_FIRST_WIN_CHECKBOX_TEMPLATE_PATH
                ),
                daily_first_win_checked_template=np.zeros(
                    (19, 19), dtype=np.uint8
                ),
                daily_first_win_checked_template_path=(
                    DAILY_FIRST_WIN_CHECKED_TEMPLATE_PATH
                ),
                capture_page_bgr_fn=capture,
                to_grayscale_fn=lambda frame: frame[:, :, 0],
                find_template_fn=find_template,
                click_fn=click,
                wait_for_flow_timeout_fn=wait,
                flow_checkpoint_fn=checkpoint,
                poll_ms=100,
            ),
            np.zeros((720, 640), dtype=np.uint8),
        )

        self.assertTrue(handled)
        self.assertEqual(click.await_count, 3)
        self.assertEqual(click.await_args_list[-1], call(self.page, 377, 478))
        self.assertEqual(
            wait.await_args_list,
            [
                call(self.page, DAILY_FIRST_WIN_CHECK_DELAY_MS, ANY),
                call(self.page, DAILY_FIRST_WIN_CHECK_DELAY_MS, ANY),
            ],
        )

    async def test_daily_first_win_never_toggles_a_checked_checkbox(self):
        frame = cv2.imread(
            str(MAP_WIN_FIXTURES_DIR / "daily_first_win_checked.png"),
            cv2.IMREAD_GRAYSCALE,
        )
        click = AsyncMock()
        wait = AsyncMock(return_value=True)

        handled = await handle_daily_first_win(
            FirstWinContext(
                page=self.page,
                stop_event=asyncio.Event(),
                daily_first_win_template=load_real_template(
                    DAILY_FIRST_WIN_TEMPLATE_PATH
                ),
                daily_first_win_template_path=DAILY_FIRST_WIN_TEMPLATE_PATH,
                daily_first_win_checkbox_template=load_real_template(
                    DAILY_FIRST_WIN_CHECKBOX_TEMPLATE_PATH
                ),
                daily_first_win_checkbox_template_path=(
                    DAILY_FIRST_WIN_CHECKBOX_TEMPLATE_PATH
                ),
                daily_first_win_checked_template=load_real_template(
                    DAILY_FIRST_WIN_CHECKED_TEMPLATE_PATH
                ),
                daily_first_win_checked_template_path=(
                    DAILY_FIRST_WIN_CHECKED_TEMPLATE_PATH
                ),
                capture_page_bgr_fn=AsyncMock(),
                to_grayscale_fn=lambda image: image,
                find_template_fn=find_real_template,
                click_fn=click,
                wait_for_flow_timeout_fn=wait,
                flow_checkpoint_fn=AsyncMock(return_value=True),
                poll_ms=100,
            ),
            frame,
        )

        self.assertTrue(handled)
        click.assert_awaited_once_with(self.page, 377, 478)
        wait.assert_not_awaited()
