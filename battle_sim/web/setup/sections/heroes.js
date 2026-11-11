// Hero list; each hero card can open its skin table (owned, star, slots).
import { html, label, optionText, colorTag, NumberInput, Checkbox, Select, Section } from "../ui.js";
import { HERO_SLOTS, heroForced, heroSlotForced, heroSlotKind } from "../skin-rules.js";
import { heroSkins, newHero } from "../profile-io.js";
import { AddButton, RemoveButton, headerRow, nameOptions, requiresNote, without } from "./shared.js";

const HEADERS = ["Skin", "Màu", "Sở hữu", "Sao", "Slot"];

export function HeroesSection({ ctx }) {
  const onToggle = (on) => ctx.toggleWithPrefill("heroes", on);
  return html`<${Section}
    title="Hero"
    hint="tối đa 5; tắt = đội hình capture"
    enabled=${!!ctx.state.heroes}
    onToggle=${onToggle}
  >
    <${HeroesBody} ctx=${ctx} />
  <//>`;
}

function HeroesBody({ ctx }) {
  const cards = ctx.state.heroes.map(
    (hero, index) => html`<${HeroCard} key=${index} ctx=${ctx} hero=${hero} index=${index} />`,
  );
  return html`
    ${cards}
    <div class="row"><${AddButton} ctx=${ctx} group="heroes" make=${newHero} /></div>
    <div class="note">
      Hero có trong capture giữ chỉ số và skill gốc; hero khác mượn chỉ số trung bình, level và level skill của các
      hero cùng độ hiếm trong capture (gần đúng, ±10%). Không tick "Tùy chỉnh skin" thì giữ skin từ capture.
    </div>
  `;
}

function HeroCard({ ctx, hero, index }) {
  const { state, dict, update } = ctx;
  const skins = heroSkins(dict, hero.name);
  const hasSkins = Object.keys(skins).length > 0;
  const options = nameOptions(dict, "heroes", state.heroes.map((h) => h.name), hero.name);
  const edit = (fn) => update((s) => void fn(s.heroes[index]));
  const setName = (v) => update((s) => void (s.heroes[index] = newHero(v)));
  const setCustom = (on) => edit((h) => (h.custom = on));
  const custom = hasSkins
    ? html`<label><${Checkbox} checked=${hero.custom} onChange=${setCustom} />Tùy chỉnh skin</label>`
    : html`<span class="note">không có skin</span>`;
  const table = hero.custom && hasSkins ? html`<${HeroSkinTable} hero=${hero} skins=${skins} edit=${edit} />` : null;
  return html`<div class="card">
    <div class="row">
      <strong>${`#${index + 1}`}</strong>
      <${Select} options=${options} value=${hero.name} onChange=${setName} />
      ${custom}
      <${RemoveButton} ctx=${ctx} group="heroes" index=${index} />
    </div>
    ${table}
  </div>`;
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
    return html`<${HeroSkinRow}
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
    />`;
  });
  return html`<div>
    <div class="row">
      <label>Đang mặc <${Select} options=${wornOptions} value=${hero.worn || ""} onChange=${setWorn} /></label>
      <span class="note">${slotNote}</span>
    </div>
    <table>
      <tbody>
        ${headerRow(HEADERS)}
        ${rows}
      </tbody>
    </table>
    <div class="note">
      Sở hữu: account có skin (cộng chỉ số). Slot: skill của skin vào trận. Skin 7 màu cần 3 skin thường ở sao ≥ sao
      của nó (trang tự nâng); gắn slot 7 màu thì 3 skin đó cũng vào slot và bị khoá đến khi bỏ slot 7 màu.
    </div>
  </div>`;
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
  return html`<tr>
    <td class="name">${label(skin)}${requiresNote(skin, skins)}</td>
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
  </tr>`;
}
