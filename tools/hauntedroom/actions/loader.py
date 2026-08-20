import json
from pathlib import Path

from hauntedroom.actions.defaults import (
    DEFAULT_CLICK_DELAY_MS,
    DEFAULT_TEMPLATE_POLL_MS,
    DEFAULT_TEMPLATE_TIMEOUT_MS,
)
from hauntedroom.actions.models import (
    Action,
    ClearBlockersAction,
    ClickAction,
    ClickTemplateAction,
    WaitAction,
)
from hauntedroom.actions.validation import (
    load_button,
    load_click_position,
    load_non_negative_int,
    load_region,
    load_scales,
    load_threshold,
    parse_int,
)


def resolve_template_file(path: Path, raw_template: str, index: int, label: str) -> Path:
    template_path = (path.parent / raw_template).resolve()
    if not template_path.is_file():
        raise ValueError(f"Action #{index} {label} does not exist: {template_path}")
    return template_path


def load_click_action(action: dict, index: int) -> ClickAction:
    if "x" not in action or "y" not in action:
        raise ValueError(f"Action #{index} click requires x and y.")
    return ClickAction(
        x=parse_int(action["x"], index, "x"),
        y=parse_int(action["y"], index, "y"),
        button=load_button(action, index),
        note=action.get("note"),
    )


def load_click_template_action(
    action: dict,
    index: int,
    path: Path,
) -> ClickTemplateAction:
    template = action.get("template")
    if not isinstance(template, str) or not template:
        raise ValueError(f"Action #{index} click_template requires template.")

    template_path = resolve_template_file(path, template, index, "template")

    skip_if_template_path = None
    skip_if_template = action.get("skip_if_template")
    if skip_if_template is not None:
        if not isinstance(skip_if_template, str) or not skip_if_template:
            raise ValueError(
                f"Action #{index} skip_if_template must be a template path."
            )
        skip_if_template_path = resolve_template_file(
            path,
            skip_if_template,
            index,
            "skip_if_template",
        )

    threshold = load_threshold(action, index)
    template_scales = load_scales(action, index, "scales")
    skip_template_scales = load_scales(action, index, "skip_template_scales")
    click_count = parse_int(action.get("click_count", 1), index, "click_count")
    if click_count < 1:
        raise ValueError(f"Action #{index} click_count must be at least 1.")
    recheck_before_repeat = action.get("recheck_before_repeat", False)
    if not isinstance(recheck_before_repeat, bool):
        raise ValueError(f"Action #{index} recheck_before_repeat must be a boolean.")
    click_position = load_click_position(
        action.get("click_position", "center"),
        index,
    )

    return ClickTemplateAction(
        template_path=template_path,
        threshold=threshold,
        timeout_ms=load_non_negative_int(
            action,
            index,
            "timeout_ms",
            DEFAULT_TEMPLATE_TIMEOUT_MS,
        ),
        poll_ms=load_non_negative_int(
            action,
            index,
            "poll_ms",
            DEFAULT_TEMPLATE_POLL_MS,
        ),
        delay_ms=load_non_negative_int(
            action,
            index,
            "delay_ms",
            DEFAULT_CLICK_DELAY_MS,
        ),
        repeat_delay_ms=(
            load_non_negative_int(action, index, "repeat_delay_ms")
            if "repeat_delay_ms" in action
            else None
        ),
        click_count=click_count,
        recheck_before_repeat=recheck_before_repeat,
        button=load_button(action, index),
        note=action.get("note"),
        skip_if_template_path=skip_if_template_path,
        click_position=click_position,
        template_scales=template_scales,
        skip_template_scales=skip_template_scales,
        region=load_region(action, index),
    )


