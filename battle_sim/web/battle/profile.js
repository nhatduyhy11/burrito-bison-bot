// Local playtest profile (?play&profile): map, heroes, traps, pets, spells and skins from
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
      const { hasSummonedJoker, JOKER_SUMMON } = await import("../hero-lineup.js");
      const captured = rb.listItems(player.heros);
      const selected = choices("heroes", 5);
      if (selected.length !== 5) throw new Error("Profile needs exactly 5 heroes");
      let jokerSkillSlotted = false;
      const buildHero = ({ option, selection }, existing) => {
        const { code, baseSkills, skins } = option;
        const config = M("HeroLO").get(code);
        if (!config) throw new Error(`Unknown hero code: ${code}`);
        const hero = existing || captured.find((entry) => entry.code === code)
          || borrowStats(makeBaseHero(code, config, baseSkills, M), config, captured, rb, M, step);
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
    }
    if (Object.hasOwn(profile, "mounts")) {
      const mounts = catalog.mounts;
      const { owned, selected = null } = profile.mounts || {};
      if (!Array.isArray(owned) || new Set(owned).size !== owned.length) throw new Error("Invalid owned mounts");
      if (selected !== null && !owned.includes(selected)) throw new Error("Selected mount must be owned");
      const captured = rb.listItems(player.mounts);
      player.mounts = asList(owned.map((name) => {
        const mount = mounts[name];
        const config = mount && M("MountLO").get(mount.code);
        const rank = mount?.ranks[0];
        if (!config || !rank || (rank.showSkill && !M("SkillBaseLO").get(rank.showSkill.code))) {
          throw new Error(`Unknown mount: ${name}`);
        }
        return captured.find((entry) => entry.code === mount.code) || { code: mount.code, skillCode: rank.showSkill?.code || 0 };
      }));
      player.mountCode = selected === null ? 0 : mounts[selected].code;
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
    if (Object.hasOwn(profile, "summonerSkins")) {
      const { SUMMONER_SLOTS, summonerSkillsConflict } = await import("../summoner-skills.js");
      const slotted = [];
      player.summonerInfos = asList(choices("summonerSkins", SUMMONER_SLOTS).map(({ option: { code }, selection: { star = 1 } }) => {
        const skin = M("DermaLO").get(code);
        const rank = Number.isSafeInteger(star) && star > 0 && M("DermaStarLO").get(code * 100 + star);
        if (skin?.dermatype !== 2 || !skin.skills?.length || !JSON.parse(rank?.skill || "[]").length) {
          throw new Error(`Invalid Summoner skin skill ${code} at star ${star}`);
        }
        const entry = { code, excludes: skin.exclusion };
        if (slotted.some((other) => summonerSkillsConflict(other, entry))) {
          throw new Error(`Conflicting Summoner skin skill ${code}`);
        }
        slotted.push(entry);
        return { code, level: star };
      }));
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
    if (Object.hasOwn(profile, "antiques")) {
      const { battleAntiques } = await import("../antiques.js");
      player.antiques = asList(battleAntiques(profile.antiques, catalog.antiques, M("AntiqueHaloLO")));
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

  // A hero outside the capture would otherwise fight at level 1 with HeroLO.baseAttr, far below the
  // account: attr is computed by the server, mostly from account-wide sources (antiques, training,
  // ...). Captured heroes at the same level end up with nearly equal attr whatever their baseAttr
  // (pmain lv 90: attack 425k-442k), so the hero's own base hardly matters.
  // Approximation from the captured heroes of the same rarity (all of them if none): attr = their
  // mean without skin selfAttr; level / breakThrough = the median hero's; own-skill slots
  // (10<NN>0<slot><LL>000) kept when most of them have the slot, at their most common level.
  // Relic / artifact skills are per-hero equipment and are not copied.
  function borrowStats(hero, config, captured, rb, M, step) {
    const heroes = M("HeroLO");
    const sameRarity = captured.filter((h) => heroes.get(h.code)?.color === config.color);
    const donors = sameRarity.length ? sameRarity : captured;
    if (!donors.length) return hero;

    const sums = new Map();
    for (const donor of donors) {
      for (const [k, v] of withoutSkinAttrs(donor, rb, M)) sums.set(k, (sums.get(k) || 0) + v);
    }
    const attrs = new Map([...sums].map(([k, v]) => [k, Math.round(v / donors.length)]));

    const byLevel = donors.slice().sort((a, b) => (a.level || 0) - (b.level || 0) || (a.breakThrough || 0) - (b.breakThrough || 0));
    const median = byLevel[Math.floor((byLevel.length - 1) / 2)];

    const OWN = /^10(\d\d)0(\d)(\d\d)000$/;
    const levels = new Map(); // slot -> Map(level -> donors)
    for (const donor of donors) {
      for (const { code } of rb.listItems(donor.skills)) {
        const m = OWN.exec(String(code));
        if (!m) continue;
        const counts = levels.get(Number(m[2])) || new Map();
        counts.set(m[3], (counts.get(m[3]) || 0) + 1);
        levels.set(Number(m[2]), counts);
      }
    }
    const nn = String(hero.code % 1000).padStart(2, "0");
    const slots = new Map(rb.listItems(hero.skills).map((s) => [Number(OWN.exec(String(s.code))[2]), s.code]));
    for (const [slot, counts] of levels) {
      const have = [...counts.values()].reduce((a, b) => a + b, 0);
      if (!slots.has(slot) && have * 2 <= donors.length) continue; // extra slot only if most donors have it
      const level = [...counts].sort((a, b) => b[1] - a[1] || b[0] - a[0])[0][0];
      const code = Number(`10${nn}0${slot}${level}000`);
      if (M("SkillBaseLO").get(code)) slots.set(slot, code);
    }
    const skills = [...slots.keys()].sort((a, b) => a - b)
      .map((slot, i) => ({ code: slots.get(slot), index: i + 1, isShow: i > 0 }));
    step("profile borrowed stats", {
      heroCode: hero.code, from: donors.map((h) => h.code), level: median.level, breakThrough: median.breakThrough,
      skills: skills.map((s) => s.code),
    });
    return {
      ...hero, level: median.level, breakThrough: median.breakThrough, fightCap: median.fightCap,
      attr: { _keyList: [...attrs.keys()], _valueList: [...attrs.values()] },
      skills,
    };
  }

  // A captured hero's attr minus the selfAttr of the skins whose skills it carries.
  function withoutSkinAttrs(hero, rb, M) {
    const attrs = new Map(rb.listItems(hero.attr._keyList).map((key, i) => [Number(key), hero.attr._valueList[i]]));
    const skills = new Set(rb.listItems(hero.skills).map((s) => s.code));
    const ranks = M("DermaStarLO");
    for (const key of Object.keys(ranks.store)) {
      if (!/^\d+$/.test(key)) continue;
      const r = ranks.get(Number(key));
      if (r.heroCode !== hero.code || !JSON.parse(r.skill || "[]").some((id) => skills.has(id))) continue;
      for (const [k, v] of JSON.parse(r.selfAttr || "[]")) if (attrs.has(k)) attrs.set(k, attrs.get(k) - v);
    }
    return attrs;
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
