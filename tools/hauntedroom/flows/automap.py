import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Awaitable, Callable, Optional

import cv2
import numpy as np

from hauntedroom.core.mouse import bot_click
from hauntedroom.core.runtime import (
    flow_checkpoint,
    save_screenshot,
    wait_for_flow_timeout,
    wait_with_countdown,
)
from hauntedroom.core.template import (
    find_template,
    find_template_matches,
    load_template,
)
from hauntedroom.core.terminal import GREEN, colorize
from hauntedroom.core.vision import capture_page_bgr
from hauntedroom.flows.automap_support.boss_action import deploy_boss_pet
from hauntedroom.flows.automap_support.boss_flow import (
    handle_boss_critical as _handle_boss_critical,
)
from hauntedroom.flows.automap_support.gear_action import deploy_initial_gear
from hauntedroom.flows.automap_support.hero_action import (
    handle_hero_levelup as _handle_hero_levelup,
)
from hauntedroom.flows.automap_support.map_completion import (
    MAP_END_CHECK_INTERVAL_SEC,
    MAP_END_TEMPLATE_THRESHOLD,
    REWARD_LIST_TITLE_TEMPLATE_THRESHOLD,
    WIN_REWARD_EMPTY_DELAY_MS,
    WIN_REWARD_FOLLOWUP_CLICK,
    WIN_REWARD_FOLLOWUP_CLICK_COUNT,
    WIN_REWARD_RECHECK_MS,
    WIN_REWARD_TEMPLATE_THRESHOLD,
)
from hauntedroom.flows.automap_support.map_completion import (
    finish_map_from_home as _finish_map_from_home,
)
from hauntedroom.flows.automap_support.upgrade_action import (
    AUTOMAP_POLL_MS,
)
from hauntedroom.flows.automap_support.upgrade_action import (
    click_level_spin_if_present as _click_level_spin_if_present,
)
from hauntedroom.flows.automap_support.upgrade_action import (
    handle_build_structure as _handle_build_structure,
)
from hauntedroom.flows.automap_support.upgrade_action import (
    handle_level_up as _handle_level_up,
)
from hauntedroom.flows.automap_support.vision.boss import (
    boss_progress_is_full,
    find_boss_health_bar,
)
from hauntedroom.flows.automap_support.vision.build import (
    find_first_available_build_option,
)
from hauntedroom.flows.automap_support.vision.gear import find_gear_button
from hauntedroom.flows.automap_support.vision.hero_levelup import (
    HERO_LEVELUP_TEMPLATE_PATHS,
    hero_levelup_price_is_available,
    load_hero_levelup_templates,
)
from hauntedroom.settings import CAPTURE_HERO_FALLBACK_SCREENSHOTS


async def _click(page, x: int, y: int) -> None:
    await bot_click(page, (x, y))


AUTOMAP_TEMPLATE_DIR = Path(__file__).resolve().parents[2] / "rooms" / "automap"
MAP_WIN_TEMPLATE_DIR = AUTOMAP_TEMPLATE_DIR / "map_win"
ROOM_TEMPLATE_DIR = AUTOMAP_TEMPLATE_DIR.parent
BOSS_TEMPLATE_DIR = ROOM_TEMPLATE_DIR / "boss"
BLOCKER_TEMPLATE_DIR = ROOM_TEMPLATE_DIR / "blocker"
LV_UP_TEMPLATE_PATH = AUTOMAP_TEMPLATE_DIR / "lv_up.png"
BUILT_TEMPLATE_PATH = AUTOMAP_TEMPLATE_DIR / "built.png"
LV_SPIN_TEMPLATE_PATH = AUTOMAP_TEMPLATE_DIR / "lv_spin.png"
MAP_END_TEMPLATE_PATH = AUTOMAP_TEMPLATE_DIR / "map_end.png"
WIN_REWARD_TEMPLATE_PATH = MAP_WIN_TEMPLATE_DIR / "win_reward.png"
REWARD_LIST_TITLE_TEMPLATE_PATH = MAP_WIN_TEMPLATE_DIR / "reward_list_title.png"
DAILY_FIRST_WIN_TEMPLATE_PATH = MAP_WIN_TEMPLATE_DIR / "daily_first_win.png"
DAILY_FIRST_WIN_CHECKBOX_TEMPLATE_PATH = (
    MAP_WIN_TEMPLATE_DIR / "daily_first_win_checkbox.png"
)
DAILY_FIRST_WIN_CHECKED_TEMPLATE_PATH = (
    MAP_WIN_TEMPLATE_DIR / "daily_first_win_checked.png"
)
BOSS_HP_TEMPLATE_PATH = BOSS_TEMPLATE_DIR / "boss_hp_bar.png"
START_HOME_TEMPLATE_PATH = ROOM_TEMPLATE_DIR / "start_home.png"
EXIT_CLICK_TEMPLATE_PATH = ROOM_TEMPLATE_DIR / "exit_click.png"
MAP_COMPLETION_BLOCKER_TEMPLATE_PATHS = tuple(
    BLOCKER_TEMPLATE_DIR / name
    for name in (
        "lubu_close.png",
        "overlay_close.png",
        "overlay_close_2.png",
        "overlay_newbie.png",
    )
)
# lv_up.png excludes the two-pixel background border. The two valid icons in
# the captured battle UI score about 0.95 and 0.86; other UI stays below 0.60.
AUTOMAP_TEMPLATE_THRESHOLD = 0.80
BOSS_RECHECK_INTERVAL_MS = 400
# Keep the process-lifetime blocker across --dev-reload module refreshes.
FIRST_WIN_DONE = globals().get("FIRST_WIN_DONE", False)

