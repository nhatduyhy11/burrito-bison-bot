"""Hero level-up orchestration for the auto-map battle flow."""

from dataclasses import dataclass
from pathlib import Path

import numpy as np


HERO_LEVELUP_OPEN_CLICK = (320, 640)
HERO_LEVELUP_OPTION_SETTLE_MS = 1_500
HERO_LEVELUP_OPTION_POLL_MS = 200
HERO_LEVELUP_OPTION_MAX_POLLS = 10
HERO_LEVELUP_SELECTION_SETTLE_MS = 600
HERO_FALLBACK_SCREENSHOT_DIR = Path(".tmp/hauntedroom-hero-fallbacks")


@dataclass(frozen=True)
class HeroLevelupOutcome:
    handled: bool
    initial_gear_unlocked: bool = False


async def handle_hero_levelup(
    page,
    stop_event,
    frame_bgr: np.ndarray,
    *,
    matcher,
    hero_levelup_price_is_available_fn,
    capture_page_bgr_fn,
    save_screenshot_fn,
    click_fn,
    wait_for_flow_timeout_fn,
    flow_checkpoint_fn,
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
        choice = matcher.find_choice(option_frame)
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
            choice.fallback_color == "other"
            and choice.fallback_option_count == 3
        ):
            await save_screenshot_fn(
                page,
                "no-priority-no-purple-hero-option",
                HERO_FALLBACK_SCREENSHOT_DIR,
                "Hero fallback tracking",
            )
        print(
            f"No prioritized hero option matched; clicking visible fallback "
            f"card at {choice.x},{choice.y}.",
            flush=True,
        )
        await click_fn(page, choice.x, choice.y)
        await wait_for_flow_timeout_fn(
            page, HERO_LEVELUP_SELECTION_SETTLE_MS, stop_event
        )
        return HeroLevelupOutcome(True, initial_gear_unlocked=True)

    print("No visible hero level-up option found; skipping.", flush=True)
    return HeroLevelupOutcome(True)
