// Setup page state <-> profile JSON (the format web/battle/profile.js reads).
// Optional sections left null keep that part of the capture; heroes always have five editable slots.
import * as R from "./skin-rules.js";
import { JOKER_SUMMON } from "../hero-lineup.js";
import { SUMMONER_SLOTS, summonerSkillsConflict } from "../summoner-skills.js";

const LIMITS = { heroes: 5, traps: 3, pets: 3, spells: 2, summonerSkins: SUMMONER_SLOTS };
const BUILDINGS = [["door", "Cửa"], ["bed", "Giường"], ["generator", "Chuột (máy phát điện)"], ["cat", "Mèo (chiêu tài)"]];

const heroSkins = (dict, name) => dict.heroes[name]?.skins || {};
const buildSkins = (dict, building) => dict.buildings[building].skins;

function emptyState() {
  return {
    battle: "", seed: "", map: null, heroes: Array.from({ length: LIMITS.heroes }, () => newHero("")),
    mounts: null, summonedJoker: newHero(JOKER_SUMMON.summonedHero), traps: null, pets: null, spells: null,
    buildings: Object.fromEntries(BUILDINGS.map(([key]) => [key, null])), goldenSkinsCount: null, summonerSkins: null,
  };
}

function newHero(name) {
  return { name, custom: false, worn: null, skins: {}, slots: [] };
}

function newBuilding(dict, building) {
  return { worn: R.defaultBuildSkin(buildSkins(dict, building)), skins: {}, slots: [] };
}

function normalize(state, dict) {
  state.heroes = Array.from({ length: LIMITS.heroes }, (_, i) => state.heroes?.[i] || newHero(""));
  if (state.mounts && !state.mounts.owned.includes(state.mounts.selected)) state.mounts.selected = null;
  if (state.heroes) for (const hero of state.heroes) R.normalizeHero(hero, heroSkins(dict, hero.name));
  state.summonedJoker ||= newHero(JOKER_SUMMON.summonedHero);
  R.normalizeHero(state.summonedJoker, heroSkins(dict, JOKER_SUMMON.summonedHero));
  for (const [building] of BUILDINGS) {
    if (state.buildings[building]) R.normalizeBuilding(state.buildings[building], buildSkins(dict, building));
  }
}

function toProfile(state, dict) {
  const profile = {};
  if (state.map) profile.map = { mode: "campaign", stage: state.map.stage };
  if (state.heroes) {
    const heroProfile = (hero) => {
      if (!hero.custom) return hero.name;
      const skins = heroSkins(dict, hero.name);
      const out = { name: hero.name };
      if (hero.worn) Object.assign(out, { skin: hero.worn, star: hero.skins[hero.worn].star });
      const owned = Object.keys(skins).filter((key) => key !== hero.worn && hero.skins[key]?.owned);
      if (owned.length) out.ownedSkins = Object.fromEntries(owned.map((key) => [key, hero.skins[key].star]));
      // Slot order: normal skins in config order, then the colorful one (skin-profile.js default order).
      out.slots = [
        ...hero.slots.filter((key) => R.isNormalHeroSkin(skins[key])),
        ...hero.slots.filter((key) => !R.isNormalHeroSkin(skins[key])),
      ];
      return out;
    };
    profile.heroes = state.heroes.filter((hero) => hero.name).map(heroProfile);
    if (state.summonedJoker?.custom) profile.summonedJoker = heroProfile(state.summonedJoker);
  }
  if (state.mounts) profile.mounts = structuredClone(state.mounts);
  if (state.traps) profile.traps = state.traps.map(({ name, level, star }) => ({ name, level, star }));
  if (state.pets) profile.pets = state.pets.map(({ name, level, star }) => ({ name, level, star }));
  if (state.spells) profile.spells = state.spells.map(({ name, star }) => ({ name, star }));
  if (state.summonerSkins) profile.summonerSkins = state.summonerSkins.map(({ name, star }) => ({ name, star }));
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
  return profile;
}

