// Per-hero customization: off keeps every captured field; on unlocks all hero overrides.
import { html, label, optionText, colorTag, COLOR_LABEL, NumberInput, Checkbox, Select, SelectPop, PopHover, StarSkillsLabel, plain, starsLabel, Accordion } from "../ui.js";
import { HERO_SLOTS, heroForced, heroSlotForced, heroSlotKind } from "../skin-rules.js";
import { heroSkins, isBlood, newHero, stashValue, takeStashed } from "../profile-state.js";
import { hasSummonedJoker, JOKER_SUMMON } from "../../hero-lineup.js";
import { resolveRelic } from "../../relics.js";
import { resolveBeautyBag } from "../../beauty-bags.js";
import { headerRow, nameOptions, requiresNote, without } from "./shared.js";
import { ArtifactBody } from "./artifact.js";
import { BloodTeams } from "./blood-teams.js";

const HEADERS = ["Skin", "Màu", "Sở hữu", "Sao", "Slot"];

export function HeroesSection({ ctx }) {
  const blood = isBlood(ctx.state);
  const hint = blood ? "Đêm Đỏ · 3 hero Master + 3 hero Guest · Joker ở slot 4 bên có Loli"
    : "5 slot bắt buộc · Joker hỗ trợ chỉ hiện khi skin Loli kích hoạt";
  return html`
    <${Accordion} title="Hero" hint=${hint}>
      ${blood ? html`<${BloodTeams} ctx=${ctx} />` : html`<${HeroesBody} ctx=${ctx} />`}
    <//>
  `;
}

function HeroesBody({ ctx }) {
  const { state } = ctx;
  const cards = state.heroes.map(
    (hero, index) => html`<${HeroCard} key=${index} ctx=${ctx} hero=${hero} index=${index} />`,
  );
  const loli = state.heroes.find(({ name }) => name === JOKER_SUMMON.hero);
  const showJoker = hasSummonedJoker(state.heroes, loli?.custom && loli.slots.includes(JOKER_SUMMON.skin));
  return html`
    ${cards}
    ${showJoker && html`<${HeroCard} ctx=${ctx} hero=${state.summonedJoker} index=${5} summoned=${true} />`}
    <div class="note">
      Ưu tiên dữ liệu hero trong trận, rồi roster của acc nếu capture có lưu. Hero ngoài cả hai nguồn mượn chỉ số trung bình, level và level skill của các
      hero cùng độ hiếm trong capture (gần đúng, ±10%). Tắt "Tùy chỉnh" giữ toàn bộ dữ liệu hero từ capture. Bật mới sửa skin, Dị Năng, Thánh Khí, Dị Vật và Thần Khí; Dị Năng bắt đầu từ 0. Roster lobby thường có thể thiếu trang bị; roster Đêm Đỏ đầy đủ hơn.
    </div>
  `;
}

