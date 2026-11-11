// Preact + htm building blocks for the setup page (vendor/: preact, preact-hooks, htm UMD globals).
// html`...` is htm bound to preact.h; the rest are small components / vnode helpers.
(function () {
  "use strict";
  const S = (window.SimSetup = window.SimSetup || {});
  const html = window.htm.bind(window.preact.h);

  const COLOR_LABEL = { red: "đỏ", gold: "vàng", colorful: "7 màu", default: "mặc định", special: "loại 3" };

  const label = (item) => html`${item.name_vn || item.name}${item.name_vn && item.name !== item.name_vn
    ? html`<span class="en">${` ${item.name}`}</span>` : null}`;
  const optionText = (item) => (item.name_vn && item.name_vn !== item.name ? `${item.name_vn} (${item.name})` : item.name);
  const colorTag = (color) => html`<span class=${`tag c-${color}`}>${COLOR_LABEL[color] || color}</span>`;

  // Committed on "change" (blur / Enter / spinner), clamped to [min, max].
  function NumberInput({ value, min, max, onChange, disabled }) {
    return html`<input type="number" value=${String(value)} min=${min} max=${max} step="1" disabled=${disabled}
      onChange=${(e) => onChange(S.clamp(e.currentTarget.value, min, max))} />`;
  }

  function Checkbox({ checked, disabled, title, onChange }) {
    return html`<input type="checkbox" checked=${!!checked} disabled=${disabled} title=${title}
      onChange=${(e) => onChange(e.currentTarget.checked)} />`;
  }

  // options: [value, text, disabled?, group?]; consecutive options with a group go in one <optgroup>.
  function Select({ options, value, onChange, ...attrs }) {
    const children = [];
    for (const [key, text, disabled, group] of options) {
      const option = html`<option value=${key} disabled=${disabled}>${text}</option>`;
      if (!group) { children.push(option); continue; }
      let last = children[children.length - 1];
      if (!last || last.optgroup !== group) children.push(last = { optgroup: group, options: [] });
      last.options.push(option);
    }
    return html`<select ...${attrs} value=${value} onChange=${(e) => onChange(e.currentTarget.value)}>
      ${children.map((c) => (c.optgroup ? html`<optgroup label=${c.optgroup}>${c.options}</optgroup>` : c))}
    </select>`;
  }

  // A form section with a "Ghi đè" toggle; body() is rendered only when enabled.
  function Section({ title, hint, enabled, onToggle, body }) {
    return html`<section class=${enabled ? "" : "off"}>
      <header>
        <h2>${title}</h2>
        <label><${Checkbox} checked=${enabled} onChange=${onToggle} />Ghi đè</label>
        ${hint ? html`<span class="hint">${hint}</span>` : null}
      </header>
      <div class="body">${enabled ? body() : null}</div>
    </section>`;
  }

  Object.assign(S, { html, COLOR_LABEL, label, optionText, colorTag, NumberInput, Checkbox, Select, Section });
})();
