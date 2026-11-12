// Local playtest profile, hero lineup (?play&profile): the 5 picked heroes (player.heros) and,
// when Joker summons him, the Joker support hero. A picked hero keeps its captured entry when the
// capture has it, else gets borrowed stats (build.js); skins go through skin.js.
(function () {
  "use strict";
  const SimBattle = (window.SimBattle = window.SimBattle || {});
  const LINEUP = 5;

  // choices(key, max) = profile.js's name -> catalog option check; returns [{ option, selection }].
  SimBattle.applyHeroSelection = async function ({ profile, player, catalog, choices, asList, rb, M, step }) {
    const { hasSummonedJoker, JOKER_SUMMON } = await import("../../hero-lineup.js");
    const captured = rb.listItems(player.heros);
    const selected = choices("heroes", LINEUP);
    if (selected.length !== LINEUP) throw new Error(`Profile needs exactly ${LINEUP} heroes`);
    let jokerSkillSlotted = false;
    const buildHero = ({ option, selection }, existing) => {
      const { code, baseSkills, skins } = option;
      const config = M("HeroLO").get(code);
      if (!config) throw new Error(`Unknown hero code: ${code}`);
      const hero = existing || captured.find((entry) => entry.code === code)
        || SimBattle.buildProfileHero(code, config, baseSkills, captured, rb, M, step);
      if (["skin", "star", "ownedSkins", "slots"].some((key) => selection[key] !== undefined)) {
        return window.applySimSkinProfile(hero, selection, skins, rb, M, (resolved) => {
          if (selection.name === JOKER_SUMMON.hero) {
            const summonSkin = skins[JOKER_SUMMON.skin];
            jokerSkillSlotted = resolved.slots.some(({ code }) => code === summonSkin?.code);
          }
          step("profile skin ranks", resolved);
        });
      }
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
  };
})();
