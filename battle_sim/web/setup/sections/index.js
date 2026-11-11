// Form sections of the setup page, in page order. Each section takes ctx =
// { state, dict, update(fn), toggleWithPrefill(group, on) }; update(fn) runs fn on a copy of the
// state (fn may also return a replacement), normalizes it with skin-rules and re-renders.
import { html } from "../ui.js";
import { MapSection } from "./map.js";
import { HeroesSection } from "./heroes.js";
import { MountSection } from "./mounts.js";
import { SummonerSection } from "./summoner.js";
import { ListSection } from "./lists.js";
import { BuildingsSection } from "./buildings.js";
import { GoldenSection } from "./golden.js";
import { AntiquesSection } from "./antiques.js";

const LIST_GROUPS = ["traps", "pets", "spells"];

export function FormSections({ ctx }) {
  const lists = LIST_GROUPS.map((group) => html`<${ListSection} key=${group} ctx=${ctx} group=${group} />`);
  return html`
    <${MapSection} ctx=${ctx} />
    <${HeroesSection} ctx=${ctx} />
    <${MountSection} ctx=${ctx} />
    <${SummonerSection} ctx=${ctx} />
    ${lists}
    <${BuildingsSection} ctx=${ctx} />
    <${GoldenSection} ctx=${ctx} />
    <${AntiquesSection} ctx=${ctx} />
  `;
}
