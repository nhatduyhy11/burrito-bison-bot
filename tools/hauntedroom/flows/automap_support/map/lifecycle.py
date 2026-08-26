"""Detect map end and drive the map lifecycle until home is ready."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Callable, Optional

import cv2
import numpy as np

from hauntedroom.core.mouse import bot_click
from hauntedroom.core.runtime import flow_checkpoint, wait_for_flow_timeout
from hauntedroom.core.template_matching import find_template, find_template_matches
from hauntedroom.core.vision import capture_page_bgr
from hauntedroom.flows.automap_support.templates import AutomapTemplates
from hauntedroom.flows.automap_support.upgrade_action import AUTOMAP_POLL_MS
from hauntedroom.flows.automap_support.vision.template_config import AutomapConfig

from . import blocker, first_win, reward
from .model_state import (
    FirstWinContext,
    MapBlockerContext,
    MapEndOutcome,
    MapLifecycleContext,
    MapLifecycleStep,
    MapOutcome,
    MapRewardContext,
    MapRunState,
    MapState,
)

MAP_END_TEMPLATE_THRESHOLD = 0.90
MAP_END_CHECK_INTERVAL_SEC = 5.0
START_HOME_TEMPLATE_THRESHOLD = 0.90


async def _click(page, x: int, y: int) -> None:
    await bot_click(page, (x, y))


def _to_grayscale(image: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)


class MapLifecycle:
    """Own map-end detection, reward flow, and map/run state synchronization."""

    def __init__(
        self,
        page,
        stop_event: asyncio.Event | None,
        *,
        config: AutomapConfig,
        templates: AutomapTemplates,
        state: MapState,
        run_state: MapRunState,
        on_win: Callable[[], int] | None = None,
        capture_page_bgr_fn=capture_page_bgr,
        find_template_fn=find_template,
        find_template_matches_fn=find_template_matches,
    ) -> None:
        self.page = page
        self.stop_event = stop_event
        self.config = config
        self.templates = templates
        self.state = state
        self.run_state = run_state
        self.on_win = on_win
        self.capture_page_bgr_fn = capture_page_bgr_fn
        self.find_template_fn = find_template_fn
        self.find_template_matches_fn = find_template_matches_fn
        self.loop = asyncio.get_running_loop()

    async def handle_map_end(self, frame_gray: np.ndarray) -> MapEndOutcome:
        now = self.loop.time()
        if (
            self.state.last_map_end_check is not None
            and now - self.state.last_map_end_check < MAP_END_CHECK_INTERVAL_SEC
        ):
            return MapEndOutcome(handled=False)

        self.state.last_map_end_check = now
        x, y, score = self.find_template_fn(
            frame_gray,
            self.templates.map_end,
            self.config.map_end_template_path.name,
        )
        if score < MAP_END_TEMPLATE_THRESHOLD:
            return MapEndOutcome(handled=False)

        # This interceptor belongs only to the first new-account battle.
        # From map end onward, popup cleanup remains owned
        # by the normal blocker lifecycle below.
        self.run_state.new_account_lubu_popup_active = False
        print(
            f"Map end at {x},{y}, score={score:.3f}; clicking back to home.",
            flush=True,
        )
        await _click(self.page, x, y)
        self.state.first_win_done = self.run_state.daily_first_win_done
        outcome = await finish_map(
            self.page,
            self.stop_event,
            config=self.config,
            templates=self.templates,
            state=self.state,
            on_win=self.on_win,
            capture_page_bgr_fn=self.capture_page_bgr_fn,
            find_template_fn=self.find_template_fn,
            find_template_matches_fn=self.find_template_matches_fn,
        )
        self.state.completed = outcome.completed
        self.state.win_recorded = outcome.win_recorded
        self.state.total_win = outcome.total_win
        self.state.first_win_done = outcome.first_win_done
        self.run_state.daily_first_win_done = outcome.first_win_done
        return MapEndOutcome(handled=True, completed=outcome.completed)


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
    context: MapLifecycleContext,
    state: MapState,
    frame_gray: np.ndarray,
) -> Optional[MapOutcome]:
    x, y, score, template_path = find_start_home(
        frame_gray,
        context.start_home_template,
        context.start_home_template_path,
        context.find_template_fn,
    )
    if score < START_HOME_TEMPLATE_THRESHOLD:
        return None

    if state.win_recorded and not state.first_win_done:
        state.first_win_done = True
        print(
            "Home reward cleanup completed without daily first-win prompt; "
            "daily check disabled for this run.",
            flush=True,
        )

    print(
        f"Home ready at {x},{y}, score={score:.3f}, "
        f"template={template_path.name}; auto-map complete.",
        flush=True,
    )
    return state.outcome(completed=True)


async def finish_map(
    page,
    stop_event,
    *,
    config: AutomapConfig,
    templates: AutomapTemplates,
    state: MapState,
    on_win: Optional[Callable[[], int]],
    capture_page_bgr_fn=capture_page_bgr,
    find_template_fn=find_template,
    find_template_matches_fn=find_template_matches,
) -> MapOutcome:
    context = MapLifecycleContext(
        page=page,
        stop_event=stop_event,
        first_win=FirstWinContext(
            page=page,
            stop_event=stop_event,
            daily_first_win_template=templates.daily_first_win,
            daily_first_win_template_path=config.daily_first_win_template_path,
            daily_first_win_checkbox_template=templates.daily_first_win_checkbox,
            daily_first_win_checkbox_template_path=(
                config.daily_first_win_checkbox_template_path
            ),
            daily_first_win_checked_template=templates.daily_first_win_checked,
            daily_first_win_checked_template_path=(
                config.daily_first_win_checked_template_path
            ),
            capture_page_bgr_fn=capture_page_bgr_fn,
            to_grayscale_fn=_to_grayscale,
            find_template_fn=find_template_fn,
            click_fn=_click,
            wait_for_flow_timeout_fn=wait_for_flow_timeout,
            flow_checkpoint_fn=flow_checkpoint,
            poll_ms=AUTOMAP_POLL_MS,
        ),
        reward=MapRewardContext(
            page=page,
            stop_event=stop_event,
            win_reward_template=templates.win_reward,
            win_reward_template_path=config.win_reward_template_path,
            reward_list_title_template=templates.reward_list_title,
            reward_list_title_template_path=config.reward_list_title_template_path,
            on_win=on_win,
            find_template_fn=find_template_fn,
            find_template_matches_fn=find_template_matches_fn,
            click_fn=_click,
            wait_for_flow_timeout_fn=wait_for_flow_timeout,
        ),
        blocker=MapBlockerContext(
            page=page,
            stop_event=stop_event,
            blocker_templates=templates.map_blockers,
            find_template_fn=find_template_fn,
            click_fn=_click,
            wait_for_flow_timeout_fn=wait_for_flow_timeout,
            poll_ms=AUTOMAP_POLL_MS,
        ),
        start_home_template=templates.start_home,
        start_home_template_path=config.start_home_template_path,
        capture_page_bgr_fn=capture_page_bgr_fn,
        to_grayscale_fn=_to_grayscale,
        find_template_fn=find_template_fn,
        wait_for_flow_timeout_fn=wait_for_flow_timeout,
        flow_checkpoint_fn=flow_checkpoint,
        poll_ms=AUTOMAP_POLL_MS,
    )

    while await context.flow_checkpoint_fn(context.stop_event):
        frame_bgr = await context.capture_page_bgr_fn(context.page)
        frame_gray = context.to_grayscale_fn(frame_bgr)

        step = await reward.handle_win_reward(context.reward, state, frame_gray)
        if step is MapLifecycleStep.CONTINUE:
            continue
        if step is MapLifecycleStep.STOP:
            break

        step = await first_win.handle_first_win(context.first_win, state, frame_gray)
        if step is MapLifecycleStep.CONTINUE:
            continue
        if step is MapLifecycleStep.STOP:
            break

        step = await reward.handle_reward_list(
            context.reward,
            state,
            frame_bgr,
            frame_gray,
        )
        if step is MapLifecycleStep.CONTINUE:
            continue
        if step is MapLifecycleStep.STOP:
            break

        if state.reward_list_title_seen:
            outcome = _complete_if_home_ready(context, state, frame_gray)
            if outcome is not None:
                return outcome

        step = await reward.handle_reward_followup(context.reward, state, frame_gray)
        if step is MapLifecycleStep.CONTINUE:
            continue
        if step is MapLifecycleStep.STOP:
            break

        step = await blocker.handle_map_blocker(context.blocker, frame_gray)
        if step is MapLifecycleStep.CONTINUE:
            # A blocker can reveal the reward-selection screen again after a
            # reward-list popup was dismissed. Re-arm both reward strategies
            # so the newly exposed card is not left behind by the one-shot
            # guard or the bounded blind-click fallback.
            if state.reward_list_title_seen:
                state.reward_click_position = None
                state.reward_followup_click_count = 0
            continue
        if step is MapLifecycleStep.STOP:
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
