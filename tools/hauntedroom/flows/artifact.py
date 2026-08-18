"""Activate every available artifact across all rarity tabs."""

import asyncio
from pathlib import Path
from typing import Optional

import numpy as np

from hauntedroom.core.mouse import click_and_wait
from hauntedroom.core.runtime import flow_checkpoint, wait_for_flow_timeout
from hauntedroom.core.template import (
    TemplateMatch,
    find_template,
    find_template_in_region,
    load_template,
)
from hauntedroom.core.vision import capture_page_grayscale


ROOMS_DIR = Path(__file__).resolve().parents[2] / "rooms"
ARTIFACT_MARK_TEMPLATE_PATH = ROOMS_DIR / "misc" / "research_available.png"
ARTIFACT_CLOSE_TEMPLATE_PATH = ROOMS_DIR / "blocker" / "lubu_close.png"

# The artifact screen has four fixed rarity tabs and ten fixed content slots.
# Keeping the searches inside these regions prevents notification marks in the
# bottom navigation from being mistaken for artifact availability.
ARTIFACT_TAB_REGIONS = (
    (150, 340, 248, 385),
    (245, 340, 325, 385),
    (325, 340, 405, 385),
    (405, 340, 490, 385),
)
ARTIFACT_CONTENT_REGION = (120, 390, 520, 600)
ARTIFACT_ACTIVATE_REGION = (220, 540, 420, 620)

ARTIFACT_TAB_SCALE = (0.8,)
ARTIFACT_CONTENT_SCALE = (0.9,)
ARTIFACT_ACTIVATE_SCALE = (0.5,)
ARTIFACT_CLOSE_SCALE = (1.0,)
ARTIFACT_TAB_THRESHOLD = 0.70
ARTIFACT_CONTENT_THRESHOLD = 0.80
ARTIFACT_ACTIVATE_THRESHOLD = 0.60
ARTIFACT_CLOSE_THRESHOLD = 0.90

ARTIFACT_SETTLE_MS = 800
ARTIFACT_ACTIVATION_REPEAT_MS = 1000
ARTIFACT_IDLE_CONFIRM_MS = 2000
ARTIFACT_POPUP_MAX_ATTEMPTS = 4
ARTIFACT_ACTIVATE_MAX_CLICKS = 10

def find_artifact_tabs(
    frame: np.ndarray,
    mark_template: np.ndarray,
) -> list[tuple[int, int, int, float]]:
    """Return marked rarity tabs from left to right."""
    matches = []
    for tab_index, region in enumerate(ARTIFACT_TAB_REGIONS):
        match = find_template_in_region(
            frame,
            mark_template,
            ARTIFACT_MARK_TEMPLATE_PATH.name,
            region,
            ARTIFACT_TAB_THRESHOLD,
            click_position="bottom_left",
            scales=ARTIFACT_TAB_SCALE,
        )
        if match is not None:
            matches.append((tab_index, *match))
    return matches


def find_artifact_item(
    frame: np.ndarray,
    mark_template: np.ndarray,
) -> Optional[TemplateMatch]:
    """Return one marked artifact card, offset into the card for clicking."""
    return find_template_in_region(
        frame,
        mark_template,
        ARTIFACT_MARK_TEMPLATE_PATH.name,
        ARTIFACT_CONTENT_REGION,
        ARTIFACT_CONTENT_THRESHOLD,
        click_position="bottom_left",
        scales=ARTIFACT_CONTENT_SCALE,
    )


def find_artifact_activation(
    frame: np.ndarray,
    mark_template: np.ndarray,
) -> Optional[TemplateMatch]:
    """Return the marked Activate button inside the artifact popup."""
    return find_template_in_region(
        frame,
        mark_template,
        ARTIFACT_MARK_TEMPLATE_PATH.name,
        ARTIFACT_ACTIVATE_REGION,
        ARTIFACT_ACTIVATE_THRESHOLD,
        click_position="bottom_left",
        scales=ARTIFACT_ACTIVATE_SCALE,
    )


def find_artifact_popup_close(
    frame: np.ndarray,
    close_template: np.ndarray,
) -> Optional[TemplateMatch]:
    """Use the existing Lu Bu close icon to detect and close the popup."""
    if frame.ndim != 2 or frame.shape != (720, 640):
        return None
    x, y, score = find_template(
        frame,
        close_template,
        ARTIFACT_CLOSE_TEMPLATE_PATH.name,
        scales=ARTIFACT_CLOSE_SCALE,
    )
    if score < ARTIFACT_CLOSE_THRESHOLD:
        return None
    return x, y, score


