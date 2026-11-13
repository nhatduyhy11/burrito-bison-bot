// Local playtest profile, one hero: Dị Năng (异能) skill nodes, `avatar: N` = the first N of the hero's
// 5 skill nodes are open (the game opens them in chapter order). Server-side the opened nodes only
// change hero.skills: each swaps `replaces` for `skill` (adds it when replaces is null), later nodes
// may replace an earlier node's skill. The battle engine loads skills by code alone, so rebuilding
// hero.skills by this rule is all the game does. Attribute nodes are not modelled.
// nodes = profile-dict avatarNodes (chapter order). See docs/planning/hero_gear.md.

export function applyAvatar(hero, nodes, count, rb, step) {
  if (!nodes?.length) throw new Error(`Hero ${hero.code} has no Dị Năng skill nodes`);
  if (!Number.isInteger(count) || count < 0 || count > nodes.length) {
    throw new Error(`Hero ${hero.code} Dị Năng must be 0-${nodes.length}, got ${count}`);
  }
  const skills = rb.listItems(hero.skills).map((s) => ({ ...s }));
  const at = (code) => skills.findIndex((s) => s.code === code);
  // Close every node the hero came with (captured or borrowed), last chapter first.
  for (const node of [...nodes].reverse()) {
    const i = at(node.skill);
    if (i < 0) continue;
    if (node.replaces && at(node.replaces) < 0) skills[i].code = node.replaces;
    else skills.splice(i, 1);
  }
  // Open the first `count` nodes in chapter order. A node is skipped on its own (the other nodes
  // still apply) when the hero is below its `minBreakThrough` (AvatarUpGradeLO.skillUnlock; a hero
  // without breakThrough is not gated), or when it replaces a skill the hero lacks (a breakthrough
  // variant it has not reached, or an earlier node's skill that was skipped).
  const skipped = [];
  nodes.slice(0, count).forEach((node, n) => {
    if (node.minBreakThrough && (hero.breakThrough ?? Infinity) < node.minBreakThrough) {
      skipped.push(n + 1);
      return;
    }
    if (!node.replaces) {
      if (at(node.skill) < 0) skills.push({ code: node.skill, index: 0, level: 1, isShow: false });
      return;
    }
    const i = at(node.replaces);
    if (i >= 0) skills[i].code = node.skill;
    else skipped.push(n + 1);
  });
  step("profile Dị Năng", { heroCode: hero.code, nodes: count, skipped, skills: skills.map((s) => s.code) });
  return { ...hero, skills };
}