// Lenient import of a profile JSON (as written by toProfile or by hand). Unknown names throw.
function fromProfile(profile, base, dict) {
  const next = { ...emptyState(), battle: base.battle, seed: base.seed };
  const need = (group, name) => {
    if (!Object.hasOwn(dict[group], name)) throw new Error(`Không có ${group} "${name}" trong profile-dict.json`);
    return name;
  };
  const entryOf = (item) => (typeof item === "string" ? { name: item } : item || {});
  if (profile.map) next.map = { stage: Number(profile.map.stage) || dict.maps.campaign.minStage };
  const readHero = (item) => {
    const sel = entryOf(item);
    const hero = newHero(need("heroes", sel.name));
    const skins = heroSkins(dict, hero.name);
    hero.custom = ["skin", "star", "ownedSkins", "slots"].some((key) => sel[key] !== undefined);
    if (!hero.custom) return hero;
    const skinName = (key) => {
      if (!skins[key]) throw new Error(`Hero ${hero.name} không có skin "${key}"`);
      return key;
    };
    for (const [key, star] of Object.entries(sel.ownedSkins || {})) Object.assign(R.skinState(hero, skinName(key)), { owned: true, star });
    if (sel.skin !== undefined) {
      hero.worn = skinName(sel.skin);
      Object.assign(R.skinState(hero, hero.worn), { owned: true, star: sel.star ?? 1 });
    }
    R.normalizeHero(hero, skins); // raises required skins before default slots are picked
    hero.slots = sel.slots !== undefined ? sel.slots.map(skinName) : Object.keys(skins).filter((key) => hero.skins[key].owned);
    return hero;
  };
  if (Array.isArray(profile.heroes)) {
    next.heroes = profile.heroes.slice(0, LIMITS.heroes).map(readHero);
  }
  if (profile.mounts !== undefined) {
    const { owned, selected = null } = profile.mounts || {};
    if (!Array.isArray(owned) || new Set(owned).size !== owned.length) throw new Error("Mount sở hữu phải là danh sách không trùng");
    next.mounts = { owned: owned.map((name) => need("mounts", name)), selected };
    if (selected !== null && !owned.includes(selected)) throw new Error("Mount đang cưỡi phải được sở hữu");
  }
  if (profile.summonedJoker !== undefined) {
    if (entryOf(profile.summonedJoker).name !== JOKER_SUMMON.summonedHero) throw new Error("Slot 6 chỉ dành cho Joker triệu hồi");
    next.summonedJoker = readHero(profile.summonedJoker);
  }
  for (const group of ["traps", "pets"]) {
    if (Array.isArray(profile[group])) {
      next[group] = profile[group].slice(0, LIMITS[group]).map((item) => {
        const { name, level = 1, star = 1 } = entryOf(item);
        return { name: need(group, name), level, star };
      });
    }
  }
  if (Array.isArray(profile.spells)) {
    next.spells = profile.spells.slice(0, LIMITS.spells).map((item) => {
      const { name, star = 1 } = entryOf(item);
      return { name: need("spells", name), star };
    });
  }
  if (Array.isArray(profile.summonerSkins)) {
    if (profile.summonerSkins.length > SUMMONER_SLOTS) throw new Error(`Skill Summoner có tối đa ${SUMMONER_SLOTS} slot`);
    next.summonerSkins = [];
    for (const item of profile.summonerSkins) {
      const { name, star = 1 } = entryOf(item);
      const skin = dict.summonerSkins[need("summonerSkins", name)];
      if (!skin.skill || next.summonerSkins.some((entry) => summonerSkillsConflict(dict.summonerSkins[entry.name], skin))) {
        throw new Error(`Không thể gắn skill Summoner "${name}"`);
      }
      next.summonerSkins.push({ name, star: R.clamp(star, 1, skin.maxStar) });
    }
  }
  for (const [building, sel] of Object.entries(profile.buildings || {})) {
    if (!dict.buildings[building]) throw new Error(`Không có building "${building}"`);
    const skins = buildSkins(dict, building);
    const skinName = (key) => {
      if (!skins[key]) throw new Error(`Building ${building} không có skin "${key}"`);
      return key;
    };
    const entry = newBuilding(dict, building);
    for (const [key, star] of Object.entries(sel.ownedSkins || {})) Object.assign(R.skinState(entry, skinName(key)), { owned: true, star });
    if (sel.skin !== undefined) {
      entry.worn = skinName(sel.skin);
      Object.assign(R.skinState(entry, entry.worn), { owned: true, star: sel.star ?? 1 });
    }
    R.normalizeBuilding(entry, skins);
    entry.slots = sel.slots !== undefined ? sel.slots.map(skinName) : R.defaultBuildingSlots(entry, skins);
    next.buildings[building] = entry;
  }
  if (Number.isSafeInteger(profile.goldenSkinsCount)) next.goldenSkinsCount = profile.goldenSkinsCount;
  normalize(next, dict);
  return next;
}

export {
  LIMITS,
  BUILDINGS,
  heroSkins,
  buildSkins,
  emptyState,
  newHero,
  newBuilding,
  normalize,
  toProfile,
  fromProfile,
};
