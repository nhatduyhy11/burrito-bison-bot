// Local playtest profile (?play&profile): map, heroes, traps, pets, spells and building skins from
// /__sim/active-profile.json, resolved by name through profile-dict.json (scripts/gen_profile_dict.js).
// Hero skins: skin-profile.js. Building skins: build-skin-profile.js.
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
    if (Object.hasOwn(profile, "pets")) {
      // A pet is a name (level 1, 1 star) or { name, level, star }.
      const pets = choices("pets", 3).map(({ option: { code }, selection: { level = 1, star = 1 } }) => {
        const config = M("SummonCreatureLO").get(code);
        const mec = config?.mecType;
        if (!config || !M("SummonCreatureStarLO").get(mec * 10000 + star * 100)
          || !M("SummonCreatureUpGradeLO").get(mec * 1000 + level)) {
          throw new Error(`Invalid pet ${code} level ${level} / star ${star}`);
        }
        return { code, star, level, skillCodes: asList(petSkillCodes(config, star, M)) };
      });
      player.summonCreatures = asList(pets);
    }
    if (Object.hasOwn(profile, "spells")) {
      // A spell (daoist) is a name (1 star) or { name, star }; 2 formation slots (DaoistFormationLO).
      const spells = choices("spells", 2).map(({ option: { code }, selection: { star = 1 } }) => {
        const mec = M("DaoistLO").get(code)?.mecType;
        const rank = mec && M("DaoistStarLO").get(mec * 10000000 + star * 1000);
        if (!rank) throw new Error(`Invalid spell ${code} star ${star}`);
        return { code, star, skillCode: rank.skillCode };
      });
      player.daoists = asList(spells);
    }
    if (Object.hasOwn(profile, "buildings")) {
      Object.assign(player, window.applySimBuildSkinProfile(player, profile.buildings, catalog.buildings, rb, M, (resolved) => {
        step("profile building skins", resolved);
      }));
    }
    if (Object.hasOwn(profile, "goldenSkinsCount")) {
      // Server-computed (pet damage bonus); source unconfirmed, so it is set by hand. See BUILD_SKINS.md.
      const count = profile.goldenSkinsCount;
      if (!Number.isSafeInteger(count) || count < 0) throw new Error("goldenSkinsCount must be a non-negative integer");
      player.goldenSkinsCount = count;
    }
    start.playerInfos = { ...start.playerInfos, 0: player };
  };

  // SummonCreatureLO.skill lists skill types; each type contributes its highest level whose
  // starRequire the pet's star meets (SummonCreatureSkillLO code = type * 100 + level).
  function petSkillCodes(config, star, M) {
    const table = M("SummonCreatureSkillLO");
    const codes = [];
    for (const type of JSON.parse(config.skill || "[]")) {
      let best = 0;
      for (let level = 1, row; (row = table.get(type * 100 + level)); level++) {
        if (row.starRequire <= star) best = row.code;
      }
      if (best) codes.push(best);
    }
    return codes;
  }

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
