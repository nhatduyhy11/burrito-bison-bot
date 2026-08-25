import asyncio
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from hauntedroom.core.terminal import GREEN, ORANGE, colorize

ACTION_LOOP_COUNT = 0

COUNTDOWN_WAIT_THRESHOLD_MS = 10000

TIMEOUT_SCREENSHOT_DIR = Path(".tmp/hauntedroom-timeouts")
FALLBACK_SCREENSHOT_DIR = Path(".tmp/hauntedroom-fallbacks")
LIVE_SCREENSHOT_DIR = Path("tests/fixtures/hauntedroom-captures")
class FlowControl:
    """Stop signal with an additional cooperative pause/resume gate."""

    PAUSE_AT_ANY_BOSS = "any_boss"
    PAUSE_AT_FINAL_BOSS = "final_boss"

    def __init__(self) -> None:
        self._stop_event = asyncio.Event()
        self._resume_event = asyncio.Event()
        self._resume_event.set()
        self._pause_started: Optional[float] = None
        self._paused_seconds = 0.0
        self._boss_pause_target: Optional[str] = None

    def is_set(self) -> bool:
        return self._stop_event.is_set()

    def set(self) -> None:
        self._stop_event.set()
        self._boss_pause_target = None
        # Release a task blocked in checkpoint() so it can observe the stop.
        self._resume_event.set()

    async def wait(self) -> None:
        await self._stop_event.wait()

    @property
    def is_paused(self) -> bool:
        return not self._resume_event.is_set() and not self.is_set()

    def pause(self) -> bool:
        if self.is_set() or self.is_paused:
            return False
        self._boss_pause_target = None
        self._resume_event.clear()
        self._pause_started = asyncio.get_running_loop().time()
        return True

    def resume(self) -> bool:
        if self.is_set() or not self.is_paused:
            return False
        assert self._pause_started is not None
        self._paused_seconds += asyncio.get_running_loop().time() - self._pause_started
        self._pause_started = None
        self._resume_event.set()
        return True

    @property
    def boss_pause_target(self) -> Optional[str]:
        return self._boss_pause_target

    def pause_at_next_boss(self, *, final_only: bool) -> bool:
        """Arm a one-shot pause for the next matching boss detection."""
        if self.is_set() or self.is_paused:
            return False
        self._boss_pause_target = (
            self.PAUSE_AT_FINAL_BOSS if final_only else self.PAUSE_AT_ANY_BOSS
        )
        return True

    def boss_pause_matches(self, *, is_final_boss: bool) -> bool:
        """Report whether the armed one-shot policy matches this boss."""
        target = self._boss_pause_target
        if target is None:
            return False
        return target != self.PAUSE_AT_FINAL_BOSS or is_final_boss

    def pause_for_detected_boss(self, *, is_final_boss: bool) -> bool:
        """Pause when a detected boss matches the armed one-shot policy."""
        if not self.boss_pause_matches(is_final_boss=is_final_boss):
            return False

        self._boss_pause_target = None
        return self.pause()

    def active_time(self) -> float:
        now = asyncio.get_running_loop().time()
        current_pause = now - self._pause_started if self._pause_started else 0.0
        return now - self._paused_seconds - current_pause

    async def checkpoint(self) -> bool:
        if self.is_set():
            return False
        await self._resume_event.wait()
        return not self.is_set()


async def flow_checkpoint(stop_event: Optional[asyncio.Event]) -> bool:
    """Wait while a pausable flow is paused and report whether it may continue."""
    if stop_event is None:
        return True
    checkpoint = getattr(stop_event, "checkpoint", None)
    if checkpoint is not None:
        return await checkpoint()
    return not stop_event.is_set()


def flow_time(stop_event: Optional[asyncio.Event]) -> float:
    """Monotonic flow time which does not advance while paused."""
    active_time = getattr(stop_event, "active_time", None)
    if active_time is not None:
        return active_time()
    return asyncio.get_running_loop().time()


async def wait_for_flow_timeout(
    page,
    ms: int,
    stop_event: Optional[asyncio.Event] = None,
) -> bool:
    """Wait without allowing a paused flow to advance to its next action."""
    # Keep the original one-shot wait behavior for ordinary stop events. Only
    # pausable controls need the additional gates.
    if getattr(stop_event, "checkpoint", None) is None:
        await page.wait_for_timeout(ms)
        return stop_event is None or not stop_event.is_set()
    if not await flow_checkpoint(stop_event):
        return False
    await page.wait_for_timeout(ms)
    return await flow_checkpoint(stop_event)


async def save_screenshot(
    page,
    label: str,
    directory: Path,
    description: str,
) -> Optional[Path]:
    safe_label = re.sub(r"[^A-Za-z0-9_.-]+", "-", label).strip("-_")
    safe_label = safe_label or description.lower().replace(" ", "-")
    if safe_label.lower().endswith(".png"):
        safe_label = safe_label[:-4]
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    screenshot_path = directory / f"{timestamp}-{safe_label}.png"
    screenshot_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        await page.screenshot(
            path=str(screenshot_path),
            type="png",
            scale="css",
        )
    except Exception as error:
        print(f"Failed to save {description.lower()} screenshot: {error}", flush=True)
        return None

    resolved_path = screenshot_path.resolve()
    saved_message = f"{description} screenshot saved: {resolved_path}"
    if description == "Live":
        saved_message = colorize(saved_message, GREEN)
    elif description == "Timeout":
        saved_message = colorize(saved_message, ORANGE)
    print(saved_message, flush=True)
    return resolved_path


async def save_timeout_screenshot(page, label: str) -> Optional[Path]:
    return await save_screenshot(page, label, TIMEOUT_SCREENSHOT_DIR, "Timeout")


async def save_fallback_screenshot(page, label: str) -> Optional[Path]:
    return await save_screenshot(page, label, FALLBACK_SCREENSHOT_DIR, "Fallback")


async def save_live_screenshot(page, label: str = "live") -> Optional[Path]:
    return await save_screenshot(page, label, LIVE_SCREENSHOT_DIR, "Live")


async def wait_with_countdown(
    page,
    ms: int,
    label: str,
    stop_event: Optional[asyncio.Event] = None,
) -> bool:
    if ms <= COUNTDOWN_WAIT_THRESHOLD_MS:
        print(f"{label}: wait {ms}ms")
    remaining_ms = ms
    while remaining_ms > 0:
        if not await flow_checkpoint(stop_event):
            return False
        if ms > COUNTDOWN_WAIT_THRESHOLD_MS:
            remaining_seconds = (remaining_ms + 999) // 1000
            print(f"{label}: wait {remaining_seconds}s remaining")
        step_ms = min(250, remaining_ms)
        await page.wait_for_timeout(step_ms)
        remaining_ms -= step_ms
    return await flow_checkpoint(stop_event)


async def wait_for_ctrl_c(page, message: str) -> None:
    print(message, flush=True)
    try:
        while True:
            await page.wait_for_timeout(1000)
    except (asyncio.CancelledError, KeyboardInterrupt):
        print("Stopping runner...", flush=True)
