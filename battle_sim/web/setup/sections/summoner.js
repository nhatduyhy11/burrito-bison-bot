// "Trang bị Summoner" (gear checkboxes) and "Skill Summoner": skill slots (up to 3), skill-less
// event skins (stats only, no slot) and the worn skin.
import { useEffect, useState } from "preact/hooks";
import { Accordion, Checkbox, html, NumberInput, optionText, PopHover, Select, StarSkillsLabel, label, plain } from "../ui.js";
import { eventUnlockNote, headerRow } from "./shared.js";
import { stashValue, takeStashed } from "../profile-state.js";
import { SUMMONER_SLOTS, isPassiveSummonerSkin, slottedSkillCount, summonerSkillsConflict } from "../../summoner-skills.js";

const COLORS = [["gold", "Vàng"], ["red", "Đỏ"]];

// The three Summoner equipment skills (support-dict summonerGear, one per gear slot at stage 20+).
// Untouched (state null) keeps the bed build from the capture; the first toggle materializes every
// checkbox from the capture, so unchecking a captured skill removes it.
export function SummonerGearSection({ ctx }) {
  const { state, dict } = ctx;
  const [captured, setCaptured] = useState(null); // gear names on the base capture's bed, for display
  const battle = state.battle;
  useEffect(() => {
    let live = true;
    ctx.capturedSummonerGear().then((names) => { if (live) setCaptured(names); });
    return () => { live = false; };
  }, [battle]);
  const rows = Object.entries(dict.summonerGear).map(([name, gear]) =>
    html`<${GearCheck} key=${name} ctx=${ctx} name=${name} gear=${gear} captured=${captured} />`);
  return html`
    <div class="card">
      <strong>Trang bị Summoner</strong>
      <div class="row">${rows}</div>
      <div class="note">Tick = thêm skill vào build Giường, bỏ tick = xóa; mặc định (chưa đụng) giữ nguyên capture.</div>
    </div>
  `;
}

function GearCheck({ ctx, name, gear, captured }) {
  const { state, dict, update } = ctx;
  const untouched = state.summonerGear === null;
  const disabled = untouched && captured === null; // capture names not loaded yet
  const setGear = (value) => update((s) => {
    s.summonerGear ??= Object.fromEntries(Object.keys(dict.summonerGear).map((key) => [key, captured.includes(key)]));
    s.summonerGear[name] = value;
  });
  return html`
    <label>
      <${Checkbox} checked=${untouched ? !!captured?.includes(name) : !!state.summonerGear[name]}
        disabled=${disabled} onChange=${setGear} />
      <${PopHover} content=${gearPop(gear)}><span class="pop-trigger">${label(gear)}</span><//>
    </label>
  `;
}

// Popover for one gear skill: effect, the gear slot that grants it (example piece) and stage range.
function gearPop(gear) {
  return html`
    <div class="pop-title">${label(gear)}</div>
    <div class="pop-desc">${plain(gear.desc_vn)}</div>
    <div class="note">vd: ${gear.example.name_vn} · stage ${gear.minStage}–${gear.maxStage}</div>
  `;
}


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
        <div class="row"><label>Đang mặc
          <${Select} options=${wornOptions} value=${state.summonerWorn || ""} onChange=${setWorn} />
        </label></div>
        <${SummonerSkills} ctx=${ctx} />
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
        <div class="table-scroll"><table><tbody>${headerRow(["Skin", "Skill", "Sao", "Slot"])}${rows}</tbody></table></div>
      </div>
    `;
  });
}

function SkillRow({ ctx, name, skin }) {
  const { state, dict, update, region } = ctx;
  const selected = state.summonerSkins;
  const entry = selected.find((item) => item.name === name);
  const passive = isPassiveSummonerSkin(skin);
  const conflict = !entry && !passive && selected.some((item) => {
    const other = dict.summonerSkins[item.name];
    return other.skill && summonerSkillsConflict(other, skin);
  });
  const full = !entry && !passive && slottedSkillCount(selected, dict.summonerSkins) >= SUMMONER_SLOTS;
  // Untick parks the star in the session stash; re-tick restores it instead of falling to 1.
  const starKey = `summonerSkin:${region}:${name}`;
  const setSlot = (on) => update((s) => {
    if (on) s.summonerSkins.push({ name, star: takeStashed(starKey) ?? 1 });
    else {
      stashValue(starKey, s.summonerSkins.find((item) => item.name === name)?.star);
      s.summonerSkins = s.summonerSkins.filter((item) => item.name !== name);
    }
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
      <td class="name"><${StarSkillsLabel} item=${skin} star=${entry?.star} empty="Skin sự kiện: không có skill, chỉ cộng chỉ số" />${passive ? eventUnlockNote(skin) : null}</td>
      <td>${passive ? html`<span class="note">Cộng chỉ số khi kích hoạt</span>` : skin.skill_vn || skin.skill}</td>
      <td>${star}</td>
      <td><${Checkbox} checked=${!!entry} disabled=${conflict || full} title=${slotTitle} onChange=${setSlot} /></td>
    </tr>
  `;
}
