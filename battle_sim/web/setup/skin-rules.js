// Setup page input rules for hero and building skins: normalize what the user picks and tell the
// form which controls are forced. Pure (no DOM); each function takes the skin catalog of one hero /
// building from profile-dict.json. The battle applies skins in web/battle/skin-profile.js and
// build-skin-profile.js, which validate the profile again.
//
// Hero: 3 normal slots + 1 colorful slot. A colorful skin needs its 3 normal skins at >= its star;
// slotting it slots them too (its skills change their effects, dermaIndex PF2-PF4).
// Building: 1 red, 2 gold, 1 special slot. A colorful skin takes a gold slot and locks its 3 required
// skins out of every slot (BuildSkinModule.checkEquipSkillSkinIsLock).

const HERO_SLOTS = { normal: 3, colorful: 1 };
const BUILD_SLOTS = { red: 1, gold: 2, special: 1 };

const clamp = (value, min, max) => Math.min(max, Math.max(min, Math.round(Number(value)) || min));
const isNormalHeroSkin = (skin) => skin.color !== "colorful";
const heroSlotKind = (skin) => (isNormalHeroSkin(skin) ? "normal" : "colorful");
const defaultBuildSkin = (skins) => Object.keys(skins).find((key) => skins[key].default);

function skinState(entry, key) {
  entry.skins[key] = entry.skins[key] || { owned: false, star: 1 };
  return entry.skins[key];
}

// Owned colorful skins raise their required skins to their star and make them owned.
function raiseRequired(entry, skins) {
  for (const [key, skin] of Object.entries(skins)) {
    if (!skin.requires || !entry.skins[key].owned) continue;
    for (const required of skin.requires) {
      const s = skinState(entry, required);
      s.owned = true;
      s.star = clamp(Math.max(s.star, entry.skins[key].star), 1, skins[required].maxStar);
    }
  }
}

// Minimum star per skin forced by owned colorful skins (1 for always-owned skins).
function forcedStars(entry, skins, alwaysOwned) {
  const forced = {};
  for (const key of alwaysOwned) if (key) forced[key] = 1;
  for (const [key, skin] of Object.entries(skins)) {
    if (!skin.requires || !entry.skins[key]?.owned) continue;
    for (const required of skin.requires) forced[required] = Math.max(forced[required] || 1, entry.skins[key].star);
  }
  return forced;
}

function clampStars(entry, skins) {
  for (const key of Object.keys(entry.skins)) if (!skins[key]) delete entry.skins[key];
  for (const key of Object.keys(skins)) {
    const s = skinState(entry, key);
    s.star = clamp(s.star, 1, skins[key].maxStar);
  }
}

// ---------- hero ----------

function heroSlotForced(hero, skins) { // skins slotted because a slotted colorful skin requires them
  return new Set(hero.slots.flatMap((key) => (skins[key] && !isNormalHeroSkin(skins[key]) && skins[key].requires) || []));
}

function heroForced(hero, skins) { // key -> minimum star (worn skin, colorful requirements)
  return forcedStars(hero, skins, [hero.worn]);
}

function normalizeHero(hero, skins) {
  clampStars(hero, skins);
  if (hero.worn && !skins[hero.worn]) hero.worn = null;
  if (hero.worn) hero.skins[hero.worn].owned = true;
  hero.slots = hero.slots.filter((key) => skins[key]);
  for (const key of hero.slots) hero.skins[key].owned = true; // a slotted skin is owned
  raiseRequired(hero, skins);
  const forced = heroSlotForced(hero, skins);
  const used = { normal: 0, colorful: 0 };
  const kept = Object.keys(skins).filter((key) => hero.slots.includes(key) || forced.has(key))
    .sort((a, b) => forced.has(b) - forced.has(a))
    .filter((key) => ++used[heroSlotKind(skins[key])] <= HERO_SLOTS[heroSlotKind(skins[key])]);
  hero.slots = Object.keys(skins).filter((key) => kept.includes(key)); // config order
}

// ---------- building ----------

function buildingLocks(skins, slots) { // skins locked by a slotted colorful skin
  return new Set(slots.flatMap((key) => (skins[key].color === "colorful" && skins[key].requires) || []));
}

function buildingForced(entry, skins) {
  return forcedStars(entry, skins, [defaultBuildSkin(skins), entry.worn]);
}

function normalizeBuilding(entry, skins) {
  clampStars(entry, skins);
  const base = defaultBuildSkin(skins);
  entry.skins[base] = { owned: true, star: 1 };
  if (!entry.worn || !skins[entry.worn]) entry.worn = base;
  entry.skins[entry.worn].owned = true;
  entry.slots = entry.slots.filter((key) => skins[key] && BUILD_SLOTS[skins[key].slot]);
  for (const key of entry.slots) entry.skins[key].owned = true; // a slotted skin is owned
  raiseRequired(entry, skins);
  const locked = buildingLocks(skins, entry.slots);
  const used = { red: 0, gold: 0, special: 0 };
  entry.slots = entry.slots.filter((key) => !locked.has(key))
    .filter((key) => ++used[skins[key].slot] <= BUILD_SLOTS[skins[key].slot]);
}

// build-skin-profile.js default: colorful first, then config order, filling 1 red / 2 gold / 1 special.
function defaultBuildingSlots(entry, skins) {
  const keys = Object.keys(skins).filter((key) => entry.skins[key]?.owned && BUILD_SLOTS[skins[key].slot]);
  keys.sort((a, b) => (skins[b].color === "colorful") - (skins[a].color === "colorful"));
  const chosen = [];
  const used = { red: 0, gold: 0, special: 0 };
  for (const key of keys) {
    if (buildingLocks(skins, chosen).has(key)) continue;
    if (used[skins[key].slot] >= BUILD_SLOTS[skins[key].slot]) continue;
    used[skins[key].slot]++;
    chosen.push(key);
  }
  const locked = buildingLocks(skins, chosen);
  return chosen.filter((key) => !locked.has(key));
}

export {
  HERO_SLOTS,
  BUILD_SLOTS,
  clamp,
  isNormalHeroSkin,
  heroSlotKind,
  defaultBuildSkin,
  skinState,
  normalizeHero,
  heroForced,
  heroSlotForced,
  normalizeBuilding,
  buildingForced,
  buildingLocks,
  defaultBuildingSlots,
};
