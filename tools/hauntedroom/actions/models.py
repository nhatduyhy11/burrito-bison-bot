from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar, Literal, Optional, Union

from hauntedroom.core.template import DEFAULT_TEMPLATE_THRESHOLD, TEMPLATE_SCALES

from .defaults import (
    DEFAULT_CLICK_DELAY_MS,
    DEFAULT_TEMPLATE_POLL_MS,
    DEFAULT_TEMPLATE_TIMEOUT_MS,
)


@dataclass(frozen=True)
class ClickAction:
    x: int
    y: int
    button: str = "left"
    note: Optional[str] = None

    type: ClassVar[Literal["click"]] = "click"


@dataclass(frozen=True)
class ClickTemplateAction:
    template_path: Path
    threshold: float = DEFAULT_TEMPLATE_THRESHOLD
    timeout_ms: int = DEFAULT_TEMPLATE_TIMEOUT_MS
    poll_ms: int = DEFAULT_TEMPLATE_POLL_MS
    delay_ms: int = DEFAULT_CLICK_DELAY_MS
    repeat_delay_ms: Optional[int] = None
    click_count: int = 1
    recheck_before_repeat: bool = False
    button: str = "left"
    note: Optional[str] = None
    skip_if_template_path: Optional[Path] = None
    click_position: str = "center"
    template_scales: tuple[float, ...] = TEMPLATE_SCALES
    skip_template_scales: tuple[float, ...] = TEMPLATE_SCALES

    type: ClassVar[Literal["click_template"]] = "click_template"

    @property
    def effective_repeat_delay_ms(self) -> int:
        return self.delay_ms if self.repeat_delay_ms is None else self.repeat_delay_ms


@dataclass(frozen=True)
class ClearBlockersAction:
    blocker_paths: tuple[Path, ...]
    until_template_path: Path
    threshold: float = DEFAULT_TEMPLATE_THRESHOLD
    timeout_ms: int = DEFAULT_TEMPLATE_TIMEOUT_MS
    poll_ms: int = DEFAULT_TEMPLATE_POLL_MS
    delay_ms: int = DEFAULT_CLICK_DELAY_MS
    click_positions: dict[str, str] = field(default_factory=dict)
    note: Optional[str] = None
    until_template_scales: tuple[float, ...] = TEMPLATE_SCALES

    type: ClassVar[Literal["clear_blockers"]] = "clear_blockers"


@dataclass(frozen=True)
class WaitAction:
    ms: int
    note: Optional[str] = None

    type: ClassVar[Literal["wait"]] = "wait"


Action = Union[ClickAction, ClickTemplateAction, ClearBlockersAction, WaitAction]
