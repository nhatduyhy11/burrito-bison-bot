import { Checkbox, html, label, NumberInput, Section, Accordion } from "../ui.js";
import { headerRow } from "./shared.js";
import { SUMMONER_SLOTS, summonerSkillsConflict } from "../../summoner-skills.js";

export function SummonerSection({ ctx }) {
  const selected = ctx.state.summonerSkins;
  const onToggle = (on) => ctx.toggleWithPrefill("summonerSkins", on);
  const hint = selected
    ? `${selected.length}/${SUMMONER_SLOTS} slot`
    : "tắt = giữ từ capture";
  return html`
    <${Accordion} title="Skill Summoner" hint=${hint}>
      <${Section} title="Cấu hình skill" enabled=${!!selected} onToggle=${onToggle}>
        <${SummonerSkills} ctx=${ctx} />
      <//>
    <//>
  `;
}

function SummonerSkills({ ctx }) {
  const skins = Object.entries(ctx.dict.summonerSkins).filter(([, skin]) => skin.skill);
  const colors = [["gold", "Vàng"], ["red", "Đỏ"]];
  return colors.map(([color, title]) => {
    const rows = skins.filter(([, skin]) => skin.color === color).map(([name, skin]) =>
      html`<${SkillRow} key=${name} ctx=${ctx} name=${name} skin=${skin} />`,
    );
    return html`
      <div class="card" key=${color}>
        <strong>${title}</strong>
        <table><tbody>${headerRow(["Skin", "Skill", "Sao", "Slot"])}${rows}</tbody></table>
      </div>
    `;
  });
}

function SkillRow({ ctx, name, skin }) {
  const { state, dict, update } = ctx;
  const selected = state.summonerSkins;
  const entry = selected.find((item) => item.name === name);
  const conflict = !entry && selected.some((item) => summonerSkillsConflict(dict.summonerSkins[item.name], skin));
  const full = !entry && selected.length >= SUMMONER_SLOTS;
  const setSlot = (on) => update((s) => {
    if (on) s.summonerSkins.push({ name, star: 1 });
    else s.summonerSkins = s.summonerSkins.filter((item) => item.name !== name);
  });
  const setStar = (star) => update((s) => {
    s.summonerSkins.find((item) => item.name === name).star = star;
  });
  return html`
    <tr>
      <td class="name">${label(skin)}</td>
      <td>${skin.skill_vn || skin.skill}</td>
      <td><${NumberInput} value=${entry?.star ?? 1} min=${1} max=${skin.maxStar} disabled=${!entry} onChange=${setStar} /></td>
      <td><${Checkbox} checked=${!!entry} disabled=${conflict || full} title=${conflict ? "Xung đột với skill đang gắn" : undefined} onChange=${setSlot} /></td>
    </tr>
  `;
}
