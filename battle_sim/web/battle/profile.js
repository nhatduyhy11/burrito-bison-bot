// Local playtest profile (?play&profile): map, heroes and traps from /__sim/active-profile.json,
// resolved by name through profile-dict.json (scripts/gen_profile_dict.js). Hero skins: skin-profile.js.
(function () {
  "use strict";
  const SimBattle = (window.SimBattle = window.SimBattle || {});

  SimBattle.applyProfile = async function (start, rb, M, step) {
    const read = async (name) => {
      const response = await fetch(`/__sim/${name}.json`);
      if (!response.ok) throw new Error(`Could not load ${name}: HTTP ${response.status}`);
      return response.json();
    };
    const [profile, catalog] = await Promise.all([read("active-profile"), read("profile-dict")]);
    if (Object.hasOwn(profile, "map")) {
      const { mode, stage } = profile.map || {};
      if (mode !== "campaign") throw new Error(`Unsupported map mode: ${mode}`);
      const level = Number.isSafeInteger(stage) && stage > 0 && M("AdventuretdLevelLO").get(stage * 10);
      if (!level || !M("BattleGroundLO").get(level.battleGroundCode)) {
        throw new Error(`Unknown campaign stage: ${stage}`);
      }
      start.level = stage;
    }
    const player = { ...rb.listItems(start.playerInfos)[0] };
    const asList = (items) => ({ ...items, _length: items.length });
    const choices = (key, max) => {
      const names = profile[key];
      if (!Array.isArray(names) || names.length > max) {
        throw new Error(`Profile ${key} must be an array of up to ${max} distinct options`);
      }
      const seen = new Set();
      return names.map((entry) => {
        const selection = typeof entry === "string" ? { name: entry } : entry;
        const name = selection?.name;
        if (typeof name !== "string" || !Object.hasOwn(catalog[key], name)) {
          throw new Error(`Unknown ${key} option: ${name}`);
        }
        const option = catalog[key][name];
        if (seen.has(option.code)) throw new Error(`Duplicate ${key} option: ${name}`);
        seen.add(option.code);
        return { option, selection };
      });
    };
    if (Object.hasOwn(profile, "heroes")) {
      const captured = rb.listItems(player.heros);
      const heroes = choices("heroes", 5).map(({ option, selection }) => {
        const { code, baseSkills, skins } = option;
        const config = M("HeroLO").get(code);
        if (!config) throw new Error(`Unknown hero code: ${code}`);
        const hero = captured.find((entry) => entry.code === code)
          || makeBaseHero(code, config, baseSkills, M);
        if (["skin", "star", "ownedSkins", "slots"].some((key) => selection[key] !== undefined)) {
          return window.applySimSkinProfile(hero, selection, skins, rb, M, (resolved) => {
            step("profile skin ranks", resolved);
          });
        }
        return hero;
      });
      if (!heroes.length) throw new Error("Profile needs at least one hero");
      player.heros = asList(heroes);
    }
    if (Object.hasOwn(profile, "traps")) {
      // A trap is a name (level 1, 1 star) or { name, level, star }.
      const traps = choices("traps", 3).map(({ option: { code }, selection: { level = 1, star = 1 } }) => {
        const rank = M("OrganStarLO").get(code * 10000000 + star * 1000);
        const upgrade = M("OrganUpGradeLO").get(code * 10000 + level);
        if (!rank || !upgrade) throw new Error(`Invalid trap ${code} level ${level} / star ${star}`);
        return { code, level, star, skillCode: rank.skillCode };
      });
      player.organs = asList(traps);
    }
    start.playerInfos = { ...start.playerInfos, 0: player };
  };

  function makeBaseHero(code, config, baseSkills, M) {
    if (!Array.isArray(baseSkills) || !baseSkills.length || baseSkills.some((id) => !M("SkillBaseLO").get(id))) {
      throw new Error(`Hero ${code} needs valid baseSkills in the profile dictionary`);
    }
    const attrs = JSON.parse(config.baseAttr);
    return {
      code, uuid: String(code).padStart(24, "0"), level: 1, derma: 0,
      attr: {
        _keyList: attrs.map(([key]) => key),
        _valueList: attrs.map(([, value]) => value),
      },
      skills: baseSkills.map((id, i) => ({ code: id, index: i + 1, isShow: i > 0 })),
    };
  }
})();
