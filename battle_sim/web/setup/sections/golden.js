// goldenSkinsCount (pet damage bonus; the server computes it, formula unknown).
import { Accordion, html, NumberInput } from "../ui.js";

export function GoldenSection({ ctx }) {
  const { state, update } = ctx;
  const enabled = state.goldenSkinsCount !== null;
  const onToggle = (on) => update((s) => void (s.goldenSkinsCount = on ? 0 : null));
  const setCount = (v) => update((s) => void (s.goldenSkinsCount = v));
  return html`
    <${Accordion}
      title="goldenSkinsCount"
      hint="tăng sát thương pet; server tự tính, chưa rõ cách"
      override=${{ enabled, onToggle }}
    >
      ${enabled && html`
        <div class="row">
          <label>Số skin vàng <${NumberInput} value=${state.goldenSkinsCount} min=${0} max=${999} onChange=${setCount} /></label>
        </div>
      `}
    <//>
  `;
}
