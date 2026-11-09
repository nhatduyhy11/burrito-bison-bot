"""Shift+] / Shift+[ campaign speed toggle (POC) with a battle watcher."""

import asyncio
from typing import Awaitable, Callable, Optional

from hauntedroom.control_events.battle_speed import (
    apply_battle_speed,
    find_game_frame,
    read_battle_speed,
    restore_battle_speed,
)
from hauntedroom.core.terminal import BLUE, ORANGE, YELLOW, colorize
from hauntedroom.screen_detect import ScreenName, detect_current_screen

SPEED_ON_COMMAND = "]"
SPEED_OFF_COMMAND = "["
DEFAULT_SPEED_SCALE = 2.2
DEFAULT_WATCH_INTERVAL_S = 5.0


def _log(message: str, color: str = BLUE) -> None:
    print(colorize(f"[speed] {message}", color), flush=True)


class BattleSpeedController:
    def __init__(
        self,
        page,
        scale: float = DEFAULT_SPEED_SCALE,
        interval_s: float = DEFAULT_WATCH_INTERVAL_S,
        detect_screen: Callable[[object], Awaitable[ScreenName]] = detect_current_screen,
    ) -> None:
        self._page = page
        self._scale = scale
        self._interval_s = interval_s
        self._detect_screen = detect_screen
        self._frame = None
        self._watcher: Optional[asyncio.Task] = None

    @property
    def active(self) -> bool:
        return self._watcher is not None and not self._watcher.done()

    async def handle_command(self, command: str) -> bool:
        if command == SPEED_ON_COMMAND:
            await self.enable()
            return True
        if command == SPEED_OFF_COMMAND:
            await self.disable("hotkey")
            return True
        return False

    async def enable(self) -> None:
        if self.active:
            _log(f"already x{self._scale}; Shift+[ to disable.", YELLOW)
            return

        screen = await self._detect_screen(self._page)
        if screen is not ScreenName.AUTOMAP:
            _log(f"not in battle (screen={screen.value}); speed unchanged.", ORANGE)
            return

        frame = await find_game_frame(self._page)
        if frame is None:
            _log("game frame not found; speed unchanged.", ORANGE)
            return

        result = await apply_battle_speed(frame, self._scale)
        if not result.get("applied"):
            _log(f"not applied: {result.get('reason')}.", ORANGE)
            return

        self._frame = frame
        self._watcher = asyncio.create_task(self._watch())
        _log(f"enabled x{self._scale} (was x{result.get('before')}).")

    async def disable(self, reason: str) -> None:
        watcher = self._watcher
        self._watcher = None
        if watcher is not None and watcher is not asyncio.current_task():
            watcher.cancel()
            await asyncio.gather(watcher, return_exceptions=True)
        if self._frame is None:
            if reason == "hotkey":
                _log("already off.", YELLOW)
            return

        frame = self._frame
        self._frame = None
        try:
            result = await restore_battle_speed(frame)
        except Exception as error:
            _log(f"restore failed ({reason}): {error}", ORANGE)
            return
        _log(f"disabled ({reason}); restored x{result.get('speed')}.", ORANGE)

    async def _watch(self) -> None:
        try:
            while True:
                await asyncio.sleep(self._interval_s)
                status = await read_battle_speed(self._frame)
                if status is None or not status.in_battle:
                    await self.disable("battle ended")
                    return
                result = await apply_battle_speed(self._frame, self._scale)
                if not result.get("applied"):
                    await self.disable(f"left campaign: {result.get('reason')}")
                    return
                if result.get("before") != self._scale:
                    _log(f"game reset speed to x{result.get('before')}; re-applied.", YELLOW)
        except asyncio.CancelledError:
            raise
        except Exception as error:
            _log(f"watcher error: {error}", ORANGE)
            await self.disable("watcher error")
