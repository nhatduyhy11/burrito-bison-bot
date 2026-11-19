// "Màn chơi" body for Đêm Đỏ (map mode "blood", battleType 47): the Ải 1-80 picker. state.map.level
// = TeamExpandLO id (key of blood-dict.json levels); the hover shows the final boss, then the 3 creep types.
// Only offered on a Đêm Đỏ capture (map.js). See docs/planning/blood_night_setup.md.
import { html, NumberInput, PopHover } from "../ui.js";
import { descLines } from "./map.js";

const levelPop = (bloodDict, id) => {
  const entry = bloodDict.levels[id];
  if (!entry) return html`<div class="note">Không có dữ liệu ải này.</div>`;
  const boss = bloodDict.monsters[entry.boss.monster];
  const creeps = entry.creeps.map((key) => bloodDict.monsters[key]).filter(Boolean);
  // Same layout as the campaign stage card: boss on top with its desc, a divider, then the creeps.
  return html`
    <div class="pop-title">${`Ải ${entry.level} · ${boss ? boss.name_vn || boss.name : "Không có boss"}`}</div>
    ${boss && descLines(boss)}
    ${boss && creeps.length > 0 && html`<hr class="pop-divider" />`}
    ${creeps.map((c) => html`<div class="pop-line"><div>${c.name_vn || c.name}</div>${descLines(c)}</div>`)}
  `;
};

export function BloodBody({ ctx }) {
  const { state, bloodDict, update } = ctx;
  const ids = Object.keys(bloodDict.levels).map(Number);
  const byAi = new Map(ids.map((id) => [bloodDict.levels[id].level, id]));
  const ais = [...byAi.keys()];
  const min = Math.min(...ais), max = Math.max(...ais);
  const ai = bloodDict.levels[state.map.level]?.level ?? min;
  const setAi = (value) => update((s) => void (s.map.level = byAi.get(value) ?? s.map.level));
  return html`
    <div class="row">
      <label>
        <${PopHover} content=${levelPop(bloodDict, state.map.level)}>
          <span class="pop-trigger">${`Ải (${min}–${max}) `}</span>
        <//>
        <${NumberInput} value=${ai} min=${min} max=${max} onChange=${setAi} />
      </label>
    </div>
  `;
}
