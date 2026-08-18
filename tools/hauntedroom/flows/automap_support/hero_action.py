"""Hero level-up orchestration for the auto-map battle flow."""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np

from hauntedroom.flows.automap_support.vision.hero_levelup import (
    HERO_ASCEND_TEMPLATE_NAME,
    HeroLevelupFrame,
    find_hero_ascend_matches,
    find_hero_options,
    find_hero_template_match,
    prepare_hero_levelup_frame,
)

HERO_LEVELUP_OPEN_CLICK = (320, 640)
HERO_LEVELUP_OPTION_SETTLE_MS = 1_500
HERO_LEVELUP_OPTION_POLL_MS = 200
HERO_LEVELUP_OPTION_MAX_POLLS = 10
HERO_LEVELUP_SELECTION_SETTLE_MS = 600
HERO_FALLBACK_SCREENSHOT_DIR = Path(".tmp/hauntedroom-hero-fallbacks")
HERO_IGNORED_PRIORITY = 99.0


def _hero_template_priority(template_name: str) -> tuple[float, str]:
    """Parse business priority encoded in a hero template filename."""
    path = Path(template_name)
    prefix = path.stem.split("_", 1)[0]
    try:
        priority = float(prefix)
    except ValueError:
        priority = float("inf")
    return priority, path.name


@dataclass(frozen=True)
class HeroLevelupOutcome:
    handled: bool
    initial_gear_unlocked: bool = False


@dataclass(frozen=True)
class HeroLevelupChoice:
    x: int
    y: int
    template_name: Optional[str] = None
    score: Optional[float] = None
    priority: Optional[float] = None
    fallback_color: Optional[str] = None
    fallback_option_count: Optional[int] = None
    fallback_has_purple: Optional[bool] = None

    @property
    def is_prioritized(self) -> bool:
        return self.template_name is not None


def choose_hero_levelup_option(
    template_paths,
    templates,
    frame: HeroLevelupFrame,
    *,
    find_ascend_fn=find_hero_ascend_matches,
    find_template_fn=find_hero_template_match,
    find_options_fn=find_hero_options,
) -> Optional[HeroLevelupChoice]:
    """Ask vision in business order and stop after the first chosen case."""
    ascend_path = next(
        (
            path
            for path in template_paths
            if path.name == HERO_ASCEND_TEMPLATE_NAME
        ),
        None,
    )
    ascend_matches = (
        find_ascend_fn(frame, templates[ascend_path])
        if ascend_path is not None
        else []
    )
    if ascend_matches:
        x, y, score = min(ascend_matches, key=lambda match: match[0])
        return HeroLevelupChoice(
            x=x,
            y=y,
            template_name=HERO_ASCEND_TEMPLATE_NAME,
            score=score,
            priority=_hero_template_priority(HERO_ASCEND_TEMPLATE_NAME)[0],
        )

    ignored_options = set()
    options = None
    priority_paths = sorted(
        (
            path
            for path in template_paths
            if path.name != HERO_ASCEND_TEMPLATE_NAME
        ),
        key=lambda path: _hero_template_priority(path.name),
    )
    for template_path in priority_paths:
        match = find_template_fn(
            frame,
            template_path,
            templates[template_path],
        )
        if match is None:
            continue
        x, y, score = match
        priority = _hero_template_priority(template_path.name)[0]
        if priority >= HERO_IGNORED_PRIORITY:
            if options is None:
                options = find_options_fn(frame)
            if options:
                ignored_options.add(
                    min(
                        options,
                        key=lambda option: abs(option[0] - x),
                    )
                )
            continue
        return HeroLevelupChoice(
            x=x,
            y=y,
            template_name=template_path.name,
            score=score,
            priority=priority,
        )

    if options is None:
        options = find_options_fn(frame)
    if not options:
        return None
    fallback_options = [
        option for option in options if option not in ignored_options
    ]
    eligible_options = fallback_options or options
    for fallback_color in ("yellow", "purple", "red"):
        matching_options = [
            option
            for option in eligible_options
            if option[2] == fallback_color
        ]
        if matching_options:
            x, y, _color = matching_options[0]
            return HeroLevelupChoice(
                x=x,
                y=y,
                fallback_color=fallback_color,
                fallback_option_count=len(options),
                fallback_has_purple=any(
                    option[2] == "purple" for option in options
                ),
            )
    return None


