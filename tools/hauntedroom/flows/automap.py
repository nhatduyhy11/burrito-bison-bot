import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Awaitable, Callable, Optional

import numpy as np

from hauntedroom.core.runtime import wait_with_countdown
from hauntedroom.core.vision import (
    capture_page_bgr,
    find_template,
    find_template_matches,
    load_template,
)
from hauntedroom.flows.boss_action import click as _click
from hauntedroom.flows.map_vision_helper import (
    BOSS_CRITICAL_REGION,
    PROTECT_AVAILABLE_REGION,
    find_boss_health_bar,
    find_first_available_build_option,
    region_has_enough_white,
    to_grayscale,
)


AUTOMAP_TEMPLATE_DIR = Path(__file__).resolve().parents[2] / "rooms" / "automap"
ROOM_TEMPLATE_DIR = AUTOMAP_TEMPLATE_DIR.parent
BOSS_TEMPLATE_DIR = ROOM_TEMPLATE_DIR / "boss"
LV_UP_TEMPLATE_PATH = AUTOMAP_TEMPLATE_DIR / "lv_up.png"
BUILT_TEMPLATE_PATH = AUTOMAP_TEMPLATE_DIR / "built.png"
LV_SPIN_TEMPLATE_PATH = AUTOMAP_TEMPLATE_DIR / "lv_spin.png"
MAP_END_TEMPLATE_PATH = AUTOMAP_TEMPLATE_DIR / "map_end.png"
WIN_REWARD_TEMPLATE_PATH = AUTOMAP_TEMPLATE_DIR / "win_reward.png"
BOSS_HP_TEMPLATE_PATH = BOSS_TEMPLATE_DIR / "boss_hp_bar.png"
START_HOME_TEMPLATE_PATH = ROOM_TEMPLATE_DIR / "start_home.png"
EXIT_CLICK_TEMPLATE_PATH = ROOM_TEMPLATE_DIR / "exit_click.png"
# lv_up.png excludes the two-pixel background border. The two valid icons in
# the captured battle UI score about 0.95 and 0.86; other UI stays below 0.60.
AUTOMAP_TEMPLATE_THRESHOLD = 0.80
BUILT_TEMPLATE_THRESHOLD = 0.80
AUTOMAP_POLL_MS = 600
AUTOMAP_ACTION_DELAY_MS = 800
LV_SPIN_CLICK_OFFSET_X = -70
LV_SPIN_TEMPLATE_THRESHOLD = 0.58
LV_SPIN_TEMPLATE_SCALES = (1.0, 0.8, 0.67)
LV_SPIN_SEARCH_TOP_RATIO = 0.75
MAP_END_TEMPLATE_THRESHOLD = 0.90
MAP_END_CHECK_INTERVAL_SEC = 5.0
WIN_REWARD_TEMPLATE_THRESHOLD = 0.90
START_HOME_TEMPLATE_THRESHOLD = 0.90
EXIT_CLICK_TEMPLATE_THRESHOLD = 0.90

PROTECT_CLICK = (320, 640)
PROTECT_CONFIRM_CLICK = (357, 623)
UPGRADE_CONFIRM_CLICK = (430, 366)
WIN_REWARD_CLICK = (320, 433)

SituationHandler = Callable[[np.ndarray, np.ndarray], Awaitable[bool]]


@dataclass(frozen=True)
class AutomapConfig:
    lv_up_template_path: Path = LV_UP_TEMPLATE_PATH
    threshold: float = AUTOMAP_TEMPLATE_THRESHOLD
    built_template_path: Path = BUILT_TEMPLATE_PATH
    lv_spin_template_path: Path = LV_SPIN_TEMPLATE_PATH
    map_end_template_path: Path = MAP_END_TEMPLATE_PATH
    win_reward_template_path: Path = WIN_REWARD_TEMPLATE_PATH
    boss_hp_template_path: Path = BOSS_HP_TEMPLATE_PATH
    start_home_template_path: Path = START_HOME_TEMPLATE_PATH
    exit_click_template_path: Path = EXIT_CLICK_TEMPLATE_PATH


