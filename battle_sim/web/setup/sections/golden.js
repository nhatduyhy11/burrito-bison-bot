// goldenSkinsCount (pet damage bonus; the server computes it, formula unknown).
import { html, NumberInput, Section } from "../ui.js";

export function GoldenSection({ ctx }) {
  const { state, update } = ctx;
  const onToggle = (on) => update((s) => void (s.goldenSkinsCount = on ? 0 : null));
  const setCount = (v) => update((s) => void (s.goldenSkinsCount = v));
  return html`
    <${Section}
      title="goldenSkinsCount"
      hint="tăng sát thương pet; server tự tính, chưa rõ cách"
      enabled=${state.goldenSkinsCount !== null}
      onToggle=${onToggle}
    >
      <div class="row">
        <label>Số skin vàng <${NumberInput} value=${state.goldenSkinsCount} min=${0} max=${999} onChange=${setCount} /></label>
      </div>
    <//>
  `;
}
