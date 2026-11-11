// Apply owned, worn and slotted hero skins from a local playtest profile.
//
// Game rule (HeroDermaModule + pmain capture 6af3d7da1d68f99b52631ef9): the worn skin
// (`derma`) only picks the model. Battle skills come from the hero's skin skill slots:
// up to 3 normal skins (color <= 7) and 1 colorful skin (color > 7), each at the skill
// code of its current star, appended after the hero's own skills in slot order.
(function () {
  "use strict";

  const MAX_NORMAL_SLOTS = 3;
  const MAX_COLOR_SLOTS = 1;
  const isColorful = (skinConfig) => skinConfig.color > 7;

  function applySkin(hero, selection, catalog, rb, M, report) {
    const skins = M("DermaLO");
    const ranks = M("DermaStarLO");
    const unlocked = new Map();
    function unlock(code, stars) {
      const rank = Number.isInteger(stars) && stars > 0 && stars < 100 && ranks.get(code * 100 + stars);
      if (!rank || rank.dermaCode !== code || rank.heroCode !== hero.code) {
        throw new Error(`Invalid skin ${code} at ${stars} stars for hero ${hero.code}`);
      }
      if ((unlocked.get(code)?.star || 0) >= stars) return rank;
      unlocked.set(code, rank);
      const skinConfig = skins.get(code);
      for (const [required, minStar] of JSON.parse(rank.requirement || skinConfig.requirement || "[]")) {
        unlock(required, isColorful(skinConfig) ? Math.max(minStar, stars) : minStar);
      }
      return rank;
    }
    const { skin, star, ownedSkins = {}, slots } = selection;
    const codeOf = (name) => {
      if (typeof name !== "string" || !catalog || !Object.hasOwn(catalog, name)) {
        throw new Error(`Unknown skin ${name} for hero ${hero.code}`);
      }
      return catalog[name];
    };
    if (!ownedSkins || typeof ownedSkins !== "object" || Array.isArray(ownedSkins)) {
      throw new Error("ownedSkins must map skin names to star counts");
    }
    if (skin === undefined && star !== undefined) {
      throw new Error(`Select a skin before setting its star for hero ${hero.code}`);
    }
    for (const [name, stars] of Object.entries(ownedSkins)) {
      if (name === skin) throw new Error("Set the equipped skin rank with star");
      unlock(codeOf(name), stars);
    }
    const derma = skin === undefined ? 0 : codeOf(skin);
    if (derma) unlock(derma, star ?? 1);

    const slotted = resolveSlots(slots, unlocked, skins, codeOf, hero.code);
    report?.({
      heroCode: hero.code,
      equipped: derma,
      star: derma ? unlocked.get(derma).star : undefined,
      unlocked: [...unlocked.values()].map((rank) => ({
        code: rank.dermaCode, name: skins.get(rank.dermaCode).name,
        color: skins.get(rank.dermaCode).color, star: rank.star,
      })),
      slots: slotted.map((code) => ({ code, star: unlocked.get(code).star, skill: JSON.parse(unlocked.get(code).skill) })),
    });

    // Drop the captured skin skills and the attributes of the captured skins they came from.
    const originalSkills = rb.listItems(hero.skills);
    const attrs = new Map(rb.listItems(hero.attr._keyList).map((key, i) => [key, hero.attr._valueList[i]]));
    const rankOfSkill = new Map();
    for (const key of Object.keys(ranks.store)) {
      if (!/^\d+$/.test(key)) continue;
      const rank = ranks.get(Number(key));
      if (rank.heroCode !== hero.code) continue;
      for (const id of JSON.parse(rank.skill)) rankOfSkill.set(id, rank);
    }
    // Only selfAttr lands on the hero; the server keeps `attr` (e.g. 1015) out of hero.attr.
    // Captures treat every owned skin's selfAttr as added, whether slotted or not.
    for (const { code } of originalSkills) {
      const rank = rankOfSkill.get(code);
      if (!rank) continue;
      for (const [key, value] of JSON.parse(rank.selfAttr)) {
        if (attrs.has(key)) attrs.set(key, attrs.get(key) - value);
      }
    }
    for (const rank of unlocked.values()) {
      for (const [key, value] of JSON.parse(rank.selfAttr)) {
        attrs.set(key, (attrs.get(key) || 0) + value);
      }
    }
    const skills = originalSkills.filter(({ code }) => !rankOfSkill.has(code));
    for (const code of slotted) {
      for (const id of JSON.parse(unlocked.get(code).skill)) {
        skills.push({ code: id, index: skills.length + 1, level: 1, isShow: false });
      }
    }
    return {
      ...hero, derma, skills,
      attr: { _keyList: [...attrs.keys()], _valueList: [...attrs.values()] },
    };
  }

  // Default: every owned skin, normal ones in config order, then the colorful one.
  // The order of the colorful skill relative to normal ones is not verified.
  function resolveSlots(slots, unlocked, skins, codeOf, heroCode) {
    const byIndex = (a, b) => skins.get(a).index - skins.get(b).index || a - b;
    let codes;
    if (slots === undefined) {
      const owned = [...unlocked.keys()].sort(byIndex);
      codes = [
        ...owned.filter((code) => !isColorful(skins.get(code))).slice(0, MAX_NORMAL_SLOTS),
        ...owned.filter((code) => isColorful(skins.get(code))).slice(0, MAX_COLOR_SLOTS),
      ];
    } else {
      if (!Array.isArray(slots)) throw new Error("slots must be an array of skin names");
      codes = slots.map(codeOf);
      if (new Set(codes).size !== codes.length) throw new Error(`Duplicate skin slot for hero ${heroCode}`);
      for (const code of codes) {
        if (!unlocked.has(code)) throw new Error(`Skin ${code} is in a slot but not owned by hero ${heroCode}`);
      }
      const color = codes.filter((code) => isColorful(skins.get(code)));
      const normal = codes.filter((code) => !isColorful(skins.get(code)));
      if (normal.length > MAX_NORMAL_SLOTS || color.length > MAX_COLOR_SLOTS) {
        throw new Error(`Hero ${heroCode} has ${MAX_NORMAL_SLOTS} normal and ${MAX_COLOR_SLOTS} colorful skin slots`);
      }
      codes = [...normal, ...color];
    }
    return codes;
  }

  if (typeof module !== "undefined" && module.exports) module.exports = { applySkin };
  else window.applySimSkinProfile = applySkin;
})();
