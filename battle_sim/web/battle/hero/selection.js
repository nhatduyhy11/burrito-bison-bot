// Local playtest profile, hero lineup (?play&profile): the 5 picked heroes (player.heros) and,
// when Joker summons him, the Joker support hero. A picked hero keeps its captured entry when the
// capture has it, else gets borrowed stats (build.js); skins go through skin.js.
import { hasSummonedJoker, JOKER_SUMMON } from "../../hero-lineup.js";
import { buildProfileHero } from "./build.js";
import { applyArtifact } from "./artifact.js";
import { applyAvatar } from "./avatar.js";
import { applyRelic } from "./relic.js";
import { applySkin } from "./skin.js";

const LINEUP = 5;

// choices(key, max) = profile.js's name -> catalog option check; returns [{ option, selection }].
export async function applyHeroSelection({ profile, player, catalog, relicLines, choices, asList, rb, M, step }) {
  const captured = rb.listItems(player.heros);
  const selected = choices("heroes", LINEUP);
  if (selected.length !== LINEUP) throw new Error(`Profile needs exactly ${LINEUP} heroes`);
  let jokerSkillSlotted = false;
  const buildHero = ({ option, selection }, existing) => {
    const { code, baseSkills, skins, avatarNodes } = option;
    const config = M("HeroLO").get(code);
    if (!config) throw new Error(`Unknown hero code: ${code}`);
    let hero = existing || captured.find((entry) => entry.code === code)
      || buildProfileHero(code, config, baseSkills, captured, rb, M, step);
    if (selection.avatar !== undefined) hero = applyAvatar(hero, avatarNodes, selection.avatar, rb, step);
    if (["skin", "star", "ownedSkins", "slots"].some((key) => selection[key] !== undefined)) {
      hero = applySkin(hero, selection, skins, rb, M, (resolved) => {
        if (selection.name === JOKER_SUMMON.hero) {
          const summonSkin = skins[JOKER_SUMMON.skin];
          jokerSkillSlotted = resolved.slots.some(({ code }) => code === summonSkin?.code);
        }
        step("profile skin ranks", resolved);
      });
    }
    if (selection.relic !== undefined) hero = applyRelic(hero, selection.relic, relicLines, rb, M, step);
    if (selection.artifact !== undefined) hero = applyArtifact(hero, selection.artifact, M, step);
    return hero;
  };
  const heroes = selected.map((entry) => buildHero(entry));
  if (hasSummonedJoker(selected.map(({ selection }) => selection), jokerSkillSlotted)) {
    const name = JOKER_SUMMON.summonedHero;
    const entry = profile.summonedJoker ?? { name };
    const selection = typeof entry === "string" ? { name: entry } : entry;
    if (selection.name !== name) throw new Error("Summoned hero must be Joker");
    const option = catalog.heroes[name];
    const existing = player.support?.code === option.code ? player.support : undefined;
    // The engine deploys support with Loli and mirrors her in-battle upgrades.
    player.support = buildHero({ option, selection }, existing);
  }
  player.heros = asList(heroes);
}
