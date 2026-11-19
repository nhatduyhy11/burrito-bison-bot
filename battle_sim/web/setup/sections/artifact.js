// Thần Khí (artifact) editor of one hero card: quality, stage and the rolled slots. Rendered inside
// the hero card in heroes.js, below the skin table — "Tùy chỉnh" on the card customizes it too.
// Item names and every description are left out on purpose (look them up in game); only line names
// (team buff, rainbow skill) are shown. State shape: profile-state.js artifactState.
import { html, Select, PopHover, plain } from "../ui.js";
import { MAX_STAGE, entryCode, parseEntryCode, rareSkill, stageSkill } from "../../artifacts.js";

const QUALITIES = [[4, "Tím"], [5, "Cam"], [6, "Đỏ"], [7, "Vàng"]];
const LINE_QUALITY = { 3: "Lam", 4: "Tím", 5: "Cam", 6: "Đỏ", 7: "Vàng" };
const KINDS = [["", "— Trống —"], ["buff", "Buff đội"], ["rare", "Skill rainbow"]];
const RAINBOW = [1, 2, 3];
const RAINBOW_QUALITY = 8;

// Hover summary for the Phẩm picker, in the shape of the Dị Năng popover: the hero's five Thần Khí
// tier skills with the game's own desc ("Thay thế Thần Khí k: …", MANUAL rows get the "(Chủ Động)"
// tag), then "→" the hero skill that desc upgrades (the name it brackets). ✅ marks the tiers open
// at the artifact's stage (a phẩm caps how far stage can go).
const BRACKET = /\[([^\]]+)\]|【([^】]+)】/;
function phamPop(artifactDict, heroDict, artifact) {
  const stage = artifact?.stage ?? 0;
  const refs = heroDict?.baseSkillRefs ?? [];
  const line = (_, i) => {
    const skill = artifactDict.skills[stageSkill(heroDict?.code, i + 1)];
    if (!skill) return null;
    const desc = plain(skill.desc_vn);
    const bracket = desc.match(BRACKET);
    const target = bracket && refs.find((r) => r.name_vn === (bracket[1] ?? bracket[2]));
    return html`
      <div class="pop-line" key=${i}>
        <span class="hint">${i < stage ? "✅ " : ""}Bậc ${i + 1}${skill.type === "MANUAL" ? " (Chủ Động)" : ""}</span>${skill.name_vn}
        <div class="pop-desc">${desc}</div>
        ${target && html`<div class="pop-desc">→ ${target.name_vn}: ${plain(target.desc_vn)}</div>`}
      </div>
    `;
  };
  return html`
    <div class="pop-title">Thần Khí · 5 bậc skill</div>
    ${Array.from({ length: 5 }, line)}
  `;
}

export function ArtifactBody({ artifact, heroCode, heroDict, pool, artifactDict, edit }) {
  const qualityOptions = [["0", "Không đeo"], ...QUALITIES.map(([q, text]) => [String(q), text])];
  const setQuality = (value) => edit((h) => {
    const quality = Number(value);
    if (!quality) h.artifact = null;
    else if (!h.artifact) h.artifact = { quality, stage: 1, slots: [] };
    else h.artifact.quality = quality;
  });
  // The phẩm Select sits inside a label, so the trigger word stays outside it (a nested pop-trigger
  // inside the label would re-open the Select — bbb-qjk).
  const quality = html`
    <${PopHover} content=${phamPop(artifactDict, heroDict, artifact)}><span class="pop-trigger">Phẩm</span><//>
    <label><${Select} aria-label="Phẩm" options=${qualityOptions}
      value=${String(artifact?.quality ?? 0)} onChange=${setQuality} /></label>`;
  if (!artifact) {
    return html`
      <div class="row">${quality}</div>
    `;
  }
  const stageOptions = Array.from({ length: MAX_STAGE[artifact.quality] }, (_, i) => [String(i + 1), String(i + 1)]);
  const setStage = (value) => edit((h) => { h.artifact.stage = Number(value); });
  const slots = artifact.slots.map((slot, i) => html`
    <${SlotRow} key=${i} index=${i} slot=${slot} slots=${artifact.slots} heroCode=${heroCode} pool=${pool} artifactDict=${artifactDict} edit=${edit} />
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

function SlotRow({ index, slot, slots, heroCode, pool, artifactDict, edit }) {
  const parsed = slot && parseEntryCode(slot.code);
  const kind = !slot ? "" : parsed.quality === RAINBOW_QUALITY ? "rare" : "buff";
  const families = Object.keys(artifactDict.buffs);
  // Lines of the same family don't stack (buff overlay_limit=1, any phẩm — same buff id), so hide
  // families and rainbows taken by sibling slots.
  const used = new Set(slots.flatMap((s, i) => {
    if (i === index || !s) return [];
    const p = parseEntryCode(s.code);
    return [p.family];
  }));
  const freeRainbows = RAINBOW.filter((family) => !used.has(family));
  const freeFamilies = families.filter((family) => !used.has(Number(family)));
  const set = (next) => edit((h) => { h.artifact.slots[index] = next; });
  const kindOptions = KINDS.map(([v, text]) => [v, text, v === "rare" && !freeRainbows.length]);
  const setKind = (value) => {
    if (value === "buff") {
      if (freeFamilies.length) set(buffEntry(pool, artifactDict, freeFamilies[0]));
    } else if (value === "rare") {
      if (freeRainbows.length) set({ code: entryCode(pool, freeRainbows[0], RAINBOW_QUALITY), value: 0 });
    } else set(null);
  };
  const kindSelect = html`<${Select} aria-label=${`Ô ${index + 1}`} options=${kindOptions} value=${kind} onChange=${setKind} />`;
  const head = html`<strong class="note">${`Ô ${index + 1}`}</strong>${kindSelect}`;
  if (kind === "rare") {
    const rainbowName = (family) => artifactDict.skills[rareSkill(heroCode, family)]?.name_vn || `Rainbow ${family}`;
    const options = RAINBOW
      .filter((family) => family === parsed.family || !used.has(family))
      .map((family) => [String(family), rainbowName(family)]);
    const setRainbow = (value) => set({ code: entryCode(pool, Number(value), RAINBOW_QUALITY), value: 0 });
    return html`
      <div class="row">${head}<${Select} aria-label="Rainbow" options=${options}
        value=${String(parsed.family)} onChange=${setRainbow} /></div>
    `;
  }
  if (kind !== "buff") {
    return html`
      <div class="row">${head}</div>
    `;
  }
  const buff = artifactDict.buffs[parsed.family];
  const [min, max] = buff.ranges[parsed.quality];
  const familyOptions = families
    .filter((family) => Number(family) === parsed.family || !used.has(Number(family)))
    .map((family) => [family, buffName(artifactDict, family)]);
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
