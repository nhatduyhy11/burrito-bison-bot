// Preact + htm building blocks for the setup page: html`` (htm bound to preact.h), small components
// and vnode helpers. Convention: templates only reference values and handlers defined above them
// (no inline functions).
import { h } from "preact";
import htm from "htm";
import { useState, useRef, useLayoutEffect, useEffect } from "preact/hooks";
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

// ---------- hover popovers (Thánh Khí picker; reused by the skin / pet / trap / spell hover tasks) ----------

// Config descs carry rich-text markup (<color>, <u>, <br>) — flatten for plain-text UI.
export const plain = (s) => String(s ?? "").replace(/<br\s*\/?>/gi, " · ").replace(/<[^>]+>/g, "").trim();

// "Sao 0–1" for a run of consecutive stars, "Sao 1, 4" for a gap.
export const starsLabel = (stars) => {
  const [first, last = first] = stars;
  const run = stars.length > 1 && last - first === stars.length - 1 ? `${first}–${last}` : stars.join(", ");
  return `Sao ${run}`;
};

// Place a popover right of the anchor row, clamped into the viewport (fixed coords, so overflow
// ancestors can't clip it).
const popAt = (target, setPop, content) => {
  const r = target.getBoundingClientRect();
  setPop({
    x: Math.min(r.right + 8, window.innerWidth - 332),
    y: Math.max(8, r.top),
    content,
  });
};

// Floating card. By default pointer-events stay off so it never blocks the controls underneath
// and mouse-leave logic stays on the trigger side (SelectPop option popovers). `interactive`
// (PopHover) lets the mouse enter it to scroll and select text. After layout it is lifted by its
// real height so a tall card (5 Dị Năng nodes) stays inside the viewport.
export function Popover({ x, y, interactive, onMouseDown, children }) {
  const ref = useRef(null);
  const [top, setTop] = useState(y);
  useLayoutEffect(() => {
    const height = ref.current?.offsetHeight ?? 0;
    setTop(Math.max(8, Math.min(y, window.innerHeight - height - 8)));
  }, [y, children]);
  // Triggers often sit inside a <label>: a click in the card would otherwise activate its control.
  const stopLabel = (e) => e.preventDefault();
  return html`
    <div class=${interactive ? "popover interactive" : "popover"} ref=${ref}
      style=${{ left: `${x}px`, top: `${top}px` }}
      onClick=${interactive ? stopLabel : undefined} onMouseDown=${onMouseDown}>${children}</div>
  `;
}

// Grace period for crossing the gap between the trigger and its card.
const HIDE_DELAY = 200;

// Hover popover on an arbitrary trigger element (skin labels, the Dị Năng (i) icon). The card is a
// DOM child of the wrapper, so moving onto it counts as still hovering; the short hide delay
// bridges the gap beside the trigger. A text-selection drag that leaves the card keeps it open
// until the mouse button is released.
export function PopHover({ content, children }) {
  const [pop, setPop] = useState(null);
  const timer = useRef(0);
  const hovered = useRef(false);
  const dragging = useRef(false);
  useEffect(() => () => clearTimeout(timer.current), []);
  const show = (e) => {
    hovered.current = true;
    clearTimeout(timer.current);
    if (!pop) popAt(e.currentTarget, setPop, content);
  };
  const scheduleHide = () => {
    clearTimeout(timer.current);
    timer.current = setTimeout(() => setPop(null), HIDE_DELAY);
  };
  const leave = () => {
    hovered.current = false;
    if (!dragging.current) scheduleHide();
  };
  const endDrag = () => {
    dragging.current = false;
    if (!hovered.current) scheduleHide();
  };
  const startDrag = () => {
    dragging.current = true;
    document.addEventListener("mouseup", endDrag, { once: true });
  };
  return html`
    <span class="pop-hover" onMouseEnter=${show} onMouseLeave=${leave}>
      ${children}
      ${pop && html`<${Popover} x=${pop.x} y=${pop.y} interactive onMouseDown=${startDrag}>${pop.content}<//>`}
    </span>
  `;
}

// Hover summary of an item's skill per star run (skins, đồ cổ, mount). The skill title sits on top
// when every run shares one skill name; otherwise each run is labelled. ✅ marks the run holding
// `star` (pass undefined when not owned). `empty` is shown for items without star skills.
export function starSkillsPop(item, star, empty = "Không có skill theo sao") {
  const runs = item.starSkills || [];
  if (!runs.length) return html`<div class="pop-title">${label(item)}</div><div class="note">${empty}</div>`;
  const shared = runs.every((s) => s.name === runs[0].name);
  const run = (s) => html`
    <div class="pop-line" key=${s.code}>
      <span class="hint">${s.stars.includes(star) ? "✅ " : ""}${starsLabel(s.stars)}</span>${shared ? null : label(s)}
      <div class="pop-desc">${plain(s.desc_vn)}</div>
    </div>
  `;
  return html`<div class="pop-title">${label(shared ? runs[0] : item)}</div>${runs.map(run)}`;
}

// Item name with a dotted underline that opens starSkillsPop on hover.
export function StarSkillsLabel({ item, star, empty }) {
  return html`<${PopHover} content=${starSkillsPop(item, star, empty)}><span class="pop-trigger">${label(item)}</span><//>`;
}

