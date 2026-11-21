import { BLOOD_SIDE, LIMITS, artifactState, newHero } from "./profile-state.js";

const captures = new Map(); // region:battle -> { start: StartGameP, team? }

async function capturedBattle(region, battle) {
  if (!battle) return null;
  const key = `${region}:${battle}`;
  if (!captures.has(key)) {
    const response = await fetch(`/__sim/battle/${battle}.json?region=${region}`);
    captures.set(key, response.ok ? await response.json() : null);
  }
  return captures.get(key);
}
const capturedStart = async (region, battle) => (await capturedBattle(region, battle))?.start ?? null;

const listItems = (list) => Array.from({ length: list?._length || 0 }, (_, i) => list[String(i)]);
export const BLOOD_BATTLE_TYPES = [47, 48]; // web/battle/blood-map.js

// Đêm Đỏ capture: the lineup heroes split by owner (uuid in each member's roster, capture.team),
// Master = leaderId. Returns { master: [hero state x3], guest: [hero state x3] }, null when the
// capture has no team roster.
export async function bloodTeams(dict, region, battle) {
  const b = await capturedBattle(region, battle);
  if (!b?.team) return null;
  const lineup = listItems(listItems(b.start.playerInfos)[0]?.heros);
  const side = (master) => {
    const member = b.team.find((m) => (m.playerId === Number(b.start.leaderId)) === master);
    const own = new Set(listItems(member?.heros).map((h) => h.uuid));
    const names = lineup.filter((h) => own.has(h.uuid))
      .map((h) => Object.keys(dict.heroes).find((key) => dict.heroes[key].code === h.code)).filter(Boolean);
    return Array.from({ length: BLOOD_SIDE }, (_, i) => newHero(names[i] || ""));
  };
  return { master: side(true), guest: side(false) };
}

// Turning a section on fills it from the base capture. The map prefills as a safe fallback only:
// a campaign capture fills its own stage, a capital capture opens the blank capital form (the
// engine forbids a campaign override on a capital base — map-profile.js applyCampaign).
export async function prefill(dict, maps, region, battle, group, navalDict) {
  const start = await capturedStart(region, battle);
  const player = start && listItems(start.playerInfos)[0];
  if (group === "mounts") {
    const owned = listItems(player?.mounts).map(({ code }) => Object.keys(dict.mounts).find((key) => dict.mounts[key].code === code)).filter(Boolean);
    const selected = owned.find((key) => dict.mounts[key].code === player?.mountCode) || null;
    return { owned, selected };
  }
  if (group === "summonerGear") {
    // Gear-skill toggles: names whose fixed skill code (9000x00000) sits on the bed build.
    const bed = listItems(player?.builds).find((build) => build.type === dict.buildings.bed.buildType);
    const codes = new Set(listItems(bed?.skills).map(({ code }) => code));
    return Object.keys(dict.summonerGear).filter((key) => codes.has(dict.summonerGear[key].code));
  }
  if (group === "map") {
    if (start?.battleType === 42) {
      const level = start.level - start.level % 100 + 1;
      const boss = Object.keys(navalDict?.bosses || {}).find((key) => navalDict.bosses[key].presets.some((p) => p.level === level));
      return { mode: "naval", stage: maps.campaign.minStage, boss: boss || null, level: boss ? level : null };
    }
    if (BLOOD_BATTLE_TYPES.includes(start?.battleType)) return { mode: "blood", stage: maps.campaign.minStage, boss: null, level: start.level };
    if (start?.battleType === maps.capital.battleType) return { mode: "capital", stage: maps.campaign.minStage, boss: null, level: null };
    return { mode: "campaign", stage: start?.level || maps.campaign.minStage, boss: null, level: null };
  }
  if (!player) return [];
  const name = (group, code) => Object.keys(dict[group]).find((key) => dict[group][key].code === code);
  const from = {
    heroes: () => listItems(player.heros).map((h) => name("heroes", h.code)).filter(Boolean).map(newHero),
    traps: () => listItems(player.organs).map((o) => ({ name: name("traps", o.code), level: o.level, star: o.star })),
    pets: () => listItems(player.summonCreatures).map((p) => ({ name: name("pets", p.code), level: p.level, star: p.star })),
    spells: () => listItems(player.daoists).map((d) => ({ name: name("spells", d.code), star: d.star })),
    summonerSkins: () => listItems(player.summonerInfos).flatMap(({ code, level }) => {
      const key = name("summonerSkins", code);
      return dict.summonerSkins[key]?.skill ? [{ name: key, star: level }] : [];
    }),
  }[group];
  return from().filter((item) => item.name).slice(0, LIMITS[group]);
}

// Thần Khí of a hero in the base capture as setup state (hero card in Teams), null when it has none.
export async function capturedArtifact(region, battle, heroCode) {
  const capture = await capturedBattle(region, battle);
  const player = listItems(capture?.start?.playerInfos)[0];
  const hero = listItems(player?.heros).find((h) => h.code === heroCode)
    || listItems(capture?.roster?.heros).find((h) => h.code === heroCode);
  const artifact = hero?.artifact;
  if (!artifact) return null;
  const entries = listItems(artifact.battleEntryInfos).map(({ code, value }) => ({ code, value }));
  return artifactState({ quality: Math.floor(artifact.code / 1000) % 100, stage: artifact.code % 1000, entries });
}
