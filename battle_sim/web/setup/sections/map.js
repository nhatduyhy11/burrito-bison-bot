// "Màn chơi": campaign stage, or capital (U Đô) boss + creep preset (off = the capture's battle).
// Capital: the room a boss shows up in never changes its stats, so the form only picks the boss and
// which 3 creep types come with it (see battle_sim/docs/planning/capital.md).
import { Accordion, html, NumberInput, PopHover, Select, SelectPop, optionText } from "../ui.js";
import { BloodBody } from "./blood-map.js";

const MODE_OPTIONS = [["campaign", "Campaign"], ["capital", "U Đô (Capital)"], ["naval", "Tranh Bá liên server"]];
const BLOOD_OPTION = ["blood", "Đêm Đỏ"]; // only on a Đêm Đỏ capture (one with the team roster)

export function MapSection({ ctx }) {
  const enabled = !!ctx.state.map;
  const onToggle = (on) => ctx.toggleWithPrefill("map", on);
  return html`
    <${Accordion} title="Màn chơi" hint="Campaign / U Đô / Tranh Bá / Đêm Đỏ; tắt = màn của capture" override=${{ enabled, onToggle }}>
      ${enabled && html`<${MapBody} ctx=${ctx} />`}
    <//>
  `;
}

function MapBody({ ctx }) {
  const { state, update } = ctx;
  const blood = !!ctx.baseBattle?.team;
  const setMode = (mode) => {
    update((s) => {
      s.map.mode = mode;
      s.map.boss = null;
      s.map.level = null;
      if (mode === "blood") s.map.level = ctx.bloodDict.levels[ctx.baseBattle.level] ? ctx.baseBattle.level : Number(Object.keys(ctx.bloodDict.levels)[0]);
    });
    if (mode === "blood") ctx.fillBloodTeams();
  };
  const body = ["capital", "naval"].includes(state.map.mode) ? html`<${CapitalBody} ctx=${ctx} />`
    : state.map.mode === "blood" ? html`<${BloodBody} ctx=${ctx} />` : html`<${CampaignBody} ctx=${ctx} />`;
  const options = blood || state.map.mode === "blood" ? [...MODE_OPTIONS, BLOOD_OPTION] : MODE_OPTIONS;
  return html`
    <div class="row">
      <label>Mode <${Select} options=${options} value=${state.map.mode} onChange=${setMode} /></label>
    </div>
    ${body}
  `;
}

// desc_vn is one "Điểm yếu: … · Kháng: … · Đặc điểm: …" string; one line per segment so the
// weakness reads at a glance.
export const descLines = (c) => (c.desc_vn || c.desc || "").split(" · ").map((p) => html`<div class="pop-desc">${p}</div>`);

// Stage hover card for the Campaign label: "Stage N · <boss>" on top with its desc, a divider,
// then each minion type with desc (campaign-dict stages reference creeps-dict's campaign section
// by code). Boss is null for the tutorial stages 1-2; an out-of-range entry falls back to a
// one-line note.
const stagePop = (campaignDict, creepsDict, stage) => {
  const entry = campaignDict?.stages[String(stage)];
  if (!entry) return html`<div class="pop-title">${`Stage ${stage || "—"}`}</div><div class="note">Không có dữ liệu stage này.</div>`;
  const creep = (code) => creepsDict.campaign[code] || { name_vn: code, desc_vn: "" };
  const boss = entry.boss && creep(entry.boss);
  // Star variants (CreepLO _type) repeat a family's name; drop a minion only when both its name
  // and desc repeat, so same-name cousins with different traits (20s/30s waves) both show — and a
  // name that survives twice gets a ★ per star so the repeat doesn't read as a dup.
  const minions = entry.minions.map(creep).filter((m, i, all) => !all.some((x, j) => j < i
    && (x.name_vn || x.name) === (m.name_vn || m.name) && (x.desc_vn || x.desc) === (m.desc_vn || m.desc)));
  const counts = new Map();
  for (const m of minions) { const n = m.name_vn || m.name; counts.set(n, (counts.get(n) || 0) + 1); }
  const minionName = (m) => {
    const n = m.name_vn || m.name;
    return counts.get(n) > 1 && m.star > 1 ? `${n} ${"★".repeat(m.star)}` : n;
  };
  return html`
    <div class="pop-title">${`Stage ${stage} · ${boss ? boss.name_vn || boss.name : "Không có boss"}`}</div>
    ${boss && descLines(boss)}
    ${boss && minions.length > 0 && html`<hr class="pop-divider" />`}
    ${minions.map((m) => html`<div class="pop-line"><div>${minionName(m)}</div>${descLines(m)}</div>`)}
  `;
};

function CampaignBody({ ctx }) {
  const { state, maps, campaignDict, creepsDict, update } = ctx;
  const { minStage, maxStage } = maps.campaign;
  const setStage = (v) => update((s) => void (s.map.stage = v));
  return html`
    <div class="row">
      <label>
        <${PopHover} content=${stagePop(campaignDict, creepsDict, state.map.stage)}>
          <span class="pop-trigger">${`Stage (${minStage}–${maxStage}) `}</span>
        <//>
        <${NumberInput} value=${state.map.stage} min=${minStage} max=${maxStage} onChange=${setStage} />
      </label>
    </div>
  `;
}

const creepName = (creepsDict, id) => {
  const c = creepsDict.creeps[id];
  return c ? c.name_vn || c.name : id;
};

// Boss hover card (U Đô picker rows).
const bossPop = (b) => html`<div class="pop-title">${b.name_vn || b.name}</div>${descLines(b)}`;

function CapitalBody({ ctx }) {
  const { state, bossDict, creepsDict, update } = ctx;
  const naval = state.map.mode === "naval";
  const { bosses } = naval ? ctx.navalDict : bossDict;
  const boss = bosses[state.map.boss];
  const bossOptions = [["", "— chọn boss —"], ...Object.entries(bosses).map(([key, b]) => [key, `${optionText(b)} · ${b.presets.length} bộ quái`, bossPop(b)])];
  const presetOptions = [["", boss ? "— chọn bộ quái —" : "— chọn boss trước —"],
    ...(boss?.presets || []).map((p) => [String(p.level), (naval ? `Nhóm ${p.subType} · Ngày ${p.day} · Phòng ${p.position} — ` : "") +
      (p.creeps.map((id) => naval ? optionText(ctx.navalDict.creeps[id]) : creepName(creepsDict, id)).join(" + ") || "Không có quái đi kèm")])];
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
