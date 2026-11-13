// Tab "Hero detail": one section per Teams slot, customizing that hero's Thần Khí (artifact).
// Untouched = as captured; "Tùy chỉnh" fills it from the capture and opens it. Item names and every
// description are left out on purpose (look them up in game); only line names (team buff, rainbow
// skill) are shown. State shape: profile-io.js artifactState.
import { html, label, Checkbox, Select } from "../ui.js";
import { MAX_STAGE, entryCode, parseEntryCode, rareSkill } from "../../artifacts.js";

const QUALITIES = [[4, "Tím"], [5, "Cam"], [6, "Đỏ"], [7, "Vàng"]];
const LINE_QUALITY = { 3: "Lam", 4: "Tím", 5: "Cam", 6: "Đỏ", 7: "Vàng" };
const KINDS = [["", "— Trống —"], ["buff", "Buff đội"], ["rare", "Skill rainbow"]];
const RAINBOW = [1, 2, 3];
const RAINBOW_QUALITY = 8;

export function HeroDetailTab({ ctx }) {
  return ctx.state.heroes.map(
    (hero, index) => html`<${ArtifactSection} key=${index} ctx=${ctx} hero=${hero} index=${index} />`,
  );
}

function ArtifactSection({ ctx, hero, index }) {
  const { dict, artifactDict, update } = ctx;
  const heroCode = dict.heroes[hero.name]?.code;
  const pool = artifactDict.heroes[heroCode]?.pool;
  const title = html`<strong>${`#${index + 1}`}</strong>${hero.name ? html`<span>${label(dict.heroes[hero.name])}</span>` : null}`;
  if (!pool) {
    const why = hero.name ? "Hero này không có Thần Khí" : "Chưa chọn hero";
    return html`<section class="off"><header>${title}<span class="hint">${why}</span></header></section>`;
  }
  const custom = hero.artifact !== undefined;
  const edit = (fn) => update((s) => void fn(s.heroes[index]));
  const setCustom = async (on) => {
    const artifact = on ? (await ctx.capturedHeroArtifact(heroCode)) ?? { quality: 4, stage: 1, slots: [] } : undefined;
    edit((h) => { h.artifact = artifact; });
  };
  const toggle = html`<label class="override"><${Checkbox} checked=${custom} onChange=${setCustom} />Tùy chỉnh</label>`;
  if (!custom) {
    return html`<section><header>${title}${toggle}<span class="hint">theo capture</span></header></section>`;
  }
  return html`
    <details class="accordion" open>
      <summary>${title}${toggle}</summary>
      <div class="accordion-body">
        <${ArtifactBody} artifact=${hero.artifact} heroCode=${heroCode} pool=${pool} artifactDict=${artifactDict} edit=${edit} />
      </div>
    </details>
  `;
}

function ArtifactBody({ artifact, heroCode, pool, artifactDict, edit }) {
  const qualityOptions = [["0", "Không đeo"], ...QUALITIES.map(([q, text]) => [String(q), text])];
  const setQuality = (value) => edit((h) => {
    const quality = Number(value);
    if (!quality) h.artifact = null;
    else if (!h.artifact) h.artifact = { quality, stage: 1, slots: [] };
    else h.artifact.quality = quality;
  });
  const quality = html`<label>Phẩm <${Select} aria-label="Phẩm" options=${qualityOptions}
    value=${String(artifact?.quality ?? 0)} onChange=${setQuality} /></label>`;
  if (!artifact) return html`<div class="row">${quality}</div>`;
  const stageOptions = Array.from({ length: MAX_STAGE[artifact.quality] }, (_, i) => [String(i + 1), String(i + 1)]);
  const setStage = (value) => edit((h) => { h.artifact.stage = Number(value); });
  const slots = artifact.slots.map((slot, i) => html`
    <${SlotRow} key=${i} index=${i} slot=${slot} heroCode=${heroCode} pool=${pool} artifactDict=${artifactDict} edit=${edit} />
  `);
  return html`
    <div class="row">
      ${quality}
      <label>Stage <${Select} aria-label="Stage" options=${stageOptions} value=${String(artifact.stage)} onChange=${setStage} /></label>
      <span class="note">${`${artifact.slots.length} ô roll`}</span>
    </div>
    ${slots}
  `;
}

// Short name of a team buff family (the line's name in game, without "(Duy nhất)").
const buffName = (artifactDict, family) =>
  (artifactDict.skills[artifactDict.buffs[family].skillCode]?.name_vn || `Buff ${family}`).replace(/\s*\(.*\)$/, "");

const topQuality = (buff) => Math.max(...Object.keys(buff.ranges).map(Number));

function buffEntry(pool, artifactDict, family, quality) {
  const buff = artifactDict.buffs[family];
  const q = buff.ranges[quality] ? quality : topQuality(buff);
  return { code: entryCode(pool, Number(family), q), value: buff.ranges[q][1] };
}

function SlotRow({ index, slot, heroCode, pool, artifactDict, edit }) {
  const parsed = slot && parseEntryCode(slot.code);
  const kind = !slot ? "" : parsed.quality === RAINBOW_QUALITY ? "rare" : "buff";
  const families = Object.keys(artifactDict.buffs);
  const set = (next) => edit((h) => { h.artifact.slots[index] = next; });
  const setKind = (value) => {
    if (value === "buff") set(buffEntry(pool, artifactDict, families[0]));
    else if (value === "rare") set({ code: entryCode(pool, RAINBOW[0], RAINBOW_QUALITY), value: 0 });
    else set(null);
  };
  const kindSelect = html`<${Select} aria-label=${`Ô ${index + 1}`} options=${KINDS} value=${kind} onChange=${setKind} />`;
  const head = html`<strong class="note">${`Ô ${index + 1}`}</strong>${kindSelect}`;
  if (kind === "rare") {
    const rainbowName = (family) => artifactDict.skills[rareSkill(heroCode, family)]?.name_vn || `Rainbow ${family}`;
    const options = RAINBOW.map((family) => [String(family), rainbowName(family)]);
    const setRainbow = (value) => set({ code: entryCode(pool, Number(value), RAINBOW_QUALITY), value: 0 });
    return html`<div class="row">${head}<${Select} aria-label="Rainbow" options=${options}
      value=${String(parsed.family)} onChange=${setRainbow} /></div>`;
  }
  if (kind !== "buff") return html`<div class="row">${head}</div>`;
  const buff = artifactDict.buffs[parsed.family];
  const [min, max] = buff.ranges[parsed.quality];
  const familyOptions = families.map((family) => [family, buffName(artifactDict, family)]);
  const qualityOptions = Object.keys(buff.ranges).map((q) => [q, LINE_QUALITY[q] || q]);
  const setFamily = (value) => set(buffEntry(pool, artifactDict, value, parsed.quality));
  const setLineQuality = (value) => set(buffEntry(pool, artifactDict, parsed.family, Number(value)));
  const setValue = (e) => set({ code: slot.code, value: Number(e.currentTarget.value) });
  const shown = buff.percent ? `${(slot.value / 100).toFixed(2)}%` : String(slot.value);
  return html`
    <div class="row artifact-slot">
      ${head}
      <${Select} aria-label="Buff" options=${familyOptions} value=${String(parsed.family)} onChange=${setFamily} />
      <${Select} aria-label="Phẩm dòng" options=${qualityOptions} value=${String(parsed.quality)} onChange=${setLineQuality} />
      <input type="range" aria-label="Giá trị" min=${min} max=${max} step="1" value=${slot.value} onInput=${setValue} />
      <span class="value">${shown}</span>
    </div>
  `;
}
