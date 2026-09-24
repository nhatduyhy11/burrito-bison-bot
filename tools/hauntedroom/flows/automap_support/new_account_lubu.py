"""One-time Lu Bu popup dismissal during the new-account map."""

from __future__ import annotations

import cv2
import numpy as np

from hauntedroom.core.mouse import bot_click
from hauntedroom.core.runtime import wait_for_flow_timeout
from hauntedroom.core.template_matching import find_template
from hauntedroom.core.terminal import BLUE, colorize
from hauntedroom.core.vision import capture_page_bgr
from hauntedroom.flows.automap_support.upgrade_action import AUTOMAP_ACTION_DELAY_MS

LUBU_CLOSE_TEMPLATE_NAME = "lubu_close.png"
LUBU_CLOSE_TEMPLATE_THRESHOLD = 0.80


async def _click(page, x: int, y: int) -> None:
    await bot_click(page, (x, y))


def _to_grayscale(image: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)


async def handle_new_account_lubu_close(
    page,
    stop_event,
    frame_gray: np.ndarray,
    *,
    template: np.ndarray,
    find_template_fn=find_template,
    capture_page_bgr_fn=capture_page_bgr,
    to_grayscale_fn=_to_grayscale,
    click_fn=_click,
    wait_for_flow_timeout_fn=wait_for_flow_timeout,
) -> bool:
    """Click the Lu Bu popup close, then confirm its disappearance."""
    x, y, score = find_template_fn(
        frame_gray,
        template,
        LUBU_CLOSE_TEMPLATE_NAME,
    )
    if score < LUBU_CLOSE_TEMPLATE_THRESHOLD:
        return False

    print(
        colorize(
            f"Lu Bu close at {x},{y}, score={score:.3f}; clicking, then "
            f"confirming disappearance in {AUTOMAP_ACTION_DELAY_MS}ms.",
            BLUE,
        ),
        flush=True,
    )
    await click_fn(page, x, y)
    if not await wait_for_flow_timeout_fn(page, AUTOMAP_ACTION_DELAY_MS, stop_event):
        return True

    confirm_frame = to_grayscale_fn(await capture_page_bgr_fn(page))
    _, _, confirm_score = find_template_fn(
        confirm_frame,
        template,
        LUBU_CLOSE_TEMPLATE_NAME,
    )
    if confirm_score < LUBU_CLOSE_TEMPLATE_THRESHOLD:
        print(
            colorize("Lu Bu close disappeared; resuming auto-map.", BLUE),
            flush=True,
        )
    else:
        print(
            f"Lu Bu close is still present, score={confirm_score:.3f}; "
            "will retry.",
            flush=True,
        )
    return True
