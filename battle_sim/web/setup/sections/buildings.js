// "Skin building": each building has its own "Ghi đè" and skin table (1 red / 2 gold / 1 special slot).
import { html, label, optionText, colorTag, COLOR_LABEL, NumberInput, Checkbox, Select, Accordion } from "../ui.js";
import { BUILD_SLOTS, buildingForced, buildingLocks } from "../skin-rules.js";
import { BUILDINGS, buildSkins, newBuilding } from "../profile-io.js";
import { eventUnlockNote, headerRow, requiresNote, without } from "./shared.js";

const HEADERS = ["Skin", "Màu / slot", "Sở hữu", "Sao", "Slot"];
const COLOR_ORDER = { red: 0, gold: 1 };

export function BuildingsSection({ ctx }) {
  const any = BUILDINGS.some(([key]) => ctx.state.buildings[key]);
  const cards = BUILDINGS.map(
    ([key, title]) => html`<${BuildingCard} key=${key} ctx=${ctx} building=${key} title=${title} />`,
  );
  const note = any
    ? html`
        <div class="note">
          Slot: 1 đỏ, 2 vàng, 1 loại 3. Skin 7 màu dùng slot vàng và khoá 3 skin yêu cầu khỏi mọi slot. Chỉ số building
          (attr) và skill do server thêm vẫn giữ từ capture.
        </div>
      `
    : null;
  return html`
    <${Accordion} title="Skin building">
      ${cards}
      ${note}
    <//>
  `;
}

function BuildingCard({ ctx, building, title }) {
  const { state, dict, update } = ctx;
  const entry = state.buildings[building];
  const edit = (fn) => update((s) => void fn(s.buildings[building]));
  const setEnabled = (on) => update((s) => void (s.buildings[building] = on ? newBuilding(dict, building) : null));
  const action = html`<label class="building-override"><${Checkbox} checked=${!!entry} onChange=${setEnabled} />Ghi đè</label>`;
  const table = entry
    ? html`<${BuildingSkinTable} entry=${entry} skins=${buildSkins(dict, building)} edit=${edit} />`
    : null;
  return html`
    <${Accordion} title=${title} action=${action}>
      <div class="building-skin-table">${table}</div>
    <//>
  `;
}

function BuildingSkinTable({ entry, skins, edit }) {
  const forced = buildingForced(entry, skins);
  const locked = buildingLocks(skins, entry.slots);
  const count = (slot) => entry.slots.filter((key) => skins[key].slot === slot).length;
  const orderedSkins = Object.entries(skins).sort(([, a], [, b]) =>
    (COLOR_ORDER[a.color] ?? 2) - (COLOR_ORDER[b.color] ?? 2));
  const wornOptions = orderedSkins.map(([key, skin]) => [key, optionText(skin)]);
  const setWorn = (v) => edit((e) => (e.worn = v));
  const slotNote = `Slot: ${count("red")}/1 đỏ, ${count("gold")}/2 vàng, ${count("special")}/1 loại 3`;
  const rows = orderedSkins.map(([key, skin]) => {
    const slotted = entry.slots.includes(key);
    return html`
      <${BuildingSkinRow}
        key=${key}
        skinKey=${key}
        skin=${skin}
        skins=${skins}
        state=${entry.skins[key]}
        forcedStar=${forced[key]}
        slotted=${slotted}
        locked=${locked.has(key)}
        slotFull=${!slotted && count(skin.slot) >= BUILD_SLOTS[skin.slot]}
        edit=${edit}
      />
    `;
  });
  return html`
    <div>
      <div class="row">
        <label>Đang mặc <${Select} options=${wornOptions} value=${entry.worn} onChange=${setWorn} /></label>
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

function BuildingSkinRow({ skinKey: key, skin, skins, state, forcedStar, slotted, locked, slotFull, edit }) {
  const slottable = !!BUILD_SLOTS[skin.slot];
  const setOwned = (on) =>
    edit((e) => {
      e.skins[key].owned = on;
      if (!on) e.slots = without(e.slots, key);
    });
  const setStar = (v) => edit((e) => (e.skins[key].star = v));
  const setSlotted = (on) =>
    edit((e) => {
      if (on) e.skins[key].owned = true;
      e.slots = on ? [...e.slots, key] : without(e.slots, key);
    });
  const slotLabel =
    slottable && skin.slot !== skin.color
      ? html`<span class="note">${` slot ${COLOR_LABEL[skin.slot] || skin.slot}`}</span>`
      : null;
  let slotCell = html`<${Checkbox} checked=${slotted} disabled=${slotFull} onChange=${setSlotted} />`;
  if (!slottable) slotCell = html`<span class="note">-</span>`;
  else if (locked) slotCell = html`<span class="warn">khoá</span>`;
  return html`
    <tr>
      <td class="name">${label(skin)}${requiresNote(skin, skins)}${eventUnlockNote(skin)}</td>
      <td>${colorTag(skin.color)}${slotLabel}</td>
      <td><${Checkbox} checked=${state.owned} disabled=${forcedStar !== undefined} onChange=${setOwned} /></td>
      <td>
        <${NumberInput}
          value=${state.star}
          min=${forcedStar || 1}
          max=${skin.maxStar}
          disabled=${!state.owned || skin.default}
          onChange=${setStar}
        /><span class="note">${` /${skin.maxStar}`}</span>
      </td>
      <td>${slotCell}</td>
    </tr>
  `;
}
