// Teams tab in Đêm Đỏ mode: 3 Master slots (state.heroes[0..2], the team leader = the player) on top,
// 3 Guest slots (state.guestHeroes) below. Each side fights with its own account's hero stats
// (battle/hero/blood-team.js). The side headers show the fightCap at capture time (server
// teamSummary, serve.js); it is not recomputed after a swap. Joker (Loli's summon skin) shows as
// slot 4 of Loli's side. See docs/planning/blood_night_setup.md.
import { html } from "../ui.js";
import { BLOOD_SIDE, lineupHeroes } from "../profile-state.js";
import { hasSummonedJoker, JOKER_SUMMON } from "../../hero-lineup.js";
import { HeroCard } from "./heroes.js";

const SIDES = [
  { side: "master", title: "Master", name: "Pandora", group: "heroes" },
  { side: "guest", title: "Guest", name: "ĐạiKGà", group: "guestHeroes" },
];

const power = (n) => (n >= 1e6 ? `${(n / 1e6).toFixed(1)}M` : Number(n || 0).toLocaleString("vi-VN"));

function sideNote(member, name) {
  if (!member) return "không có roster trong capture";
  return `${name} · lực 3 hero lúc capture ${power(member.lineupFightCap)} · lực acc ${power(member.fightCap)}`;
}

export function BloodTeams({ ctx }) {
  const { state, baseBattle } = ctx;
  const lineup = lineupHeroes(state);
  const chosen = lineup.map((h) => h.name);
  const loli = lineup.find(({ name }) => name === JOKER_SUMMON.hero);
  const showJoker = hasSummonedJoker(lineup, loli?.custom && loli.slots.includes(JOKER_SUMMON.skin));
  const loliSide = loli && (state.heroes.slice(0, BLOOD_SIDE).includes(loli) ? "master" : "guest");
  const sides = SIDES.map(({ side, title, name, group }) => {
    const heroes = state[group].slice(0, BLOOD_SIDE);
    const member = baseBattle?.team?.find((m) => m.side === side);
    return html`
      <div class="subsection" key=${side}>
        <h3>${title} <span class="note">${sideNote(member, name)}</span></h3>
        ${heroes.map((hero, index) => html`
          <${HeroCard} key=${`${side}${index}`} ctx=${ctx} hero=${hero} index=${index} group=${group} chosen=${chosen} />`)}
        ${showJoker && loliSide === side && html`
          <${HeroCard} ctx=${ctx} hero=${state.summonedJoker} index=${BLOOD_SIDE} summoned=${true} />`}
      </div>
    `;
  });
  return html`
    ${sides}
    <div class="note">
      Mỗi hero đánh bằng chỉ số của acc sở hữu. Hero acc đó có (trong trận hoặc roster) giữ chỉ số gốc; hero acc
      đó không có mượn chỉ số trung bình các hero cùng độ hiếm của chính acc đó. Lực chiến là số lúc capture, không
      tính lại khi đổi hero.
    </div>
  `;
}