async def _click_activation_three_times(
    page,
    x: int,
    y: int,
    stop_event,
) -> bool:
    """Click Activate once plus two repeats, spaced one second apart."""
    for _ in range(3):
        if not await click_and_wait(
            page,
            (x, y),
            ARTIFACT_ACTIVATION_REPEAT_MS,
            stop_event,
        ):
            return False
    return True


async def _open_artifact_popup(
    page,
    item: TemplateMatch,
    close_template: np.ndarray,
    stop_event,
    delay_ms: int,
) -> Optional[TemplateMatch]:
    x, y, _score = item
    for attempt in range(1, ARTIFACT_POPUP_MAX_ATTEMPTS + 1):
        if not await click_and_wait(page, (x, y), delay_ms, stop_event):
            return None
        close_match = find_artifact_popup_close(
            await capture_page_grayscale(page), close_template
        )
        if close_match is not None:
            return close_match
        print(
            "Artifact popup not detected after card click "
            f"({attempt}/{ARTIFACT_POPUP_MAX_ATTEMPTS}); retrying {x},{y}.",
            flush=True,
        )
    return None


async def _activate_current_artifact(
    page,
    mark_template: np.ndarray,
    close_template: np.ndarray,
    stop_event,
) -> Optional[int]:
    activation_count = 0
    while activation_count < ARTIFACT_ACTIVATE_MAX_CLICKS:
        if not await flow_checkpoint(stop_event):
            return None
        frame = await capture_page_grayscale(page)
        # The low activation region overlaps the bottom navigation vertically.
        # Only open that search region after the close icon proves a popup is
        # present; list state must stay inside the narrower tab/content ROIs.
        if find_artifact_popup_close(frame, close_template) is None:
            return activation_count

        activation = find_artifact_activation(frame, mark_template)
        if activation is None:
            return activation_count

        x, y, score = activation
        activation_count += 1
        print(
            f"Artifact activation mark at {x},{y}, score={score:.3f}; "
            "clicking once plus two repeats with a "
            f"{ARTIFACT_ACTIVATION_REPEAT_MS}ms gap.",
            flush=True,
        )
        if not await _click_activation_three_times(page, x, y, stop_event):
            return None

    print(
        "Artifact activation mark remained after "
        f"{ARTIFACT_ACTIVATE_MAX_CLICKS} clicks; stopping safely.",
        flush=True,
    )
    return None


async def _process_artifact_item(
    page,
    item: TemplateMatch,
    mark_template: np.ndarray,
    close_template: np.ndarray,
    stop_event,
    delay_ms: int,
) -> Optional[int]:
    close_match = await _open_artifact_popup(
        page,
        item,
        close_template,
        stop_event,
        delay_ms,
    )
    if close_match is None:
        if stop_event is not None and stop_event.is_set():
            return None
        print(
            "Artifact popup did not appear after all retries; stopping safely.",
            flush=True,
        )
        return None

    activated = await _activate_current_artifact(
        page, mark_template, close_template, stop_event
    )
    if activated is None:
        return None

    # Never click a stale close coordinate. Activation may close the popup by
    # itself, so only click when the close pattern is still present now.
    fresh_close = find_artifact_popup_close(
        await capture_page_grayscale(page), close_template
    )
    if fresh_close is not None:
        close_x, close_y, close_score = fresh_close
        print(
            f"Artifact popup close at {close_x},{close_y}, "
            f"score={close_score:.3f}; closing.",
            flush=True,
        )
        if not await click_and_wait(
            page, (close_x, close_y), delay_ms, stop_event
        ):
            return None
    return activated


