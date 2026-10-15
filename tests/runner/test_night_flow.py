import asyncio
from pathlib import Path
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, Mock

import cv2

from hauntedroom.flows.night import run_night_flow


FIXTURES = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "hauntedroom-captures"
    / "night"
)


def _load(name: str):
    frame = cv2.imread(str(FIXTURES / name))
    assert frame is not None
    return frame


class NightFlowTest(IsolatedAsyncioTestCase):
    async def test_runs_requested_loops_and_confirms_lobby_after_each_win(self):
        lobby = _load("night-solo.png")
        popup = _load("night-solo-accept.png")
        win = _load("night-win.png")
        capture = AsyncMock(
            side_effect=[lobby, popup, win, lobby, lobby, popup, win, lobby]
        )
        click = AsyncMock()
        wait = AsyncMock(return_value=True)

        completed = await run_night_flow(
            Mock(),
            asyncio.Event(),
            loop_limit=2,
            capture_fn=capture,
            click_fn=click,
            wait_fn=wait,
        )

        self.assertTrue(completed)
        self.assertEqual(
            [call.args[1:] for call in click.await_args_list],
            [
                (320, 666),
                (394, 464),
                (320, 677),
                (320, 666),
                (394, 464),
                (320, 677),
            ],
        )
        self.assertEqual(capture.await_count, 8)

    async def test_stop_during_one_second_wait_ends_flow(self):
        wait = AsyncMock(return_value=False)

        completed = await run_night_flow(
            Mock(),
            asyncio.Event(),
            loop_limit=1,
            capture_fn=AsyncMock(return_value=_load("night-solo.png")),
            click_fn=AsyncMock(),
            wait_fn=wait,
        )

        self.assertFalse(completed)
