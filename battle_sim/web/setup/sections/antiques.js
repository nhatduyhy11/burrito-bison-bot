import { starterAntiques } from "../../antiques.js";
import { Accordion, Checkbox, html, NumberInput, StarSkillsLabel } from "../ui.js";
import { stashValue, takeStashed } from "../profile-state.js";

const COLORS = [["gold", "Vàng"], ["red", "Đỏ"], ["orange", "Cam"], ["purple", "Tím"], ["blue", "Xanh dương"]];

export function AntiquesSection({ ctx }) {
  const { state, antiqueDict, update, region } = ctx;
  const owned = state.antiques;
  const catalog = antiqueDict.antiques;
  const useStarter = () => update((s) => { s.antiques = starterAntiques(catalog); });
  const groups = COLORS.map(([color, title]) => {
    const items = Object.entries(catalog).filter(([, item]) => item.color === color);
    const count = items.filter(([name]) => Object.hasOwn(owned, name)).length;
    const rows = items.map(([name, item]) => {
      const star = owned[name];
      // Untick parks the star in the session stash; re-tick restores it instead of falling to 1.
      const setOwned = (on) => update((s) => {
        const key = `antique:${region}:${name}`;
        if (on) s.antiques[name] = takeStashed(key) ?? 1;
        else {
          stashValue(key, s.antiques[name]);
          delete s.antiques[name];
        }
      });
      const setStar = (value) => update((s) => { s.antiques[name] = value; });
      return html`
        <div class="antique-option" key=${name}>
          <label><${Checkbox} checked=${star !== undefined} onChange=${setOwned} /><${StarSkillsLabel} item=${item} star=${star} /></label>
          <label>Sao <${NumberInput} value=${star ?? 1} min=${1} max=${item.maxStar} disabled=${star === undefined} onChange=${setStar} /></label>
        </div>
      `;
    });
    return html`
      <${Accordion} key=${color} title=${title} hint=${`${count}/${items.length} sở hữu`} defaultOpen=${false}>${rows}<//>
    `;
  });
  return html`
    <${Accordion} title="Đồ Cổ" hint=${`${Object.keys(owned).length} sở hữu`} defaultOpen=${false}>
      <div class="row">
        <button type="button" onClick=${useStarter}>Cam, tím, xanh dương · 1 sao</button>
        <span class="note">Max Lv15</span>
      </div>
      ${groups}
    <//>
  `;
}
