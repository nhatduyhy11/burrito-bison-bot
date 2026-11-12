// Preact + htm building blocks for the setup page: html`` (htm bound to preact.h), small components
// and vnode helpers. Convention: templates only reference values and handlers defined above them
// (no inline functions).
import { h } from "preact";
import htm from "htm";
import { clamp } from "./skin-rules.js";

export const html = htm.bind(h);

export const COLOR_LABEL = { red: "đỏ", gold: "vàng", colorful: "7 màu", default: "mặc định", special: "loại 3" };

export function label(item) {
  const english = item.name_vn && item.name !== item.name_vn ? ` ${item.name}` : null;
  return html`
    ${item.name_vn || item.name}${english ? html`<span class="en">${english}</span>` : null}
  `;
}

export const optionText = (item) =>
  item.name_vn && item.name_vn !== item.name ? `${item.name_vn} (${item.name})` : item.name;

export const colorTag = (color) => html`<span class=${`tag c-${color}`}>${COLOR_LABEL[color] || color}</span>`;

// Committed on "change" (blur / Enter / spinner), clamped to [min, max].
export function NumberInput({ value, min, max, onChange, disabled }) {
  const handleChange = (e) => onChange(clamp(e.currentTarget.value, min, max));
  return html`
    <input
      type="number"
      value=${String(value)}
      min=${min}
      max=${max}
      step="1"
      disabled=${disabled}
      onChange=${handleChange}
    />
  `;
}

export function Checkbox({ checked, disabled, title, onChange }) {
  const handleChange = (e) => onChange(e.currentTarget.checked);
  return html`
    <input type="checkbox" checked=${!!checked} disabled=${disabled} title=${title} onChange=${handleChange} />
  `;
}

// options: [value, text, disabled?, group?]; consecutive options with a group go in one <optgroup>.
function groupOptions(options) {
  const out = [];
  for (const [key, text, disabled, group] of options) {
    const option = html`<option value=${key} disabled=${disabled}>${text}</option>`;
    if (!group) {
      out.push(option);
      continue;
    }
    const last = out[out.length - 1];
    if (last?.optgroup === group) last.options.push(option);
    else out.push({ optgroup: group, options: [option] });
  }
  return out.map((c) => (c.optgroup ? html`<optgroup label=${c.optgroup}>${c.options}</optgroup>` : c));
}

export function Select({ options, value, onChange, ...attrs }) {
  const handleChange = (e) => onChange(e.currentTarget.value);
  return html`
    <select ...${attrs} value=${value} onChange=${handleChange}>
      ${groupOptions(options)}
    </select>
  `;
}

// Collapsible panel. `override` = { enabled, onToggle } puts a "Ghi đè" checkbox next to the title;
// collapsing is presentation only, the override keeps its own state. An empty body is hidden (CSS).
export function Accordion({ title, hint, override, children, defaultOpen = true }) {
  const toggle = override
    ? html`<label class="override"><${Checkbox} checked=${override.enabled} onChange=${override.onToggle} />Ghi đè</label>`
    : null;
  return html`
    <details class=${override && !override.enabled ? "accordion off" : "accordion"} open=${defaultOpen}>
      <summary><strong>${title}</strong>${toggle}${hint && html`<span class="hint">${hint}</span>`}</summary>
      <div class="accordion-body">${children}</div>
    </details>
  `;
}
