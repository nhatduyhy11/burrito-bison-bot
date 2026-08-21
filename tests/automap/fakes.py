from __future__ import annotations

import numpy as np

from hauntedroom.flows.automap_support.config import AutomapConfig
from hauntedroom.flows.automap_support.templates import AutomapTemplates
from hauntedroom.flows.automap_support.vision.hero_levelup import (
    load_hero_levelup_templates,
)


def fake_automap_templates(
    config: AutomapConfig | None = None,
    *,
    load_hero_templates: bool = False,
) -> AutomapTemplates:
    """Build explicit, in-memory templates for tests instantiating the flow."""
    config = config or AutomapConfig()
    image = np.zeros((2, 2), dtype=np.uint8)
    hero_levelup = (
        load_hero_levelup_templates(config.hero_levelup_template_paths)
        if load_hero_templates
        else {}
    )
    return AutomapTemplates(
        lv_up=image,
        built=image,
        lv_spin=image,
        map_end=image,
        win_reward=image,
        reward_list_title=image,
        daily_first_win=image,
        daily_first_win_checkbox=image,
        daily_first_win_checked=image,
        boss_hp=image,
        start_home=image,
        exit_click=image,
        map_completion_blockers=(),
        hero_levelup=hero_levelup,
    )
