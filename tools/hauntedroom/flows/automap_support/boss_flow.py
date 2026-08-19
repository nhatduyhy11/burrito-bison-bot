"""Boss policy orchestration for the auto-map battle flow."""

from dataclasses import dataclass
from typing import Optional

import numpy as np

from hauntedroom.core.terminal import YELLOW, colorize


EXIT_CLICK_TEMPLATE_THRESHOLD = 0.90


@dataclass(frozen=True)
class BossCriticalOutcome:
    handled: bool
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
        detection_message = (
            f"{boss_kind} HP entered upper search region at {x},{y}, "
            f"score={score:.3f}."
        )
        print(
            colorize(detection_message, YELLOW)
            if is_final_boss
            else detection_message,
            flush=True,
        )

    boss_pause_matches = getattr(stop_event, "boss_pause_matches", None)
    pause_for_detected_boss = getattr(
        stop_event,
        "pause_for_detected_boss",
        None,
    )
    if (
        boss_pause_matches is not None
        and pause_for_detected_boss is not None
        and boss_pause_matches(is_final_boss=is_final_boss)
    ):
        try:
            pause_match = find_template_fn(
                frame_gray,
                exit_click_template,
                exit_click_template_name,
            )
        except Exception as error:
            print(
                f"Game pause detection failed for {boss_kind}: {error}; "
                "pausing script anyway.",
                flush=True,
            )
        else:
            exit_x, exit_y, exit_score = pause_match
            if exit_score < EXIT_CLICK_TEMPLATE_THRESHOLD:
                print(
                    f"Game pause button was not found for {boss_kind} "
                    f"(score={exit_score:.3f}); pausing script anyway.",
                    flush=True,
                )
            else:
                print(
                    f"Clicking game pause at {exit_x},{exit_y} for {boss_kind}.",
                    flush=True,
                )
                try:
                    await click_fn(page, exit_x, exit_y)
                except Exception as error:
                    print(
                        f"Game pause click failed for {boss_kind}: {error}; "
                        "pausing script anyway.",
                        flush=True,
                    )

        if pause_for_detected_boss(is_final_boss=is_final_boss):
            print(
                colorize(
                    f"Auto-map flow paused at {boss_kind.lower()}.", YELLOW
                ),
                flush=True,
            )
        return BossCriticalOutcome(True, boss_detection_logged=True)

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
