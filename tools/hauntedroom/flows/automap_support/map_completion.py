"""Map completion and reward cleanup for the auto-map battle flow."""

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

import numpy as np

from hauntedroom.flows.automap_support import map_first_win


MAP_END_TEMPLATE_THRESHOLD = 0.90
MAP_END_CHECK_INTERVAL_SEC = 5.0
WIN_REWARD_TEMPLATE_THRESHOLD = 0.85
WIN_REWARD_RECHECK_MS = 2_000
WIN_REWARD_EMPTY_DELAY_MS = 3_000
WIN_REWARD_FOLLOWUP_CLICK = (220, 560)
WIN_REWARD_FOLLOWUP_CLICK_COUNT = 2
MAP_COMPLETION_BLOCKER_THRESHOLD = 0.90
MAP_COMPLETION_BLOCKER_CLICK_POSITIONS = {
    "overlay_newbie.png": "top_middle",
}
REWARD_LIST_TITLE_TEMPLATE_THRESHOLD = 0.90
REWARD_LIST_TITLE_SEARCH_REGION = (180, 200, 460, 300)
START_HOME_TEMPLATE_THRESHOLD = 0.90


@dataclass(frozen=True)
class MapCompletionOutcome:
    completed: bool
    win_recorded: bool
    total_win: Optional[int]
    first_win_done: bool


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


def find_map_completion_blocker(
    frame_gray: np.ndarray,
    blocker_templates: tuple[tuple[Path, np.ndarray], ...],
    find_template_fn,
) -> Optional[tuple[int, int, float, Path]]:
    for blocker_path, blocker_template in blocker_templates:
        x, y, score = find_template_fn(
            frame_gray,
            blocker_template,
            blocker_path.name,
            click_position=MAP_COMPLETION_BLOCKER_CLICK_POSITIONS.get(
                blocker_path.name,
                "center",
            ),
        )
        if score >= MAP_COMPLETION_BLOCKER_THRESHOLD:
            return x, y, score, blocker_path
    return None


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
    reward_followup_click_count = 0
    reward_click_position: Optional[tuple[int, int]] = None
    reward_list_title_seen = False
    while await flow_checkpoint_fn(stop_event):
        frame_bgr = await capture_page_bgr_fn(page)
        frame_gray = to_grayscale_fn(frame_bgr)

        if reward_click_position is None:
            reward_matches = find_template_matches_fn(
                frame_gray,
                win_reward_template,
                win_reward_template_path.name,
                threshold=WIN_REWARD_TEMPLATE_THRESHOLD,
                scales=(1.0,),
            )
        else:
            reward_matches = []

        if reward_matches:
            if not first_win_done:
                first_win_done = True
                print(
                    "Reward appeared without daily first-win prompt; "
                    "daily check disabled for this run.",
                    flush=True,
                )
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
            reward_click_position = (center_x, click_y)
            await click_fn(page, center_x, click_y)
            if not await wait_for_flow_timeout_fn(
                page, WIN_REWARD_RECHECK_MS, stop_event
            ):
                break
            continue

        if not first_win_done:
            daily_first_win_match = map_first_win.find_daily_first_win(
                frame_gray,
                daily_first_win_template,
                daily_first_win_template_path,
                find_template_fn,
            )
            if daily_first_win_match is not None:
                daily_x, daily_y, daily_score = daily_first_win_match
                print(
                    f"Daily first-win prompt at {daily_x},{daily_y}, "
                    f"score={daily_score:.3f}; entering isolated flow.",
                    flush=True,
                )
                first_win_done = await map_first_win.handle_daily_first_win(
                    page,
                    stop_event,
                    frame_gray,
                    daily_first_win_template=daily_first_win_template,
                    daily_first_win_template_path=daily_first_win_template_path,
                    daily_first_win_checkbox_template=(
                        daily_first_win_checkbox_template
                    ),
                    daily_first_win_checkbox_template_path=(
                        daily_first_win_checkbox_template_path
                    ),
                    daily_first_win_checked_template=(
                        daily_first_win_checked_template
                    ),
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
                )
                if not first_win_done:
                    break
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
            if not await wait_for_flow_timeout_fn(
                page, WIN_REWARD_RECHECK_MS, stop_event
            ):
                break
            continue

        if reward_click_position is not None and not reward_list_title_seen:
            click_x, click_y = reward_click_position
            print(
                "Reward list title not found; clicking previous win reward "
                f"position at {click_x},{click_y} and checking again in 2s.",
                flush=True,
            )
            await click_fn(page, click_x, click_y)
            if not await wait_for_flow_timeout_fn(
                page, WIN_REWARD_RECHECK_MS, stop_event
            ):
                break
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
                return MapCompletionOutcome(
                    True, win_recorded, total_win, first_win_done
                )

        if reward_followup_click_count < WIN_REWARD_FOLLOWUP_CLICK_COUNT:
            next_click = reward_followup_click_count + 1
            print(
                "No win reward remains; waiting 3s then clicking "
                f"{WIN_REWARD_FOLLOWUP_CLICK[0]},"
                f"{WIN_REWARD_FOLLOWUP_CLICK[1]} "
                f"({next_click}/{WIN_REWARD_FOLLOWUP_CLICK_COUNT}) "
                "before rechecking.",
                flush=True,
            )
            if not await wait_for_flow_timeout_fn(
                page, WIN_REWARD_EMPTY_DELAY_MS, stop_event
            ):
                break
            await click_fn(page, *WIN_REWARD_FOLLOWUP_CLICK)
            reward_followup_click_count += 1
            continue

        blocker_match = find_map_completion_blocker(
            frame_gray,
            blocker_templates,
            find_template_fn,
        )
        if blocker_match is not None:
            blocker_x, blocker_y, blocker_score, blocker_path = blocker_match
            print(
                f"Post-map blocker {blocker_path.name} at "
                f"{blocker_x},{blocker_y}, score={blocker_score:.3f}; clearing.",
                flush=True,
            )
            await click_fn(page, blocker_x, blocker_y)
            if not await wait_for_flow_timeout_fn(page, poll_ms, stop_event):
                break
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
            return MapCompletionOutcome(
                True, win_recorded, total_win, first_win_done
            )

        await wait_for_flow_timeout_fn(page, poll_ms, stop_event)

    print("Auto-map flow stopped while waiting for home reward.", flush=True)
    return MapCompletionOutcome(False, win_recorded, total_win, first_win_done)
