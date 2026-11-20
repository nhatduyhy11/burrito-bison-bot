// Local playtest profile, Dị Vật (BeautyBag) of one hero. Server-side the worn suit and gold item only
// add their skills on index 0 (6000TT00N00 suit, 6000TT10N00 gold); the battle loads them by code.
// Every dict suit/gold skill the hero came with is dropped, the selected ones go where the first was.
// hero.attr is left as is (suit/gold attrs are server-merged), like relic.js.
import { beautyBagCodes, resolveBeautyBag } from "../../beauty-bags.js";

export function applyBeautyBag(hero, selection, types, rb, M, step) {
  const selected = selection === null ? null : resolveBeautyBag(selection, types);
  const codes = selected ? [selected.suitSkill.code, ...(selected.goldSkill ? [selected.goldSkill.code] : [])] : [];
  const missing = codes.find((code) => !M("SkillBaseLO").get(code));
  if (missing) throw new Error(`Dị Vật skill ${missing} không có trong config trận`);
  const known = beautyBagCodes(types);
  const isBagSkill = ({ code, index }) => index === 0 && known.has(code);
  const originalSkills = rb.listItems(hero.skills);
  const first = originalSkills.findIndex(isBagSkill);
  const skills = originalSkills.filter((skill) => !isBagSkill(skill));
  skills.splice(first === -1 ? skills.length : first, 0,
    ...codes.map((code) => ({ code, index: 0, level: 1, isShow: false })));
  step("profile Dị Vật", { heroCode: hero.code, beautyBag: selected && { type: selected.type, star: selected.star, gold: selected.gold }, skills: codes });
  return { ...hero, skills };
}
