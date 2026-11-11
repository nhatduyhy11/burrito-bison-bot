// Apply owned, worn and slotted building skins (door, bed, generator, cat) from a local playtest
// profile. Rules: BUILD_SKINS.md (BuildSkinModule + pmain captures 6af3d7da / 6af3dacb).
//
// - BuildSkinLO code = skinId * 100 + star. The worn skin (`skinId`, `skinLevel`) only picks the model.
// - Battle skills (`builds[].skills`) come from the slotted skins at their current star:
//   1 red, 2 gold, 1 special slot (BuildSkinLO.skillType 1 / 2 / 3). A colorful skin takes a gold
//   slot and locks the 3 skins it requires out of every slot.
// - A colorful skin at N stars requires its 3 skins at >= N stars; they are raised to that rank.
// - `skinInfos` lists every owned building skin; `builds[].attr` is kept from the capture.
(function () {
  "use strict";

  const SLOT_CAPACITY = { 1: 1, 2: 2, 3: 1 }; // skillType -> slots
  const SLOT_ORDER = [1, 2, 3]; // default skill order: red, gold, special
  const isColorful = (row) => row.color > 7;

  function applyBuildSkins(player, selections, catalog, rb, M, report) {
    if (!selections || typeof selections !== "object" || Array.isArray(selections)) {
      throw new Error("buildings must map building names (door, bed, generator, cat) to skin selections");
    }
    const table = M("BuildSkinLO");
    const rowOf = (skinId, star) => table.get(skinId * 100 + star);
    // Skill codes that belong to some building skin; anything else in builds[].skills was added by
    // the server (e.g. 90000300000 on the bed) and is kept.
    const skinSkills = new Set();
    for (const key of Object.keys(table.store)) {
      if (!/^\d+$/.test(key)) continue;
      for (const id of JSON.parse(table.get(Number(key)).skill || "[]")) skinSkills.add(id);
    }

    const builds = rb.listItems(player.builds).slice();
    let skinInfos = rb.listItems(player.skinInfos);
    const resolvedAll = [];
    for (const [name, selection] of Object.entries(selections)) {
      if (!Object.hasOwn(catalog, name)) throw new Error(`Unknown building: ${name}`);
      const { buildType, skins } = catalog[name];
      const index = builds.findIndex((build) => build.type === buildType);
      if (index < 0) throw new Error(`Captured StartGameP has no building of type ${buildType}`);
      const resolved = resolveBuilding(selection || {}, buildType, skins, rowOf, name);
      resolvedAll.push(resolved);

      const extras = rb.listItems(builds[index].skills).filter(({ code }) => !skinSkills.has(code));
      const skills = resolved.slots.flatMap(({ skinId, star }) => JSON.parse(rowOf(skinId, star).skill || "[]"))
        .map((code) => ({ code, index: 1, level: 1, isShow: false }));
      builds[index] = {
        ...builds[index], skinId: resolved.skinId, skinLevel: resolved.skinLevel,
        skills: asList([...skills, ...extras]),
      };
      skinInfos = skinInfos.filter(({ skinId, skinLevel }) => rowOf(skinId, skinLevel)?.buildType !== buildType);
      skinInfos.push(...resolved.owned.map(({ skinId, star }) => ({ skinId, skinLevel: star })));
    }
    report?.(resolvedAll);
    return { builds: asList(builds), skinInfos: asList(skinInfos) };
  }

  function resolveBuilding(selection, buildType, skins, rowOf, building) {
    const { skin, star, ownedSkins = {}, slots } = selection;
    const idOf = (name) => {
      if (typeof name !== "string" || !Object.hasOwn(skins, name)) {
        throw new Error(`Unknown skin ${name} for building ${building}`);
      }
      return skins[name].skinId;
    };
    if (!ownedSkins || typeof ownedSkins !== "object" || Array.isArray(ownedSkins)) {
      throw new Error("ownedSkins must map skin names to star counts");
    }
    if (skin === undefined && star !== undefined) {
      throw new Error(`Select a skin before setting its star for building ${building}`);
    }
    const unlocked = new Map(); // skinId -> BuildSkinLO row at its star
    function unlock(skinId, stars) {
      const row = Number.isInteger(stars) && stars > 0 && stars < 100 && rowOf(skinId, stars);
      if (!row || row.skinId !== skinId || row.buildType !== buildType) {
        throw new Error(`Invalid skin ${skinId} at ${stars} stars for building ${building}`);
      }
      if ((unlocked.get(skinId)?.star || 0) >= stars) return;
      unlocked.set(skinId, row);
      // Rows of colorful skins list the requirement at their own star.
      for (const [required, minStar] of JSON.parse(row.requirement || "[]")) unlock(required, minStar);
    }
    for (const option of Object.values(skins)) if (option.default) unlock(option.skinId, 1);
    for (const [name, stars] of Object.entries(ownedSkins)) {
      if (name === skin) throw new Error("Set the equipped skin rank with star");
      unlock(idOf(name), stars);
    }
    const defaultSkin = Object.values(skins).find((option) => option.default);
    const skinId = skin === undefined ? defaultSkin.skinId : idOf(skin);
    unlock(skinId, star ?? 1);

    const slotted = resolveSlots(slots, unlocked, idOf, building).map((id) => unlocked.get(id));
    const pick = (row) => ({ skinId: row.skinId, name: row.name, color: row.color, star: row.star });
    return {
      building, buildType, skinId, skinLevel: unlocked.get(skinId).star,
      owned: [...unlocked.values()].map(pick),
      slots: slotted.map((row) => ({ ...pick(row), skillType: row.skillType, skill: JSON.parse(row.skill || "[]") })),
    };
  }

  // Default (no `slots`): colorful skins first, then config order, filling 1 red / 2 gold /
  // 1 special and skipping skins a slotted colorful skin locks. Explicit `slots` keep their order.
  function resolveSlots(slots, unlocked, idOf, building) {
    const slottable = [...unlocked.values()].filter((row) => SLOT_CAPACITY[row.skillType]);
    const lockedBy = (rows) => new Set(rows.filter(isColorful)
      .flatMap((row) => JSON.parse(row.requirement || "[]").map(([id]) => id)));
    if (slots === undefined) {
      const sorted = slottable.sort((a, b) => isColorful(b) - isColorful(a) || a.index - b.index || a.skinId - b.skinId);
      const chosen = [];
      for (const row of sorted) {
        if (lockedBy(chosen).has(row.skinId)) continue;
        if (chosen.filter((r) => r.skillType === row.skillType).length >= SLOT_CAPACITY[row.skillType]) continue;
        chosen.push(row);
      }
      // Drop anything a later colorful pick locked, then order red, gold, special.
      const locked = lockedBy(chosen);
      return SLOT_ORDER.flatMap((type) => chosen.filter((r) => r.skillType === type && !locked.has(r.skinId)))
        .map((row) => row.skinId);
    }
    if (!Array.isArray(slots)) throw new Error("slots must be an array of skin names");
    const ids = slots.map(idOf);
    if (new Set(ids).size !== ids.length) throw new Error(`Duplicate skin slot for building ${building}`);
    const rows = ids.map((id) => {
      const row = unlocked.get(id);
      if (!row) throw new Error(`Skin ${id} is in a slot but not owned for building ${building}`);
      if (!SLOT_CAPACITY[row.skillType]) throw new Error(`Skin ${id} has no skill slot (default skin)`);
      return row;
    });
    for (const type of SLOT_ORDER) {
      if (rows.filter((row) => row.skillType === type).length > SLOT_CAPACITY[type]) {
        throw new Error(`Building ${building} has 1 red, 2 gold and 1 special skin slot`);
      }
    }
    const locked = lockedBy(rows);
    for (const id of ids) {
      if (locked.has(id)) throw new Error(`Skin ${id} is locked by the colorful skin slotted on building ${building}`);
    }
    return ids;
  }

  function asList(items) {
    return { ...items, _length: items.length };
  }

  if (typeof module !== "undefined" && module.exports) module.exports = { applyBuildSkins };
  else window.applySimBuildSkinProfile = applyBuildSkins;
})();
