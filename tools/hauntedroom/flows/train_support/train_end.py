"""Train end lifecycle: detect train victory and click the bottom red button."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Callable

import numpy as np

from hauntedroom.core.mouse import bot_click
from hauntedroom.core.runtime import wait_for_flow_timeout
from hauntedroom.core.template_matching import find_template, load_template
from hauntedroom.core.terminal import GREEN, colorize
from hauntedroom.flows.automap_support.map.model_state import MapEndOutcome, MapState
from hauntedroom.flows.train_support.common import (
    TRAIN_WIN_BUTTON_GEOMETRY,
    TRAIN_WIN_BUTTON_REGION,
    TRAIN_WIN_TEMPLATE_PATH,
    TRAIN_WIN_TEMPLATE_THRESHOLD,
)
from hauntedroom.vision.buttons import ButtonGeometry, find_colored_button

TRAIN_WIN_CHECK_INTERVAL_SEC = 1.0


async def _click(page, x: int, y: int) -> None:
    await bot_click(page, (x, y))


class TrainEndLifecycle:
    """Detect train victory, click the bottom red button, and complete train flow."""

    def __init__(
        self,
        page,
        stop_event: asyncio.Event | None = None,
        *,
        state: MapState | None = None,
        on_win: Callable[[], int] | None = None,
        template: np.ndarray | None = None,
        template_path: Path = TRAIN_WIN_TEMPLATE_PATH,
        template_threshold: float = TRAIN_WIN_TEMPLATE_THRESHOLD,
        button_region: tuple[int, int, int, int] = TRAIN_WIN_BUTTON_REGION,
        button_geometry: ButtonGeometry = TRAIN_WIN_BUTTON_GEOMETRY,
        click_fn: Callable[[object, int, int], object] = _click,
        wait_for_flow_timeout_fn=wait_for_flow_timeout,
        find_template_fn=find_template,
        find_colored_button_fn=find_colored_button,
    ) -> None:
        self.page = page
        self.stop_event = stop_event
        self.state = state or MapState()
        self.on_win = on_win
        self.template_path = template_path
        self.template = (
            template
            if template is not None
            else load_template(template_path)
        )
        self.template_threshold = template_threshold
        self.button_region = button_region
        self.button_geometry = button_geometry
        self.click_fn = click_fn
        self.wait_for_flow_timeout_fn = wait_for_flow_timeout_fn
        self.find_template_fn = find_template_fn
        self.find_colored_button_fn = find_colored_button_fn
        self.last_check_time: float | None = None
        self.loop = asyncio.get_running_loop()

    async def handle_map_end(
        self,
        frame_gray: np.ndarray,
        frame_bgr: np.ndarray | None = None,
    ) -> MapEndOutcome:
        if self.state.completed:
            return MapEndOutcome(handled=True, completed=True)

        now = self.loop.time()
        if (
            self.last_check_time is not None
            and now - self.last_check_time < TRAIN_WIN_CHECK_INTERVAL_SEC
        ):
            return MapEndOutcome(handled=False)

        self.last_check_time = now

        x, y, score = self.find_template_fn(
            frame_gray,
            self.template,
            self.template_path.name,
            scales=(1.0,),
        )
        if score < self.template_threshold:
            return MapEndOutcome(handled=False)

        if frame_bgr is None:
            return MapEndOutcome(handled=True, completed=False)

        button = self.find_colored_button_fn(
            frame_bgr,
            self.button_region,
            "red",
            self.button_geometry,
        )
        if button is None:
            print(
                f"Train win detected (score={score:.3f}), waiting for bottom red button...",
                flush=True,
            )
            return MapEndOutcome(handled=True, completed=False)

        click_x, click_y = button.center
        print(
            colorize(
                f"Train win detected (score={score:.3f}); clicking bottom red button at "
                f"{click_x},{click_y} to complete train flow.",
                GREEN,
            ),
            flush=True,
        )
        await self.click_fn(self.page, click_x, click_y)

        self.state.completed = True
        self.state.win_recorded = True
        if self.on_win is not None:
            self.state.total_win = self.on_win()

        await self.wait_for_flow_timeout_fn(self.page, 1000, self.stop_event)

        return MapEndOutcome(handled=True, completed=True)
