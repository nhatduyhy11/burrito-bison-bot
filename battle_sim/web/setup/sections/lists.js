// Trap / Pet / Spell lists: name, level (traps, pets), star.
import { Accordion, html, NumberInput, Select } from "../ui.js";
import { LIMITS } from "../profile-io.js";
import { AddButton, RemoveButton, nameOptions } from "./shared.js";

const LIST_TITLES = { traps: "Trap", pets: "Pet", spells: "Spell (thần)" };

const newListItem = (group) => (name) => (group === "spells" ? { name, star: 1 } : { name, level: 1, star: 1 });

export function ListSection({ ctx, group }) {
  const enabled = !!ctx.state[group];
  const onToggle = (on) => ctx.toggleWithPrefill(group, on);
  return html`
    <${Accordion}
      title=${LIST_TITLES[group]}
      hint=${`tối đa ${LIMITS[group]}; tắt = giữ từ capture`}
      override=${{ enabled, onToggle }}
    >
      ${enabled && html`<${ListBody} ctx=${ctx} group=${group} />`}
    <//>
  `;
}

function ListBody({ ctx, group }) {
  const rows = ctx.state[group].map(
    (item, index) => html`<${ListRow} key=${index} ctx=${ctx} group=${group} item=${item} index=${index} />`,
  );
  return html`
    ${rows}
    <div class="row"><${AddButton} ctx=${ctx} group=${group} make=${newListItem(group)} /></div>
  `;
}

function ListRow({ ctx, group, item, index }) {
  const { state, dict, update } = ctx;
  const info = dict[group][item.name];
  const options = nameOptions(dict, group, state[group].map((x) => x.name), item.name);
  const edit = (fn) => update((s) => void fn(s[group][index]));
  const setName = (v) => edit((x) => (x.name = v));
  const setLevel = (v) => edit((x) => (x.level = v));
  const setStar = (v) => edit((x) => (x.star = v));
  const level = info.maxLevel
    ? html`<label>Level <${NumberInput} value=${item.level} min=${1} max=${info.maxLevel} onChange=${setLevel} /></label>`
    : null;
  return html`
    <div class="row list-row">
      <${Select} options=${options} value=${item.name} onChange=${setName} />
      ${level}
      <label>Sao <${NumberInput} value=${item.star} min=${1} max=${info.maxStar} onChange=${setStar} /></label>
      <span class="note">${`max lv ${info.maxLevel || "-"} / ${info.maxStar}★`}</span>
      <${RemoveButton} ctx=${ctx} group=${group} index=${index} />
    </div>
  `;
}