def load_clear_blockers_action(
    action: dict,
    index: int,
    path: Path,
) -> ClearBlockersAction:
    templates_dir = action.get("templates_dir")
    until_template = action.get("until_template")
    if not isinstance(templates_dir, str) or not templates_dir:
        raise ValueError(f"Action #{index} clear_blockers requires templates_dir.")
    if not isinstance(until_template, str) or not until_template:
        raise ValueError(f"Action #{index} clear_blockers requires until_template.")

    templates_dir_path = (path.parent / templates_dir).resolve()
    if not templates_dir_path.is_dir():
        raise ValueError(
            f"Action #{index} blocker directory does not exist: {templates_dir_path}"
        )
    blocker_paths = sorted(templates_dir_path.glob("*.png"))
    if not blocker_paths:
        raise ValueError(
            f"Action #{index} blocker directory has no PNG files: {templates_dir_path}"
        )

    priority = action.get("priority", [])
    if not isinstance(priority, list) or not all(
        isinstance(name, str) for name in priority
    ):
        raise ValueError(f"Action #{index} priority must be an array of names.")
    blocker_paths_by_name = {
        blocker_path.name: blocker_path for blocker_path in blocker_paths
    }
    unknown_priority_names = [
        name for name in priority if name not in blocker_paths_by_name
    ]
    if unknown_priority_names:
        raise ValueError(
            f"Action #{index} priority references unknown blockers: "
            f"{unknown_priority_names}"
        )
    if len(priority) != len(set(priority)):
        raise ValueError(f"Action #{index} priority contains duplicate names.")
    prioritized_names = priority + [
        blocker_path.name
        for blocker_path in blocker_paths
        if blocker_path.name not in priority
    ]
    blocker_paths = [blocker_paths_by_name[name] for name in prioritized_names]

    until_template_path = resolve_template_file(
        path,
        until_template,
        index,
        "until_template",
    )

    click_positions = action.get("click_positions", {})
    if not isinstance(click_positions, dict):
        raise ValueError(f"Action #{index} click_positions must be an object.")
    blocker_names = {blocker_path.name for blocker_path in blocker_paths}
    for template_name, click_position in click_positions.items():
        if template_name not in blocker_names:
            raise ValueError(
                f"Action #{index} click_positions references unknown blocker: "
                f"{template_name}"
            )
        click_positions[template_name] = load_click_position(click_position, index)

    return ClearBlockersAction(
        blocker_paths=tuple(blocker_paths),
        until_template_path=until_template_path,
        threshold=load_threshold(action, index),
        timeout_ms=load_non_negative_int(
            action,
            index,
            "timeout_ms",
            DEFAULT_TEMPLATE_TIMEOUT_MS,
        ),
        poll_ms=load_non_negative_int(
            action,
            index,
            "poll_ms",
            DEFAULT_TEMPLATE_POLL_MS,
        ),
        delay_ms=load_non_negative_int(
            action,
            index,
            "delay_ms",
            DEFAULT_CLICK_DELAY_MS,
        ),
        click_positions=dict(click_positions),
        note=action.get("note"),
        until_template_scales=load_scales(action, index, "until_template_scales"),
    )


def load_wait_action(action: dict, index: int) -> WaitAction:
    if "ms" not in action:
        raise ValueError(f"Action #{index} wait requires ms.")
    return WaitAction(
        ms=parse_int(action["ms"], index, "ms"),
        note=action.get("note"),
    )


def load_actions(path: Path) -> list[Action]:
    with path.open("r", encoding="utf-8") as file:
        raw_actions = json.load(file)

    if not isinstance(raw_actions, list):
        raise ValueError("Actions file must contain a JSON array.")

    actions: list[Action] = []
    for index, action in enumerate(raw_actions, start=1):
        if not isinstance(action, dict):
            raise ValueError(f"Action #{index} must be an object.")

        kind = action.get("type")
        if kind == "click":
            actions.append(load_click_action(action, index))
        elif kind == "click_template":
            actions.append(load_click_template_action(action, index, path))
        elif kind == "clear_blockers":
            actions.append(load_clear_blockers_action(action, index, path))
        elif kind == "wait":
            actions.append(load_wait_action(action, index))
        else:
            raise ValueError(f"Action #{index} has unsupported type: {kind!r}.")

    return actions
