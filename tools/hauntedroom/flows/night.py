"""Run the Night challenge from its lobby for at most twenty wins."""

import asyncio
from typing import Callable, Optional

from hauntedroom.core.mouse import bot_click
from hauntedroom.core.runtime import flow_checkpoint, wait_for_flow_timeout
from hauntedroom.core.terminal import BLUE, GREEN, colorize
from hauntedroom.core.vision import capture_page_bgr
from hauntedroom.vision.night import (
    load_night_challenge_flame,
    load_night_crow_template,
    night_challenge_flame_visible,
    night_lobby_visible,
)
from hauntedroom.vision.buttons import (
    ButtonGeometry,
    ButtonPair,
    find_colored_button,
    find_red_yellow_button_pair,
)
from hauntedroom.vision.victory import victory_panel_visible


NIGHT_LOOP_LIMIT = 20
NIGHT_POLL_MS = 1_000
NIGHT_WIN_DISMISS_RATIO = (0.50, 0.94)
NIGHT_CHALLENGE_REGION = (190, 600, 450, 710)
NIGHT_CHALLENGE_GEOMETRY = ButtonGeometry(
    min_area=8_000,
    min_width=180,
    max_width=220,
    min_height=55,
    max_height=80,
)
NIGHT_POPUP_RED_REGION = (170, 420, 320, 510)
NIGHT_POPUP_YELLOW_REGION = (320, 420, 470, 510)
NIGHT_POPUP_BUTTON_GEOMETRY = ButtonGeometry(
    min_area=2_500,
    min_width=100,
    max_width=120,
    min_height=28,
    max_height=38,
    min_fill_ratio=0.60,
)


async def _click(page, x: int, y: int) -> None:
    await bot_click(page, (x, y))


def _relative_click(frame, ratio: tuple[float, float]) -> tuple[int, int]:
    height, width = frame.shape[:2]
    return round(width * ratio[0]), round(height * ratio[1])


def find_night_challenge_button(frame_bgr, flame_template=None):
    if not night_challenge_flame_visible(frame_bgr, flame_template):
        return None
    return find_colored_button(
        frame_bgr,
        NIGHT_CHALLENGE_REGION,
        "yellow",
        NIGHT_CHALLENGE_GEOMETRY,
    )


def find_night_accept_pair(frame_bgr) -> Optional[ButtonPair]:
    return find_red_yellow_button_pair(
        frame_bgr,
        NIGHT_POPUP_RED_REGION,
        NIGHT_POPUP_YELLOW_REGION,
        NIGHT_POPUP_BUTTON_GEOMETRY,
        NIGHT_POPUP_BUTTON_GEOMETRY,
        min_gap=25,
        max_gap=50,
    )


async def run_night_flow(
    page,
    stop_event: Optional[asyncio.Event] = None,
    debug: bool = False,
    *,
    loop_limit: int = NIGHT_LOOP_LIMIT,
    capture_fn=capture_page_bgr,
    click_fn: Callable = _click,
    wait_fn=wait_for_flow_timeout,
) -> bool:
    """Challenge, accept, wait for victory, dismiss, and confirm lobby."""
    del debug
    crow_template = load_night_crow_template()
    flame_template = load_night_challenge_flame()

    for loop_index in range(1, loop_limit + 1):
        print(
            "\n" + colorize(
                f"--- Night Run #{loop_index}/{loop_limit} ---",
                BLUE,
            ),
            flush=True,
        )

        while True:
            if not await flow_checkpoint(stop_event):
                return False
            frame = await capture_fn(page)
            if night_lobby_visible(frame, crow_template):
                challenge = find_night_challenge_button(frame, flame_template)
                if challenge is not None:
                    break
            if not await wait_fn(page, NIGHT_POLL_MS, stop_event):
                return False

        challenge_x, challenge_y = challenge.center
        print(
            f"Night challenge ready at {challenge_x},{challenge_y}; clicking.",
            flush=True,
        )
        await click_fn(page, challenge_x, challenge_y)
        if not await wait_fn(page, NIGHT_POLL_MS, stop_event):
            return False

        while True:
            if not await flow_checkpoint(stop_event):
                return False
            frame = await capture_fn(page)
            pair = find_night_accept_pair(frame)
            if pair is not None:
                accept_x, accept_y = pair.yellow.center
                print(
                    f"Night solo popup confirmed; clicking yellow accept at "
                    f"{accept_x},{accept_y}.",
                    flush=True,
                )
                await click_fn(page, accept_x, accept_y)
                break
            if not await wait_fn(page, NIGHT_POLL_MS, stop_event):
                return False

        while True:
            if not await wait_fn(page, NIGHT_POLL_MS, stop_event):
                return False
            frame = await capture_fn(page)
            if not victory_panel_visible(frame):
                continue
            dismiss_x, dismiss_y = _relative_click(
                frame,
                NIGHT_WIN_DISMISS_RATIO,
            )
            print(
                colorize(
                    "Night win detected by symmetric red panel; clicking "
                    f"below it at {dismiss_x},{dismiss_y}.",
                    GREEN,
                ),
                flush=True,
            )
            await click_fn(page, dismiss_x, dismiss_y)
            break

        while True:
            if not await wait_fn(page, NIGHT_POLL_MS, stop_event):
                return False
            frame = await capture_fn(page)
            if night_lobby_visible(frame, crow_template):
                print(f"Night loop #{loop_index} returned to lobby.", flush=True)
                break

    print(f"Night run completed {loop_limit} loops.", flush=True)
    return True
