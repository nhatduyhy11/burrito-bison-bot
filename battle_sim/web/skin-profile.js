// Apply equipped and owned hero skins from a local playtest profile.
(function () {
  "use strict";

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
        unlock(required, skinConfig.color === 8 ? Math.max(minStar, stars) : minStar);
      }
      return rank;
    }
    const { skin, star = 1, ownedSkins = {} } = selection;
    const codeOf = (name) => {
      if (typeof name !== "string" || !catalog || !Object.hasOwn(catalog, name)) {
        throw new Error(`Unknown skin ${name} for hero ${hero.code}`);
      }
      return catalog[name];
    };
    if (!ownedSkins || typeof ownedSkins !== "object" || Array.isArray(ownedSkins)) {
      throw new Error("ownedSkins must map skin names to star counts");
    }
    const derma = codeOf(skin);
    for (const [name, stars] of Object.entries(ownedSkins)) {
      if (name === skin) throw new Error("Set the equipped skin rank with star");
      unlock(codeOf(name), stars);
    }
    const equipped = unlock(derma, star);
    report?.({
      heroCode: hero.code,
      equipped: derma,
      star,
      unlocked: [...unlocked.values()].map((rank) => ({
        code: rank.dermaCode, name: skins.get(rank.dermaCode).name,
        color: skins.get(rank.dermaCode).color, star: rank.star,
      })),
    });
    const originalSkills = rb.listItems(hero.skills);
    const skinSkills = new Set();
    const attrs = new Map(rb.listItems(hero.attr._keyList).map((key, i) => [key, hero.attr._valueList[i]]));
    const addAttrs = (rank, sign) => {
      for (const [key, value] of [...JSON.parse(rank.attr), ...JSON.parse(rank.selfAttr)]) {
        attrs.set(key, (attrs.get(key) || 0) + sign * value);
      }
    };
    for (const key of Object.keys(ranks.store)) {
      if (!/^\d+$/.test(key)) continue;
      const rank = ranks.get(Number(key));
      if (rank.heroCode !== hero.code) continue;
      const ids = JSON.parse(rank.skill);
      ids.forEach((id) => skinSkills.add(id));
      if (rank.dermaCode === hero.derma && originalSkills.some(({ code }) => ids.includes(code))) {
        // Captures do not necessarily include every skin attribute (e.g. 1015).
        for (const [attr, value] of [...JSON.parse(rank.attr), ...JSON.parse(rank.selfAttr)]) {
          if (attrs.has(attr)) attrs.set(attr, attrs.get(attr) - value);
        }
      }
    }
    for (const rank of unlocked.values()) addAttrs(rank, 1);
    const skills = originalSkills.filter(({ code }) => !skinSkills.has(code));
    for (const code of JSON.parse(equipped.skill)) {
      skills.push({ code, index: 5, level: 1, isShow: false });
    }
    return {
      ...hero, derma, skills,
      attr: { _keyList: [...attrs.keys()], _valueList: [...attrs.values()] },
    };
  }

  if (typeof module !== "undefined" && module.exports) module.exports = { applySkin };
  else window.applySimSkinProfile = applySkin;
})();
