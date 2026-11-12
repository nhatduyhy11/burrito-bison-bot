import { starterAntiques } from "../../antiques.js";
import { Accordion, Checkbox, html, label, NumberInput } from "../ui.js";

const COLORS = [["gold", "Vàng"], ["red", "Đỏ"], ["orange", "Cam"], ["purple", "Tím"], ["blue", "Xanh dương"]];

export function AntiquesSection({ ctx }) {
  const { state, antiqueDict, update } = ctx;
  const owned = state.antiques;
  const catalog = antiqueDict.antiques;
  const useStarter = () => update((s) => { s.antiques = starterAntiques(catalog); });
  const groups = COLORS.map(([color, title]) => {
    const items = Object.entries(catalog).filter(([, item]) => item.color === color);
    const count = items.filter(([name]) => Object.hasOwn(owned, name)).length;
    const rows = items.map(([name, item]) => {
      const star = owned[name];
      const setOwned = (on) => update((s) => {
        if (on) s.antiques[name] = 1;
        else delete s.antiques[name];
      });
      const setStar = (value) => update((s) => { s.antiques[name] = value; });
      return html`
        <div class="antique-option" key=${name}>
          <label><${Checkbox} checked=${star !== undefined} onChange=${setOwned} /><span>${label(item)}</span></label>
          <label>Sao <${NumberInput} value=${star ?? 1} min=${1} max=${item.maxStar} disabled=${star === undefined} onChange=${setStar} /></label>
        </div>
      `;
    });
    return html`<${Accordion} key=${color} title=${title} hint=${`${count}/${items.length} sở hữu`} defaultOpen=${false}>${rows}<//>`;
  });
  return html`
    <${Accordion} title="Đồ Cổ" hint=${`${Object.keys(owned).length} sở hữu`} defaultOpen=${false}>
      <button type="button" class="antique-preset" onClick=${useStarter}>Cam, tím, xanh dương · 1 sao</button>
      ${groups}
    <//>
  `;
}
