"""Reward popup handling for the post-map completion flow."""

import numpy as np

from hauntedroom.flows.automap_support.completion_flow.state import (
    CompletionStep,
    MapCompletionState,
    MapRewardContext,
)

WIN_REWARD_TEMPLATE_THRESHOLD = 0.85
WIN_REWARD_RECHECK_MS = 2_000
WIN_REWARD_EMPTY_DELAY_MS = 3_000
WIN_REWARD_FOLLOWUP_CLICK = (220, 560)
WIN_REWARD_FOLLOWUP_CLICK_COUNT = 2
REWARD_LIST_TITLE_TEMPLATE_THRESHOLD = 0.90
REWARD_LIST_TITLE_SEARCH_REGION = (180, 200, 460, 300)


async def handle_win_reward(
    context: MapRewardContext,
    state: MapCompletionState,
    frame_gray: np.ndarray,
) -> CompletionStep:
    if state.reward_click_position is not None:
        return CompletionStep.NOT_HANDLED

    reward_matches = context.find_template_matches_fn(
        frame_gray,
        context.win_reward_template,
        context.win_reward_template_path.name,
        threshold=WIN_REWARD_TEMPLATE_THRESHOLD,
        scales=(1.0,),
    )
    if not reward_matches:
        return CompletionStep.NOT_HANDLED

    if not state.first_win_done:
        state.first_win_done = True
        print(
            "Reward appeared without daily first-win prompt; "
            "daily check disabled for this run.",
            flush=True,
        )
    if not state.win_recorded:
        state.win_recorded = True
        if context.on_win is not None:
            state.total_win = context.on_win()
        print("Win reward detected; win recorded.", flush=True)

    center_x, center_y, score = reward_matches[0]
    template_height = context.win_reward_template.shape[0]
    click_y = center_y - template_height // 2 + min(
        1,
        template_height - 1,
    )
    print(
        f"Win reward found at {center_x},{center_y}, "
        f"score={score:.3f}; clicking first match top-middle at "
        f"{center_x},{click_y} and checking again in 2s.",
        flush=True,
    )
    state.reward_click_position = (center_x, click_y)
    await context.click_fn(context.page, center_x, click_y)
    ready = await context.wait_for_flow_timeout_fn(
        context.page,
        WIN_REWARD_RECHECK_MS,
        context.stop_event,
    )
    return CompletionStep.CONTINUE if ready else CompletionStep.STOP


async def handle_reward_list(
    context: MapRewardContext,
    state: MapCompletionState,
    frame_gray: np.ndarray,
) -> CompletionStep:
    left, top, right, bottom = REWARD_LIST_TITLE_SEARCH_REGION
    title_frame = frame_gray[top:bottom, left:right]
    title_x, title_y, title_score = context.find_template_fn(
        title_frame,
        context.reward_list_title_template,
        context.reward_list_title_template_path.name,
        click_position="top_middle",
        scales=(1.0,),
    )
    if title_score >= REWARD_LIST_TITLE_TEMPLATE_THRESHOLD:
        click_x = left + title_x
        click_y = top + title_y
        print(
            f"Reward list title found at {click_x},{click_y}, "
            f"score={title_score:.3f}; clicking top-middle and "
            "checking again in 2s.",
            flush=True,
        )
        await context.click_fn(context.page, click_x, click_y)
        state.reward_list_title_seen = True
        ready = await context.wait_for_flow_timeout_fn(
            context.page,
            WIN_REWARD_RECHECK_MS,
            context.stop_event,
        )
        return CompletionStep.CONTINUE if ready else CompletionStep.STOP

    if state.reward_click_position is None or state.reward_list_title_seen:
        return CompletionStep.NOT_HANDLED

    click_x, click_y = state.reward_click_position
    print(
        "Reward list title not found; clicking previous win reward "
        f"position at {click_x},{click_y} and checking again in 2s.",
        flush=True,
    )
    await context.click_fn(context.page, click_x, click_y)
    ready = await context.wait_for_flow_timeout_fn(
        context.page,
        WIN_REWARD_RECHECK_MS,
        context.stop_event,
    )
    return CompletionStep.CONTINUE if ready else CompletionStep.STOP


async def handle_reward_followup(
    context: MapRewardContext,
    state: MapCompletionState,
) -> CompletionStep:
    if state.reward_followup_click_count >= WIN_REWARD_FOLLOWUP_CLICK_COUNT:
        return CompletionStep.NOT_HANDLED

    next_click = state.reward_followup_click_count + 1
    print(
        "No win reward remains; waiting 3s then clicking "
        f"{WIN_REWARD_FOLLOWUP_CLICK[0]},"
        f"{WIN_REWARD_FOLLOWUP_CLICK[1]} "
        f"({next_click}/{WIN_REWARD_FOLLOWUP_CLICK_COUNT}) "
        "before rechecking.",
        flush=True,
    )
    ready = await context.wait_for_flow_timeout_fn(
        context.page,
        WIN_REWARD_EMPTY_DELAY_MS,
        context.stop_event,
    )
    if not ready:
        return CompletionStep.STOP

    await context.click_fn(context.page, *WIN_REWARD_FOLLOWUP_CLICK)
    state.reward_followup_click_count += 1
    return CompletionStep.CONTINUE