// group = state list the card edits ("heroes" or Đêm Đỏ "guestHeroes"); slot = shown label;
// chosen = names taken elsewhere in the lineup (disabled in the picker).
export function HeroCard({ ctx, hero, index, summoned = false, group = "heroes", slot = `#${index + 1}`, chosen }) {
  const { state, dict, artifactDict, update, capturedHeroArtifact, region } = ctx;
  const skins = heroSkins(dict, hero.name);
  const hasSkins = Object.keys(skins).length > 0;
  const nodes = dict.heroes[hero.name]?.avatarNodes || [];
  const heroCode = dict.heroes[hero.name]?.code;
  const pool = artifactDict.heroes[heroCode]?.pool;
  const options = [["", "— Chọn hero —"], ...nameOptions(dict, "heroes", chosen ?? state.heroes.map((h) => h.name), hero.name)];
  const edit = (fn) => update((s) => void fn(summoned ? s.summonedJoker : s[group][index]));
  const editSkin = (fn) => edit((h) => { h.skinOverride = true; fn(h); });
  const setName = (v) => update((s) => void (s[group][index] = newHero(v)));
  // "Tùy chỉnh" also owns the Thần Khí: tick fills it from the capture (Teams slots only — the
  // summoned Joker has none), untick returns to "theo capture". Untick parks the typed relic,
  // beauty bag, Thần Khí and Dị Năng in the session stash; re-tick restores them (an untouched
  // Thần Khí still refills from the capture). Keyed by hero name too — switching the slot's hero
  // must not restore the previous hero's parked values.
  const customKey = `custom:${region}:${summoned ? "joker" : `${group}:${index}`}:${hero.name}`;
  const setCustom = async (on) => {
    const artifact = on && !summoned && pool
      ? (await capturedHeroArtifact(heroCode)) ?? { quality: 4, stage: 1, slots: [] }
      : undefined;
    edit((h) => {
      if (on) {
        h.custom = true;
        h.skinOverride = true;
        const parked = takeStashed(customKey);
        if (parked) Object.assign(h, parked);
        if (pool && !summoned && h.artifact === undefined) h.artifact = artifact;
      } else {
        h.custom = false;
        h.skinOverride = false;
        stashValue(customKey, { relic: h.relic, beautyBag: h.beautyBag, artifact: h.artifact, avatar: h.avatar });
        h.relic = undefined;
        h.beautyBag = undefined;
        h.artifact = undefined;
      }
    });
  };
  const custom = html`<label><${Checkbox} checked=${hero.custom} onChange=${setCustom} />Tùy chỉnh</label>`;
  const avatar = hero.custom && nodes.length ? html`<${AvatarPicker} hero=${hero} nodes=${nodes} edit=${editSkin} />` : null;
  const table = hero.custom && hasSkins ? html`<${HeroSkinTable} hero=${hero} skins=${skins} edit=${editSkin} />` : null;
  const artifact = !summoned && hero.custom && pool
    ? html`<div class="subsection"><${ArtifactBody} artifact=${hero.artifact} heroCode=${heroCode} pool=${pool} artifactDict=${artifactDict} edit=${edit} /></div>`
    : null;
  return html`
    <div class="card">
      <div class="row">
        <strong>${slot}</strong>
        ${summoned
          ? html`<span>${label(dict.heroes[hero.name])}</span><span class="note">Hỗ trợ · Ra sân cùng Pháo Loli</span>`
          : html`<${Select} aria-label=${`Hero ${group === "heroes" ? "" : "Guest "}slot ${index + 1}`} options=${options} value=${hero.name} onChange=${setName} />`}
        ${custom}
      </div>
      ${hero.name && hero.custom && html`<${RelicPicker} selection=${hero.relic} lines=${ctx.relicLines} edit=${edit} />`}
      ${hero.name && hero.custom && html`<${BeautyBagPicker} selection=${hero.beautyBag} types=${ctx.beautyBagTypes} edit=${edit} />`}
      ${hero.name && !hero.custom && html`<div class="note">Theo capture: chỉ số, skill, skin, Dị Năng, Thánh Khí, Dị Vật và Thần Khí.</div>`}
      ${avatar}
      ${table}
      ${artifact}
    </div>
  `;
}

// Hover summary for the Dị Năng skill nodes in chapter order: the new skill, what it replaces (the
// hero's base skill or an earlier node's skill) and the break-through gate. ✅ marks open nodes.
function avatarPop(nodes, level) {
  const node = (n, i) => {
    const prev = nodes.findIndex((m) => m.skill === n.replaces);
    const replaces = prev >= 0 ? `nâng cấp mốc ${prev + 1}` : n.replacesInfo && html`thay ${label(n.replacesInfo)}`;
    return html`
      <div class="pop-line" key=${n.skill}>
        <span class="hint">${i < level ? "✅ " : ""}Mốc ${i + 1}</span> ${label(n.skillInfo)}
        ${(replaces || n.minBreakThrough) && html`
          <div class="hint">${replaces}${replaces && n.minBreakThrough ? " · " : ""}${n.minBreakThrough ? `cần đột phá ≥ ${n.minBreakThrough}` : ""}</div>`}
        <div class="pop-desc">${plain(n.skillInfo?.desc_vn)}</div>
      </div>
    `;
  };
  return html`
    <div class="avatar-pop">
      <div class="pop-title">Dị Năng · ${nodes.length} mốc skill</div>
      ${nodes.map(node)}
    </div>
  `;
}

// Dị Năng level N = skill nodes 1..N open (opening a node opens every lower one); "Tùy chỉnh" starts
// it at 0. Attribute nodes are not modelled.
function AvatarPicker({ hero, nodes, edit }) {
  const setLevel = (v) => edit((h) => (h.avatar = v));
  return html`
    <div class="row">
      <${PopHover} content=${avatarPop(nodes, hero.avatar ?? 0)}><label class="pop-trigger">Dị Năng (node skill)</label><//>
      <${NumberInput} value=${hero.avatar ?? 0} min=${0} max=${nodes.length} onChange=${setLevel} />
      <span class="note">${` /${nodes.length}`}</span>
    </div>
  `;
}

