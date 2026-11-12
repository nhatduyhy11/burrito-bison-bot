// Hero list; "Tùy chỉnh" on a hero card opens its Dị Năng skill nodes (red heroes) and skin table
// (owned, star, slots).
import { html, label, optionText, colorTag, NumberInput, Checkbox, Select, Accordion } from "../ui.js";
import { HERO_SLOTS, heroForced, heroSlotForced, heroSlotKind } from "../skin-rules.js";
import { heroSkins, newHero } from "../profile-io.js";
import { hasSummonedJoker, JOKER_SUMMON } from "../../hero-lineup.js";
import { headerRow, nameOptions, requiresNote, without } from "./shared.js";

const HEADERS = ["Skin", "Màu", "Sở hữu", "Sao", "Slot"];

export function HeroesSection({ ctx }) {
  return html`
    <${Accordion} title="Hero" hint="5 slot bắt buộc · Joker hỗ trợ chỉ hiện khi skin Loli kích hoạt">
      <${HeroesBody} ctx=${ctx} />
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
      Hero có trong capture giữ chỉ số và skill gốc; hero khác mượn chỉ số trung bình, level và level skill của các
      hero cùng độ hiếm trong capture (gần đúng, ±10%). Không tick "Tùy chỉnh" thì giữ skin và Dị Năng từ capture; tick thì Dị Năng bắt đầu từ 0.
    </div>
  `;
}

function HeroCard({ ctx, hero, index, summoned = false }) {
  const { state, dict, update } = ctx;
  const skins = heroSkins(dict, hero.name);
  const hasSkins = Object.keys(skins).length > 0;
  const nodes = dict.heroes[hero.name]?.avatarNodes || [];
  const options = [["", "— Chọn hero —"], ...nameOptions(dict, "heroes", state.heroes.map((h) => h.name), hero.name)];
  const edit = (fn) => update((s) => void fn(summoned ? s.summonedJoker : s.heroes[index]));
  const setName = (v) => update((s) => void (s.heroes[index] = newHero(v)));
  const setCustom = (on) => edit((h) => (h.custom = on));
  const custom = hasSkins || nodes.length
    ? html`<label><${Checkbox} checked=${hero.custom} onChange=${setCustom} />Tùy chỉnh</label>`
    : html`<span class="note">không có skin</span>`;
  const avatar = hero.custom && nodes.length ? html`<${AvatarPicker} hero=${hero} nodes=${nodes} edit=${edit} />` : null;
  const table = hero.custom && hasSkins ? html`<${HeroSkinTable} hero=${hero} skins=${skins} edit=${edit} />` : null;
  return html`
    <div class="card">
      <div class="row">
        <strong>${`#${index + 1}`}</strong>
        ${summoned
          ? html`<span>${label(dict.heroes[hero.name])}</span><span class="note">Hỗ trợ · Ra sân cùng Pháo Loli</span>`
          : html`<${Select} aria-label=${`Hero slot ${index + 1}`} options=${options} value=${hero.name} onChange=${setName} />`}
        ${custom}
      </div>
      ${avatar}
      ${table}
    </div>
  `;
}

// Dị Năng level N = skill nodes 1..N open (opening a node opens every lower one); "Tùy chỉnh" starts
// it at 0. Attribute nodes are not modelled.
function AvatarPicker({ hero, nodes, edit }) {
  const setLevel = (v) => edit((h) => (h.avatar = v));
  return html`
    <div class="row">
      <label>Dị Năng (node skill)</label>
      <${NumberInput} value=${hero.avatar ?? 0} min=${0} max=${nodes.length} onChange=${setLevel} />
      <span class="note">${` /${nodes.length}`}</span>
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
      <table>
        <tbody>
          ${headerRow(HEADERS)}
          ${rows}
        </tbody>
      </table>
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
        ${label(skin)}${requiresNote(skin, skins)}
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
