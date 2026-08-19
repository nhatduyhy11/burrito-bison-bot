"""Level-up, level-spin, and build actions for the auto-map battle flow."""

from dataclasses import dataclass

import numpy as np

from hauntedroom.core.terminal import BLUE, colorize


BUILT_TEMPLATE_THRESHOLD = 0.80
AUTOMAP_POLL_MS = 600
AUTOMAP_ACTION_DELAY_MS = 800
LV_SPIN_CLICK_OFFSET_X = -70
LV_SPIN_TEMPLATE_THRESHOLD = 0.58
LV_SPIN_TEMPLATE_SCALES = (1.0, 0.8, 0.67)
LV_SPIN_SEARCH_TOP_RATIO = 0.75
UPGRADE_CONFIRM_CLICK = (430, 366)


@dataclass(frozen=True)
class UpgradeOutcome:
    handled: bool
    initial_gear_unlocked: bool = False


async def click_level_spin_if_present(
    page,
    stop_event,
    frame_gray: np.ndarray,
    *,
    lv_spin_template: np.ndarray,
    lv_spin_template_name: str,
    find_template_fn,
    click_fn,
    wait_for_flow_timeout_fn,
) -> bool:
    search_top = int(frame_gray.shape[0] * LV_SPIN_SEARCH_TOP_RATIO)
    search_frame = frame_gray[search_top:, :]
    x, y, score = find_template_fn(
        search_frame,
        lv_spin_template,
        lv_spin_template_name,
        scales=LV_SPIN_TEMPLATE_SCALES,
    )
    if score < LV_SPIN_TEMPLATE_THRESHOLD:
        return False

    y += search_top
    click_x = max(0, x + LV_SPIN_CLICK_OFFSET_X)
    print(
        colorize(
            f"Level spin interrupt at {x},{y}, score={score:.3f}; "
            f"clicking {click_x},{y}.",
            BLUE,
        ),
        flush=True,
    )
    await click_fn(page, click_x, y)
    await wait_for_flow_timeout_fn(page, AUTOMAP_POLL_MS, stop_event)
    return True


async def handle_level_up(
    page,
    stop_event,
    frame_gray: np.ndarray,
    *,
    lv_up_template: np.ndarray,
    lv_up_template_name: str,
    lv_up_threshold: float,
    capture_page_bgr_fn,
    to_grayscale_fn,
    find_template_matches_fn,
    click_level_spin_if_present_fn,
    click_fn,
    wait_with_countdown_fn,
) -> UpgradeOutcome:
    matches = find_template_matches_fn(
        frame_gray,
        lv_up_template,
        lv_up_template_name,
        threshold=lv_up_threshold,
    )
    if not matches:
        return UpgradeOutcome(False)

    x, y, score = max(matches, key=lambda match: match[1])
    print(
        f"Level up at {x},{y}, score={score:.3f}; "
        "clicking bottom-most match, then confirm in 800ms.",
        flush=True,
    )
    await click_fn(page, x, y)
    if not await wait_with_countdown_fn(
        page,
        AUTOMAP_ACTION_DELAY_MS,
        "Level up",
        stop_event,
    ):
        return UpgradeOutcome(True)
    frame_bgr = await capture_page_bgr_fn(page)
    frame_gray = to_grayscale_fn(frame_bgr)
    if await click_level_spin_if_present_fn(frame_gray):
        return UpgradeOutcome(True)
    await click_fn(page, *UPGRADE_CONFIRM_CLICK)
    return UpgradeOutcome(True, initial_gear_unlocked=True)


async def handle_build_structure(
    page,
    stop_event,
    frame_gray: np.ndarray,
    *,
    built_template: np.ndarray,
    built_template_name: str,
    capture_page_bgr_fn,
    find_template_matches_fn,
    find_first_available_build_option_fn,
    click_fn,
    wait_with_countdown_fn,
) -> bool:
    matches = find_template_matches_fn(
        frame_gray,
        built_template,
        built_template_name,
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
    await click_fn(page, x, y)
    if not await wait_with_countdown_fn(
        page,
        AUTOMAP_ACTION_DELAY_MS,
        "Build menu",
        stop_event,
    ):
        return True

    popup_frame = await capture_page_bgr_fn(page)
    available_option = find_first_available_build_option_fn(popup_frame)
    if available_option is not None:
        print("White-price build option is available; clicking it.", flush=True)
        await click_fn(page, *available_option)
        return True

    print("No white-price build option is available; skipping.", flush=True)
    return True
