// Local playtest profile (?play&profile): traps, pets, spells, mounts, Summoner skins, buildings and
// antiques from /__sim/active-profile.json, resolved by name through profile-dict.json and
// antique-dict.json (scripts/gen_profile_dict.js).
// Map: map-profile.js. Heroes: hero/ (selection.js, build.js, skin.js).
// Building skins: build-skin-profile.js.
import { battleAntiques } from "../antiques.js";
import { SUMMONER_SLOTS, isPassiveSummonerSkin, summonerSkillsConflict } from "../summoner-skills.js";
import { applyBuildSkins } from "./build-skin-profile.js";
import { applyHeroSelection } from "./hero/selection.js";
import { applyMapProfile } from "./map-profile.js";

// Rewrites start (StartGameP) in place. Returns what the page stubs need beyond StartGameP:
// { summonerDerma } = worn Summoner skin (read by stubs.js stubNetwork), 0 when unset.
export async function applyProfile(start, rb, M, step) {
  const read = async (name) => {
    const response = await fetch(`/__sim/${name}.json`);
    if (!response.ok) throw new Error(`Could not load ${name}: HTTP ${response.status}`);
    return response.json();
  };
  const [profile, catalog] = await Promise.all([read("active-profile"), read("dict/profile-dict")]);
  if (Object.hasOwn(profile, "map")) await applyMapProfile(start, profile.map || {}, rb, M, step);
  const player = { ...rb.listItems(start.playerInfos)[0] };
  let summonerDerma = 0;
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
    await applyHeroSelection({ profile, player, catalog, choices, asList, rb, M, step });
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
    const slotted = [];
    const picked = choices("summonerSkins", Object.keys(catalog.summonerSkins).length);
    // Skill-less event skins only add account stats (server side) and can be worn; they never go in
    // summonerInfos, which carries the skill slots only.
    const skills = picked.filter(({ option }) => !isPassiveSummonerSkin(option));
    if (skills.length > SUMMONER_SLOTS) throw new Error(`Profile summonerSkins has more than ${SUMMONER_SLOTS} skill slots`);
    const worn = profile.summonerWorn ?? null;
    if (worn !== null) {
      const entry = picked.find(({ selection }) => selection.name === worn);
      if (!entry || M("DermaLO").get(entry.option.code)?.dermatype !== 2) throw new Error(`Invalid summonerWorn: ${worn}`);
      // Worn skin = SummonerInfoP / base player info `derma` (model only); read by stubNetwork.
      summonerDerma = entry.option.code;
    }
    player.summonerInfos = asList(skills.map(({ option: { code }, selection: { star = 1 } }) => {
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
    Object.assign(player, applyBuildSkins(player, profile.buildings, catalog.buildings, rb, M, (resolved) => {
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
    const antiqueDict = await read("dict/antique-dict");
    player.antiques = asList(battleAntiques(profile.antiques, antiqueDict.antiques, M("AntiqueHaloLO")));
  }
  start.playerInfos = { ...start.playerInfos, 0: player };
  return { summonerDerma };
}

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
