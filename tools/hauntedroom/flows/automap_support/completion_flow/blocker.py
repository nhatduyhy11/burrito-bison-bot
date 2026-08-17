"""Post-map blocker detection and cleanup."""

from pathlib import Path
from typing import Optional

import numpy as np

from hauntedroom.flows.automap_support.completion_flow.state import (
    CompletionStep,
    MapCompletionBlockerContext,
)

MAP_COMPLETION_BLOCKER_THRESHOLD = 0.90
MAP_COMPLETION_BLOCKER_CLICK_POSITIONS = {
    "overlay_newbie.png": "top_middle",
}


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


async def handle_completion_blocker(
    context: MapCompletionBlockerContext,
    frame_gray: np.ndarray,
) -> CompletionStep:
    blocker_match = find_map_completion_blocker(
        frame_gray,
        context.blocker_templates,
        context.find_template_fn,
    )
    if blocker_match is None:
        return CompletionStep.NOT_HANDLED

    blocker_x, blocker_y, blocker_score, blocker_path = blocker_match
    print(
        f"Post-map blocker {blocker_path.name} at "
        f"{blocker_x},{blocker_y}, score={blocker_score:.3f}; clearing.",
        flush=True,
    )
    await context.click_fn(context.page, blocker_x, blocker_y)
    ready = await context.wait_for_flow_timeout_fn(
        context.page,
        context.poll_ms,
        context.stop_event,
    )
    return CompletionStep.CONTINUE if ready else CompletionStep.STOP
