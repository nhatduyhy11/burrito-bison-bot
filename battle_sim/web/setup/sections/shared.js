// Pieces shared by the form sections: name pickers grouped by rarity, add / remove buttons, table
// header row and the "cần: ..." note under colorful skins.
import { html, optionText } from "../ui.js";
import { LIMITS } from "../profile-io.js";

// Rarity groups in the hero / trap / pet pickers (card border in game), highest first. Spells have none.
const RARITY_GROUPS = [
  ["gold", "Vàng"],
  ["red", "Đỏ"],
  ["orange", "Cam"],
  ["purple", "Tím"],
];

export const without = (list, key) => list.filter((k) => k !== key);

// Options for a name <Select>: names already chosen elsewhere in the list are disabled.
export function nameOptions(dict, group, chosen, current) {
  const entries = Object.entries(dict[group]).map(([key, item]) => [
    key,
    optionText(item),
    key !== current && chosen.includes(key),
  ]);
  if (!entries.some(([key]) => dict[group][key].color)) return entries;
  return RARITY_GROUPS.flatMap(([color, title]) =>
    entries
      .filter(([key]) => dict[group][key].color === color)
      .map((entry) => [...entry, group === "heroes" && color === "red" ? `${title} (có skin)` : title]),
  );
}

export function AddButton({ ctx, group, make }) {
  const list = ctx.state[group];
  const unused = Object.keys(ctx.dict[group]).find((key) => !list.some((item) => item.name === key));
  const disabled = list.length >= LIMITS[group] || !unused;
  const add = () => ctx.update((s) => void s[group].push(make(unused)));
  return html`<button disabled=${disabled} onClick=${add}>${`+ Thêm (${list.length}/${LIMITS[group]})`}</button>`;
}

export function RemoveButton({ ctx, group, index }) {
  const remove = () => ctx.update((s) => void s[group].splice(index, 1));
  return html`<button class="x" title="Bỏ" onClick=${remove}>×</button>`;
}

export function headerRow(titles) {
  const cells = titles.map((t) => html`<th>${t}</th>`);
  return html`<tr>${cells}</tr>`;
}

export function requiresNote(skin, skins) {
  if (!skin.requires) return null;
  const names = skin.requires.map((r) => skins[r].name_vn || skins[r].name).join(", ");
  return html`<div class="note">${`cần: ${names}`}</div>`;
}
