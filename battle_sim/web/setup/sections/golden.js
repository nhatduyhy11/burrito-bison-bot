// goldenSkinsCount: total stars of the hero gold skins (DermaLO color 7). Only feeds a pet
// FinalHurtAdd bonus (value x 150) on GAT battle types 21/37/38/42/43; VN config has no gate. See BUILD_SKINS.md.
import { Accordion, html, NumberInput } from "../ui.js";

export function GoldenSection({ ctx }) {
  const { state, update } = ctx;
  const enabled = state.goldenSkinsCount !== null;
  const onToggle = (on) => update((s) => void (s.goldenSkinsCount = on ? 0 : null));
  const setCount = (v) => update((s) => void (s.goldenSkinsCount = v));
  return html`
    <${Accordion}
      title="goldenSkinsCount"
      hint="tổng sao skin vàng hero; pet +ST cuối (×150) ở U Đô, World Boss, Guild Co-Boss, Ác Mộng. Chỉ GAT, VN vô tác dụng"
      override=${{ enabled, onToggle }}
    >
      ${enabled && html`
        <div class="row">
          <label>Tổng sao skin vàng hero <${NumberInput} value=${state.goldenSkinsCount} min=${0} max=${999} onChange=${setCount} /></label>
        </div>
      `}
    <//>
  `;
}