class AutomapFlow:
    """Own auto-map templates, mutable state, handlers, and scheduling."""

    def __init__(
        self,
        page,
        stop_event: Optional[asyncio.Event],
        config: AutomapConfig,
    ) -> None:
        self.page = page
        self.stop_event = stop_event
        self.config = config
        self.lv_up_template = load_template(config.lv_up_template_path)
        self.built_template = load_template(config.built_template_path)
        self.lv_spin_template = load_template(config.lv_spin_template_path)
        self.map_end_template = load_template(config.map_end_template_path)
        self.win_reward_template = load_template(config.win_reward_template_path)
        self.boss_hp_template = load_template(config.boss_hp_template_path)
        self.start_home_template = load_template(config.start_home_template_path)
        self.exit_click_template = load_template(config.exit_click_template_path)
        self.loop = asyncio.get_running_loop()
        self.last_map_end_check: Optional[float] = None
        self.map_completed = False
        self.boss_handoff_requested = False

    async def click_level_spin_if_present(self, frame_gray: np.ndarray) -> bool:
        search_top = int(frame_gray.shape[0] * LV_SPIN_SEARCH_TOP_RATIO)
        search_frame = frame_gray[search_top:, :]
        x, y, score = find_template(
            search_frame,
            self.lv_spin_template,
            self.config.lv_spin_template_path.name,
            scales=LV_SPIN_TEMPLATE_SCALES,
        )
        if score < LV_SPIN_TEMPLATE_THRESHOLD:
            return False

        y += search_top
        click_x = max(0, x + LV_SPIN_CLICK_OFFSET_X)
        print(
            f"Level spin interrupt at {x},{y}, score={score:.3f}; "
            f"clicking {click_x},{y}.",
            flush=True,
        )
        await _click(self.page, click_x, y)
        await self.page.wait_for_timeout(AUTOMAP_POLL_MS)
        return True

    async def handle_level_spin_interrupt(
        self,
        _frame_bgr: np.ndarray,
        frame_gray: np.ndarray,
    ) -> bool:
        return await self.click_level_spin_if_present(frame_gray)

    async def handle_map_end(
        self,
        _frame_bgr: np.ndarray,
        frame_gray: np.ndarray,
    ) -> bool:
        now = self.loop.time()
        if (
            self.last_map_end_check is not None
            and now - self.last_map_end_check < MAP_END_CHECK_INTERVAL_SEC
        ):
            return False

        self.last_map_end_check = now
        x, y, score = find_template(
            frame_gray,
            self.map_end_template,
            self.config.map_end_template_path.name,
        )
        if score < MAP_END_TEMPLATE_THRESHOLD:
            return False

        print(
            f"Map end at {x},{y}, score={score:.3f}; clicking back to home.",
            flush=True,
        )
        await _click(self.page, x, y)
        self.map_completed = await self.finish_map_from_home()
        return True

    async def finish_map_from_home(self) -> bool:
        reward_clicked = False
        while self.stop_event is None or not self.stop_event.is_set():
            frame_bgr = await capture_page_bgr(self.page)
            frame_gray = to_grayscale(frame_bgr)

            if not reward_clicked:
                reward_matches = find_template_matches(
                    frame_gray,
                    self.win_reward_template,
                    self.config.win_reward_template_path.name,
                    threshold=WIN_REWARD_TEMPLATE_THRESHOLD,
                    scales=(1.0,),
                )
                if reward_matches:
                    best_score = max(match[2] for match in reward_matches)
                    print(
                        f"Win reward found, best score={best_score:.3f}; "
                        f"clicking fixed position {WIN_REWARD_CLICK[0]},"
                        f"{WIN_REWARD_CLICK[1]}.",
                        flush=True,
                    )
                    await _click(self.page, *WIN_REWARD_CLICK)
                    reward_clicked = True
                    await self.page.wait_for_timeout(AUTOMAP_POLL_MS)
                    continue

            x, y, score = find_template(
                frame_gray,
                self.start_home_template,
                self.config.start_home_template_path.name,
            )
            if score >= START_HOME_TEMPLATE_THRESHOLD:
                print(
                    f"Home ready at {x},{y}, score={score:.3f}; auto-map complete.",
                    flush=True,
                )
                return True

            await self.page.wait_for_timeout(AUTOMAP_POLL_MS)

        print("Auto-map flow stopped while waiting for home reward.", flush=True)
        return False

    async def handle_protect_gate(
        self,
        frame_bgr: np.ndarray,
        _frame_gray: np.ndarray,
    ) -> bool:
        if not region_has_enough_white(frame_bgr):
            return False

        print("Protect gate available; clicking twice with 800ms delay.", flush=True)
        await _click(self.page, *PROTECT_CLICK)
        if not await wait_with_countdown(
            self.page,
            AUTOMAP_ACTION_DELAY_MS,
            "Protect gate",
            self.stop_event,
        ):
            return True
        await _click(self.page, *PROTECT_CONFIRM_CLICK)
        return True

    async def handle_boss_critical(
        self,
        _frame_bgr: np.ndarray,
        frame_gray: np.ndarray,
    ) -> bool:
        match = find_boss_health_bar(frame_gray, self.boss_hp_template)
        if match is None:
            return False

        x, y, score = match
        exit_x, exit_y, exit_score = find_template(
            frame_gray,
            self.exit_click_template,
            self.config.exit_click_template_path.name,
        )
        if exit_score < EXIT_CLICK_TEMPLATE_THRESHOLD:
            print(
                f"Boss HP entered critical region at {x},{y}, score={score:.3f}; "
                f"exit_click not found (score={exit_score:.3f}).",
                flush=True,
            )
            return False

        print(
            f"Boss HP entered critical region at {x},{y}, score={score:.3f}; "
            f"clicking exit_click once at {exit_x},{exit_y} and stopping auto-map.",
            flush=True,
        )
        await _click(self.page, exit_x, exit_y)
        self.boss_handoff_requested = True
        return True

    async def handle_level_up(
        self,
        _frame_bgr: np.ndarray,
        frame_gray: np.ndarray,
    ) -> bool:
        matches = find_template_matches(
            frame_gray,
            self.lv_up_template,
            self.config.lv_up_template_path.name,
            threshold=self.config.threshold,
        )
        if not matches:
            return False

        x, y, score = max(matches, key=lambda match: match[1])
        print(
            f"Level up at {x},{y}, score={score:.3f}; "
            "clicking bottom-most match, then confirm in 800ms.",
            flush=True,
        )
        await _click(self.page, x, y)
        if not await wait_with_countdown(
            self.page,
            AUTOMAP_ACTION_DELAY_MS,
            "Level up",
            self.stop_event,
        ):
            return True
        frame_bgr = await capture_page_bgr(self.page)
        frame_gray = to_grayscale(frame_bgr)
        if await self.click_level_spin_if_present(frame_gray):
            return True
        await _click(self.page, *UPGRADE_CONFIRM_CLICK)
        return True

    async def handle_build_structure(
        self,
        _frame_bgr: np.ndarray,
        frame_gray: np.ndarray,
    ) -> bool:
        matches = find_template_matches(
            frame_gray,
            self.built_template,
            self.config.built_template_path.name,
            threshold=BUILT_TEMPLATE_THRESHOLD,
            scales=(1.0,),
        )
        if not matches:
            return False

        x, y, score = max(matches, key=lambda match: (match[0], match[1]))
        print(
            f"Build marker at {x},{y}, score={score:.3f}; "
            "clicking the highest-x/highest-y match.",
            flush=True,
        )
        await _click(self.page, x, y)
        if not await wait_with_countdown(
            self.page,
            AUTOMAP_ACTION_DELAY_MS,
            "Build menu",
            self.stop_event,
        ):
            return True

        popup_frame = await capture_page_bgr(self.page)
        available_option = find_first_available_build_option(popup_frame)
        if available_option is not None:
            print("White-price build option is available; clicking it.", flush=True)
            await _click(self.page, *available_option)
            return True

        print("No white-price build option is available; skipping.", flush=True)
        return True

    async def run(self) -> bool:
        """Run handlers in priority order until stopped or the map completes."""
        map_end_handler = self.handle_map_end
        handlers: tuple[SituationHandler, ...] = (
            self.handle_level_spin_interrupt,
            map_end_handler,
            self.handle_boss_critical,
            self.handle_protect_gate,
            self.handle_level_up,
            self.handle_build_structure,
        )

        while self.stop_event is None or not self.stop_event.is_set():
            frame_bgr = await capture_page_bgr(self.page)
            frame_gray = to_grayscale(frame_bgr)
            for handler in handlers:
                if self.stop_event is not None and self.stop_event.is_set():
                    break
                if await handler(frame_bgr, frame_gray):
                    if self.boss_handoff_requested:
                        print(
                            "Auto-map stopped after boss handoff; runner is idle.",
                            flush=True,
                        )
                        return False
                    if handler is map_end_handler:
                        if self.map_completed:
                            print(
                                "Auto-map flow completed; runner is idle.",
                                flush=True,
                            )
                        return self.map_completed
                    break
            else:
                await self.page.wait_for_timeout(AUTOMAP_POLL_MS)

        print("Auto-map flow stopped; runner is idle.", flush=True)
        return False


