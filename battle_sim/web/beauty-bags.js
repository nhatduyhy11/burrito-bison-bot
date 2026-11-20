// Dị Vật (BeautyBag) selection -> index-0 skill codes. A profile can keep the captured skills (omitted),
// clear them (null), or pick { type, star, gold }: type = beautybag-dict key, star = suit star 1..maxStar,
// gold = gold item star 0..maxStar (0 = none). The gold item only counts while its suit is on, and each
// gold star only up to the suit's star (client BeautyBagSuitTypeEnhanceItem), so its skill follows
// min(gold, star). See docs/planning/hero_gear.md, Dị Vật.
export function resolveBeautyBag(selection, types) {
  const { type, star, gold = 0 } = selection;
  if (!types || !Object.hasOwn(types, type)) throw new Error(`Không có Dị Vật "${type}"`);
  const entry = types[type];
  if (!Number.isInteger(star) || star < 1 || star > entry.suit.maxStar) {
    throw new Error(`Sao bộ Dị Vật phải từ 1 đến ${entry.suit.maxStar}`);
  }
  if (!Number.isInteger(gold) || gold < 0 || gold > entry.gold.maxStar) {
    throw new Error(`Sao món vàng Dị Vật phải từ 0 đến ${entry.gold.maxStar}`);
  }
  const suitSkill = entry.suit.starSkills.find(({ stars }) => stars.includes(star));
  const goldStar = Math.min(gold, star);
  const goldSkill = goldStar ? entry.gold.starSkills.find(({ stars }) => stars.includes(goldStar)) : null;
  return { type, star, gold, goldStar, entry, suitSkill, goldSkill };
}

// Every suit / gold skill code in the dict: what a selection replaces on index 0.
export const beautyBagCodes = (types) => new Set(Object.values(types).flatMap(({ suit, gold }) =>
  [...suit.starSkills, ...gold.starSkills].map(({ code }) => code)));
