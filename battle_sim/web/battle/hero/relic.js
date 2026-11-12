import { resolveRelic } from "../../relics.js";

export function applyRelic(hero, selection, lines, rb, M, step) {
  const selected = selection === null ? null : resolveRelic(selection, lines);
  const relic = selected?.tier.code ?? 0;
  const codes = selected ? [selected.starSkill.code] : [];
  if (selected?.tier.fixedSkill) codes.push(selected.tier.fixedSkill.code);
  if (selected && (!M("RelicLO").get(relic) || codes.some((code) => !M("SkillBaseLO").get(code)))) {
    throw new Error(`Thánh Khí "${selected.name}" không có trong config trận`);
  }
  const relicSkills = new Set(Object.values(lines).flatMap(({ starSkills, purifications }) => [
    ...starSkills.map(({ code }) => code),
    ...purifications.flatMap(({ fixedSkill }) => fixedSkill ? [fixedSkill.code] : []),
  ]));
  const isRelicSkill = ({ code, index }) => index === 0 && relicSkills.has(code);
  const originalSkills = rb.listItems(hero.skills);
  const first = originalSkills.findIndex(isRelicSkill);
  const skills = originalSkills.filter((skill) => !isRelicSkill(skill));
  skills.splice(first === -1 ? skills.length : first, 0,
    ...codes.map((code) => ({ code, index: 0, level: 1, isShow: false })));
  step("profile Thánh Khí", { heroCode: hero.code, relic, skills: codes });
  return { ...hero, relic, skills };
}
