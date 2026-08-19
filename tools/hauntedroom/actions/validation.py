from typing import Optional, cast

from hauntedroom.core.template_matching import (
    DEFAULT_TEMPLATE_THRESHOLD,
    SUPPORTED_CLICK_POSITIONS,
    TEMPLATE_SCALES,
    ClickPosition,
    Region,
)


SUPPORTED_MOUSE_BUTTONS = {"left", "middle", "right"}


def parse_int(value: object, index: int, field: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"Action #{index} {field} must be an integer.")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"Action #{index} {field} must be an integer.") from error
    if isinstance(value, float) and not value.is_integer():
        raise ValueError(f"Action #{index} {field} must be an integer.")
    return parsed


def parse_float(value: object, index: int, field: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"Action #{index} {field} must be a number.")
    try:
        return float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"Action #{index} {field} must be a number.") from error


def load_button(action: dict, index: int) -> str:
    button = action.get("button", "left")
    if not isinstance(button, str) or button not in SUPPORTED_MOUSE_BUTTONS:
        raise ValueError(f"Action #{index} unsupported mouse button: {button!r}.")
    return button


def load_click_position(value: object, index: int) -> ClickPosition:
    if not isinstance(value, str) or value not in SUPPORTED_CLICK_POSITIONS:
        raise ValueError(f"Action #{index} unsupported click position: {value!r}.")
    return cast(ClickPosition, value)


def load_scales(action: dict, index: int, field: str) -> tuple[float, ...]:
    raw_scales = action.get(field)
    if raw_scales is None:
        return TEMPLATE_SCALES
    if not isinstance(raw_scales, list) or not raw_scales:
        raise ValueError(f"Action #{index} {field} must be a non-empty array.")

    scales = tuple(
        parse_float(scale, index, f"{field}[{scale_index}]")
        for scale_index, scale in enumerate(raw_scales)
    )
    if any(scale <= 0 for scale in scales):
        raise ValueError(f"Action #{index} {field} must contain positive numbers.")
    return scales


def load_region(action: dict, index: int) -> Optional[Region]:
    raw_region = action.get("region")
    if raw_region is None:
        return None
    if not isinstance(raw_region, list) or len(raw_region) != 4:
        raise ValueError(f"Action #{index} region must be a four-number array.")
    try:
        left, top, right, bottom = (
            parse_int(value, index, f"region[{value_index}]")
            for value_index, value in enumerate(raw_region)
        )
    except ValueError as error:
        raise ValueError(
            f"Action #{index} region must be a four-number array."
        ) from error
    if left < 0 or top < 0 or left >= right or top >= bottom:
        raise ValueError(
            f"Action #{index} region must have non-negative, increasing bounds."
        )
    return left, top, right, bottom


def load_threshold(action: dict, index: int) -> float:
    threshold = parse_float(
        action.get("threshold", DEFAULT_TEMPLATE_THRESHOLD),
        index,
        "threshold",
    )
    if not 0 < threshold <= 1:
        raise ValueError(
            f"Action #{index} threshold must be greater than 0 and at most 1."
        )
    return threshold


def load_non_negative_int(
    action: dict,
    index: int,
    field: str,
    default: Optional[int] = None,
) -> int:
    if field not in action:
        if default is None:
            raise ValueError(f"Action #{index} requires {field}.")
        return default
    value = parse_int(action[field], index, field)
    if value < 0:
        raise ValueError(f"Action #{index} {field} cannot be negative.")
    return value
