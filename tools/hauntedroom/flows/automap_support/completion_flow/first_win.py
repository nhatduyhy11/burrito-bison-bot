"""Daily first-win handling for the post-map completion flow."""

from pathlib import Path
from typing import Optional

import numpy as np

from hauntedroom.flows.automap_support.completion_flow.state import (
    CompletionStep,
    FirstWinContext,
    MapCompletionState,
)

DAILY_FIRST_WIN_TEMPLATE_THRESHOLD = 0.90
DAILY_FIRST_WIN_CHECKBOX_THRESHOLD = 0.95
DAILY_FIRST_WIN_CHECK_DELAY_MS = 1_000
DAILY_FIRST_WIN_CHECKBOX_OFFSET = (-88, -1)
DAILY_FIRST_WIN_CONFIRM_OFFSET = (45, 36)
DAILY_FIRST_WIN_CHECKBOX_SEARCH_PAD = 8


def find_daily_first_win(
    frame_gray: np.ndarray,
    daily_first_win_template: np.ndarray,
    daily_first_win_template_path: Path,
    find_template_fn,
) -> Optional[tuple[int, int, float]]:
    x, y, score = find_template_fn(
        frame_gray,
        daily_first_win_template,
        daily_first_win_template_path.name,
        scales=(1.0,),
    )
    if score < DAILY_FIRST_WIN_TEMPLATE_THRESHOLD:
        return None
    return x, y, score


def find_daily_first_win_checkbox(
    frame_gray: np.ndarray,
    label_position: tuple[int, int],
    checkbox_template: np.ndarray,
    checkbox_template_path: Path,
    find_template_fn,
) -> tuple[int, int, float]:
    expected_x = label_position[0] + DAILY_FIRST_WIN_CHECKBOX_OFFSET[0]
    expected_y = label_position[1] + DAILY_FIRST_WIN_CHECKBOX_OFFSET[1]
    height, width = checkbox_template.shape
    pad = DAILY_FIRST_WIN_CHECKBOX_SEARCH_PAD
    left = max(expected_x - width // 2 - pad, 0)
    top = max(expected_y - height // 2 - pad, 0)
    right = min(expected_x + (width + 1) // 2 + pad, frame_gray.shape[1])
    bottom = min(expected_y + (height + 1) // 2 + pad, frame_gray.shape[0])
    checkbox_frame = frame_gray[top:bottom, left:right]
    x, y, score = find_template_fn(
        checkbox_frame,
        checkbox_template,
        checkbox_template_path.name,
        scales=(1.0,),
    )
    return left + x, top + y, score


async def handle_daily_first_win(
    context: FirstWinContext,
    initial_frame_gray: np.ndarray,
) -> bool:
    frame_gray = initial_frame_gray
    while await context.flow_checkpoint_fn(context.stop_event):
        daily_first_win_match = find_daily_first_win(
            frame_gray,
            context.daily_first_win_template,
            context.daily_first_win_template_path,
            context.find_template_fn,
        )
        if daily_first_win_match is None:
            ready = await context.wait_for_flow_timeout_fn(
                context.page,
                context.poll_ms,
                context.stop_event,
            )
            if not ready:
                return False
            frame_gray = context.to_grayscale_fn(
                await context.capture_page_bgr_fn(context.page)
            )
            continue
        label_x, label_y, _label_score = daily_first_win_match

        checked_x, checked_y, checked_score = find_daily_first_win_checkbox(
            frame_gray,
            (label_x, label_y),
            context.daily_first_win_checked_template,
            context.daily_first_win_checked_template_path,
            context.find_template_fn,
        )
        if checked_score >= DAILY_FIRST_WIN_CHECKBOX_THRESHOLD:
            confirm_x = label_x + DAILY_FIRST_WIN_CONFIRM_OFFSET[0]
            confirm_y = label_y + DAILY_FIRST_WIN_CONFIRM_OFFSET[1]
            print(
                f"Daily first-win checkbox confirmed at {checked_x},{checked_y}, "
                f"score={checked_score:.3f}; clicking decline at "
                f"{confirm_x},{confirm_y}.",
                flush=True,
            )
            await context.click_fn(context.page, confirm_x, confirm_y)
            return True

        checkbox_x, checkbox_y, checkbox_score = find_daily_first_win_checkbox(
            frame_gray,
            (label_x, label_y),
            context.daily_first_win_checkbox_template,
            context.daily_first_win_checkbox_template_path,
            context.find_template_fn,
        )
        if checkbox_score >= DAILY_FIRST_WIN_CHECKBOX_THRESHOLD:
            print(
                f"Daily first-win checkbox at {checkbox_x},{checkbox_y}, "
                f"score={checkbox_score:.3f}; clicking and confirming in 1s.",
                flush=True,
            )
            await context.click_fn(context.page, checkbox_x, checkbox_y)
            ready = await context.wait_for_flow_timeout_fn(
                context.page,
                DAILY_FIRST_WIN_CHECK_DELAY_MS,
                context.stop_event,
            )
            if not ready:
                return False
            frame_gray = context.to_grayscale_fn(
                await context.capture_page_bgr_fn(context.page)
            )
            continue

        # Neither explicit state is reliable on this frame. Re-capture without
        # clicking so a transition/animation can never toggle a checked box.
        ready = await context.wait_for_flow_timeout_fn(
            context.page,
            context.poll_ms,
            context.stop_event,
        )
        if not ready:
            return False
        frame_gray = context.to_grayscale_fn(
            await context.capture_page_bgr_fn(context.page)
        )

    return False


async def handle_first_win(
    context: FirstWinContext,
    state: MapCompletionState,
    frame_gray: np.ndarray,
) -> CompletionStep:
    if state.first_win_done:
        return CompletionStep.NOT_HANDLED

    first_win_match = find_daily_first_win(
        frame_gray,
        context.daily_first_win_template,
        context.daily_first_win_template_path,
        context.find_template_fn,
    )
    if first_win_match is None:
        return CompletionStep.NOT_HANDLED

    daily_x, daily_y, daily_score = first_win_match
    print(
        f"Daily first-win prompt at {daily_x},{daily_y}, "
        f"score={daily_score:.3f}; entering isolated flow.",
        flush=True,
    )
    state.first_win_done = await handle_daily_first_win(context, frame_gray)
    return CompletionStep.CONTINUE if state.first_win_done else CompletionStep.STOP
