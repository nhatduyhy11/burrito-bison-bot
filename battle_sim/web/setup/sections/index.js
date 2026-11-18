// Form sections of the setup page, in page order: Màn chơi, then tabs (Teams, Support, Summoner).
// Teams holds the hero cards (skins, Dị Năng, Thần Khí editor in sections/artifact.js); Support
// holds Trap, Pet, Spell (lists.js), building skins, Golden; Summoner holds what the Summoner
// wears: Trang bị (gear skill checkboxes) and Skill Summoner (both in summoner.js), Mounts, Đồ Cổ.
// (Account gốc lives inside the "Thao tác" section, see side.js.)
// Each section takes ctx = { state, dict, update(fn), toggleWithPrefill(group, on) }; update(fn)
// runs fn on a copy of the state (fn may also return a replacement), normalizes it with skin-rules
// and re-renders. Inactive tabs stay rendered (hidden) so accordion open state survives switching.
import { useState } from "preact/hooks";
import { html } from "../ui.js";
import { MapSection } from "./map.js";
import { HeroesSection } from "./heroes.js";
import { MountSection } from "./mounts.js";
import { SummonerGearSection, SummonerSection } from "./summoner.js";
import { ListSection } from "./lists.js";
import { BuildingsSection } from "./buildings.js";
import { GoldenSection } from "./golden.js";
import { AntiquesSection } from "./antiques.js";

const TAB_KEY = "battleSimSetupTab";
const TABS = [["teams", "Teams"], ["support", "Support"], ["summoner", "Summoner"]];

function savedTab() {
  // Legacy key "heroDetail" (tab removed by the bbb-xbq/bbb-1rl rework) falls back to Teams through
  // the same unknown-key path; the next explicit pick overwrites the key. ("summoner" was legacy
  // too until bbb-505 reused it for this tab — old stored values land on the new tab, which is fine.)
  try {
    const tab = localStorage.getItem(TAB_KEY);
    return TABS.some(([key]) => key === tab) ? tab : TABS[0][0];
  } catch {
    return TABS[0][0];
  }
}

function TabBar({ active, onSelect }) {
  const buttons = TABS.map(([key, title]) => {
    const select = () => onSelect(key);
    return html`
      <button type="button" role="tab" key=${key} class=${key === active ? "tab active" : "tab"}
        aria-selected=${key === active} onClick=${select}>${title}</button>
    `;
  });
  return html`
    <div class="tabs" role="tablist">${buttons}</div>
  `;
}

export function FormSections({ ctx }) {
  const [tab, setTab] = useState(savedTab);
  const selectTab = (key) => {
    setTab(key);
    try {
      localStorage.setItem(TAB_KEY, key);
    } catch {
      // storage off
    }
  };
  const list = (group) => html`<${ListSection} ctx=${ctx} group=${group} />`;
  return html`
    <${MapSection} ctx=${ctx} />
    <hr class="section-divider" />
    <${TabBar} active=${tab} onSelect=${selectTab} />
    <div role="tabpanel" hidden=${tab !== "teams"}>
      <${HeroesSection} ctx=${ctx} />
    </div>
    <div role="tabpanel" hidden=${tab !== "support"}>
      ${list("traps")}
      ${list("pets")}
      ${list("spells")}
      <${BuildingsSection} ctx=${ctx} />
      <${GoldenSection} ctx=${ctx} />
    </div>
    <div role="tabpanel" hidden=${tab !== "summoner"}>
      <${SummonerGearSection} ctx=${ctx} />
      <${SummonerSection} ctx=${ctx} />
      <${MountSection} ctx=${ctx} />
      <${AntiquesSection} ctx=${ctx} />
    </div>
  `;
}
