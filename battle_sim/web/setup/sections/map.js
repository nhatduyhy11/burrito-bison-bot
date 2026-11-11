// "Màn chơi": campaign stage to play (off = the capture's stage).
import { html, NumberInput, Select, Section } from "../ui.js";

const MODE_OPTIONS = [["campaign", "Campaign"]];
const noop = () => {};

export function MapSection({ ctx }) {
  const onToggle = (on) => ctx.toggleWithPrefill("map", on);
  return html`
    <${Section}
      title="Màn chơi"
      hint="Campaign; tắt = stage của capture"
      enabled=${!!ctx.state.map}
      onToggle=${onToggle}
    >
      <${MapBody} ctx=${ctx} />
    <//>
  `;
}

function MapBody({ ctx }) {
  const { state, dict, update } = ctx;
  const { minStage, maxStage } = dict.maps.campaign;
  const setStage = (v) => update((s) => void (s.map.stage = v));
  return html`
    <div class="row">
      <label>Mode <${Select} options=${MODE_OPTIONS} value="campaign" onChange=${noop} /></label>
      <label>
        ${`Stage (${minStage}–${maxStage}) `}
        <${NumberInput} value=${state.map.stage} min=${minStage} max=${maxStage} onChange=${setStage} />
      </label>
    </div>
  `;
}
