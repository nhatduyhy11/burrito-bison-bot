// Preact + htm building blocks for the setup page (vendor/: preact, preact-hooks, htm UMD globals).
// html`...` is htm bound to preact.h; the rest are small components / vnode helpers.
// Convention: templates only reference values and handlers defined above them (no inline functions).
(function () {
  "use strict";
  const S = (window.SimSetup = window.SimSetup || {});
  const html = window.htm.bind(window.preact.h);

  const COLOR_LABEL = { red: "đỏ", gold: "vàng", colorful: "7 màu", default: "mặc định", special: "loại 3" };

  function label(item) {
    const english = item.name_vn && item.name !== item.name_vn ? ` ${item.name}` : null;
    return html`${item.name_vn || item.name}${english ? html`<span class="en">${english}</span>` : null}`;
  }

  const optionText = (item) => (item.name_vn && item.name_vn !== item.name ? `${item.name_vn} (${item.name})` : item.name);
  const colorTag = (color) => html`<span class=${`tag c-${color}`}>${COLOR_LABEL[color] || color}</span>`;

  // Committed on "change" (blur / Enter / spinner), clamped to [min, max].
  function NumberInput({ value, min, max, onChange, disabled }) {
    const handleChange = (e) => onChange(S.clamp(e.currentTarget.value, min, max));
    return html`<input
      type="number"
      value=${String(value)}
      min=${min}
      max=${max}
      step="1"
      disabled=${disabled}
      onChange=${handleChange}
    />`;
  }

  function Checkbox({ checked, disabled, title, onChange }) {
    const handleChange = (e) => onChange(e.currentTarget.checked);
    return html`<input type="checkbox" checked=${!!checked} disabled=${disabled} title=${title} onChange=${handleChange} />`;
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

  function Select({ options, value, onChange, ...attrs }) {
    const handleChange = (e) => onChange(e.currentTarget.value);
    return html`<select ...${attrs} value=${value} onChange=${handleChange}>
      ${groupOptions(options)}
    </select>`;
  }

  // A form section with a "Ghi đè" toggle; children are rendered only when enabled.
  function Section({ title, hint, enabled, onToggle, children }) {
    return html`<section class=${enabled ? "" : "off"}>
      <header>
        <h2>${title}</h2>
        <label><${Checkbox} checked=${enabled} onChange=${onToggle} />Ghi đè</label>
        ${hint ? html`<span class="hint">${hint}</span>` : null}
      </header>
      <div class="body">${enabled ? children : null}</div>
    </section>`;
  }

  Object.assign(S, { html, COLOR_LABEL, label, optionText, colorTag, NumberInput, Checkbox, Select, Section });
})();