async def _confirm_artifact_idle(
    page,
    mark_template: np.ndarray,
    close_template: np.ndarray,
    stop_event,
    delay_ms: int,
    idle_confirm_ms: int,
) -> tuple[Optional[bool], int]:
    """Require a quiet window with neither actionable marks nor popup close."""
    quiet_ms = 0
    extra_activations = 0
    while True:
        if not await flow_checkpoint(stop_event):
            return None, extra_activations

        frame = await capture_page_grayscale(page)
        close_match = find_artifact_popup_close(frame, close_template)
        if close_match is not None:
            # Popup state: widen the mark search down to the Activate button.
            # The close signal gates this detector so bottom-nav badges cannot
            # be interpreted as activation marks while the list is visible.
            activation = find_artifact_activation(frame, mark_template)
            if activation is not None:
                x, y, score = activation
                print(
                    f"Artifact activation mark returned at {x},{y}, "
                    f"score={score:.3f}; clicking once plus two repeats "
                    f"with a {ARTIFACT_ACTIVATION_REPEAT_MS}ms gap.",
                    flush=True,
                )
                if not await _click_activation_three_times(
                    page, x, y, stop_event
                ):
                    return None, extra_activations
                extra_activations += 1
                quiet_ms = 0
                continue

            close_x, close_y, close_score = close_match
            print(
                f"Artifact popup is still open at {close_x},{close_y}, "
                f"score={close_score:.3f}; clicking close again.",
                flush=True,
            )
            if not await click_and_wait(
                page, (close_x, close_y), delay_ms, stop_event
            ):
                return None, extra_activations
            quiet_ms = 0
            continue

        # List state: these ROIs end above the Equipment / Holy Artifact /
        # Artifact / Machine / Pet navigation row.
        if find_artifact_tabs(frame, mark_template) or find_artifact_item(
            frame, mark_template
        ):
            return False, extra_activations

        if quiet_ms >= idle_confirm_ms:
            return True, extra_activations

        if not await wait_for_flow_timeout(page, delay_ms, stop_event):
            return None, extra_activations
        quiet_ms += delay_ms if delay_ms > 0 else idle_confirm_ms


async def run_artifact_flow(
    page,
    stop_event: Optional[asyncio.Event] = None,
    mark_template_path: Path = ARTIFACT_MARK_TEMPLATE_PATH,
    close_template_path: Path = ARTIFACT_CLOSE_TEMPLATE_PATH,
    delay_ms: int = ARTIFACT_SETTLE_MS,
    idle_confirm_ms: int = ARTIFACT_IDLE_CONFIRM_MS,
) -> bool:
    """Process marked artifacts tab-by-tab until no actionable mark remains."""
    mark_template = load_template(mark_template_path)
    close_template = load_template(close_template_path)
    artifact_count = 0

    while await flow_checkpoint(stop_event):
        frame = await capture_page_grayscale(page)
        tab_matches = find_artifact_tabs(frame, mark_template)
        if not tab_matches:
            # A tab badge may disappear one frame before its current content
            # badge, so finish that visible item before entering idle polling.
            item = find_artifact_item(frame, mark_template)
            if item is not None:
                activated = await _process_artifact_item(
                    page,
                    item,
                    mark_template,
                    close_template,
                    stop_event,
                    delay_ms,
                )
                if activated is None:
                    return False
                artifact_count += activated
                continue

            idle, extra_activations = await _confirm_artifact_idle(
                page,
                mark_template,
                close_template,
                stop_event,
                delay_ms,
                idle_confirm_ms,
            )
            artifact_count += extra_activations
            if idle is None:
                return False
            if not idle:
                continue
            print(
                "No artifact marks or popup close detected for at least "
                f"{idle_confirm_ms}ms; activated {artifact_count}. Runner is idle.",
                flush=True,
            )
            return True

        pass_count = 0
        for tab_index, tab_x, tab_y, tab_score in tab_matches:
            if not await flow_checkpoint(stop_event):
                return False
            print(
                f"Artifact tab {tab_index + 1} marked at {tab_x},{tab_y}, "
                f"score={tab_score:.3f}; opening.",
                flush=True,
            )
            if not await click_and_wait(
                page, (tab_x, tab_y), delay_ms, stop_event
            ):
                return False

            while await flow_checkpoint(stop_event):
                item = find_artifact_item(
                    await capture_page_grayscale(page), mark_template
                )
                if item is None:
                    break

                item_x, item_y, item_score = item
                print(
                    f"Marked artifact card at {item_x},{item_y}, "
                    f"score={item_score:.3f}; opening popup.",
                    flush=True,
                )
                activated = await _process_artifact_item(
                    page,
                    item,
                    mark_template,
                    close_template,
                    stop_event,
                    delay_ms,
                )
                if activated is None:
                    return False
                artifact_count += activated
                pass_count += 1

        if pass_count == 0:
            print(
                "Marked artifact tabs remain, but none contains an actionable "
                "card; rechecking signals after the click settle interval.",
                flush=True,
            )

    print("Artifact flow stopped; runner is idle.", flush=True)
    return False
