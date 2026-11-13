// A region switch preserves the rest of the profile when a catalog entry is unavailable.
export function forRegion(profile, dict, { antiqueDict }) {
  const adjusted = structuredClone(profile);
  const removed = new Set();
  const exists = (catalog, key) => {
    if (Object.hasOwn(catalog, key)) return true;
    removed.add(key);
    return false;
  };

  for (const group of ["traps", "pets", "summonerSkins"]) {
    if (adjusted[group]) {
      adjusted[group] = adjusted[group].filter((entry) => exists(dict[group], entry.name ?? entry));
    }
  }
  if (adjusted.summonerWorn && !exists(dict.summonerSkins, adjusted.summonerWorn)) {
    delete adjusted.summonerWorn;
  }
  if (adjusted.antiques) {
    adjusted.antiques = Object.fromEntries(Object.entries(adjusted.antiques)
      .filter(([key]) => exists(antiqueDict.antiques, key)));
  }

  for (const hero of [...(adjusted.heroes || []), adjusted.summonedJoker]) {
    if (!hero || typeof hero === "string") continue;
    const skins = dict.heroes[hero.name]?.skins || {};
    if (hero.skin && !exists(skins, hero.skin)) {
      delete hero.skin;
      delete hero.star;
    }
    if (hero.ownedSkins) {
      hero.ownedSkins = Object.fromEntries(Object.entries(hero.ownedSkins).filter(([key]) => exists(skins, key)));
    }
    if (hero.slots) hero.slots = hero.slots.filter((key) => exists(skins, key));
  }
  return { profile: adjusted, removed: [...removed] };
}
