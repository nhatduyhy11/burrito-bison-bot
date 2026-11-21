// Setup page state -> profile JSON (the format web/battle/profile.js reads).
import * as R from "./skin-rules.js";
import { hasSummonedJoker, JOKER_SUMMON } from "../hero-lineup.js";
import { BLOOD_SIDE, BUILDINGS, heroSkins, buildSkins, isBlood, lineupHeroes } from "./profile-state.js";

export function toProfile(state, dict) {
  const profile = {};
  if (["capital", "naval"].includes(state.map?.mode)) profile.map = { mode: state.map.mode, boss: state.map.boss, level: state.map.level };
  else if (isBlood(state)) profile.map = { mode: "blood", level: state.map.level };
  else if (state.map) profile.map = { mode: "campaign", stage: state.map.stage };
  if (state.heroes) {
    const heroProfile = (hero) => {
      if (!hero.custom) return hero.name;
      const out = { name: hero.name };
      if (hero.relic !== undefined) out.relic = hero.relic;
      if (hero.beautyBag !== undefined) out.beautyBag = hero.beautyBag;
      if (hero.artifact !== undefined) out.artifact = artifactProfile(hero.artifact);
      if (hero.skinOverride === false) return out;
      const skins = heroSkins(dict, hero.name);
      if (hero.avatar !== null && dict.heroes[hero.name].avatarNodes) out.avatar = hero.avatar;
      if (!Object.keys(skins).length) return out;
      if (hero.worn) Object.assign(out, { skin: hero.worn, star: hero.skins[hero.worn].star });
      const owned = Object.keys(skins).filter((key) => key !== hero.worn && hero.skins[key]?.owned);
      if (owned.length) out.ownedSkins = Object.fromEntries(owned.map((key) => [key, hero.skins[key].star]));
      // Slot order: normal skins in config order, then the colorful one (battle/hero/skin.js default order).
      out.slots = [
        ...hero.slots.filter((key) => R.isNormalHeroSkin(skins[key])),
        ...hero.slots.filter((key) => !R.isNormalHeroSkin(skins[key])),
      ];
      return out;
    };
    const lineup = lineupHeroes(state);
    if (isBlood(state)) {
      profile.heroes = state.heroes.slice(0, BLOOD_SIDE).filter((hero) => hero.name).map(heroProfile);
      profile.guestHeroes = state.guestHeroes.filter((hero) => hero.name).map(heroProfile);
    } else profile.heroes = state.heroes.filter((hero) => hero.name).map(heroProfile);
    const loli = lineup.find(({ name }) => name === JOKER_SUMMON.hero);
    if (state.summonedJoker && (state.summonedJoker.custom || state.summonedJoker.relic
      || hasSummonedJoker(lineup, loli?.custom && loli.slots.includes(JOKER_SUMMON.skin)))) {
      profile.summonedJoker = heroProfile(state.summonedJoker);
    }
  }
  if (state.mounts) profile.mounts = structuredClone(state.mounts);
  // Reserved slots keep null placeholders in the state; the profile stays compact — the engine reads
  // every emitted entry head-on (web/battle/profile.js), so empty slots must not be emitted.
  if (state.traps) profile.traps = state.traps.filter(Boolean).map(({ name, level, star }) => ({ name, level, star }));
  if (state.pets) profile.pets = state.pets.filter(Boolean).map(({ name, level, star }) => ({ name, level, star }));
  if (state.spells) profile.spells = state.spells.filter(Boolean).map(({ name, star }) => ({ name, star }));
  if (state.summonerSkins) {
    profile.summonerSkins = state.summonerSkins.map(({ name, star }) => ({ name, star }));
    profile.summonerWorn = state.summonerWorn;
  }
  // Gear skills: true/false per known name; names left out keep the capture (null state = untouched).
  if (state.summonerGear) {
    const gear = Object.fromEntries(Object.keys(dict.summonerGear)
      .filter((key) => state.summonerGear[key] !== undefined)
      .map((key) => [key, !!state.summonerGear[key]]));
    if (Object.keys(gear).length) profile.summonerGear = gear;
  }
  const buildings = {};
  for (const [building] of BUILDINGS) {
    const entry = state.buildings[building];
    if (!entry) continue;
    const skins = buildSkins(dict, building);
    const base = R.defaultBuildSkin(skins);
    const out = {};
    if (entry.worn !== base) Object.assign(out, { skin: entry.worn, star: entry.skins[entry.worn].star });
    const owned = Object.keys(skins).filter((key) => key !== base && key !== entry.worn && entry.skins[key]?.owned);
    if (owned.length) out.ownedSkins = Object.fromEntries(owned.map((key) => [key, entry.skins[key].star]));
    out.slots = ["red", "gold", "special"].flatMap((slot) => entry.slots.filter((key) => skins[key].slot === slot));
    buildings[building] = out;
  }
  if (Object.keys(buildings).length) profile.buildings = buildings;
  if (state.goldenSkinsCount !== null) profile.goldenSkinsCount = state.goldenSkinsCount;
  profile.antiques = { ...state.antiques };
  return profile;
}

function artifactProfile(artifact) {
  if (artifact === null) return null;
  const { quality, stage, slots } = artifact;
  return { quality, stage, entries: slots.filter(Boolean).map(({ code, value }) => ({ code, value })) };
}
