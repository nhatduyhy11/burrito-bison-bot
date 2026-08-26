import asyncio
from pathlib import Path
from typing import Optional

import numpy as np

from hauntedroom.actions.hero_select_battle import click_hero_select_battle
from hauntedroom.actions.models import (
    Action,
    ClearBlockersAction,
    ClickAction,
    ClickHeroSelectBattleAction,
    ClickMapExitBackAction,
    ClickPauseExitAction,
    ClickTemplateAction,
    WaitAction,
)
from hauntedroom.actions.pause_exit import click_map_exit_back, click_pause_exit
from hauntedroom.control_events.blockers import clear_blockers
from hauntedroom.core.mouse import bot_click
from hauntedroom.core.runtime import wait_for_flow_timeout, wait_with_countdown
from hauntedroom.core.template_detection import TemplateWaitStatus, wait_for_template
from hauntedroom.core.template_matching import find_template
from hauntedroom.core.vision import capture_page_grayscale


def action_label(loop_index: int, action_index: int, note: Optional[str]) -> str:
    label = f"{loop_index}.{action_index}"
    return f"{label} ({note})" if note else label


async def execute_clear_blockers_action(
    page,
    action: ClearBlockersAction,
    templates: dict[Path, np.ndarray],
    label: str,
    stop_event: Optional[asyncio.Event],
) -> bool:
    return await clear_blockers(
        page=page,
        blocker_paths=action.blocker_paths,
        until_template_path=action.until_template_path,
        templates=templates,
        threshold=action.threshold,
        timeout_ms=action.timeout_ms,
        poll_ms=action.poll_ms,
        delay_ms=action.delay_ms,
        click_positions=action.click_positions,
        label=label,
        stop_event=stop_event,
        until_template_scales=action.until_template_scales,
    )


async def execute_click_template_action(
    page,
    action: ClickTemplateAction,
    templates: dict[Path, np.ndarray],
    label: str,
    stop_event: Optional[asyncio.Event],
) -> bool:
    template_path = action.template_path
    skip_template_path = action.skip_if_template_path
    repeat_delay_ms = action.effective_repeat_delay_ms

    print(
        f"{label}: wait for {template_path.name}",
        flush=True,
    )
    result = await wait_for_template(
        page,
        templates[template_path],
        template_path.name,
        action.threshold,
        action.timeout_ms,
        action.poll_ms,
        stop_event=stop_event,
        skip_template=(
            templates[skip_template_path] if skip_template_path is not None else None
        ),
        skip_template_name=(
            skip_template_path.name if skip_template_path is not None else None
        ),
        click_position=action.click_position,
        template_scales=action.template_scales,
        skip_template_scales=action.skip_template_scales,
        region=action.region,
    )
    if result.status is TemplateWaitStatus.ALTERNATIVE_MATCHED:
        skip_template_name = (
            skip_template_path.name
            if skip_template_path is not None
            else "skip template"
        )
        print(
            f"{label}: skip {template_path.name}; "
            f"{skip_template_name} already ready",
            flush=True,
        )
        return True
    if result.status is TemplateWaitStatus.STOPPED:
        return False

    assert result.match is not None
    x, y, score = result.match
    repeat_summary = (
        f"; up to {action.click_count - 1} repeat(s), recheck after "
        f"{repeat_delay_ms}ms"
        if action.recheck_before_repeat and action.click_count > 1
        else f"; click {action.click_count} time(s)"
    )
    print(
        f"{label}: detected "
        f"{template_path.name} at {x},{y}, score={score:.3f}; "
        f"first click after {action.delay_ms}ms{repeat_summary}",
        flush=True,
    )

    for click_index in range(action.click_count):
        wait_ms = action.delay_ms if click_index == 0 else repeat_delay_ms
        if not await wait_for_flow_timeout(page, wait_ms, stop_event):
            return False

        if click_index > 0 and action.recheck_before_repeat:
            screenshot = await capture_page_grayscale(page)
            x, y, score = find_template(
                screenshot,
                templates[template_path],
                template_path.name,
                action.click_position,
                scales=action.template_scales,
                region=action.region,
            )
            if score < action.threshold:
                print(
                    f"{label}: {template_path.name} disappeared after "
                    f"{click_index} click(s), score={score:.3f}; "
                    "skip remaining repeat clicks",
                    flush=True,
                )
                break
            print(
                f"{label}: {template_path.name} still present at {x},{y}, "
                f"score={score:.3f}; repeat click",
                flush=True,
            )

        await bot_click(page, (x, y), button=action.button)

    return True


async def execute_action(
    page,
    action: Action,
    templates: dict[Path, np.ndarray],
    loop_index: int,
    action_index: int,
    stop_event: Optional[asyncio.Event],
) -> bool:
    label = action_label(loop_index, action_index, action.note)
    if isinstance(action, ClickAction):
        print(f"{label}: click {action.x},{action.y}", flush=True)
        await bot_click(page, (action.x, action.y), button=action.button)
        return True
    if isinstance(action, ClearBlockersAction):
        return await execute_clear_blockers_action(
            page,
            action,
            templates,
            label,
            stop_event,
        )
    if isinstance(action, ClickTemplateAction):
        return await execute_click_template_action(
            page,
            action,
            templates,
            label,
            stop_event,
        )
    if isinstance(action, ClickHeroSelectBattleAction):
        return await click_hero_select_battle(
            page=page,
            blocker_paths=action.blocker_paths,
            header_template_path=action.header_template_path,
            entry_template_path=action.entry_template_path,
            templates=templates,
            threshold=action.threshold,
            timeout_ms=action.timeout_ms,
            poll_ms=action.poll_ms,
            delay_ms=action.delay_ms,
            click_positions=action.click_positions,
            entry_click_position=action.entry_click_position,
            entry_template_scales=action.entry_template_scales,
            label=label,
            stop_event=stop_event,
        )
    if isinstance(action, ClickPauseExitAction):
        return await click_pause_exit(
            page=page,
            timeout_ms=action.timeout_ms,
            poll_ms=action.poll_ms,
            delay_ms=action.delay_ms,
            label=label,
            stop_event=stop_event,
        )
    if isinstance(action, ClickMapExitBackAction):
        return await click_map_exit_back(
            page=page,
            skip_if_template_path=action.skip_if_template_path,
            templates=templates,
            threshold=action.threshold,
            timeout_ms=action.timeout_ms,
            poll_ms=action.poll_ms,
            delay_ms=action.delay_ms,
            label=label,
            stop_event=stop_event,
        )
    if isinstance(action, WaitAction):
        return await wait_with_countdown(page, action.ms, label, stop_event)

    raise TypeError(f"Unsupported action object: {action!r}")
