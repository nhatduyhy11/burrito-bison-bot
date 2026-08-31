"""Auto-map priority scheduler and gameplay handler adapters."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

import cv2
import numpy as np

from hauntedroom.actions.pause_exit import find_pause_exit_button
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
from hauntedroom.core.terminal import BLUE, GREEN, RED, colorize
from hauntedroom.core.vision import capture_page_bgr
from hauntedroom.flows.automap_support.boss_action import deploy_boss_pet
from hauntedroom.flows.automap_support.boss_flow import (
    handle_boss_critical as _handle_boss_critical,
)
from hauntedroom.flows.automap_support.gear_action import deploy_initial_gear
from hauntedroom.flows.automap_support.hero_action import (
    handle_hero_levelup as _handle_hero_levelup,
)
from hauntedroom.flows.automap_support.map.lifecycle import MapLifecycle
from hauntedroom.flows.automap_support.map.model_state import (
    MapRunState,
    MapState,
)
from hauntedroom.flows.automap_support.templates import AutomapTemplates
from hauntedroom.flows.automap_support.upgrade_action import (
    AUTOMAP_ACTION_DELAY_MS,
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
from hauntedroom.flows.automap_support.vision.boss_hp import find_boss_health_bar
from hauntedroom.flows.automap_support.vision.boss_progress import (
    boss_progress_is_full,
)
from hauntedroom.flows.automap_support.vision.build import (
    find_first_available_build_option,
)
from hauntedroom.flows.automap_support.vision.gear import find_gear_button
from hauntedroom.flows.automap_support.vision.hero_levelup import (
    hero_levelup_price_is_available,
)
from hauntedroom.flows.automap_support.vision.template_config import AutomapConfig

BOSS_RECHECK_INTERVAL_MS = 400
LUBU_CLOSE_TEMPLATE_NAME = "lubu_close.png"
LUBU_CLOSE_TEMPLATE_THRESHOLD = 0.80

SituationHandler = Callable[[np.ndarray, np.ndarray], Awaitable[bool]]


async def _click(page, x: int, y: int) -> None:
    await bot_click(page, (x, y))


def _to_grayscale(image: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)


class AutomapFlow:
    """Own per-map state and coordinate handlers in priority order."""

    def __init__(
        self,
        page,
        stop_event: asyncio.Event | None,
        config: AutomapConfig,
        templates: AutomapTemplates,
        state: MapState | None = None,
        run_state: MapRunState | None = None,
        on_win: Callable[[], int] | None = None,
    ) -> None:
        self.page = page
        self.stop_event = stop_event
        self.config = config
        self.templates = templates
        self.state = state or MapState()
        self.run_state = run_state or MapRunState()
        self.lubu_close_template = next(
            (
                template
                for path, template in templates.map_blockers
                if path.name == LUBU_CLOSE_TEMPLATE_NAME
            ),
            None,
        )
        self.map_lifecycle = MapLifecycle(
            page,
            stop_event,
            config=config,
            templates=templates,
            state=self.state,
            run_state=self.run_state,
            on_win=on_win,
            capture_page_bgr_fn=capture_page_bgr,
            find_template_fn=find_template,
            find_template_matches_fn=find_template_matches,
        )

    async def handle_new_account_lubu_close(
        self,
        _frame_bgr: np.ndarray,
        frame_gray: np.ndarray,
    ) -> bool:
        """Dismiss the one-time Lu Bu popup during the new-account map."""
        if (
            not self.run_state.new_account_lubu_popup_active
            or self.lubu_close_template is None
        ):
            return False

        x, y, score = find_template(
            frame_gray,
            self.lubu_close_template,
            LUBU_CLOSE_TEMPLATE_NAME,
        )
        if score < LUBU_CLOSE_TEMPLATE_THRESHOLD:
            return False

        print(
            colorize(
                f"Lu Bu close at {x},{y}, score={score:.3f}; clicking, then "
                f"confirming disappearance in {AUTOMAP_ACTION_DELAY_MS}ms.",
                BLUE,
            ),
            flush=True,
        )
        await _click(self.page, x, y)
        if not await wait_for_flow_timeout(
            self.page,
            AUTOMAP_ACTION_DELAY_MS,
            self.stop_event,
        ):
            return True

        confirm_frame = _to_grayscale(await capture_page_bgr(self.page))
        _, _, confirm_score = find_template(
            confirm_frame,
            self.lubu_close_template,
            LUBU_CLOSE_TEMPLATE_NAME,
        )
        if confirm_score < LUBU_CLOSE_TEMPLATE_THRESHOLD:
            print(
                colorize("Lu Bu close disappeared; resuming auto-map.", BLUE),
                flush=True,
            )
        else:
            print(
                f"Lu Bu close is still present, score={confirm_score:.3f}; "
                "will retry.",
                flush=True,
            )
        return True

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
        handled = await self.click_level_spin_if_present(frame_gray)
        if handled:
            self.state.map_end_armed = True
        return handled

    async def handle_map_end(
        self,
        _frame_bgr: np.ndarray,
        frame_gray: np.ndarray,
    ) -> bool:
        outcome = await self.map_lifecycle.handle_map_end(frame_gray)
        return outcome.handled

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
        if outcome.handled:
            self.state.map_end_armed = True
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
            find_pause_exit_button_fn=find_pause_exit_button,
            deploy_boss_pet_fn=deploy_boss_pet,
            click_fn=_click,
            capture_page_bgr_fn=capture_page_bgr,
            wait_for_flow_timeout_fn=wait_for_flow_timeout,
        )
        if outcome.final_boss_pet_deployed is not None:
            self.state.final_boss_pet_deployed = outcome.final_boss_pet_deployed
        self.state.boss_detection_logged = outcome.boss_detection_logged
        if outcome.final_boss_detected:
            self.state.map_end_armed = True
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
        if outcome.handled:
            self.state.map_end_armed = True
        return outcome.handled

    async def handle_build_structure(
        self,
        _frame_bgr: np.ndarray,
        frame_gray: np.ndarray,
    ) -> bool:
        handled = await _handle_build_structure(
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
        if handled:
            self.state.map_end_armed = True
        return handled

    async def run(self) -> bool:
        """Run handlers in priority order until stopped or the map completes."""
        map_end_handler = self.handle_map_end
        boss_handler = self.handle_boss_critical
        handlers: tuple[SituationHandler, ...] = (
            self.handle_new_account_lubu_close,
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
                        if self.state.completed:
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
                        return self.state.completed
                    break
            else:
                await wait_for_flow_timeout(
                    self.page,
                    AUTOMAP_POLL_MS,
                    self.stop_event,
                )

        print(
            colorize("Auto-map flow stopped; runner is idle.", RED),
            flush=True,
        )
        return False