async def run_automap_flow(
    page,
    stop_event: Optional[asyncio.Event] = None,
    lv_up_template_path: Path = LV_UP_TEMPLATE_PATH,
    threshold: float = AUTOMAP_TEMPLATE_THRESHOLD,
    built_template_path: Path = BUILT_TEMPLATE_PATH,
    lv_spin_template_path: Path = LV_SPIN_TEMPLATE_PATH,
    map_end_template_path: Path = MAP_END_TEMPLATE_PATH,
    win_reward_template_path: Path = WIN_REWARD_TEMPLATE_PATH,
    boss_hp_template_path: Path = BOSS_HP_TEMPLATE_PATH,
    start_home_template_path: Path = START_HOME_TEMPLATE_PATH,
    exit_click_template_path: Path = EXIT_CLICK_TEMPLATE_PATH,
) -> bool:
    """Build and run one auto-map flow while preserving the public API."""
    config = AutomapConfig(
        lv_up_template_path=lv_up_template_path,
        threshold=threshold,
        built_template_path=built_template_path,
        lv_spin_template_path=lv_spin_template_path,
        map_end_template_path=map_end_template_path,
        win_reward_template_path=win_reward_template_path,
        boss_hp_template_path=boss_hp_template_path,
        start_home_template_path=start_home_template_path,
        exit_click_template_path=exit_click_template_path,
    )
    return await AutomapFlow(page, stop_event, config).run()
