// Form sections of the setup page, in page order: Account gốc, Màn chơi, then tabs (Teams, Summoner).
// Each section takes ctx = { state, dict, update(fn), toggleWithPrefill(group, on) }; update(fn)
// runs fn on a copy of the state (fn may also return a replacement), normalizes it with skin-rules
// and re-renders. Inactive tabs stay rendered (hidden) so accordion open state survives switching.
import { useState } from "preact/hooks";
import { html } from "../ui.js";
import { AccountSection } from "./account.js";
import { MapSection } from "./map.js";
import { HeroesSection } from "./heroes.js";
import { MountSection } from "./mounts.js";
import { SummonerSection } from "./summoner.js";
import { ListSection } from "./lists.js";
import { BuildingsSection } from "./buildings.js";
import { GoldenSection } from "./golden.js";
import { AntiquesSection } from "./antiques.js";

const TAB_KEY = "battleSimSetupTab";
const TABS = [["teams", "Teams"], ["summoner", "Summoner"]];

function savedTab() {
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
  return html`<div class="tabs" role="tablist">${buttons}</div>`;
}

export function FormSections({ ctx, battles }) {
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
    <${AccountSection} ctx=${ctx} battles=${battles} />
    <${MapSection} ctx=${ctx} />
    <${TabBar} active=${tab} onSelect=${selectTab} />
    <div role="tabpanel" hidden=${tab !== "teams"}>
      <${HeroesSection} ctx=${ctx} />
      ${list("traps")}
      ${list("pets")}
      <${SummonerSection} ctx=${ctx} />
      <${BuildingsSection} ctx=${ctx} />
      ${list("spells")}
    </div>
    <div role="tabpanel" hidden=${tab !== "summoner"}>
      <${MountSection} ctx=${ctx} />
      <${AntiquesSection} ctx=${ctx} />
      <${GoldenSection} ctx=${ctx} />
    </div>
  `;
}
