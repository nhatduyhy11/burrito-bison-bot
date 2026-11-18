// Trap / Pet / Spell lists: name, level (traps, pets), star.
import { Accordion, html, label, NumberInput, plain, Select, SelectPop } from "../ui.js";
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

// Hover summary for a pet: one block per star (Sao 1..maxStar) listing the skills a pet gains or
// upgrades at that star. Pets have up to 5 skills, each unlocking/upgrading on its own stars.
function petPop(pet) {
  const runs = pet.skills.flatMap((skill) => skill.starSkills);
  const star = (n) => {
    const here = runs.filter((s) => s.stars.includes(n));
    return html`
      <div class="pop-line" key=${n}>
        <span class="hint">Sao ${n}</span>
        ${here.length ? here.map((s) => html`
          <div class="pop-desc" key=${s.code}><b>${label(s)}</b> · ${plain(s.desc_vn)}</div>`)
          : html`<div class="pop-desc note">Không đổi skill</div>`}
      </div>
    `;
  };
  return html`
    <div class="pop-title">${label(pet)}</div>
    ${Array.from({ length: pet.maxStar }, (_, i) => star(i + 1))}
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
  const picker = group === "pets"
    ? html`<${SelectPop} options=${options.map(([key, text, disabled, grp]) => [key, text, petPop(dict.pets[key]), disabled, grp])}
        value=${item.name} onChange=${setName} />`
    : html`<${Select} options=${options} value=${item.name} onChange=${setName} />`;
  return html`
    <div class="row list-row">
      ${picker}
      ${level}
      <label>Sao <${NumberInput} value=${item.star} min=${1} max=${info.maxStar} onChange=${setStar} /></label>
      <span class="note">${`max lv ${info.maxLevel || "-"} / ${info.maxStar}★`}</span>
      <${RemoveButton} ctx=${ctx} group=${group} index=${index} />
    </div>
  `;
}
