// A profile can keep the captured relic (omitted), clear it (null), or select a line.
export function resolveRelic(selection, lines) {
  const { name, star = 0, purification = 0 } = selection;
  if (!lines || !Object.hasOwn(lines, name)) throw new Error(`Không có Thánh Khí "${name}"`);
  const line = lines[name];
  const tier = line.purifications.find(({ times }) => times === purification);
  if (!tier) throw new Error("Mức thanh tẩy Thánh Khí phải từ 0 đến 2");
  const starSkill = line.starSkills.find(({ stars }) => stars.includes(star));
  if (!starSkill) throw new Error(`Sao Thánh Khí phải từ 0 đến ${tier.maxStar}`);
  return { name, star, purification, tier, starSkill };
}