// Hover summary for a relic line: the line skill's title, the gold/colorful purification skills
// ("2 mốc thanh tẩy"), a divider, then every star run of the line skill. With a resolved selection,
// ✅ marks the chosen purification tier and star run.
function relicPop(line, selected) {
  const mark = (on) => (on ? "✅ " : "");
  const star = (s) => html`
    <div class="pop-line" key=${s.code}>
      <span class="hint">${mark(s === selected?.starSkill)}${starsLabel(s.stars)}</span>
      <div class="pop-desc">${plain(s.desc_vn)}</div>
    </div>
  `;
  const pur = (p) => html`
    <div class="pop-line" key=${p.fixedSkill.code}>
      <span class="hint">${mark(p === selected?.tier)}Thanh tẩy ${COLOR_LABEL[p.color]}</span> ${label(p.fixedSkill)}
      <div class="pop-desc">${plain(p.fixedSkill.desc_vn)}</div>
    </div>
  `;
  const purs = line.purifications.filter((p) => p.fixedSkill);
  const title = line.starSkills[0];
  return html`
    <div class="relic-pop">
      ${title && html`<div class="pop-title">${label(title)}</div>`}
      ${purs.map(pur)}
      ${purs.length && line.starSkills.length ? html`<hr class="pop-divider" />` : null}
      ${line.starSkills.map(star)}
    </div>
  `;
}

function RelicPicker({ selection, lines, edit }) {
  const selected = selection ? resolveRelic(selection, lines) : null;
  const options = [
    ["", "Không có Thánh Khí"],
    ["capture", "Theo capture"],
    ...Object.entries(lines).map(([key, line]) => [key, optionText(line), relicPop(line)]),
  ];
  const stars = selected ? Array.from({ length: selected.tier.maxStar + 1 }, (_, star) => [String(star), String(star)]) : [];
  const levels = [["0", "0 · Đỏ"], ["1", "1 · Vàng"], ["2", "2 · 7 màu"]];
  const choose = (name) => edit((h) => {
    if (name === "capture") h.relic = undefined;
    else h.relic = name ? { name, star: 0, purification: 0 } : null;
  });
  const setStar = (value) => edit((h) => (h.relic.star = Number(value)));
  const setPurification = (value) => edit((h) => (h.relic.purification = Number(value)));
  return html`
    <div class="row">
      ${selected
        ? html`<${PopHover} content=${relicPop(lines[selection.name], selected)}><label class="pop-trigger">Thánh Khí</label><//>`
        : html`<label>Thánh Khí</label>`}
      <${SelectPop} aria-label="Thánh Khí" options=${options}
        value=${selection === undefined ? "capture" : selection?.name ?? ""} onChange=${choose} />
      ${selected && html`
        <label>Sao <${Select} aria-label="Sao" options=${stars} value=${String(selected.star)} onChange=${setStar} /></label>
        <label>Thanh tẩy
          <${Select} aria-label="Thanh tẩy" options=${levels} value=${String(selected.purification)} onChange=${setPurification} />
        </label>
      `}
    </div>
  `;
}

// Hover summary for one Dị Vật type: the suit's star runs, a divider, then the gold item's. With a
// resolved selection, ✅ marks the suit run and the gold run in effect (gold counts up to the suit star).
function beautyBagPop(entry, selected) {
  const run = (s, on) => html`
    <div class="pop-line" key=${s.code}>
      <span class="hint">${on ? "✅ " : ""}${starsLabel(s.stars)}</span>
      <div class="pop-desc">${plain(s.desc_vn)}</div>
    </div>
  `;
  return html`
    <div class="relic-pop">
      <div class="pop-title">${label(entry)} · ${label(entry.suit.starSkills[0])}</div>
      <div class="hint">Bộ 4 món</div>
      ${entry.suit.starSkills.map((s) => run(s, s === selected?.suitSkill))}
      <hr class="pop-divider" />
      <div class="hint">Món vàng · cần bộ cùng hệ, mỗi mốc cần sao bộ ≥ mốc</div>
      ${entry.gold.starSkills.map((s) => run(s, s === selected?.goldSkill))}
    </div>
  `;
}

// Dị Vật: one suit type with its star, plus the gold item star (0 = not worn). Only the index-0
// skills change in battle; the suit/gold attrs stay as captured (server-merged).
function BeautyBagPicker({ selection, types, edit }) {
  if (!types) return null;
  const selected = selection ? resolveBeautyBag(selection, types) : null;
  const options = [
    ["capture", "Theo capture"],
    ["", "Không đeo Dị Vật"],
    ...Object.entries(types).map(([key, entry]) => [key, optionText(entry), beautyBagPop(entry)]),
  ];
  const range = (from, to, zero) => Array.from({ length: to - from + 1 }, (_, i) => {
    const n = from + i;
    return [String(n), n === 0 && zero ? zero : String(n)];
  });
  const choose = (key) => edit((h) => {
    if (key === "capture") h.beautyBag = undefined;
    else if (!key) h.beautyBag = null;
    else {
      const { suit, gold } = types[key];
      h.beautyBag = { type: key, star: Math.min(h.beautyBag?.star ?? 1, suit.maxStar), gold: Math.min(h.beautyBag?.gold ?? 0, gold.maxStar) };
    }
  });
  const setStar = (value) => edit((h) => (h.beautyBag.star = Number(value)));
  const setGold = (value) => edit((h) => (h.beautyBag.gold = Number(value)));
  return html`
    <div class="row">
      ${selected
        ? html`<${PopHover} content=${beautyBagPop(selected.entry, selected)}><label class="pop-trigger">Dị Vật</label><//>`
        : html`<label>Dị Vật</label>`}
      <${SelectPop} aria-label="Dị Vật" options=${options}
        value=${selection === undefined ? "capture" : selection?.type ?? ""} onChange=${choose} />
      ${selected && html`
        <label>Sao bộ <${Select} aria-label="Sao bộ Dị Vật" options=${range(1, selected.entry.suit.maxStar)}
          value=${String(selected.star)} onChange=${setStar} /></label>
        <label>Món vàng <${Select} aria-label="Sao món vàng Dị Vật" options=${range(0, selected.entry.gold.maxStar, "Không")}
          value=${String(selected.gold)} onChange=${setGold} /></label>
        ${selected.gold > selected.star && html`<span class="note">${`vàng tính tới sao ${selected.star}`}</span>`}
      `}
    </div>
  `;
}

function HeroSkinTable({ hero, skins, edit }) {
  const forced = heroForced(hero, skins);
  const slotForced = heroSlotForced(hero, skins);
  const count = (kind) => hero.slots.filter((key) => heroSlotKind(skins[key]) === kind).length;
  const wornOptions = [["", "model gốc"], ...Object.entries(skins).map(([key, skin]) => [key, optionText(skin)])];
  const setWorn = (v) => edit((h) => (h.worn = v || null));
  const slotNote = `Slot: ${count("normal")}/${HERO_SLOTS.normal} thường, ${count("colorful")}/${HERO_SLOTS.colorful} 7 màu`;
  const rows = Object.entries(skins).map(([key, skin]) => {
    const kind = heroSlotKind(skin);
    const slotted = hero.slots.includes(key);
    return html`
      <${HeroSkinRow}
        key=${key}
        skinKey=${key}
        skin=${skin}
        skins=${skins}
        state=${hero.skins[key]}
        forcedStar=${forced[key]}
        slotted=${slotted}
        slotLocked=${slotForced.has(key)}
        slotFull=${!slotted && count(kind) >= HERO_SLOTS[kind]}
        edit=${edit}
      />
    `;
  });
  return html`
    <div>
      <div class="row">
        <label class="skin-picker">Đang mặc <${Select} options=${wornOptions} value=${hero.worn || ""} onChange=${setWorn} /></label>
        <span class="note">${slotNote}</span>
      </div>
      <div class="table-scroll">
        <table>
          <tbody>
            ${headerRow(HEADERS)}
            ${rows}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

