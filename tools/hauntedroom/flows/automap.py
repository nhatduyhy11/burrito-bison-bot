from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from pathlib import Path

import cv2
import numpy as np

from hauntedroom.core.mouse import bot_click
from hauntedroom.core.runtime import (
    flow_checkpoint,
    save_fallback_screenshot,
    wait_for_flow_timeout,
    wait_with_countdown,
)
from hauntedroom.core.template_matching import (
    find_template,
    find_template_matches,
)
from hauntedroom.core.terminal import GREEN, RED, colorize
from hauntedroom.core.vision import capture_page_bgr
from hauntedroom.flows.automap_support.boss_action import deploy_boss_pet
from hauntedroom.flows.automap_support.boss_flow import (
    handle_boss_critical as _handle_boss_critical,
)
from hauntedroom.flows.automap_support.config import (
    AUTOMAP_TEMPLATE_THRESHOLD,
    BOSS_HP_TEMPLATE_PATH,
    BUILT_TEMPLATE_PATH,
    DAILY_FIRST_WIN_CHECKBOX_TEMPLATE_PATH,
    DAILY_FIRST_WIN_CHECKED_TEMPLATE_PATH,
    DAILY_FIRST_WIN_TEMPLATE_PATH,
    EXIT_CLICK_TEMPLATE_PATH,
    LV_SPIN_TEMPLATE_PATH,
    LV_UP_TEMPLATE_PATH,
    MAP_COMPLETION_BLOCKER_TEMPLATE_PATHS,
    MAP_END_TEMPLATE_PATH,
    REWARD_LIST_TITLE_TEMPLATE_PATH,
    START_HOME_TEMPLATE_PATH,
    WIN_REWARD_TEMPLATE_PATH,
    AutomapConfig,
)
from hauntedroom.flows.automap_support.gear_action import deploy_initial_gear
from hauntedroom.flows.automap_support.hero_action import (
    handle_hero_levelup as _handle_hero_levelup,
)
from hauntedroom.flows.automap_support.map_completion import (
    MAP_END_CHECK_INTERVAL_SEC,
    MAP_END_TEMPLATE_THRESHOLD,
)
from hauntedroom.flows.automap_support.map_completion import (
    finish_map_from_home as _finish_map_from_home,
)
from hauntedroom.flows.automap_support.state import AutomapRunContext, AutomapState
from hauntedroom.flows.automap_support.templates import AutomapTemplates
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
from hauntedroom.flows.automap_support.vision.boss_hp import (
    find_boss_health_bar,
)
from hauntedroom.flows.automap_support.vision.boss_progress import (
    boss_progress_is_full,
)
from hauntedroom.flows.automap_support.vision.build import (
    find_first_available_build_option,
)
from hauntedroom.flows.automap_support.vision.gear import find_gear_button
from hauntedroom.flows.automap_support.vision.hero_levelup import (
    HERO_LEVELUP_TEMPLATE_PATHS,
    hero_levelup_price_is_available,
)
from hauntedroom.settings import CAPTURE_HERO_FALLBACK_SCREENSHOTS

__all__ = [
    "AutomapConfig",
    "AutomapFlow",
    "AutomapRunContext",
    "run_automap_flow",
]


async def _click(page, x: int, y: int) -> None:
    await bot_click(page, (x, y))


BOSS_RECHECK_INTERVAL_MS = 400

SituationHandler = Callable[[np.ndarray, np.ndarray], Awaitable[bool]]


def _to_grayscale(image: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)


