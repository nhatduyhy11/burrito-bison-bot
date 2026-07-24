import asyncio
from pathlib import Path
from typing import Optional

from hauntedroom.common import wait_with_countdown
from hauntedroom.cv_pattern_matching import (
    capture_page_grayscale,
    find_template,
    load_template,
)


MISC_TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "rooms" / "misc"
RESEARCH_AVAILABLE_TEMPLATE_PATH = MISC_TEMPLATE_DIR / "research_available.png"
RESEARCH_ACTIVE_TEMPLATE_PATH = MISC_TEMPLATE_DIR / "research_active.png"
RESEARCH_TEMPLATE_THRESHOLD = 0.6
RESEARCH_TEMPLATE_SCALES = (1.0,)
RESEARCH_POLL_MS = 400
RESEARCH_AVAILABLE_MAX_MISSES = 4
RESEARCH_ACTIVE_MAX_MISSES = 4


async def run_research_flow(
    page,
    stop_event: Optional[asyncio.Event] = None,
    available_template_path: Path = RESEARCH_AVAILABLE_TEMPLATE_PATH,
    active_template_path: Path = RESEARCH_ACTIVE_TEMPLATE_PATH,
    threshold: float = RESEARCH_TEMPLATE_THRESHOLD,
    delay_ms: int = 600,
) -> bool:
    available_template = load_template(available_template_path)
    active_template = load_template(active_template_path)

    while True:
        if stop_event is not None and stop_event.is_set():
            print("Research flow stopped; runner is idle.", flush=True)
            return False

        available_misses = 0
        while True:
            screenshot = await capture_page_grayscale(page)
            x, y, score = find_template(
                screenshot,
                available_template,
                available_template_path.name,
                "bottom_left",
                scales=RESEARCH_TEMPLATE_SCALES,
            )
            if score >= threshold:
                break

            available_misses += 1
            if available_misses >= RESEARCH_AVAILABLE_MAX_MISSES:
                print(
                    "Research is not available after "
                    f"{RESEARCH_AVAILABLE_MAX_MISSES} checks "
                    f"(score={score:.3f}); runner is idle.",
                    flush=True,
                )
                return True
            print(
                "Research available not found "
                f"({available_misses}/{RESEARCH_AVAILABLE_MAX_MISSES}, "
                f"score={score:.3f}); retrying in {RESEARCH_POLL_MS}ms",
                flush=True,
            )
            await page.wait_for_timeout(RESEARCH_POLL_MS)
            if stop_event is not None and stop_event.is_set():
                print("Research flow stopped; runner is idle.", flush=True)
                return False

        print(
            f"Research available at {x},{y}, score={score:.3f}; "
            f"click in {delay_ms}ms",
            flush=True,
        )
        completed = await wait_with_countdown(
            page,
            delay_ms,
            "Research available",
            stop_event,
        )
        if not completed:
            print("Research flow stopped; runner is idle.", flush=True)
            return False
        await page.evaluate(
            "() => { window.__hauntedRoomSuppressNextClickLog = true; }"
        )
        await page.mouse.click(x, y)

        active_misses = 0
        while True:
            await page.wait_for_timeout(RESEARCH_POLL_MS)
            if stop_event is not None and stop_event.is_set():
                print("Research flow stopped; runner is idle.", flush=True)
                return False

            screenshot = await capture_page_grayscale(page)
            x, y, score = find_template(
                screenshot,
                active_template,
                active_template_path.name,
                scales=RESEARCH_TEMPLATE_SCALES,
            )
            if score < threshold:
                active_misses += 1
                if active_misses < RESEARCH_ACTIVE_MAX_MISSES:
                    print(
                        "Active research not found "
                        f"({active_misses}/{RESEARCH_ACTIVE_MAX_MISSES}, "
                        f"score={score:.3f}); retrying in {RESEARCH_POLL_MS}ms",
                        flush=True,
                    )
                    continue
                print(
                    "No active research remains after "
                    f"{RESEARCH_ACTIVE_MAX_MISSES} checks "
                    f"(score={score:.3f}); returning to research available.",
                    flush=True,
                )
                break

            active_misses = 0
            print(
                f"Active research at {x},{y}, score={score:.3f}; "
                f"click in {delay_ms}ms",
                flush=True,
            )
            completed = await wait_with_countdown(
                page,
                delay_ms,
                "Active research",
                stop_event,
            )
            if not completed:
                print("Research flow stopped; runner is idle.", flush=True)
                return False

            await page.evaluate(
                "() => { window.__hauntedRoomSuppressNextClickLog = true; }"
            )
            await page.mouse.click(x, y)
