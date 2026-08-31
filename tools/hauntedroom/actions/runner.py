import asyncio
from pathlib import Path
from typing import Optional

from hauntedroom.actions.models import (
    Action,
    ClearBlockersAction,
    ClickHeroSelectBattleAction,
    ClickMapExitBackAction,
    ClickPauseExitAction,
    ClickTemplateAction,
)
from hauntedroom.actions.runner_executor import action_label, execute_action
from hauntedroom.core.runtime import (
    ACTION_LOOP_COUNT,
    flow_checkpoint,
)
from hauntedroom.core.template_matching import load_template
from hauntedroom.core.terminal import BLUE, ORANGE, colorize


def collect_template_paths(actions: list[Action]) -> set[Path]:
    template_paths: set[Path] = set()
    for action in actions:
        if isinstance(action, ClickTemplateAction):
            template_paths.add(action.template_path)
            if action.skip_if_template_path is not None:
                template_paths.add(action.skip_if_template_path)
        elif isinstance(action, ClearBlockersAction):
            template_paths.update(action.blocker_paths)
            template_paths.add(action.until_template_path)
        elif isinstance(action, ClickHeroSelectBattleAction):
            template_paths.update(action.blocker_paths)
            template_paths.add(action.header_template_path)
            template_paths.add(action.entry_template_path)
        elif isinstance(action, ClickMapExitBackAction):
            if action.skip_if_template_path is not None:
                template_paths.add(action.skip_if_template_path)
        elif isinstance(action, ClickPauseExitAction):
            if action.retry_template_path is not None:
                template_paths.add(action.retry_template_path)
    return template_paths


def log_action_timeout(
    error: TimeoutError,
    loop_index: int,
    loop_total: str,
    label: str,
    timeout_count: int,
    loop_count: Optional[int],
    loop_label: str,
) -> bool:
    print(
        colorize(
            f"{label}: timeout count={timeout_count}/2: {error}",
            ORANGE,
        ),
        flush=True,
    )
    if timeout_count >= 2:
        print(
            colorize("Second timeout; stopping runner.", ORANGE),
            flush=True,
        )
        raise error
    if loop_count is not None and loop_index >= loop_count:
        print(
            colorize(
                "Skipping the rest of the final action attempt; "
                "no retry remains.",
                ORANGE,
            ),
            flush=True,
        )
    else:
        print(
            colorize(
                f"Skipping the rest of {loop_label.lower()} "
                f"{loop_index}/{loop_total}; retrying from the "
                "first action on the next loop.",
                ORANGE,
            ),
            flush=True,
        )
    return True


async def run_actions(
    page,
    actions: list[Action],
    loop_count: Optional[int] = ACTION_LOOP_COUNT,
    stop_event: Optional[asyncio.Event] = None,
    stop_after_success: bool = False,
    loop_label: str = "Action loop",
) -> bool:
    template_paths = collect_template_paths(actions)
    templates = {path: load_template(path) for path in template_paths}
    timeout_count = 0

    loop_index = 0
    while loop_count is None or loop_index < loop_count:
        if not await flow_checkpoint(stop_event):
            print("Flow stopped; runner is idle.", flush=True)
            return False
        loop_index += 1
        loop_total = "infinite" if loop_count is None else str(loop_count)
        start_message = f"{loop_label} {loop_index}/{loop_total} start"
        print(colorize(start_message, BLUE), flush=True)
        loop_timed_out = False

        for action_index, action in enumerate(actions, start=1):
            if not await flow_checkpoint(stop_event):
                print("Flow stopped; runner is idle.", flush=True)
                return False

            label = action_label(loop_index, action_index, action.note)
            try:
                completed = await execute_action(
                    page,
                    action,
                    templates,
                    loop_index,
                    action_index,
                    stop_event,
                )
            except TimeoutError as error:
                timeout_count += 1
                loop_timed_out = log_action_timeout(
                    error,
                    loop_index,
                    loop_total,
                    label,
                    timeout_count,
                    loop_count,
                    loop_label,
                )
                break
            if not completed:
                print("Flow stopped; runner is idle.", flush=True)
                return False

        if loop_timed_out:
            if loop_count is not None and loop_index >= loop_count:
                print(
                    colorize(
                        f"{loop_label} {loop_index}/{loop_total} exhausted "
                        "after a timeout; returning failure.",
                        ORANGE,
                    ),
                    flush=True,
                )
                return False
            continue

        if timeout_count:
            print(
                colorize(
                    f"{loop_label} {loop_index}/{loop_total} completed "
                    "successfully; resetting timeout count to 0.",
                    ORANGE,
                ),
                flush=True,
            )
            timeout_count = 0

        finish_message = f"{loop_label} {loop_index}/{loop_total} finish"
        print(colorize(finish_message, BLUE), flush=True)
        if stop_after_success:
            return True

    return True
