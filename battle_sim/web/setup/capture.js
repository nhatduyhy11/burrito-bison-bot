import { LIMITS, artifactState, newHero } from "./profile-io.js";

const captures = new Map(); // region:battle -> StartGameP

async function capturedStart(region, battle) {
  if (!battle) return null;
  const key = `${region}:${battle}`;
  if (!captures.has(key)) {
    const response = await fetch(`/__sim/battle/${battle}.json?region=${region}`);
    captures.set(key, response.ok ? (await response.json()).start : null);
  }
  return captures.get(key);
}

const listItems = (list) => Array.from({ length: list?._length || 0 }, (_, i) => list[String(i)]);

// Turning a section on fills it from the base capture. The map prefills as a safe fallback only:
// a campaign capture fills its own stage, a capital capture opens the blank capital form (the
// engine forbids a campaign override on a capital base — map-profile.js applyCampaign).
export async function prefill(dict, maps, region, battle, group) {
  const start = await capturedStart(region, battle);
  const player = start && listItems(start.playerInfos)[0];
  if (group === "mounts") {
    const owned = listItems(player?.mounts).map(({ code }) => Object.keys(dict.mounts).find((key) => dict.mounts[key].code === code)).filter(Boolean);
    const selected = owned.find((key) => dict.mounts[key].code === player?.mountCode) || null;
    return { owned, selected };
  }
  if (group === "map") {
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
  const start = await capturedStart(region, battle);
  const player = start && listItems(start.playerInfos)[0];
  const artifact = listItems(player?.heros).find((h) => h.code === heroCode)?.artifact;
  if (!artifact) return null;
  const entries = listItems(artifact.battleEntryInfos).map(({ code, value }) => ({ code, value }));
  return artifactState({ quality: Math.floor(artifact.code / 1000) % 100, stage: artifact.code % 1000, entries });
}
