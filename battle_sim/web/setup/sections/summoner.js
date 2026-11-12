// "Skill Summoner": skill slots (up to 3), skill-less event skins (stats only, no slot) and the worn skin.
import { Accordion, Checkbox, html, label, NumberInput, optionText, Select } from "../ui.js";
import { eventUnlockNote, headerRow } from "./shared.js";
import { SUMMONER_SLOTS, isPassiveSummonerSkin, slottedSkillCount, summonerSkillsConflict } from "../../summoner-skills.js";

const COLORS = [["gold", "Vàng"], ["red", "Đỏ"]];

export function SummonerSection({ ctx }) {
  const { state, dict, update } = ctx;
  const selected = state.summonerSkins;
  const onToggle = (on) => ctx.toggleWithPrefill("summonerSkins", on);
  const setWorn = (name) => update((s) => { s.summonerWorn = name || null; });
  const wornText = state.summonerWorn ? optionText(dict.summonerSkins[state.summonerWorn]) : "mặc định";
  const hint = selected
    ? `${slottedSkillCount(selected, dict.summonerSkins)}/${SUMMONER_SLOTS} slot · đang mặc ${wornText}`
    : "tắt = giữ từ capture";
  const wornOptions = [["", "Mặc định"], ...(selected || []).map(({ name }) => [name, optionText(dict.summonerSkins[name])])];
  return html`
    <${Accordion} title="Skill Summoner" hint=${hint} override=${{ enabled: !!selected, onToggle }}>
      ${selected && html`
        <${SummonerSkills} ctx=${ctx} />
        <div class="row"><label>Đang mặc
          <${Select} options=${wornOptions} value=${state.summonerWorn || ""} onChange=${setWorn} />
        </label></div>
        <div class="note">
          Đang mặc: model Summoner trong trận, chọn trong các skin đã tick. Skin sự kiện không có skill chỉ cộng chỉ
          số (server tính, sim giữ chỉ số capture), không chiếm slot.
        </div>
      `}
    <//>
  `;
}

function SummonerSkills({ ctx }) {
  const skins = Object.entries(ctx.dict.summonerSkins).filter(([, skin]) => skin.skill || isPassiveSummonerSkin(skin));
  return COLORS.map(([color, title]) => {
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
  const passive = isPassiveSummonerSkin(skin);
  const conflict = !entry && !passive && selected.some((item) => {
    const other = dict.summonerSkins[item.name];
    return other.skill && summonerSkillsConflict(other, skin);
  });
  const full = !entry && !passive && slottedSkillCount(selected, dict.summonerSkins) >= SUMMONER_SLOTS;
  const setSlot = (on) => update((s) => {
    if (on) s.summonerSkins.push({ name, star: 1 });
    else s.summonerSkins = s.summonerSkins.filter((item) => item.name !== name);
  });
  const setStar = (star) => update((s) => {
    s.summonerSkins.find((item) => item.name === name).star = star;
  });
  let slotTitle;
  if (passive) slotTitle = "Skin sự kiện: không có skill, không chiếm slot; tick để chọn được ở Đang mặc";
  else if (conflict) slotTitle = "Xung đột với skill đang gắn";
  const star = passive
    ? html`<span class="note">${`${skin.maxStar} · sự kiện`}</span>`
    : html`<${NumberInput} value=${entry?.star ?? 1} min=${1} max=${skin.maxStar} disabled=${!entry} onChange=${setStar} />`;
  return html`
    <tr>
      <td class="name">${label(skin)}${passive ? eventUnlockNote(skin) : null}</td>
      <td>${passive ? html`<span class="note">Cộng chỉ số khi kích hoạt</span>` : skin.skill_vn || skin.skill}</td>
      <td>${star}</td>
      <td><${Checkbox} checked=${!!entry} disabled=${conflict || full} title=${slotTitle} onChange=${setSlot} /></td>
    </tr>
  `;
}
