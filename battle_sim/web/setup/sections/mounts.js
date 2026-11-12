import { Accordion, Checkbox, html, label, optionText, Select } from "../ui.js";

export function MountSection({ ctx }) {
  const { state, dict, update } = ctx;
  const mounts = state.mounts;
  const onToggle = (on) => ctx.toggleWithPrefill("mounts", on);
  const setSelected = (selected) => update((s) => { s.mounts.selected = selected || null; });
  const options = [["", "Không chọn"], ...Object.entries(dict.mounts)
    .filter(([name]) => mounts?.owned.includes(name))
    .map(([name, mount]) => [name, optionText(mount)])];
  const groups = [["red", "Đỏ"], ["gold", "Vàng"], ["orange", "Cam"]].map(([color, title]) => {
    const rows = Object.entries(dict.mounts).filter(([, mount]) => mount.color === color).map(([name, mount]) => {
      const setOwned = (on) => update((s) => {
        s.mounts.owned = on ? [...s.mounts.owned, name] : s.mounts.owned.filter((key) => key !== name);
      });
      return html`
        <label class="mount-option" key=${name}>
          <${Checkbox} checked=${mounts?.owned.includes(name)} onChange=${setOwned} />
          <span>${label(mount)}</span>
        </label>
      `;
    });
    return html`
      <div class=${`mount-group mount-${color}`} key=${color}>
        <strong class=${`mount-group-title c-${color}`}>${title}</strong>
        <div class="mount-options">${rows}</div>
      </div>
    `;
  });
  const hint = mounts ? `${mounts.owned.length} sở hữu · ${mounts.selected ? optionText(dict.mounts[mounts.selected]) : "Không chọn"}` : "giữ từ capture";
  return html`
    <${Accordion} title="Mount" hint=${hint} override=${{ enabled: !!mounts, onToggle }}>
      ${mounts && html`
        <div class="mount-groups">${groups}</div>
        <div class="row"><label>Đang cưỡi
          <${Select} options=${options} value=${mounts.selected || ""} onChange=${setSelected} />
        </label></div>
      `}
    <//>
  `;
}