SituationHandler = Callable[[np.ndarray, np.ndarray], Awaitable[bool]]


def _to_grayscale(image: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)


@dataclass(frozen=True)
class AutomapConfig:
    lv_up_template_path: Path = LV_UP_TEMPLATE_PATH
    threshold: float = AUTOMAP_TEMPLATE_THRESHOLD
    built_template_path: Path = BUILT_TEMPLATE_PATH
    lv_spin_template_path: Path = LV_SPIN_TEMPLATE_PATH
    map_end_template_path: Path = MAP_END_TEMPLATE_PATH
    win_reward_template_path: Path = WIN_REWARD_TEMPLATE_PATH
    reward_list_title_template_path: Path = REWARD_LIST_TITLE_TEMPLATE_PATH
    daily_first_win_template_path: Path = DAILY_FIRST_WIN_TEMPLATE_PATH
    daily_first_win_checkbox_template_path: Path = (
        DAILY_FIRST_WIN_CHECKBOX_TEMPLATE_PATH
    )
    daily_first_win_checked_template_path: Path = (
        DAILY_FIRST_WIN_CHECKED_TEMPLATE_PATH
    )
    boss_hp_template_path: Path = BOSS_HP_TEMPLATE_PATH
    start_home_template_path: Path = START_HOME_TEMPLATE_PATH
    exit_click_template_path: Path = EXIT_CLICK_TEMPLATE_PATH
    map_completion_blocker_template_paths: tuple[
        Path, ...
    ] = MAP_COMPLETION_BLOCKER_TEMPLATE_PATHS
    hero_levelup_template_paths: tuple[Path, ...] = HERO_LEVELUP_TEMPLATE_PATHS
    capture_hero_fallback_screenshots: bool = CAPTURE_HERO_FALLBACK_SCREENSHOTS
    debug: bool = False
    on_win: Optional[Callable[[], int]] = None


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
        self.reward_list_title_template = load_template(
            config.reward_list_title_template_path
        )
        self.daily_first_win_template = load_template(
            config.daily_first_win_template_path
        )
        self.daily_first_win_checkbox_template = load_template(
            config.daily_first_win_checkbox_template_path
        )
        self.daily_first_win_checked_template = load_template(
            config.daily_first_win_checked_template_path
        )
        self.boss_hp_template = load_template(config.boss_hp_template_path)
        self.start_home_template = load_template(config.start_home_template_path)
        self.exit_click_template = load_template(config.exit_click_template_path)
        self.map_completion_blocker_templates = tuple(
            (path, load_template(path))
            for path in config.map_completion_blocker_template_paths
        )
        self.hero_levelup_templates = load_hero_levelup_templates(
            config.hero_levelup_template_paths
        )
        self.loop = asyncio.get_running_loop()
        self.last_map_end_check: Optional[float] = None
        self.map_completed = False
        self.win_recorded = False
        self.total_win: Optional[int] = None
        self.first_win_done = FIRST_WIN_DONE
        self.final_boss_pet_deployed = False
        self.boss_detection_logged = False
        self.initial_gear_unlocked = False
        self.initial_gear_attempted = False
        self.initial_gear_placed = False

    async def click_level_spin_if_present(self, frame_gray: np.ndarray) -> bool:
        return await _click_level_spin_if_present(
            self.page,
            self.stop_event,
            frame_gray,
            lv_spin_template=self.lv_spin_template,
            lv_spin_template_name=self.config.lv_spin_template_path.name,
            find_template_fn=find_template,
            click_fn=_click,
            wait_for_flow_timeout_fn=wait_for_flow_timeout,
        )

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
        global FIRST_WIN_DONE

        outcome = await _finish_map_from_home(
            self.page,
            self.stop_event,
            win_reward_template=self.win_reward_template,
            win_reward_template_path=self.config.win_reward_template_path,
            reward_list_title_template=self.reward_list_title_template,
            reward_list_title_template_path=self.config.reward_list_title_template_path,
            start_home_template=self.start_home_template,
            start_home_template_path=self.config.start_home_template_path,
            blocker_templates=self.map_completion_blocker_templates,
            daily_first_win_template=self.daily_first_win_template,
            daily_first_win_template_path=self.config.daily_first_win_template_path,
            daily_first_win_checkbox_template=(
                self.daily_first_win_checkbox_template
            ),
            daily_first_win_checkbox_template_path=(
                self.config.daily_first_win_checkbox_template_path
            ),
            daily_first_win_checked_template=self.daily_first_win_checked_template,
            daily_first_win_checked_template_path=(
                self.config.daily_first_win_checked_template_path
            ),
            first_win_done=self.first_win_done,
            win_recorded=self.win_recorded,
            total_win=self.total_win,
            on_win=self.config.on_win,
            capture_page_bgr_fn=capture_page_bgr,
            to_grayscale_fn=_to_grayscale,
            find_template_fn=find_template,
            find_template_matches_fn=find_template_matches,
            click_fn=_click,
            wait_for_flow_timeout_fn=wait_for_flow_timeout,
            flow_checkpoint_fn=flow_checkpoint,
            poll_ms=AUTOMAP_POLL_MS,
        )
        self.win_recorded = outcome.win_recorded
        self.total_win = outcome.total_win
        self.first_win_done = outcome.first_win_done
        FIRST_WIN_DONE = outcome.first_win_done
        return outcome.completed

    async def hero_levelup(
        self,
        frame_bgr: np.ndarray,
        _frame_gray: np.ndarray,
    ) -> bool:
        outcome = await _handle_hero_levelup(
            self.page,
            self.stop_event,
            frame_bgr,
            hero_levelup_template_paths=self.config.hero_levelup_template_paths,
            hero_levelup_templates=self.hero_levelup_templates,
            hero_levelup_price_is_available_fn=hero_levelup_price_is_available,
            capture_page_bgr_fn=capture_page_bgr,
            save_screenshot_fn=save_screenshot,
            click_fn=_click,
            wait_for_flow_timeout_fn=wait_for_flow_timeout,
            flow_checkpoint_fn=flow_checkpoint,
            capture_fallback_screenshots=(
                self.config.capture_hero_fallback_screenshots
            ),
        )
        if outcome.initial_gear_unlocked:
            self.initial_gear_unlocked = True
        return outcome.handled

    async def handle_initial_gear(
        self,
        frame_bgr: np.ndarray,
        _frame_gray: np.ndarray,
    ) -> bool:
        """Place the first gear once, after the first stable upgrade milestone."""
        if not self.initial_gear_unlocked or self.initial_gear_attempted:
            return False
        if find_gear_button(frame_bgr) is None:
            return False

        # Mark before interacting: a failed drag must not loop forever or move
        # another control on a later animated frame.
        self.initial_gear_attempted = True
        self.initial_gear_placed = await deploy_initial_gear(
            self.page,
            frame_bgr,
        )
        return True

    async def handle_boss_critical(
        self,
        frame_bgr: np.ndarray,
        frame_gray: np.ndarray,
    ) -> bool:
        outcome = await _handle_boss_critical(
            self.page,
            self.stop_event,
            frame_bgr,
            frame_gray,
            boss_hp_template=self.boss_hp_template,
            exit_click_template=self.exit_click_template,
            exit_click_template_name=self.config.exit_click_template_path.name,
            final_boss_pet_deployed=self.final_boss_pet_deployed,
            boss_detection_logged=self.boss_detection_logged,
            find_boss_health_bar_fn=find_boss_health_bar,
            boss_progress_is_full_fn=boss_progress_is_full,
            find_template_fn=find_template,
            deploy_boss_pet_fn=deploy_boss_pet,
            click_fn=_click,
        )
        if outcome.final_boss_pet_deployed is not None:
            self.final_boss_pet_deployed = outcome.final_boss_pet_deployed
        self.boss_detection_logged = outcome.boss_detection_logged
        return outcome.handled

    async def handle_level_up(
        self,
        _frame_bgr: np.ndarray,
        frame_gray: np.ndarray,
    ) -> bool:
        outcome = await _handle_level_up(
            self.page,
            self.stop_event,
            frame_gray,
            lv_up_template=self.lv_up_template,
            lv_up_template_name=self.config.lv_up_template_path.name,
            lv_up_threshold=self.config.threshold,
            capture_page_bgr_fn=capture_page_bgr,
            to_grayscale_fn=_to_grayscale,
            find_template_matches_fn=find_template_matches,
            click_level_spin_if_present_fn=self.click_level_spin_if_present,
            click_fn=_click,
            wait_with_countdown_fn=wait_with_countdown,
        )
        if outcome.initial_gear_unlocked:
            self.initial_gear_unlocked = True
        return outcome.handled

    async def handle_build_structure(
        self,
        _frame_bgr: np.ndarray,
        frame_gray: np.ndarray,
    ) -> bool:
        return await _handle_build_structure(
            self.page,
            self.stop_event,
            frame_gray,
            built_template=self.built_template,
            built_template_name=self.config.built_template_path.name,
            capture_page_bgr_fn=capture_page_bgr,
            find_template_matches_fn=find_template_matches,
            find_first_available_build_option_fn=find_first_available_build_option,
            click_fn=_click,
            wait_with_countdown_fn=wait_with_countdown,
        )

    async def run(self) -> bool:
        """Run handlers in priority order until stopped or the map completes."""
        map_end_handler = self.handle_map_end
        boss_handler = self.handle_boss_critical
        handlers: tuple[SituationHandler, ...] = (
            self.handle_level_spin_interrupt,
            map_end_handler,
            self.handle_initial_gear,
            boss_handler,
            self.handle_level_up, # gate, bed
            self.handle_build_structure,
            self.hero_levelup,
        )

        while await flow_checkpoint(self.stop_event):
            frame_bgr = await capture_page_bgr(self.page)
            frame_gray = _to_grayscale(frame_bgr)
            for handler in handlers:
                if not await flow_checkpoint(self.stop_event):
                    break
                if await handler(frame_bgr, frame_gray):
                    if handler is boss_handler:
                        await wait_for_flow_timeout(
                            self.page,
                            BOSS_RECHECK_INTERVAL_MS,
                            self.stop_event,
                        )
                    if handler is map_end_handler:
                        if self.map_completed:
                            if self.win_recorded:
                                displayed_win = (
                                    self.total_win
                                    if self.total_win is not None
                                    else 1
                                )
                                print(
                                    colorize(
                                        f">>> [{displayed_win}] win", GREEN
                                    ),
                                    flush=True,
                                )
                            print(
                                "Auto-map flow completed; runner is idle.",
                                flush=True,
                            )
                        return self.map_completed
                    break
            else:
                await wait_for_flow_timeout(
                    self.page, AUTOMAP_POLL_MS, self.stop_event
                )

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
    reward_list_title_template_path: Path = REWARD_LIST_TITLE_TEMPLATE_PATH,
    daily_first_win_template_path: Path = DAILY_FIRST_WIN_TEMPLATE_PATH,
    daily_first_win_checkbox_template_path: Path = (
        DAILY_FIRST_WIN_CHECKBOX_TEMPLATE_PATH
    ),
    daily_first_win_checked_template_path: Path = (
        DAILY_FIRST_WIN_CHECKED_TEMPLATE_PATH
    ),
    boss_hp_template_path: Path = BOSS_HP_TEMPLATE_PATH,
    start_home_template_path: Path = START_HOME_TEMPLATE_PATH,
    exit_click_template_path: Path = EXIT_CLICK_TEMPLATE_PATH,
    map_completion_blocker_template_paths: tuple[Path, ...] = (
        MAP_COMPLETION_BLOCKER_TEMPLATE_PATHS
    ),
    hero_levelup_template_paths: tuple[Path, ...] = HERO_LEVELUP_TEMPLATE_PATHS,
    capture_hero_fallback_screenshots: bool = CAPTURE_HERO_FALLBACK_SCREENSHOTS,
    debug: bool = False,
    on_win: Optional[Callable[[], int]] = None,
) -> bool:
    """Build and run one auto-map flow while preserving the public API."""
    config = AutomapConfig(
        lv_up_template_path=lv_up_template_path,
        threshold=threshold,
        built_template_path=built_template_path,
        lv_spin_template_path=lv_spin_template_path,
        map_end_template_path=map_end_template_path,
        win_reward_template_path=win_reward_template_path,
        reward_list_title_template_path=reward_list_title_template_path,
        daily_first_win_template_path=daily_first_win_template_path,
        daily_first_win_checkbox_template_path=(
            daily_first_win_checkbox_template_path
        ),
        daily_first_win_checked_template_path=(
            daily_first_win_checked_template_path
        ),
        boss_hp_template_path=boss_hp_template_path,
        start_home_template_path=start_home_template_path,
        exit_click_template_path=exit_click_template_path,
        map_completion_blocker_template_paths=(
            map_completion_blocker_template_paths
        ),
        hero_levelup_template_paths=hero_levelup_template_paths,
        capture_hero_fallback_screenshots=capture_hero_fallback_screenshots,
        debug=debug,
        on_win=on_win,
    )
    return await AutomapFlow(page, stop_event, config).run()
