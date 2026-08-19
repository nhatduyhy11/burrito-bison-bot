"""Detect templates over time against live browser-page captures.

Dependency direction: this module builds on ``template``; that lower-level
matching module must never import this higher-level detection module.
"""

import asyncio
from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional

import numpy as np

from hauntedroom.core.runtime import (
    flow_checkpoint,
    flow_time,
    save_timeout_screenshot,
    wait_for_flow_timeout,
)
from hauntedroom.core.template import (
    TEMPLATE_SCALES,
    Region,
    TemplateMatch,
    find_template,
)
from hauntedroom.core.vision import capture_page_grayscale


class TemplateWaitStatus(Enum):
    MATCHED = auto()
    ALTERNATIVE_MATCHED = auto()
    STOPPED = auto()


@dataclass(frozen=True)
class TemplateWaitResult:
    status: TemplateWaitStatus
    match: Optional[TemplateMatch] = None


async def wait_for_template(
    page,
    template: np.ndarray,
    template_name: str,
    threshold: float,
    timeout_ms: int,
    poll_ms: int,
    stop_event: Optional[asyncio.Event] = None,
    skip_template: Optional[np.ndarray] = None,
    skip_template_name: Optional[str] = None,
    click_position: str = "center",
    template_scales: tuple[float, ...] = TEMPLATE_SCALES,
    skip_template_scales: tuple[float, ...] = TEMPLATE_SCALES,
    region: Optional[Region] = None,
) -> TemplateWaitResult:
    deadline = flow_time(stop_event) + timeout_ms / 1000
    best_score = -1.0
    best_skip_score = -1.0

    while True:
        if not await flow_checkpoint(stop_event):
            return TemplateWaitResult(TemplateWaitStatus.STOPPED)
        screenshot = await capture_page_grayscale(page)
        center_x, center_y, score = find_template(
            screenshot,
            template,
            template_name,
            click_position,
            scales=template_scales,
            region=region,
        )
        best_score = max(best_score, score)

        if score >= threshold:
            return TemplateWaitResult(
                TemplateWaitStatus.MATCHED,
                (center_x, center_y, score),
            )

        if skip_template is not None and skip_template_name is not None:
            _, _, skip_score = find_template(
                screenshot,
                skip_template,
                skip_template_name,
                scales=skip_template_scales,
            )
            best_skip_score = max(best_skip_score, skip_score)
            if skip_score >= threshold:
                return TemplateWaitResult(TemplateWaitStatus.ALTERNATIVE_MATCHED)

        if flow_time(stop_event) >= deadline:
            screenshot_path = await save_timeout_screenshot(page, template_name)
            screenshot_suffix = (
                f", screenshot={screenshot_path}" if screenshot_path else ""
            )
            skip_suffix = (
                f", best {skip_template_name} score={best_skip_score:.3f}"
                if skip_template_name is not None
                else ""
            )
            raise TimeoutError(
                f"Timed out waiting for {template_name!r}; "
                f"best score={best_score:.3f}, threshold={threshold:.3f}"
                f"{skip_suffix}{screenshot_suffix}."
            )

        if not await wait_for_flow_timeout(page, poll_ms, stop_event):
            return TemplateWaitResult(TemplateWaitStatus.STOPPED)
