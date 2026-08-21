"""Map blocker detection and cleanup."""

from pathlib import Path
from typing import Optional

import numpy as np

from .model_state import MapBlockerContext, MapLifecycleStep

MAP_BLOCKER_THRESHOLD = 0.90
MAP_BLOCKER_CLICK_POSITIONS = {
    "overlay_newbie.png": "top_middle",
}


def find_map_blocker(
    frame_gray: np.ndarray,
    blocker_templates: tuple[tuple[Path, np.ndarray], ...],
    find_template_fn,
) -> Optional[tuple[int, int, float, Path]]:
    for blocker_path, blocker_template in blocker_templates:
        x, y, score = find_template_fn(
            frame_gray,
            blocker_template,
            blocker_path.name,
            click_position=MAP_BLOCKER_CLICK_POSITIONS.get(
                blocker_path.name,
                "center",
            ),
        )
        if score >= MAP_BLOCKER_THRESHOLD:
            return x, y, score, blocker_path
    return None


async def handle_map_blocker(
    context: MapBlockerContext,
    frame_gray: np.ndarray,
) -> MapLifecycleStep:
    blocker_match = find_map_blocker(
        frame_gray,
        context.blocker_templates,
        context.find_template_fn,
    )
    if blocker_match is None:
        return MapLifecycleStep.NOT_HANDLED

    blocker_x, blocker_y, blocker_score, blocker_path = blocker_match
    print(
        f"Map blocker {blocker_path.name} at "
        f"{blocker_x},{blocker_y}, score={blocker_score:.3f}; clearing.",
        flush=True,
    )
    await context.click_fn(context.page, blocker_x, blocker_y)
    ready = await context.wait_for_flow_timeout_fn(
        context.page,
        context.poll_ms,
        context.stop_event,
    )
    return MapLifecycleStep.CONTINUE if ready else MapLifecycleStep.STOP
