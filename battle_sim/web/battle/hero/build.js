// Local playtest profile, one hero (?play&profile): the hero object for a hero the capture does
// not have, with stats borrowed from the captured heroes. Used by selection.js.

export function buildProfileHero(code, config, baseSkills, captured, rb, M, step) {
  return borrowStats(makeBaseHero(code, config, baseSkills, M), config, captured, rb, M, step);
}

// A hero outside the capture would otherwise fight at level 1 with HeroLO.baseAttr, far below the
// account: attr is computed by the server, mostly from account-wide sources (antiques, training,
// ...). Captured heroes at the same level end up with nearly equal attr whatever their baseAttr
// (pmain lv 90: attack 425k-442k), so the hero's own base hardly matters.
// Approximation from the captured heroes of the same rarity (all of them if none): attr = their
// mean without skin selfAttr; level / breakThrough = the median hero's; own-skill slots
// (10<NN>0<slot><LL>000) kept when most of them have the slot, at their most common level.
// Relic / artifact skills are per-hero equipment and are not copied.
function borrowStats(hero, config, captured, rb, M, step) {
  const heroes = M("HeroLO");
  const sameRarity = captured.filter((h) => heroes.get(h.code)?.color === config.color);
  const donors = sameRarity.length ? sameRarity : captured;
  if (!donors.length) return hero;

  const sums = new Map();
  for (const donor of donors) {
    for (const [k, v] of withoutSkinAttrs(donor, rb, M)) sums.set(k, (sums.get(k) || 0) + v);
  }
  const attrs = new Map([...sums].map(([k, v]) => [k, Math.round(v / donors.length)]));

  const byLevel = donors.slice().sort((a, b) => (a.level || 0) - (b.level || 0) || (a.breakThrough || 0) - (b.breakThrough || 0));
  const median = byLevel[Math.floor((byLevel.length - 1) / 2)];

  const OWN = /^10(\d\d)0(\d)(\d\d)000$/;
  const levels = new Map(); // slot -> Map(level -> donors)
  for (const donor of donors) {
    for (const { code } of rb.listItems(donor.skills)) {
      const m = OWN.exec(String(code));
      if (!m) continue;
      const counts = levels.get(Number(m[2])) || new Map();
      counts.set(m[3], (counts.get(m[3]) || 0) + 1);
      levels.set(Number(m[2]), counts);
    }
  }
  const nn = String(hero.code % 1000).padStart(2, "0");
  const slots = new Map(rb.listItems(hero.skills).map((s) => [Number(OWN.exec(String(s.code))[2]), s.code]));
  for (const [slot, counts] of levels) {
    const have = [...counts.values()].reduce((a, b) => a + b, 0);
    if (!slots.has(slot) && have * 2 <= donors.length) continue; // extra slot only if most donors have it
    const level = [...counts].sort((a, b) => b[1] - a[1] || b[0] - a[0])[0][0];
    const code = Number(`10${nn}0${slot}${level}000`);
    if (M("SkillBaseLO").get(code)) slots.set(slot, code);
  }
  const skills = [...slots.keys()].sort((a, b) => a - b)
    .map((slot, i) => ({ code: slots.get(slot), index: i + 1, isShow: i > 0 }));
  step("profile borrowed stats", {
    heroCode: hero.code, from: donors.map((h) => h.code), level: median.level, breakThrough: median.breakThrough,
    skills: skills.map((s) => s.code),
  });
  return {
    ...hero, level: median.level, breakThrough: median.breakThrough, fightCap: median.fightCap,
    attr: { _keyList: [...attrs.keys()], _valueList: [...attrs.values()] },
    skills,
  };
}

// A captured hero's attr minus the selfAttr of the skins whose skills it carries.
function withoutSkinAttrs(hero, rb, M) {
  const attrs = new Map(rb.listItems(hero.attr._keyList).map((key, i) => [Number(key), hero.attr._valueList[i]]));
  const skills = new Set(rb.listItems(hero.skills).map((s) => s.code));
  const ranks = M("DermaStarLO");
  for (const key of Object.keys(ranks.store)) {
    if (!/^\d+$/.test(key)) continue;
    const r = ranks.get(Number(key));
    if (r.heroCode !== hero.code || !JSON.parse(r.skill || "[]").some((id) => skills.has(id))) continue;
    for (const [k, v] of JSON.parse(r.selfAttr || "[]")) if (attrs.has(k)) attrs.set(k, attrs.get(k) - v);
  }
  return attrs;
}

function makeBaseHero(code, config, baseSkills, M) {
  if (!Array.isArray(baseSkills) || !baseSkills.length || baseSkills.some((id) => !M("SkillBaseLO").get(id))) {
    throw new Error(`Hero ${code} needs valid baseSkills in the profile dictionary`);
  }
  const attrs = JSON.parse(config.baseAttr);
  return {
    code, uuid: String(code).padStart(24, "0"), level: 1, derma: 0,
    attr: {
      _keyList: attrs.map(([key]) => key),
      _valueList: attrs.map(([, value]) => value),
    },
    skills: baseSkills.map((id, i) => ({ code: id, index: i + 1, isShow: i > 0 })),
  };
}
