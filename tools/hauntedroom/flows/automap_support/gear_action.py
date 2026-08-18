"""One-shot deployment of the first low-map gear."""

from typing import Optional

import numpy as np

from hauntedroom.core.mouse import click_and_wait, smooth_drag
from hauntedroom.core.terminal import BLUE, RED, colorize
from hauntedroom.core.vision import capture_page_bgr
from hauntedroom.flows.automap_support.vision.gear import (
    find_gear_button,
    find_gear_drop_position,
    gear_menu_is_open,
)

GEAR_ITEM_POSITION = (320, 526)
GEAR_MENU_SETTLE_MS = 1_000
GEAR_MENU_OPEN_ATTEMPTS = 3
GEAR_MENU_CLOSE_ATTEMPTS = 3
GEAR_DROP_SETTLE_MS = 800
GEAR_DRAG_HOLD_MS = 700
GEAR_DRAG_STEPS = 12
GEAR_DRAG_STEP_DELAY_MS = 50
GEAR_DROP_HOLD_MS = 150


def _print_gear_error(message: str) -> None:
    print(colorize(message, RED), flush=True)


async def _soft_fail_initial_gear(
    page,
    gear_button: tuple[int, int],
    reason: str,
    *,
    frame_bgr: Optional[np.ndarray] = None,
    menu_was_open: bool = False,
) -> bool:
    """Best-effort close the gear popup, then let auto-map continue."""
    _print_gear_error(reason)

    menu_open = menu_was_open
    if frame_bgr is not None:
        menu_open = gear_menu_is_open(frame_bgr)
    else:
        try:
            frame_bgr = await capture_page_bgr(page)
            menu_open = gear_menu_is_open(frame_bgr)
        except Exception as error:
            _print_gear_error(
                f"Could not inspect the gear menu during recovery: {error}."
            )

    if not menu_open:
        _print_gear_error("Gear menu is closed; continuing as placed.")
        return True

    for attempt in range(1, GEAR_MENU_CLOSE_ATTEMPTS + 1):
        try:
            await click_and_wait(page, gear_button, GEAR_MENU_SETTLE_MS)
        except Exception as error:
            _print_gear_error(
                "Could not click the gear icon during close attempt "
                f"{attempt}/{GEAR_MENU_CLOSE_ATTEMPTS}: {error}."
            )

        try:
            frame_bgr = await capture_page_bgr(page)
        except Exception as error:
            # Do not blindly click again: the previous click may have closed
            # the popup, and another click would reopen it.
            _print_gear_error(
                "Could not verify that the gear menu closed: "
                f"{error}. Continuing as placed."
            )
            return True

        if not gear_menu_is_open(frame_bgr):
            _print_gear_error("Gear menu closed; continuing as placed.")
            return True

    _print_gear_error(
        "Gear menu remained open after recovery attempts; continuing as placed."
    )
    return True


async def deploy_initial_gear(
    page,
    frame_bgr: np.ndarray,
) -> bool:
    """Open, drag and verify the only gear available on the low map."""
    gear_button = find_gear_button(frame_bgr)
    if gear_button is None:
        return False

    popup_frame = frame_bgr
    menu_was_open = False
    try:
        for attempt in range(1, GEAR_MENU_OPEN_ATTEMPTS + 1):
            print(
                colorize(
                    "Initial gear is available; opening menu at "
                    f"{gear_button[0]},{gear_button[1]} "
                    f"(attempt {attempt}/{GEAR_MENU_OPEN_ATTEMPTS}).",
                    BLUE,
                ),
                flush=True,
            )
            await click_and_wait(page, gear_button, GEAR_MENU_SETTLE_MS)
            popup_frame = await capture_page_bgr(page)
            if gear_menu_is_open(popup_frame):
                menu_was_open = True
                break

            if attempt < GEAR_MENU_OPEN_ATTEMPTS:
                # Refresh the button position in case its animation moved
                # between clicks. Fall back on a transient detector miss.
                gear_button = find_gear_button(popup_frame) or gear_button
                _print_gear_error("Gear menu did not open; retrying gear click.")
        else:
            return await _soft_fail_initial_gear(
                page,
                gear_button,
                f"Gear menu did not open after {GEAR_MENU_OPEN_ATTEMPTS} attempts.",
                frame_bgr=popup_frame,
            )

        drop_position = find_gear_drop_position(popup_frame)
        if drop_position is None:
            return await _soft_fail_initial_gear(
                page,
                gear_button,
                "Door HP anchor was not found; gear was not dragged.",
                frame_bgr=popup_frame,
                menu_was_open=True,
            )

        print(
            colorize(
                f"Dragging initial gear from {GEAR_ITEM_POSITION[0]},"
                f"{GEAR_ITEM_POSITION[1]} to {drop_position[0]},"
                f"{drop_position[1]} using the door HP anchor.",
                BLUE,
            ),
            flush=True,
        )
        await page.evaluate(
            "() => { window.__hauntedRoomSuppressNextClickLog = true; }"
        )
        await smooth_drag(
            page,
            GEAR_ITEM_POSITION,
            drop_position,
            # The game changes to its placement grid only after a real
            # click-hold.
            hold_before_move_ms=GEAR_DRAG_HOLD_MS,
            steps=GEAR_DRAG_STEPS,
            step_delay_ms=GEAR_DRAG_STEP_DELAY_MS,
            hold_before_release_ms=GEAR_DROP_HOLD_MS,
        )
        await page.wait_for_timeout(GEAR_DROP_SETTLE_MS)

        result_frame = await capture_page_bgr(page)
        menu_closed = not gear_menu_is_open(result_frame)
        plus_gone = find_gear_button(result_frame) is None
        if menu_closed and plus_gone:
            print(
                "Initial gear placed; menu closed and availability plus is gone.",
                flush=True,
            )
            return True

        return await _soft_fail_initial_gear(
            page,
            gear_button,
            "Initial gear placement could not be verified "
            f"(menu_closed={menu_closed}, plus_gone={plus_gone}).",
            frame_bgr=result_frame,
            menu_was_open=menu_was_open,
        )
    except Exception as error:
        return await _soft_fail_initial_gear(
            page,
            gear_button,
            f"Initial gear deployment failed: {error}.",
            menu_was_open=menu_was_open,
        )
