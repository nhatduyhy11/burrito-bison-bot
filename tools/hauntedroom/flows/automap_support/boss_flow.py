"""Boss policy orchestration for the auto-map battle flow."""

from dataclasses import dataclass
from typing import Optional

import numpy as np


EXIT_CLICK_TEMPLATE_THRESHOLD = 0.90


@dataclass(frozen=True)
class BossCriticalOutcome:
    handled: bool
    boss_handoff_requested: bool = False
    final_boss_pet_deployed: Optional[bool] = None
    boss_detection_logged: bool = False


async def handle_boss_critical(
    page,
    stop_event,
    frame_bgr: np.ndarray,
    frame_gray: np.ndarray,
    *,
    boss_hp_template: np.ndarray,
    exit_click_template: np.ndarray,
    exit_click_template_name: str,
    click_exit_on_boss: bool,
    final_boss_pet_deployed: bool,
    boss_detection_logged: bool,
    find_boss_health_bar_fn,
    boss_progress_is_full_fn,
    find_template_fn,
    deploy_boss_pet_fn,
    click_fn,
) -> BossCriticalOutcome:
    match = find_boss_health_bar_fn(frame_gray, boss_hp_template)
    if match is None:
        return BossCriticalOutcome(False, boss_detection_logged=False)

    x, y, score = match
    is_final_boss = boss_progress_is_full_fn(frame_bgr)
    boss_kind = "Final boss" if is_final_boss else "Mini-boss"
    should_log_detection = not boss_detection_logged
    if should_log_detection:
        print(
            f"{boss_kind} HP entered upper search region at {x},{y}, "
            f"score={score:.3f}; click_exit_on_boss={click_exit_on_boss}.",
            flush=True,
        )

    pause_for_detected_boss = getattr(
        stop_event,
        "pause_for_detected_boss",
        None,
    )
    if (
        pause_for_detected_boss is not None
        and pause_for_detected_boss(is_final_boss=is_final_boss)
    ):
        print(f"Start-auto loop paused at {boss_kind.lower()}.", flush=True)
        return BossCriticalOutcome(True, boss_detection_logged=True)

    if click_exit_on_boss:
        exit_x, exit_y, exit_score = find_template_fn(
            frame_gray,
            exit_click_template,
            exit_click_template_name,
        )
        if exit_score < EXIT_CLICK_TEMPLATE_THRESHOLD:
            if should_log_detection:
                print(
                    f"exit_click not found for {boss_kind} "
                    f"(score={exit_score:.3f}).",
                    flush=True,
                )
            return BossCriticalOutcome(False, boss_detection_logged=True)

        print(
            f"clicking exit_click once at {exit_x},{exit_y} and stopping auto-map.",
            flush=True,
        )
        await click_fn(page, exit_x, exit_y)
        return BossCriticalOutcome(
            True,
            boss_handoff_requested=True,
            boss_detection_logged=True,
        )

    if is_final_boss and not final_boss_pet_deployed:
        deployed = await deploy_boss_pet_fn(
            page,
            boss_position=(x, y),
            frame_bgr=frame_bgr,
            stop_event=stop_event,
        )
        return BossCriticalOutcome(
            True,
            final_boss_pet_deployed=deployed,
            boss_detection_logged=True,
        )

    return BossCriticalOutcome(False, boss_detection_logged=True)
