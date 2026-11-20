// Local playtest profile, hero lineup (?play&profile): the 5 picked heroes (player.heros) and,
// when Joker summons him, the Joker support hero. A picked hero keeps its captured entry when the
// capture has it, else gets borrowed stats (build.js); skins go through skin.js.
// Đêm Đỏ (map mode "blood") has a 3 + 3 team lineup instead: blood-team.js.
import { hasSummonedJoker, JOKER_SUMMON } from "../../hero-lineup.js";
import { buildProfileHero } from "./build.js";
import { applyArtifact, warnMissingStamps } from "./artifact.js";
import { applyAvatar } from "./avatar.js";
import { applyRelic } from "./relic.js";
import { applySkin } from "./skin.js";
import { applyBloodTeam } from "./blood-team.js";

const LINEUP = 5;

// One hero object from a { option, selection } pick. `owned` = hero objects to take as they are
// (matched by code), `donors` = heroes to borrow stats from when `owned` has none. `jokerSlots`
// records whether Loli's skin slots hold the Joker-summon skin.
export function heroBuilder({ relicLines, rb, M, step }) {
  const state = { jokerSkillSlotted: false };
  const build = ({ option, selection }, { owned, donors }, existing) => {
    const { code, baseSkills, skins, avatarNodes } = option;
    const config = M("HeroLO").get(code);
    if (!config) throw new Error(`Unknown hero code: ${code}`);
    let hero = existing || owned.find((entry) => entry.code === code)
      || buildProfileHero(code, config, baseSkills, donors, rb, M, step);
    if (selection.avatar !== undefined) hero = applyAvatar(hero, avatarNodes, selection.avatar, rb, step);
    if (["skin", "star", "ownedSkins", "slots"].some((key) => selection[key] !== undefined)) {
      hero = applySkin(hero, selection, skins, rb, M, (resolved) => {
        if (selection.name === JOKER_SUMMON.hero) {
          const summonSkin = skins[JOKER_SUMMON.skin];
          state.jokerSkillSlotted = resolved.slots.some(({ code }) => code === summonSkin?.code);
        }
        step("profile skin ranks", resolved);
      });
    }
    if (selection.relic !== undefined) hero = applyRelic(hero, selection.relic, relicLines, rb, M, step);
    if (selection.artifact !== undefined) hero = applyArtifact(hero, selection.artifact, rb, M, step);
    warnMissingStamps(hero, rb);
    return hero;
  };
  return { build, state };
}

// profile.summonedJoker (or plain Joker) as a { option, selection } pick.
export function jokerPick(profile, catalog) {
  const name = JOKER_SUMMON.summonedHero;
  const entry = profile.summonedJoker ?? { name };
  const selection = typeof entry === "string" ? { name: entry } : entry;
  if (selection.name !== name) throw new Error("Summoned hero must be Joker");
  return { option: catalog.heroes[name], selection };
}

// choices(key, max) = profile.js's name -> catalog option check; returns [{ option, selection }].
export async function applyHeroSelection({ profile, player, catalog, relicLines, choices, asList, rb, M, step, start, team }) {
  if (profile.map?.mode === "blood") {
    return applyBloodTeam({ profile, player, catalog, relicLines, asList, rb, M, step, start, team });
  }
  const captured = rb.listItems(player.heros);
  const selected = choices("heroes", LINEUP);
  if (selected.length !== LINEUP) throw new Error(`Profile needs exactly ${LINEUP} heroes`);
  const { build, state } = heroBuilder({ relicLines, rb, M, step });
  const source = { owned: captured, donors: captured };
  const heroes = selected.map((entry) => build(entry, source));
  if (hasSummonedJoker(selected.map(({ selection }) => selection), state.jokerSkillSlotted)) {
    const joker = jokerPick(profile, catalog);
    const existing = player.support?.code === joker.option.code ? player.support : undefined;
    // The engine deploys support with Loli and mirrors her in-battle upgrades.
    player.support = build(joker, source, existing);
  }
  player.heros = asList(heroes);
}