class AutomapFlow:
    """Own auto-map templates, mutable state, handlers, and scheduling."""

    def __init__(
        self,
        page,
        stop_event: asyncio.Event | None,
        config: AutomapConfig,
        templates: AutomapTemplates,
        state: AutomapState | None = None,
        run_context: AutomapRunContext | None = None,
        on_win: Callable[[], int] | None = None,
    ) -> None:
        self.page = page
        self.stop_event = stop_event
        self.config = config
        self.templates = templates
        self.state = state or AutomapState()
        self.run_context = run_context or AutomapRunContext()
        self.on_win = on_win
        self.loop = asyncio.get_running_loop()

    async def click_level_spin_if_present(self, frame_gray: np.ndarray) -> bool:
        return await _click_level_spin_if_present(
            self.page,
            self.stop_event,
            frame_gray,
            lv_spin_template=self.templates.lv_spin,
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
            self.state.last_map_end_check is not None
            and now - self.state.last_map_end_check < MAP_END_CHECK_INTERVAL_SEC
        ):
            return False

        self.state.last_map_end_check = now
        x, y, score = find_template(
            frame_gray,
            self.templates.map_end,
            self.config.map_end_template_path.name,
        )
        if score < MAP_END_TEMPLATE_THRESHOLD:
            return False

        print(
            f"Map end at {x},{y}, score={score:.3f}; clicking back to home.",
            flush=True,
        )
        await _click(self.page, x, y)
        self.state.map_completed = await self.finish_map_from_home()
        return True

    async def finish_map_from_home(self) -> bool:
        outcome = await _finish_map_from_home(
            self.page,
            self.stop_event,
            win_reward_template=self.templates.win_reward,
            win_reward_template_path=self.config.win_reward_template_path,
            reward_list_title_template=self.templates.reward_list_title,
            reward_list_title_template_path=self.config.reward_list_title_template_path,
            start_home_template=self.templates.start_home,
            start_home_template_path=self.config.start_home_template_path,
            blocker_templates=self.templates.map_completion_blockers,
            daily_first_win_template=self.templates.daily_first_win,
            daily_first_win_template_path=self.config.daily_first_win_template_path,
            daily_first_win_checkbox_template=self.templates.daily_first_win_checkbox,
            daily_first_win_checkbox_template_path=(
                self.config.daily_first_win_checkbox_template_path
            ),
            daily_first_win_checked_template=self.templates.daily_first_win_checked,
            daily_first_win_checked_template_path=(
                self.config.daily_first_win_checked_template_path
            ),
            first_win_done=self.run_context.daily_first_win_done,
            win_recorded=self.state.win_recorded,
            total_win=self.state.total_win,
            on_win=self.on_win,
            capture_page_bgr_fn=capture_page_bgr,
            to_grayscale_fn=_to_grayscale,
            find_template_fn=find_template,
            find_template_matches_fn=find_template_matches,
            click_fn=_click,
            wait_for_flow_timeout_fn=wait_for_flow_timeout,
            flow_checkpoint_fn=flow_checkpoint,
            poll_ms=AUTOMAP_POLL_MS,
        )
        self.state.win_recorded = outcome.win_recorded
        self.state.total_win = outcome.total_win
        self.run_context.daily_first_win_done = outcome.first_win_done
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
            hero_levelup_templates=self.templates.hero_levelup,
            hero_levelup_price_is_available_fn=hero_levelup_price_is_available,
            capture_page_bgr_fn=capture_page_bgr,
            save_fallback_screenshot_fn=save_fallback_screenshot,
            click_fn=_click,
            wait_for_flow_timeout_fn=wait_for_flow_timeout,
            flow_checkpoint_fn=flow_checkpoint,
            capture_fallback_screenshots=(
                self.config.capture_hero_fallback_screenshots
            ),
        )
        if outcome.initial_gear_unlocked:
            self.state.initial_gear_unlocked = True
        return outcome.handled

    async def handle_initial_gear(
        self,
        frame_bgr: np.ndarray,
        _frame_gray: np.ndarray,
    ) -> bool:
        """Place the first gear once, after the first stable upgrade milestone."""
        if not self.state.initial_gear_unlocked or self.state.initial_gear_attempted:
            return False
        if find_gear_button(frame_bgr) is None:
            return False

        # Mark before interacting: a failed drag must not loop forever or move
        # another control on a later animated frame.
        self.state.initial_gear_attempted = True
        self.state.initial_gear_placed = await deploy_initial_gear(
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
            boss_hp_template=self.templates.boss_hp,
            exit_click_template=self.templates.exit_click,
            exit_click_template_name=self.config.exit_click_template_path.name,
            final_boss_pet_deployed=self.state.final_boss_pet_deployed,
            boss_detection_logged=self.state.boss_detection_logged,
            find_boss_health_bar_fn=find_boss_health_bar,
            boss_progress_is_full_fn=boss_progress_is_full,
            find_template_fn=find_template,
            deploy_boss_pet_fn=deploy_boss_pet,
            click_fn=_click,
        )
        if outcome.final_boss_pet_deployed is not None:
            self.state.final_boss_pet_deployed = outcome.final_boss_pet_deployed
        self.state.boss_detection_logged = outcome.boss_detection_logged
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
            lv_up_template=self.templates.lv_up,
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
            self.state.initial_gear_unlocked = True
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
            built_template=self.templates.built,
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
            self.handle_level_up,  # gate, bed
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
                        if self.state.map_completed:
                            if self.state.win_recorded:
                                displayed_win = (
                                    self.state.total_win
                                    if self.state.total_win is not None
                                    else 1
                                )
                                print(
                                    colorize(f">>> [{displayed_win}] win", GREEN),
                                    flush=True,
                                )
                            print(
                                "Auto-map flow completed; runner is idle.",
                                flush=True,
                            )
                        return self.state.map_completed
                    break
            else:
                await wait_for_flow_timeout(self.page, AUTOMAP_POLL_MS, self.stop_event)

        print(
            colorize("Auto-map flow stopped; runner is idle.", RED),
            flush=True,
        )
        return False


async def run_automap_flow(
    page,
    stop_event: asyncio.Event | None = None,
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
    on_win: Callable[[], int] | None = None,
    run_context: AutomapRunContext | None = None,
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
        daily_first_win_checkbox_template_path=(daily_first_win_checkbox_template_path),
        daily_first_win_checked_template_path=(daily_first_win_checked_template_path),
        boss_hp_template_path=boss_hp_template_path,
        start_home_template_path=start_home_template_path,
        exit_click_template_path=exit_click_template_path,
        map_completion_blocker_template_paths=(map_completion_blocker_template_paths),
        hero_levelup_template_paths=hero_levelup_template_paths,
        capture_hero_fallback_screenshots=capture_hero_fallback_screenshots,
        debug=debug,
    )
    templates = AutomapTemplates.load(config)
    state = AutomapState()
    return await AutomapFlow(
        page,
        stop_event,
        config,
        templates=templates,
        state=state,
        run_context=run_context,
        on_win=on_win,
    ).run()
