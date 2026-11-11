export const JOKER_SUMMON = {
  hero: "cannon_girl",
  skin: "guns_n_roses",
  skillName: "Đồng Đội Điên Cuồng",
  summonedHero: "joker",
};

export function hasSummonedJoker(heroes, skillIsSlotted) {
  return skillIsSlotted && !heroes.some(({ name }) => name === JOKER_SUMMON.summonedHero);
}