function HeroSkinRow({ skinKey: key, skin, skins, state, forcedStar, slotted, slotLocked, slotFull, edit }) {
  const isForced = forcedStar !== undefined;
  const setOwned = (on) =>
    edit((h) => {
      h.skins[key].owned = on;
      if (!on) h.slots = without(h.slots, key);
    });
  const setStar = (v) => edit((h) => (h.skins[key].star = v));
  const setSlotted = (on) =>
    edit((h) => {
      if (on) h.skins[key].owned = true;
      h.slots = on ? [...h.slots, key] : without(h.slots, key);
    });
  const ownedTitle = isForced ? "Bắt buộc (đang mặc hoặc skin 7 màu yêu cầu)" : null;
  const slotTitle = slotLocked ? "Bắt buộc: skin 7 màu trong slot cần skin này" : null;
  return html`
    <tr>
      <td class="name">
        <${StarSkillsLabel} item=${skin} star=${state.owned ? state.star : undefined} />${requiresNote(skin, skins)}
        ${key === JOKER_SUMMON.skin && html`<div class="note">${JOKER_SUMMON.skillName} · Triệu hồi Joker</div>`}
      </td>
      <td>${colorTag(skin.color)}</td>
      <td><${Checkbox} checked=${state.owned} disabled=${isForced} title=${ownedTitle} onChange=${setOwned} /></td>
      <td>
        <${NumberInput}
          value=${state.star}
          min=${forcedStar || 1}
          max=${skin.maxStar}
          disabled=${!state.owned}
          onChange=${setStar}
        /><span class="note">${` /${skin.maxStar}`}</span>
      </td>
      <td>
        <${Checkbox}
          checked=${slotted}
          disabled=${slotLocked || slotFull}
          title=${slotTitle}
          onChange=${setSlotted}
        />
      </td>
    </tr>
  `;
}
