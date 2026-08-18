import asyncio
from pathlib import Path
from typing import Mapping, Optional

from hauntedroom import settings
from hauntedroom.actions.models import Action
from hauntedroom.core.runtime import save_live_screenshot, start_hotkey_listener


START_AUTO_HOTKEY_ACTIONS = frozenset(
    {
        "pause_resume",
        "pause_at_boss",
        "pause_at_final_boss",
        "stop",
        "screenshot",
    }
)


def validate_start_auto_hotkeys(hotkeys: Mapping[str, str]) -> dict[str, str]:
    """Validate and copy the configurable Shift+3 control mapping."""
    configured_actions = set(hotkeys)
    if configured_actions != START_AUTO_HOTKEY_ACTIONS:
        missing = sorted(START_AUTO_HOTKEY_ACTIONS - configured_actions)
        unknown = sorted(configured_actions - START_AUTO_HOTKEY_ACTIONS)
        raise ValueError(
            "START_AUTO_HOTKEYS must contain exactly the supported actions; "
            f"missing={missing}, unknown={unknown}."
        )

    configured_keys = list(hotkeys.values())
    invalid_keys = sorted(
        [key for key in configured_keys if key not in tuple("0123456789")],
        key=repr,
    )
    if invalid_keys:
        raise ValueError(
            "START_AUTO_HOTKEYS values must be digit strings from '0' to '9'; "
            f"invalid={invalid_keys}."
        )
    if len(set(configured_keys)) != len(configured_keys):
        raise ValueError("START_AUTO_HOTKEYS cannot assign one digit twice.")

    return dict(hotkeys)


def format_start_auto_hotkeys(hotkeys: Mapping[str, str]) -> str:
    return (
        f"Shift+{hotkeys['pause_resume']} pause/resume; "
        f"Shift+{hotkeys['pause_at_boss']} pause at boss; "
        f"Shift+{hotkeys['pause_at_final_boss']} pause at final boss; "
        f"Shift+{hotkeys['screenshot']} screenshot; "
        f"Shift+{hotkeys['stop']} stop"
    )


def format_flow_menu(flow_commands: Mapping[str, object]) -> str:
    return "\n".join(
        f"  Shift+{command.key}    {command.menu_label}"
        for command in flow_commands.values()
    )


def start_resolved_flow(command, page, resolved, stop_event, debug: bool):
    print(f"Starting {command.name} flow...", flush=True)
    return asyncio.create_task(resolved.run(page, stop_event, debug))


async def handle_control_command(
    command: str,
    page,
    flow_task,
    stop_event,
    current_command: Optional[str],
    start_auto_hotkeys: Optional[Mapping[str, str]] = None,
) -> bool:
    if current_command == "3" and flow_task is not None:
        hotkeys = (
            start_auto_hotkeys
            if start_auto_hotkeys is not None
            else validate_start_auto_hotkeys(settings.START_AUTO_HOTKEYS)
        )
        action = next(
            (name for name, key in hotkeys.items() if key == command),
            None,
        )

        if action == "stop":
            print("Stopping current flow...", flush=True)
            stop_event.set()
            return True

        if action == "screenshot":
            await save_live_screenshot(page)
            print("Current flow continues.", flush=True)
            return True

        if action == "pause_resume":
            if stop_event.is_paused:
                stop_event.resume()
                print("Start-auto loop resumed.", flush=True)
            else:
                stop_event.pause()
                print(
                    "Start-auto loop paused. "
                    f"Press Shift+{hotkeys['pause_resume']} to resume or "
                    f"Shift+{hotkeys['stop']} to stop.",
                    flush=True,
                )
            return True

        if action == "pause_at_boss":
            if stop_event.pause_at_next_boss(final_only=False):
                print(
                    "Start-auto loop will pause at the next boss.",
                    flush=True,
                )
            return True

        if action == "pause_at_final_boss":
            if stop_event.pause_at_next_boss(final_only=True):
                print(
                    "Start-auto loop will pause at the final boss.",
                    flush=True,
                )
            return True

        # While start-auto owns the runner, unmapped Shift+digit commands are
        # intentionally ignored.
        return True

    if command == "0":
        if flow_task is None:
            print("Runner is already idle.", flush=True)
        else:
            print("Stopping current flow...", flush=True)
            stop_event.set()
        return True

    if command == "8":
        await save_live_screenshot(page)
        if flow_task is None:
            print("Runner idle.", flush=True)
        else:
            print("Current flow continues.", flush=True)
        return True

    return False


def finish_flow_task(flow_task) -> None:
    try:
        flow_task.result()
    except Exception as error:
        print(f"Flow failed; runner is idle: {error}", flush=True)


async def run_standby_controller(
    page,
    actions: list[Action],
    flow_commands: Mapping[str, object],
    dev_reload: bool = False,
    debug: bool = False,
    actions_path: Optional[Path] = None,
) -> None:
    start_auto_hotkeys = validate_start_auto_hotkeys(settings.START_AUTO_HOTKEYS)
    command_queue: asyncio.Queue[str] = asyncio.Queue()
    await start_hotkey_listener(page, command_queue)

    flow_task = None
    stop_event = None
    current_command = None
    print(
        "\n"
        "Haunted Room runner ready\n"
        "-------------------------\n"
        f"{format_flow_menu(flow_commands)}\n"
        "  Shift+8    Capture screenshot\n"
        "  Shift+0    Stop current flow\n"
        f"  During Shift+3: {format_start_auto_hotkeys(start_auto_hotkeys)}\n"
        "  Ctrl+C     Close runner\n"
        "-------------------------\n"
        "Runner idle.",
        flush=True,
    )

    command_task = asyncio.create_task(command_queue.get())
    try:
        while True:
            wait_for = {command_task}
            if flow_task is not None:
                wait_for.add(flow_task)

            done, _ = await asyncio.wait(wait_for, return_when=asyncio.FIRST_COMPLETED)

            if flow_task is not None and flow_task in done:
                finish_flow_task(flow_task)
                flow_task = None
                stop_event = None
                current_command = None
                print("Runner idle.", flush=True)

            if command_task not in done:
                continue

            command_key = command_task.result()
            command_task = asyncio.create_task(command_queue.get())

            if await handle_control_command(
                command_key,
                page,
                flow_task,
                stop_event,
                current_command,
                start_auto_hotkeys,
            ):
                continue

            command = flow_commands.get(command_key)
            if command is None:
                print(f"Shift+{command_key}: no flow configured.", flush=True)
                continue

            if flow_task is not None:
                print(
                    f"Runner busy; press Shift+0 before starting Shift+{command_key}.",
                    flush=True,
                )
                continue

            try:
                resolved = command.resolve(actions, dev_reload, actions_path)
                if command_key == "3":
                    start_auto_hotkeys = validate_start_auto_hotkeys(
                        settings.START_AUTO_HOTKEYS
                    )
            except Exception as error:
                print(f"Dev reload failed; runner remains idle: {error}", flush=True)
                continue

            stop_event = command.control_factory()
            current_command = command_key
            actions = resolved.actions
            if command_key == "3":
                print(
                    "Start-auto controls: "
                    f"{format_start_auto_hotkeys(start_auto_hotkeys)}.",
                    flush=True,
                )
            flow_task = start_resolved_flow(
                command,
                page,
                resolved,
                stop_event,
                debug,
            )
    finally:
        command_task.cancel()
        await asyncio.gather(command_task, return_exceptions=True)
        if flow_task is not None:
            stop_event.set()
            await asyncio.gather(flow_task, return_exceptions=True)
