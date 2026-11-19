// Trap / Pet / Spell lists: name, level (traps, pets), star.
import { Accordion, html, label, NumberInput, plain, SelectPop, starsLabel } from "../ui.js";
import { LIMITS } from "../profile-state.js";
import { nameOptions } from "./shared.js";

const LIST_TITLES = { traps: "Trap", pets: "Pet", spells: "Spell (thần)" };

const newListItem = (group) => (name) => (group === "spells" ? { name, star: 1 } : { name, level: 1, star: 1 });

export function ListSection({ ctx, group }) {
  const enabled = !!ctx.state[group];
  const onToggle = (on) => ctx.toggleWithPrefill(group, on);
  return html`
    <${Accordion}
      title=${LIST_TITLES[group]}
      hint=${`${LIMITS[group]} slot; tắt = giữ từ capture`}
      override=${{ enabled, onToggle }}
    >
      ${enabled && html`<${ListBody} ctx=${ctx} group=${group} />`}
    <//>
  `;
}

// Every group reserves LIMITS slots: empty slot = picker '(trống)', × = reset the slot to empty.
function ListBody({ ctx, group }) {
  return Array.from({ length: LIMITS[group] }, (_, index) =>
    html`<${ListRow} key=${index} ctx=${ctx} group=${group} item=${ctx.state[group][index] || null} index=${index} />`);
}

// Hover summary for a pet: one block per star (Sao 1..maxStar) listing the skills a pet gains or
// upgrades at that star. Pets have up to 5 skills, each unlocking/upgrading on its own stars.
function petPop(pet) {
  // A pet without skill data (e.g. a GAT-only pet not yet filled in gat-overrides.json).
  if (!pet.skills?.length) return html`<div class="pop-title">${label(pet)}</div><div class="note">Không có dữ liệu skill</div>`;
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

// Hover summary for a trap / spell: the skill title, then one compact line per star run (star label
// inline with the desc — traps have 10 runs). Spells add each run's CD, and the range once on top
// when every run shares it.
function starRunsPop(item, group) {
  const runs = item.starSkills || [];
  if (!runs.length) return html`<div class="pop-title">${label(item)}</div><div class="note">Không có skill theo sao</div>`;
  const ranges = new Set(runs.map((s) => s.range).filter(Boolean));
  const range = group === "spells" && ranges.size === 1 ? ` · tầm ${[...ranges][0]}` : "";
  const run = (s) => html`
    <div class="pop-line compact" key=${s.code}>
      <span class="hint">${starsLabel(s.stars)}${group === "spells" && s.cd ? ` · CD ${s.cd}s` : ""}${ranges.size > 1 && s.range ? ` · tầm ${s.range}` : ""}</span>
      ${plain(s.desc_vn)}
    </div>
  `;
  return html`<div class="pop-title">${label(runs[0])}<span class="note">${range}</span></div>${runs.map(run)}`;
}

const OPTION_POP = { pets: (item) => petPop(item), traps: (item) => starRunsPop(item, "traps"), spells: (item) => starRunsPop(item, "spells") };

function ListRow({ ctx, group, item, index }) {
  const { state, dict, update } = ctx;
  const chosen = state[group].map((x) => x?.name).filter(Boolean);
  // The slot fills in place (null = empty): pick a name to fill, '(trống)' or ↻ to reset it.
  const setSlot = (v) => update((s) => void (s[group][index] = v ? newListItem(group)(v) : null));
  const edit = (fn) => update((s) => void fn(s[group][index]));
  const setLevel = (v) => edit((x) => (x.level = v));
  const setStar = (v) => edit((x) => (x.star = v));
  // Reset sits on every row — disabled when the slot is already empty — so the layout never shifts.
  const reset = html`<button class="x" title=${item ? "Reset về trống" : "Slot trống"} disabled=${!item}
    onClick=${() => setSlot("")}>×</button>`;
  const options = [
    ["", "(trống)"],
    ...nameOptions(dict, group, chosen, item?.name),
  ].map(([key, text, disabled, grp]) => [key, text, key ? OPTION_POP[group](dict[group][key]) : null, disabled, grp]);
  const picker = html`<${SelectPop} options=${options} value=${item?.name || ""} onChange=${setSlot} />`;
  if (!item) return html`<div class="row list-row">${reset}${picker}</div>`;
  const info = dict[group][item.name];
  const level = info.maxLevel
    ? html`<label>Level <${NumberInput} value=${item.level} min=${1} max=${info.maxLevel} onChange=${setLevel} /></label>`
    : null;
  return html`
    <div class="row list-row">
      ${reset}
      ${picker}
      ${level}
      <label>Sao <${NumberInput} value=${item.star} min=${1} max=${info.maxStar} onChange=${setStar} /></label>
      <span class="note">${`max lv ${info.maxLevel || "-"} / ${info.maxStar}★`}</span>
    </div>
  `;
}
