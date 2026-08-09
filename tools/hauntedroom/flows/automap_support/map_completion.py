"""Map completion and reward cleanup for the auto-map battle flow."""

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

import numpy as np


MAP_END_TEMPLATE_THRESHOLD = 0.90
MAP_END_CHECK_INTERVAL_SEC = 5.0
WIN_REWARD_TEMPLATE_THRESHOLD = 0.85
WIN_REWARD_RECHECK_MS = 2_000
WIN_REWARD_EMPTY_DELAY_MS = 3_000
WIN_REWARD_FOLLOWUP_CLICK = (220, 560)
REWARD_LIST_TITLE_TEMPLATE_THRESHOLD = 0.90
REWARD_LIST_TITLE_SEARCH_REGION = (180, 200, 460, 300)
START_HOME_TEMPLATE_THRESHOLD = 0.90


@dataclass(frozen=True)
class MapCompletionOutcome:
    completed: bool
    win_recorded: bool
    total_win: Optional[int]


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
    reward_followup_clicked = False
    reward_list_title_seen = False
    while await flow_checkpoint_fn(stop_event):
        frame_bgr = await capture_page_bgr_fn(page)
        frame_gray = to_grayscale_fn(frame_bgr)

        reward_matches = find_template_matches_fn(
            frame_gray,
            win_reward_template,
            win_reward_template_path.name,
            threshold=WIN_REWARD_TEMPLATE_THRESHOLD,
            scales=(1.0,),
        )
        if reward_matches:
            if not win_recorded:
                win_recorded = True
                if on_win is not None:
                    total_win = on_win()
                print("Win reward detected; win recorded.", flush=True)
            center_x, center_y, score = reward_matches[0]
            template_height = win_reward_template.shape[0]
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
            await click_fn(page, center_x, click_y)
            await wait_for_flow_timeout_fn(
                page, WIN_REWARD_RECHECK_MS, stop_event
            )
            continue

        left, top, right, bottom = REWARD_LIST_TITLE_SEARCH_REGION
        title_frame = frame_gray[top:bottom, left:right]
        title_x, title_y, title_score = find_template_fn(
            title_frame,
            reward_list_title_template,
            reward_list_title_template_path.name,
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
            await click_fn(page, click_x, click_y)
            reward_list_title_seen = True
            await wait_for_flow_timeout_fn(
                page, WIN_REWARD_RECHECK_MS, stop_event
            )
            continue

        if reward_list_title_seen:
            x, y, score, template_path = find_start_home(
                frame_gray,
                start_home_template,
                start_home_template_path,
                find_template_fn,
            )
            if score >= START_HOME_TEMPLATE_THRESHOLD:
                print(
                    f"Home ready at {x},{y}, score={score:.3f}, "
                    f"template={template_path.name}; auto-map complete.",
                    flush=True,
                )
                return MapCompletionOutcome(True, win_recorded, total_win)

        if not reward_followup_clicked:
            print(
                "No win reward remains; waiting 1s then clicking "
                f"{WIN_REWARD_FOLLOWUP_CLICK[0]},"
                f"{WIN_REWARD_FOLLOWUP_CLICK[1]} once before rechecking.",
                flush=True,
            )
            if not await wait_for_flow_timeout_fn(
                page, WIN_REWARD_EMPTY_DELAY_MS, stop_event
            ):
                break
            await click_fn(page, *WIN_REWARD_FOLLOWUP_CLICK)
            reward_followup_clicked = True
            continue

        x, y, score, template_path = find_start_home(
            frame_gray,
            start_home_template,
            start_home_template_path,
            find_template_fn,
        )
        if score >= START_HOME_TEMPLATE_THRESHOLD:
            print(
                f"Home ready at {x},{y}, score={score:.3f}, "
                f"template={template_path.name}; auto-map complete.",
                flush=True,
            )
            return MapCompletionOutcome(True, win_recorded, total_win)

        await wait_for_flow_timeout_fn(page, poll_ms, stop_event)

    print("Auto-map flow stopped while waiting for home reward.", flush=True)
    return MapCompletionOutcome(False, win_recorded, total_win)
