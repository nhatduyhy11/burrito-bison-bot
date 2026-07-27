import json
from pathlib import Path

from hauntedroom.cv_pattern_matching import validate_threshold


SUPPORTED_CLICK_POSITIONS = {"bottom_left", "center", "top_middle"}


def validate_timing_fields(action: dict, index: int) -> None:
    for field in ("timeout_ms", "poll_ms", "delay_ms"):
        if field in action and int(action[field]) < 0:
            raise ValueError(f"Action #{index} {field} cannot be negative.")


def load_actions(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as file:
        actions = json.load(file)

    if not isinstance(actions, list):
        raise ValueError("Actions file must contain a JSON array.")

    for index, action in enumerate(actions, start=1):
        if not isinstance(action, dict):
            raise ValueError(f"Action #{index} must be an object.")

        kind = action.get("type")
        if kind == "click":
            if "x" not in action or "y" not in action:
                raise ValueError(f"Action #{index} click requires x and y.")
        elif kind == "click_template":
            template = action.get("template")
            if not isinstance(template, str) or not template:
                raise ValueError(f"Action #{index} click_template requires template.")

            template_path = (path.parent / template).resolve()
            if not template_path.is_file():
                raise ValueError(
                    f"Action #{index} template does not exist: {template_path}"
                )
            action["_template_path"] = template_path

            skip_if_template = action.get("skip_if_template")
            if skip_if_template is not None:
                if not isinstance(skip_if_template, str) or not skip_if_template:
                    raise ValueError(
                        f"Action #{index} skip_if_template must be a template path."
                    )
                skip_if_template_path = (path.parent / skip_if_template).resolve()
                if not skip_if_template_path.is_file():
                    raise ValueError(
                        f"Action #{index} skip_if_template does not exist: "
                        f"{skip_if_template_path}"
                    )
                action["_skip_if_template_path"] = skip_if_template_path

            validate_threshold(action, index)
            validate_timing_fields(action, index)
            click_count = int(action.get("click_count", 1))
            if click_count < 1:
                raise ValueError(f"Action #{index} click_count must be at least 1.")
        elif kind == "clear_blockers":
            templates_dir = action.get("templates_dir")
            until_template = action.get("until_template")
            if not isinstance(templates_dir, str) or not templates_dir:
                raise ValueError(
                    f"Action #{index} clear_blockers requires templates_dir."
                )
            if not isinstance(until_template, str) or not until_template:
                raise ValueError(
                    f"Action #{index} clear_blockers requires until_template."
                )

            templates_dir_path = (path.parent / templates_dir).resolve()
            if not templates_dir_path.is_dir():
                raise ValueError(
                    f"Action #{index} blocker directory does not exist: "
                    f"{templates_dir_path}"
                )
            blocker_paths = sorted(templates_dir_path.glob("*.png"))
            if not blocker_paths:
                raise ValueError(
                    f"Action #{index} blocker directory has no PNG files: "
                    f"{templates_dir_path}"
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
            blocker_paths = [
                blocker_paths_by_name[name] for name in prioritized_names
            ]

            until_template_path = (path.parent / until_template).resolve()
            if not until_template_path.is_file():
                raise ValueError(
                    f"Action #{index} until_template does not exist: "
                    f"{until_template_path}"
                )

            action["_blocker_paths"] = blocker_paths
            action["_until_template_path"] = until_template_path

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
                if click_position not in SUPPORTED_CLICK_POSITIONS:
                    raise ValueError(
                        f"Action #{index} unsupported click position: "
                        f"{click_position!r}."
                    )
            validate_threshold(action, index)
            validate_timing_fields(action, index)
        elif kind == "wait":
            if "ms" not in action:
                raise ValueError(f"Action #{index} wait requires ms.")
        else:
            raise ValueError(f"Action #{index} has unsupported type: {kind!r}.")

    return actions
