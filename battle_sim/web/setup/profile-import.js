// Profile JSON -> setup page state (lenient import; unknown names throw).
import * as R from "./skin-rules.js";
import { JOKER_SUMMON } from "../hero-lineup.js";
import { SUMMONER_SLOTS, isPassiveSummonerSkin, slottedSkillCount, summonerSkillsConflict } from "../summoner-skills.js";
import { antiqueSelections } from "../antiques.js";
import { resolveRelic } from "../relics.js";
import {
  LIMITS, BLOOD_SIDE, buildSkins, heroSkins, emptyState, newHero, newBuilding, normalize, artifactState,
} from "./profile-state.js";

// Lenient import of a profile JSON (as written by toProfile or by hand). Unknown names throw.
// catalogs: { maps (map-dict.json), bossDict (boss-dict.json), antiqueDict (antique-dict.json) },
// each needed only when the profile has that part.
export function fromProfile(profile, base, dict, { maps, bossDict, bloodDict, antiqueDict, relicLines } = {}) {
  const next = { ...emptyState(dict, antiqueDict), battle: base.battle, seed: base.seed };
  const need = (group, name) => {
    if (!Object.hasOwn(dict[group], name)) throw new Error(`Không có ${group} "${name}" trong hero-dict.json / support-dict.json`);
    return name;
  };
  const entryOf = (item) => (typeof item === "string" ? { name: item } : item || {});
  if (profile.map) next.map = readMap(profile.map, { maps, bossDict, bloodDict });
  const readHero = (item) => {
    const sel = entryOf(item);
    const hero = newHero(need("heroes", sel.name));
    hero.relic = sel.relic;
    if (sel.artifact !== undefined) hero.artifact = artifactState(sel.artifact);
    if (sel.relic != null) {
      const { name, star, purification } = resolveRelic(sel.relic, relicLines);
      hero.relic = { name, star, purification };
    }
    const skins = heroSkins(dict, hero.name);
    hero.custom = ["skin", "star", "ownedSkins", "slots", "avatar"].some((key) => sel[key] !== undefined);
    if (!hero.custom) return hero;
    if (sel.avatar !== undefined) {
      const nodes = dict.heroes[hero.name].avatarNodes || [];
      if (!Number.isInteger(sel.avatar) || sel.avatar < 0 || sel.avatar > nodes.length) {
        throw new Error(`Hero ${hero.name}: Dị Năng phải là số node 0-${nodes.length}`);
      }
      hero.avatar = sel.avatar;
    }
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
  if (Array.isArray(profile.guestHeroes)) next.guestHeroes = profile.guestHeroes.slice(0, BLOOD_SIDE).map(readHero);
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
    next.summonerSkins = [];
    for (const item of profile.summonerSkins) {
      const { name, star = 1 } = entryOf(item);
      const skin = dict.summonerSkins[need("summonerSkins", name)];
      const taken = next.summonerSkins.map((entry) => dict.summonerSkins[entry.name]);
      const ok = isPassiveSummonerSkin(skin)
        ? !taken.includes(skin)
        : skin.skill && !taken.some((other) => other.skill && summonerSkillsConflict(other, skin));
      if (!ok) throw new Error(`Không thể gắn skill Summoner "${name}"`);
      next.summonerSkins.push({ name, star: R.clamp(star, 1, skin.maxStar) });
    }
    if (slottedSkillCount(next.summonerSkins, dict.summonerSkins) > SUMMONER_SLOTS) {
      throw new Error(`Skill Summoner có tối đa ${SUMMONER_SLOTS} slot`);
    }
    const worn = profile.summonerWorn ?? null;
    if (worn !== null && !next.summonerSkins.some(({ name }) => name === worn)) {
      throw new Error("Skin Summoner đang mặc phải nằm trong các skin đã chọn");
    }
    next.summonerWorn = worn;
  }
  if (profile.summonerGear && typeof profile.summonerGear === "object") {
    next.summonerGear = {};
    for (const [name, on] of Object.entries(profile.summonerGear)) {
      next.summonerGear[need("summonerGear", name)] = !!on;
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
  if (Object.hasOwn(profile, "antiques")) {
    if (!antiqueDict) throw new Error("Thiếu antique-dict.json");
    next.antiques = Object.fromEntries(antiqueSelections(profile.antiques, antiqueDict.antiques).map(({ name, star }) => [name, star]));
  }
  normalize(next, dict);
  return next;
}

function readMap(map, { maps, bossDict, bloodDict }) {
  if (!maps) throw new Error("Thiếu map-dict.json");
  const stage = Number(map.stage) || maps.campaign.minStage;
  if (map.mode === "blood") {
    if (!bloodDict) throw new Error("Thiếu blood-dict.json");
    if (!bloodDict.levels[map.level]) throw new Error(`Không có ải Đêm Đỏ ${map.level} trong blood-dict.json`);
    return { mode: "blood", stage, boss: null, level: map.level };
  }
  if (map.mode !== "capital") return { mode: "campaign", stage, boss: null, level: null };
  if (map.boss == null) return { mode: "capital", stage, boss: null, level: null };
  if (!bossDict) throw new Error("Thiếu boss-dict.json");
  const entry = bossDict.bosses[map.boss];
  if (!entry) throw new Error(`Không có boss U Đô "${map.boss}" trong boss-dict.json`);
  const level = entry.presets.some((p) => p.level === map.level) ? map.level : null;
  return { mode: "capital", stage, boss: map.boss, level };
}