async def handle_hero_levelup(
    page,
    stop_event,
    frame_bgr: np.ndarray,
    *,
    hero_levelup_template_paths,
    hero_levelup_templates,
    hero_levelup_price_is_available_fn,
    capture_page_bgr_fn,
    save_screenshot_fn,
    click_fn,
    wait_for_flow_timeout_fn,
    flow_checkpoint_fn,
    capture_fallback_screenshots: bool,
) -> HeroLevelupOutcome:
    # Option fallback matching intentionally uses a broad saturated-panel
    # heuristic. Never run it on the battle frame: other open panels can
    # resemble a card and cause an endless click loop. Only inspect options
    # after the fixed price region proves that level-up is available and we
    # have opened the picker ourselves.
    if not hero_levelup_price_is_available_fn(frame_bgr):
        return HeroLevelupOutcome(False)

    print("Hero level-up available; opening option picker.", flush=True)
    await click_fn(page, *HERO_LEVELUP_OPEN_CLICK)
    # The cards flash white while the picker animates in. Waiting for the
    # animation to settle prevents the saturated-panel fallback from winning
    # before the prioritized name/art templates become visible.
    if not await wait_for_flow_timeout_fn(
        page, HERO_LEVELUP_OPTION_SETTLE_MS, stop_event
    ):
        return HeroLevelupOutcome(True)

    choice = None
    for _poll in range(HERO_LEVELUP_OPTION_MAX_POLLS):
        if not await flow_checkpoint_fn(stop_event):
            return HeroLevelupOutcome(True)
        option_frame = await capture_page_bgr_fn(page)
        prepared_frame = prepare_hero_levelup_frame(option_frame)
        choice = (
            choose_hero_levelup_option(
                hero_levelup_template_paths,
                hero_levelup_templates,
                prepared_frame,
            )
            if prepared_frame is not None
            else None
        )
        if choice is not None:
            break
        await wait_for_flow_timeout_fn(
            page, HERO_LEVELUP_OPTION_POLL_MS, stop_event
        )

    if choice is not None and choice.is_prioritized:
        print(
            f"Hero level-up option {choice.template_name!r} matched at "
            f"{choice.x},{choice.y}, score={choice.score:.3f}; "
            "clicking by priority.",
            flush=True,
        )
        await click_fn(page, choice.x, choice.y)
        await wait_for_flow_timeout_fn(
            page, HERO_LEVELUP_SELECTION_SETTLE_MS, stop_event
        )
        return HeroLevelupOutcome(True, initial_gear_unlocked=True)

    if choice is not None:
        # TEMP FALLBACK TRACKING: capture only a complete three-card layout
        # with no purple option. Partial layouts are expected while cards
        # animate in and are not useful tracking evidence.
        if (
            capture_fallback_screenshots
            and choice.fallback_option_count == 3
            and not choice.fallback_has_purple
        ):
            await save_screenshot_fn(
                page,
                "no-priority-no-purple-hero-option",
                HERO_FALLBACK_SCREENSHOT_DIR,
                "Hero fallback tracking",
            )
        print(
            f"No prioritized hero option matched; falling back to "
            f"{choice.fallback_color} hero card at {choice.x},{choice.y}.",
            flush=True,
        )
        await click_fn(page, choice.x, choice.y)
        await wait_for_flow_timeout_fn(
            page, HERO_LEVELUP_SELECTION_SETTLE_MS, stop_event
        )
        return HeroLevelupOutcome(True, initial_gear_unlocked=True)

    print("No visible hero level-up option found; skipping.", flush=True)
    return HeroLevelupOutcome(True)
