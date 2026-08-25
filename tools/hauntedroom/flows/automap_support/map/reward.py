"""Map reward handling."""

import cv2
import numpy as np

from hauntedroom.core.terminal import GREEN, colorize

from .model_state import MapLifecycleStep, MapRewardContext, MapState

WIN_REWARD_TEMPLATE_THRESHOLD = 0.85
WIN_REWARD_RECHECK_MS = 2_000
WIN_REWARD_EMPTY_DELAY_MS = 3_000
# The whole center reward area is clickable. Keep the target relative to the
# captured page so this action does not depend on reward artwork or language.
WIN_REWARD_HOTSPOT_RATIO = (0.50, 0.65)
# Reference coordinate for the production 640x720 capture. Runtime clicks are
# calculated from the ratio above; this name remains useful to tests/docs.
WIN_REWARD_FOLLOWUP_CLICK = (320, 468)
WIN_REWARD_FOLLOWUP_CLICK_COUNT = 2
REWARD_LIST_TITLE_TEMPLATE_THRESHOLD = 0.90
REWARD_LIST_TITLE_SEARCH_REGION = (180, 200, 460, 300)
# The reward-list panel is a large, stable red surface. Detecting its color and
# geometry avoids using the localized title as the primary confirmation.
REWARD_LIST_PANEL_REGION_RATIO = (117 / 640, 250 / 720, 522 / 640, 476 / 720)
REWARD_LIST_PANEL_MIN_RED_RATIO = 0.50
REWARD_LIST_DISMISS_RATIO = (0.50, 0.33)


def relative_position(
    frame: np.ndarray,
    position_ratio: tuple[float, float],
) -> tuple[int, int]:
    height, width = frame.shape[:2]
    x_ratio, y_ratio = position_ratio
    return round(width * x_ratio), round(height * y_ratio)


def reward_list_popup_visible(frame_bgr: np.ndarray) -> bool:
    """Detect the red reward-list panel without matching localized text."""
    if frame_bgr.ndim != 3 or frame_bgr.shape[2] != 3:
        return False

    height, width = frame_bgr.shape[:2]
    left_ratio, top_ratio, right_ratio, bottom_ratio = (
        REWARD_LIST_PANEL_REGION_RATIO
    )
    left = round(width * left_ratio)
    top = round(height * top_ratio)
    right = round(width * right_ratio)
    bottom = round(height * bottom_ratio)
    panel = frame_bgr[top:bottom, left:right]
    if panel.size == 0:
        return False

    hsv = cv2.cvtColor(panel, cv2.COLOR_BGR2HSV)
    hue = hsv[:, :, 0]
    saturation = hsv[:, :, 1]
    value = hsv[:, :, 2]
    red_pixels = (
        ((hue <= 12) | (hue >= 170))
        & (saturation >= 80)
        & (value >= 35)
    )
    return float(np.mean(red_pixels)) >= REWARD_LIST_PANEL_MIN_RED_RATIO


def _record_confirmed_win(context: MapRewardContext, state: MapState) -> None:
    if not state.first_win_done:
        state.first_win_done = True
        print(
            "Reward confirmed without daily first-win prompt; "
            "daily check disabled for this run.",
            flush=True,
        )
    if state.win_recorded:
        return

    state.win_recorded = True
    if context.on_win is not None:
        state.total_win = context.on_win()
    print(colorize("Reward popup confirmed; win recorded.", GREEN), flush=True)


async def handle_win_reward(
    context: MapRewardContext,
    state: MapState,
    frame_gray: np.ndarray,
) -> MapLifecycleStep:
    if state.reward_click_position is not None:
        return MapLifecycleStep.NOT_HANDLED

    reward_matches = context.find_template_matches_fn(
        frame_gray,
        context.win_reward_template,
        context.win_reward_template_path.name,
        threshold=WIN_REWARD_TEMPLATE_THRESHOLD,
        scales=(1.0,),
    )
    if not reward_matches:
        return MapLifecycleStep.NOT_HANDLED

    _center_x, _center_y, score = reward_matches[0]
    click_x, click_y = relative_position(frame_gray, WIN_REWARD_HOTSPOT_RATIO)
    print(
        f"Win reward visual hint found, score={score:.3f}; "
        "clicking the language-independent reward hotspot at "
        f"{click_x},{click_y} and checking again in 2s.",
        flush=True,
    )
    state.reward_click_position = (click_x, click_y)
    state.reward_followup_click_count += 1
    await context.click_fn(context.page, click_x, click_y)
    ready = await context.wait_for_flow_timeout_fn(
        context.page,
        WIN_REWARD_RECHECK_MS,
        context.stop_event,
    )
    return MapLifecycleStep.CONTINUE if ready else MapLifecycleStep.STOP


async def handle_reward_list(
    context: MapRewardContext,
    state: MapState,
    frame_bgr: np.ndarray,
    frame_gray: np.ndarray,
) -> MapLifecycleStep:
    popup_visible = reward_list_popup_visible(frame_bgr)
    if popup_visible:
        click_x, click_y = relative_position(
            frame_bgr,
            REWARD_LIST_DISMISS_RATIO,
        )
        confirmation = "language-independent red panel"
    else:
        # Compatibility fallback for captures whose panel theme differs from
        # the current red layout. Correctness no longer depends on this text.
        left, top, right, bottom = REWARD_LIST_TITLE_SEARCH_REGION
        title_frame = frame_gray[top:bottom, left:right]
        title_x, title_y, title_score = context.find_template_fn(
            title_frame,
            context.reward_list_title_template,
            context.reward_list_title_template_path.name,
            click_position="top_middle",
            scales=(1.0,),
        )
        popup_visible = title_score >= REWARD_LIST_TITLE_TEMPLATE_THRESHOLD
        if not popup_visible:
            return MapLifecycleStep.NOT_HANDLED
        click_x = left + title_x
        click_y = top + title_y
        confirmation = f"title fallback, score={title_score:.3f}"

    _record_confirmed_win(context, state)
    print(
        f"Reward list confirmed by {confirmation}; clicking "
        f"{click_x},{click_y} and checking again in 2s.",
        flush=True,
    )
    await context.click_fn(context.page, click_x, click_y)
    state.reward_list_title_seen = True
    ready = await context.wait_for_flow_timeout_fn(
        context.page,
        WIN_REWARD_RECHECK_MS,
        context.stop_event,
    )
    return MapLifecycleStep.CONTINUE if ready else MapLifecycleStep.STOP


async def handle_reward_followup(
    context: MapRewardContext,
    state: MapState,
    frame: np.ndarray,
) -> MapLifecycleStep:
    if state.reward_followup_click_count >= WIN_REWARD_FOLLOWUP_CLICK_COUNT:
        return MapLifecycleStep.NOT_HANDLED

    next_click = state.reward_followup_click_count + 1
    click_x, click_y = relative_position(frame, WIN_REWARD_HOTSPOT_RATIO)
    print(
        "Reward popup not confirmed; waiting 3s then clicking "
        f"the center reward hotspot at {click_x},{click_y} "
        f"({next_click}/{WIN_REWARD_FOLLOWUP_CLICK_COUNT}) before rechecking.",
        flush=True,
    )
    ready = await context.wait_for_flow_timeout_fn(
        context.page,
        WIN_REWARD_EMPTY_DELAY_MS,
        context.stop_event,
    )
    if not ready:
        return MapLifecycleStep.STOP

    await context.click_fn(context.page, click_x, click_y)
    state.reward_followup_click_count += 1
    return MapLifecycleStep.CONTINUE
