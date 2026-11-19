// Setup page state shape: slot limits, empty-state factories and normalize (pads fixed slots,
// drops selections that no longer hold). Serialization lives in profile-export.js / profile-import.js.
// Optional sections left null keep that part of the capture; heroes always have five editable slots.
import * as R from "./skin-rules.js";
import { JOKER_SUMMON } from "../hero-lineup.js";
import { SUMMONER_SLOTS } from "../summoner-skills.js";
import { defaultAntiques } from "../antiques.js";
import { MAX_STAGE, holeNum } from "../artifacts.js";

const LIMITS = { heroes: 5, traps: 3, pets: 3, spells: 2, summonerSkins: SUMMONER_SLOTS };
// Đêm Đỏ (map mode "blood"): Teams shows heroes[0..2] as Master and guestHeroes as Guest
// (docs/planning/blood_night_setup.md); heroes[3..4] stay in the state but are not exported.
const BLOOD_SIDE = 3;
const isBlood = (state) => state.map?.mode === "blood";
const lineupHeroes = (state) => (isBlood(state) ? [...state.heroes.slice(0, BLOOD_SIDE), ...state.guestHeroes] : state.heroes);
const BUILDINGS = [["door", "Cửa"], ["bed", "Giường"], ["generator", "Chuột (máy phát điện)"], ["cat", "Mèo (chiêu tài)"]];

const heroSkins = (dict, name) => dict.heroes[name]?.skins || {};
const buildSkins = (dict, building) => dict.buildings[building].skins;

// antiqueDict = antique-dict.json; without it the antique section starts empty.
function emptyState(dict, antiqueDict) {
  return {
    battle: "", seed: "", map: null, heroes: Array.from({ length: LIMITS.heroes }, () => newHero("")),
    guestHeroes: Array.from({ length: BLOOD_SIDE }, () => newHero("")),
    mounts: null, summonedJoker: newHero(JOKER_SUMMON.summonedHero), traps: null, pets: null, spells: null,
    buildings: Object.fromEntries(BUILDINGS.map(([key]) => [key, null])), goldenSkinsCount: null, summonerSkins: null,
    summonerWorn: null, summonerGear: null,
    antiques: antiqueDict ? defaultAntiques(antiqueDict.antiques) : {},
  };
}

function newHero(name) {
  // avatar: number of open Dị Năng skill nodes (red heroes, set when custom), null = as captured / borrowed.
  return { name, custom: false, worn: null, skins: {}, slots: [], avatar: null, relic: null };
}

function newBuilding(dict, building) {
  return { worn: R.defaultBuildSkin(buildSkins(dict, building)), skins: {}, slots: [] };
}

function normalize(state, dict) {
  state.heroes = Array.from({ length: LIMITS.heroes }, (_, i) => state.heroes?.[i] || newHero(""));
  state.guestHeroes = Array.from({ length: BLOOD_SIDE }, (_, i) => state.guestHeroes?.[i] || newHero(""));
  // Trap / Pet / Spell reserve fixed slots: the state pads with null placeholders; null stays null
  // so "tắt = giữ từ capture" still works.
  for (const group of ["traps", "pets", "spells"]) {
    if (state[group]) state[group] = Array.from({ length: LIMITS[group] }, (_, i) => state[group][i] || null);
  }
  if (state.mounts && !state.mounts.owned.includes(state.mounts.selected)) state.mounts.selected = null;
  // The worn Summoner skin is picked among the skins checked in the Summoner table.
  if (!state.summonerSkins?.some(({ name }) => name === state.summonerWorn)) state.summonerWorn = null;
  for (const hero of [...state.heroes, ...state.guestHeroes, state.summonedJoker].filter(Boolean)) {
    // "Tùy chỉnh" customizes everything: a red hero's Dị Năng defaults to 0; untouched = as captured.
    if (!hero.custom || !dict.heroes[hero.name]?.avatarNodes) hero.avatar = null;
    else hero.avatar ??= 0;
  }
  for (const hero of [...state.heroes, ...state.guestHeroes]) R.normalizeHero(hero, heroSkins(dict, hero.name));
  for (const hero of [...state.heroes, ...state.guestHeroes]) normalizeArtifact(hero.artifact);
  state.summonedJoker ||= newHero(JOKER_SUMMON.summonedHero);
  R.normalizeHero(state.summonedJoker, heroSkins(dict, JOKER_SUMMON.summonedHero));
  for (const [building] of BUILDINGS) {
    if (state.buildings[building]) R.normalizeBuilding(state.buildings[building], buildSkins(dict, building));
  }
}

// Thần Khí (hero card in Teams, artifact.js). State: undefined = as captured, null = none,
// { quality, stage, slots } with one slot per rolled hole (holeNum), each null (empty) or { code, value }.
// The profile keeps only the filled slots as `entries` (profile-export.js); battle/hero/artifact.js checks them.
export function artifactState(artifact) {
  if (!artifact) return artifact;
  const { quality, stage, entries = [] } = artifact;
  return { quality, stage, slots: entries.map(({ code, value = 0 }) => ({ code, value })) };
}

// Stage within the quality's range; slots cut or padded to the holes open at that quality + stage.
function normalizeArtifact(artifact) {
  if (!artifact || !MAX_STAGE[artifact.quality]) return;
  artifact.stage = Math.min(Math.max(artifact.stage || 1, 1), MAX_STAGE[artifact.quality]);
  const holes = holeNum(artifact.quality, artifact.stage);
  artifact.slots = Array.from({ length: holes }, (_, i) => artifact.slots[i] || null);
}

export {
  LIMITS,
  BLOOD_SIDE,
  isBlood,
  lineupHeroes,
  BUILDINGS,
  heroSkins,
  buildSkins,
  emptyState,
  newHero,
  newBuilding,
  normalize,
};
