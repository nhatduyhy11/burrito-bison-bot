// Small DOM helpers for the setup page.
(function () {
  "use strict";
  const SimSetup = (window.SimSetup = window.SimSetup || {});

  const COLOR_LABEL = { red: "đỏ", gold: "vàng", colorful: "7 màu", default: "mặc định", special: "loại 3" };

  function el(tag, attrs = {}, ...children) {
    const node = document.createElement(tag);
    for (const [key, value] of Object.entries(attrs)) {
      if (value === undefined || value === null || value === false) continue;
      if (key.startsWith("on")) node.addEventListener(key.slice(2), value);
      else if (key === "class") node.className = value;
      else if (key in node && typeof value !== "string") node[key] = value;
      else node.setAttribute(key, value === true ? "" : value);
    }
    for (const child of children.flat()) if (child !== null && child !== undefined && child !== false) node.append(child);
    return node;
  }

  const label = (item) => [item.name_vn || item.name, item.name_vn && item.name !== item.name_vn ? el("span", { class: "en" }, ` ${item.name}`) : null];
  const optionText = (item) => (item.name_vn && item.name_vn !== item.name ? `${item.name_vn} (${item.name})` : item.name);
  const colorTag = (color) => el("span", { class: `tag c-${color}` }, COLOR_LABEL[color] || color);

  function numberInput(value, min, max, onChange, disabled) {
    return el("input", {
      type: "number", value, min, max, step: 1, disabled,
      onchange: (e) => onChange(SimSetup.clamp(e.target.value, min, max)),
    });
  }

  // options: [value, text, disabled?, group?]; consecutive options with a group go in one <optgroup>.
  function selectOf(options, value, onChange, attrs = {}) {
    const children = [];
    for (const [key, text, disabled, group] of options) {
      const option = el("option", { value: key, selected: key === value, disabled }, text);
      if (!group) { children.push(option); continue; }
      let last = children[children.length - 1];
      if (!last || last.tagName !== "OPTGROUP" || last.label !== group) children.push(last = el("optgroup", { label: group }));
      last.append(option);
    }
    return el("select", { ...attrs, onchange: (e) => onChange(e.target.value) }, children);
  }

  // A form section with a "Ghi đè" toggle; body() is rendered only when enabled.
  function section(title, hint, enabled, onToggle, body) {
    return el("section", { class: enabled ? "" : "off" },
      el("header", {},
        el("h2", {}, title),
        el("label", {}, el("input", { type: "checkbox", checked: enabled, onchange: (e) => onToggle(e.target.checked) }), "Ghi đè"),
        hint ? el("span", { class: "hint" }, hint) : null),
      el("div", { class: "body" }, enabled ? body() : []));
  }

  Object.assign(SimSetup, { COLOR_LABEL, el, label, optionText, colorTag, numberInput, selectOf, section });
})();