// One row of the SelectPop listbox; popover content shows while hovered.
function PopOption({ opt, selected, active, onPick, onHover, onLeave }) {
  const [value, text, , disabled] = opt;
  // Keep focus on the trigger: a focusout (blur to body) must not close the list before the
  // option's click event lands. preventDefault on the click also cancels a wrapping <label>'s
  // activation behavior — it would forward this click to the trigger button and re-open the
  // just-closed list.
  const press = (e) => e.preventDefault();
  const pick = (e) => { e.preventDefault(); if (!disabled) onPick(value); };
  const hover = (e) => onHover(opt, e.currentTarget);
  const cls = `dd-opt${selected ? " selected" : ""}${active ? " active" : ""}${disabled ? " disabled" : ""}`;
  return html`
    <div class=${cls} role="option" aria-selected=${selected} aria-disabled=${!!disabled}
      onMouseDown=${press} onClick=${pick} onMouseEnter=${hover} onMouseLeave=${onLeave}>
      ${text}
    </div>
  `;
}

// Custom dropdown for options that need a hover popover (native <select> options can't). options:
// [value, text, popover?, disabled?, group?] — the popover element is optional per option; like
// Select, consecutive options with a group sit under one group header and disabled ones can't be picked. Commits like <select>:
// pick on click or Enter, closes on pick / outside click (focusout) / Escape; arrows move the
// keyboard cursor. Reused by the relic picker and the later hover tasks.
export function SelectPop({ options, value, onChange, ...attrs }) {
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(-1);
  const [pop, setPop] = useState(null);
  const [up, setUp] = useState(false);
  const root = useRef(null);
  const list = useRef(null);
  const reset = () => { setOpen(false); setActive(-1); setPop(null); setUp(false); };
  // Open upward when the list would run past the viewport bottom and there is more room above.
  useLayoutEffect(() => {
    if (!open || !list.current) return;
    const btn = root.current.getBoundingClientRect();
    const below = window.innerHeight - btn.bottom;
    setUp(list.current.offsetHeight + 8 > below && btn.top > below);
  }, [open]);
  // A fresh list starts at scrollTop 0, so a selected option deeper down opens out of sight (like
  // a native <select>, which scrolls to its selected option). Center the keyboard cursor — the
  // selected option on open — whenever it sits outside the visible rows.
  useLayoutEffect(() => {
    if (!open || !list.current) return;
    const box = list.current;
    const el = box.querySelector(".dd-opt.active") || box.querySelector(".dd-opt.selected");
    if (!el) return;
    const top = el.offsetTop;
    if (top >= box.scrollTop && top + el.offsetHeight <= box.scrollTop + box.clientHeight) return;
    box.scrollTop = Math.max(0, top - (box.clientHeight - el.offsetHeight) / 2);
  }, [open, active]);
  const hidePop = () => setPop(null);
  const hover = (opt, target) => (opt[2] ? popAt(target, setPop, opt[2]) : hidePop());
  const pick = (key) => { reset(); if (key !== value) onChange(key); };
  const toggle = () => {
    if (open) reset();
    else { setOpen(true); setActive(Math.max(0, options.findIndex(([k]) => k === value))); }
  };
  // Next enabled option in direction dir; stays put at either end.
  const step = (a, dir) => {
    for (let i = a + dir; i >= 0 && i < options.length; i += dir) if (!options[i][3]) return i;
    return clamp(a, 0, options.length - 1);
  };
  const onKey = (e) => {
    if (e.key === "Escape") { reset(); return; }
    if (!open) {
      if (e.key === "Enter" || e.key === " ") { e.preventDefault(); toggle(); }
      return;
    }
    if (e.key === "ArrowDown") { e.preventDefault(); setActive((a) => step(a, 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setActive((a) => step(a, -1)); }
    else if (e.key === "Enter") { e.preventDefault(); if (active >= 0 && !options[active][3]) pick(options[active][0]); }
  };
  // Clicking outside the dropdown (focus leaves it) closes; relatedTarget is null for body clicks.
  const blur = (e) => { if (!root.current?.contains(e.relatedTarget)) reset(); };
  const current = options.find(([k]) => k === value);
  return html`
    <span class="dd" ref=${root} onKeyDown=${onKey} onFocusOut=${blur}>
      <button type="button" ...${attrs} aria-haspopup="listbox" aria-expanded=${open} onClick=${toggle}>
        ${current ? current[1] : value}
        <span class="dd-caret" />
      </button>
      ${open && html`
        <div class=${up ? "dd-list up" : "dd-list"} ref=${list} role="listbox" onMouseLeave=${hidePop}>
          ${options.map((opt, i) => html`
            ${opt[4] && opt[4] !== options[i - 1]?.[4] && html`<div class="dd-group" key=${`g-${opt[4]}`}>${opt[4]}</div>`}
            <${PopOption} key=${opt[0]} opt=${opt} selected=${opt[0] === value} active=${i === active}
              onPick=${pick} onHover=${hover} onLeave=${hidePop} />`)}
        </div>
      `}
      ${pop && html`<${Popover} x=${pop.x} y=${pop.y}>${pop.content}<//>`}
    </span>
  `;
}

// Collapsible panel. `override` = { enabled, onToggle } puts a "Ghi đè" checkbox next to the title;
// collapsing is presentation only, the override keeps its own state. An empty body is hidden (CSS).
// skipExpandAll: "Mở tất cả" leaves this panel closed ("Thu gọn tất cả" still closes it).
export function Accordion({ title, hint, override, children, defaultOpen = true, skipExpandAll = false }) {
  const toggle = override
    ? html`<label class="override"><${Checkbox} checked=${override.enabled} onChange=${override.onToggle} />Ghi đè</label>`
    : null;
  return html`
    <details class=${override && !override.enabled ? "accordion off" : "accordion"} open=${defaultOpen}
      data-skip-expand-all=${skipExpandAll || undefined}>
      <summary><strong>${title}</strong>${toggle}${hint && html`<span class="hint">${hint}</span>`}</summary>
      <div class="accordion-body">${children}</div>
    </details>
  `;
}
