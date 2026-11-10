"""Optional speed override, scoped to the lifetime of a battle flow."""

import asyncio
from typing import Optional

from hauntedroom.control_events.battle_speed import (
    apply_battle_speed,
    find_game_frame,
    restore_battle_speed,
)
from hauntedroom.core.terminal import BLUE, ORANGE, colorize

SPEED_ON_COMMAND = "]"
SPEED_OFF_COMMAND = "["
SPEED_BOOST_COMMAND = "'"
BOOST_SPEED_SCALE = 3.0
DEFAULT_SPEED_SCALE = 2.2
DEFAULT_WATCH_INTERVAL_S = 1.0


def _log(message: str, color: str = BLUE) -> None:
    print(colorize(f"[speed] {message}", color), flush=True)


class BattleSpeedController:
    def __init__(
        self, page, scale: float = DEFAULT_SPEED_SCALE,
        interval_s: float = DEFAULT_WATCH_INTERVAL_S,
    ) -> None:
        self._page = page
        self._base_scale = scale
        self._scale = scale
        self._interval_s = interval_s
        self.enabled = False
        self._battle_flow = False
        self._frame = None
        self._watcher: Optional[asyncio.Task] = None

    @property
    def active(self) -> bool:
        return self._watcher is not None and not self._watcher.done()

    async def handle_command(self, command: str) -> bool:
        if command == SPEED_ON_COMMAND:
            self._scale = self._base_scale
            self.enabled = True
            await self._start()
            _log(f"x{self._scale} enabled for battle flows.")
            return True
        if command == SPEED_BOOST_COMMAND:
            if self.enabled:
                self._scale = BOOST_SPEED_SCALE
                await self._start()
                _log(f"x{self._scale} enabled for battle flows.")
            return True
        if command == SPEED_OFF_COMMAND:
            self.enabled = False
            await self.disable("hotkey")
            return True
        return False

    async def set_battle_flow(self, running: bool) -> None:
        self._battle_flow = running
        if running:
            await self._start()
        else:
            await self.disable("flow stopped/idle")

    async def _apply(self) -> None:
        if self._frame is None:
            self._frame = await find_game_frame(self._page)
        if self._frame is not None:
            await apply_battle_speed(self._frame, self._scale)

    async def _start(self) -> None:
        if not self.enabled or not self._battle_flow:
            return
        # Repeated hotkeys still ensure speed; only the watcher is deduplicated.
        if not self.active:
            self._watcher = asyncio.create_task(self._watch())
        try:
            await self._apply()
        except Exception as error:
            self._frame = None
            _log(f"apply failed; will retry: {error}", ORANGE)

    async def disable(self, reason: str) -> None:
        watcher = self._watcher
        self._watcher = None
        if watcher is not None:
            watcher.cancel()
            await asyncio.gather(watcher, return_exceptions=True)
        if self._frame is None:
            return
        frame = self._frame
        self._frame = None
        try:
            await restore_battle_speed(frame)
            _log(f"speed restored ({reason}).", ORANGE)
        except Exception as error:
            _log(f"restore failed ({reason}): {error}", ORANGE)

    async def _watch(self) -> None:
        while True:
            await asyncio.sleep(self._interval_s)
            try:
                # No battle is normal between rounds. Keep watching until flow ends.
                await self._apply()
            except Exception as error:
                self._frame = None
                _log(f"apply failed; will retry: {error}", ORANGE)
