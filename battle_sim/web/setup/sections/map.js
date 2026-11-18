// "Màn chơi": campaign stage, or capital (U Đô) boss + creep preset (off = the capture's battle).
// Capital: the room a boss shows up in never changes its stats, so the form only picks the boss and
// which 3 creep types come with it (see battle_sim/docs/planning/capital.md).
import { Accordion, html, NumberInput, Select, SelectPop, optionText } from "../ui.js";

const MODE_OPTIONS = [["campaign", "Campaign"], ["capital", "U Đô (Capital)"]];

export function MapSection({ ctx }) {
  const enabled = !!ctx.state.map;
  const onToggle = (on) => ctx.toggleWithPrefill("map", on);
  return html`
    <${Accordion} title="Màn chơi" hint="Campaign / U Đô; tắt = màn của capture" override=${{ enabled, onToggle }}>
      ${enabled && html`<${MapBody} ctx=${ctx} />`}
    <//>
  `;
}

function MapBody({ ctx }) {
  const { state, update } = ctx;
  const setMode = (mode) => update((s) => void (s.map.mode = mode));
  const body = state.map.mode === "capital" ? html`<${CapitalBody} ctx=${ctx} />` : html`<${CampaignBody} ctx=${ctx} />`;
  return html`
    <div class="row">
      <label>Mode <${Select} options=${MODE_OPTIONS} value=${state.map.mode} onChange=${setMode} /></label>
    </div>
    ${body}
  `;
}

function CampaignBody({ ctx }) {
  const { state, maps, update } = ctx;
  const { minStage, maxStage } = maps.campaign;
  const setStage = (v) => update((s) => void (s.map.stage = v));
  return html`
    <div class="row">
      <label>
        ${`Stage (${minStage}–${maxStage}) `}
        <${NumberInput} value=${state.map.stage} min=${minStage} max=${maxStage} onChange=${setStage} />
      </label>
    </div>
  `;
}

const creepName = (creepsDict, id) => {
  const c = creepsDict.creeps[id];
  return c ? c.name_vn || c.name : id;
};

// Boss hover card: desc_vn is one "Điểm yếu: … · Kháng: … · Đặc điểm: …" string; split it into
// one line per segment so the weakness reads at a glance.
const bossPop = (b) => {
  const parts = (b.desc_vn || b.desc || "").split(" · ");
  return html`<div class="pop-title">${b.name_vn || b.name}</div>${parts.map((p) => html`<div class="pop-desc">${p}</div>`)}`;
};

function CapitalBody({ ctx }) {
  const { state, bossDict, creepsDict, update } = ctx;
  const { bosses } = bossDict;
  const boss = bosses[state.map.boss];
  const bossOptions = [["", "— chọn boss —"], ...Object.entries(bosses).map(([key, b]) => [key, `${optionText(b)} · ${b.presets.length} bộ quái`, bossPop(b)])];
  const presetOptions = [["", boss ? "— chọn bộ quái —" : "— chọn boss trước —"],
    ...(boss?.presets || []).map((p) => [String(p.level), p.creeps.map((id) => creepName(creepsDict, id)).join(" + ")])];
  const preset = boss?.presets.find((p) => p.level === state.map.level);
  // A new boss resets the preset; a boss with a single preset gets it right away.
  const setBoss = (key) => update((s) => {
    s.map.boss = key || null;
    const presets = bosses[key]?.presets || [];
    s.map.level = presets.length === 1 ? presets[0].level : null;
  });
  const setPreset = (value) => update((s) => void (s.map.level = value ? Number(value) : null));
  return html`
    <div class="row wide">
      <label>Boss <${SelectPop} options=${bossOptions} value=${state.map.boss || ""} onChange=${setBoss} /></label>
    </div>
    ${boss && html`<p class="hint">${boss.desc_vn || boss.desc}</p>`}
    <div class="row wide">
      <label>Bộ quái <${Select} options=${presetOptions} value=${preset ? String(preset.level) : ""} disabled=${!boss} onChange=${setPreset} /></label>
    </div>
  `;
}
