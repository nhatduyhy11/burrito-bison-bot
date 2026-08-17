"""Orchestrate post-map cleanup until the home screen is ready."""

from pathlib import Path
from typing import Callable, Optional

import numpy as np

from hauntedroom.flows.automap_support.completion_flow import (
    CompletionStep,
    FirstWinContext,
    MapCompletionBlockerContext,
    MapCompletionContext,
    MapCompletionOutcome,
    MapCompletionState,
    MapRewardContext,
    blocker,
    first_win,
    reward,
)
from hauntedroom.flows.automap_support.completion_flow.reward import (
    REWARD_LIST_TITLE_SEARCH_REGION,
    REWARD_LIST_TITLE_TEMPLATE_THRESHOLD,
    WIN_REWARD_EMPTY_DELAY_MS,
    WIN_REWARD_FOLLOWUP_CLICK,
    WIN_REWARD_FOLLOWUP_CLICK_COUNT,
    WIN_REWARD_RECHECK_MS,
    WIN_REWARD_TEMPLATE_THRESHOLD,
)

MAP_END_TEMPLATE_THRESHOLD = 0.90
MAP_END_CHECK_INTERVAL_SEC = 5.0
START_HOME_TEMPLATE_THRESHOLD = 0.90


def find_start_home(
    frame_gray: np.ndarray,
    start_home_template: np.ndarray,
    start_home_template_path: Path,
    find_template_fn,
) -> tuple[int, int, float, Path]:
    x, y, score = find_template_fn(
        frame_gray,
        start_home_template,
        start_home_template_path.name,
        scales=(1.0,),
    )
    return x, y, score, start_home_template_path


def _complete_if_home_ready(
    context: MapCompletionContext,
    state: MapCompletionState,
    frame_gray: np.ndarray,
) -> Optional[MapCompletionOutcome]:
    x, y, score, template_path = find_start_home(
        frame_gray,
        context.start_home_template,
        context.start_home_template_path,
        context.find_template_fn,
    )
    if score < START_HOME_TEMPLATE_THRESHOLD:
        return None

    print(
        f"Home ready at {x},{y}, score={score:.3f}, "
        f"template={template_path.name}; auto-map complete.",
        flush=True,
    )
    return state.outcome(completed=True)


async def finish_map_from_home(
    page,
    stop_event,
    *,
    win_reward_template: np.ndarray,
    win_reward_template_path: Path,
    reward_list_title_template: np.ndarray,
    reward_list_title_template_path: Path,
    start_home_template: np.ndarray,
    start_home_template_path: Path,
    blocker_templates: tuple[tuple[Path, np.ndarray], ...],
    daily_first_win_template: np.ndarray,
    daily_first_win_template_path: Path,
    daily_first_win_checkbox_template: np.ndarray,
    daily_first_win_checkbox_template_path: Path,
    daily_first_win_checked_template: np.ndarray,
    daily_first_win_checked_template_path: Path,
    first_win_done: bool,
    win_recorded: bool,
    total_win: Optional[int],
    on_win: Optional[Callable[[], int]],
    capture_page_bgr_fn,
    to_grayscale_fn,
    find_template_fn,
    find_template_matches_fn,
    click_fn,
    wait_for_flow_timeout_fn,
    flow_checkpoint_fn,
    poll_ms: int,
) -> MapCompletionOutcome:
    context = MapCompletionContext(
        page=page,
        stop_event=stop_event,
        first_win=FirstWinContext(
            page=page,
            stop_event=stop_event,
            daily_first_win_template=daily_first_win_template,
            daily_first_win_template_path=daily_first_win_template_path,
            daily_first_win_checkbox_template=(
                daily_first_win_checkbox_template
            ),
            daily_first_win_checkbox_template_path=(
                daily_first_win_checkbox_template_path
            ),
            daily_first_win_checked_template=daily_first_win_checked_template,
            daily_first_win_checked_template_path=(
                daily_first_win_checked_template_path
            ),
            capture_page_bgr_fn=capture_page_bgr_fn,
            to_grayscale_fn=to_grayscale_fn,
            find_template_fn=find_template_fn,
            click_fn=click_fn,
            wait_for_flow_timeout_fn=wait_for_flow_timeout_fn,
            flow_checkpoint_fn=flow_checkpoint_fn,
            poll_ms=poll_ms,
        ),
        reward=MapRewardContext(
            page=page,
            stop_event=stop_event,
            win_reward_template=win_reward_template,
            win_reward_template_path=win_reward_template_path,
            reward_list_title_template=reward_list_title_template,
            reward_list_title_template_path=reward_list_title_template_path,
            on_win=on_win,
            find_template_fn=find_template_fn,
            find_template_matches_fn=find_template_matches_fn,
            click_fn=click_fn,
            wait_for_flow_timeout_fn=wait_for_flow_timeout_fn,
        ),
        blocker=MapCompletionBlockerContext(
            page=page,
            stop_event=stop_event,
            blocker_templates=blocker_templates,
            find_template_fn=find_template_fn,
            click_fn=click_fn,
            wait_for_flow_timeout_fn=wait_for_flow_timeout_fn,
            poll_ms=poll_ms,
        ),
        start_home_template=start_home_template,
        start_home_template_path=start_home_template_path,
        capture_page_bgr_fn=capture_page_bgr_fn,
        to_grayscale_fn=to_grayscale_fn,
        find_template_fn=find_template_fn,
        wait_for_flow_timeout_fn=wait_for_flow_timeout_fn,
        flow_checkpoint_fn=flow_checkpoint_fn,
        poll_ms=poll_ms,
    )
    state = MapCompletionState(
        first_win_done=first_win_done,
        win_recorded=win_recorded,
        total_win=total_win,
    )

    while await context.flow_checkpoint_fn(context.stop_event):
        frame_bgr = await context.capture_page_bgr_fn(context.page)
        frame_gray = context.to_grayscale_fn(frame_bgr)

        step = await reward.handle_win_reward(context.reward, state, frame_gray)
        if step is CompletionStep.CONTINUE:
            continue
        if step is CompletionStep.STOP:
            break

        step = await first_win.handle_first_win(
            context.first_win,
            state,
            frame_gray,
        )
        if step is CompletionStep.CONTINUE:
            continue
        if step is CompletionStep.STOP:
            break

        step = await reward.handle_reward_list(context.reward, state, frame_gray)
        if step is CompletionStep.CONTINUE:
            continue
        if step is CompletionStep.STOP:
            break

        if state.reward_list_title_seen:
            outcome = _complete_if_home_ready(context, state, frame_gray)
            if outcome is not None:
                return outcome

        step = await reward.handle_reward_followup(context.reward, state)
        if step is CompletionStep.CONTINUE:
            continue
        if step is CompletionStep.STOP:
            break

        step = await blocker.handle_completion_blocker(
            context.blocker,
            frame_gray,
        )
        if step is CompletionStep.CONTINUE:
            continue
        if step is CompletionStep.STOP:
            break

        outcome = _complete_if_home_ready(context, state, frame_gray)
        if outcome is not None:
            return outcome

        await context.wait_for_flow_timeout_fn(
            context.page,
            context.poll_ms,
            context.stop_event,
        )

    print("Auto-map flow stopped while waiting for home reward.", flush=True)
    return state.outcome(completed=False)
