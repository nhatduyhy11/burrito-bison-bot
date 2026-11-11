// Setup page for local playtest profiles (served at /__sim/setup.html).
//
// Builds the JSON that web/battle/profile.js reads (`sandbox.py --play --profile <file>`), from the
// catalog in profile-dict.json (scripts/gen_profile_dict.js). A section left off ("Ghi đè" unchecked)
// is omitted from the profile, so the battle keeps that part of the captured StartGameP.
// Skin rules mirror skin-profile.js (heroes) and build-skin-profile.js (buildings); the backend
// validates again when the battle starts.
//
// Opened through `sandbox.py --setup`, the page gets window.simPlay({battle, seed, profile}): sandbox
// saves the profile under .tmp/battle_sim/profiles/ and opens the battle with it.
(function () {
  "use strict";

  const LIMITS = { heroes: 5, traps: 3, pets: 3, spells: 2 };
  const LIST_TITLES = { traps: "Trap", pets: "Pet", spells: "Spell (thần)" };
  const BUILDINGS = [["door", "Cửa"], ["bed", "Giường"], ["generator", "Chuột (máy phát điện)"], ["cat", "Mèo (chiêu tài)"]];
  const BUILD_SLOTS = { red: 1, gold: 2, special: 1 };
  const HERO_SLOTS = { normal: 3, colorful: 1 };
  const COLOR_LABEL = { red: "đỏ", gold: "vàng", colorful: "7 màu", default: "mặc định", special: "loại 3" };
  const STORE_KEY = "battleSimSetup";
  // Rarity groups in the hero / trap / pet pickers (card border in game), highest first. Spells have none.
  const RARITY_GROUPS = [["gold", "Vàng"], ["red", "Đỏ"], ["orange", "Cam"], ["purple", "Tím"]];

  let dict, battles = [], state;
  const captures = new Map(); // uuid -> StartGameP
  const $ = (id) => document.getElementById(id);

  // ---------- state <-> profile ----------

  function emptyState() {
    return {
      battle: "", seed: "", map: null, heroes: null, traps: null, pets: null, spells: null,
      buildings: Object.fromEntries(BUILDINGS.map(([key]) => [key, null])), goldenSkinsCount: null,
    };
  }

  const heroSkins = (name) => dict.heroes[name]?.skins || {};
  const buildSkins = (building) => dict.buildings[building].skins;
  const defaultBuildSkin = (building) => Object.keys(buildSkins(building)).find((key) => buildSkins(building)[key].default);
  const isNormalHeroSkin = (skin) => skin.color !== "colorful";

  function newHero(name) {
    return { name, custom: false, worn: null, skins: {}, slots: [] };
  }

  function newBuilding(building) {
    return { worn: defaultBuildSkin(building), skins: {}, slots: [] };
  }

  function skinState(entry, key) {
    entry.skins[key] = entry.skins[key] || { owned: false, star: 1 };
    return entry.skins[key];
  }

  // Raise the skins a colorful skin requires to its star (both games' rule), keep worn skins owned,
  // drop slots that are not owned, locked or over capacity.
  function normalizeHero(hero) {
    const skins = heroSkins(hero.name);
    for (const key of Object.keys(hero.skins)) if (!skins[key]) delete hero.skins[key];
    for (const key of Object.keys(skins)) {
      const s = skinState(hero, key);
      s.star = clamp(s.star, 1, skins[key].maxStar);
    }
    if (hero.worn && !skins[hero.worn]) hero.worn = null;
    if (hero.worn) hero.skins[hero.worn].owned = true;
    for (const [key, skin] of Object.entries(skins)) {
      if (!skin.requires || !hero.skins[key].owned) continue;
      for (const required of skin.requires) {
        const s = skinState(hero, required);
        s.owned = true;
        s.star = clamp(Math.max(s.star, hero.skins[key].star), 1, skins[required].maxStar);
      }
    }
    const used = { normal: 0, colorful: 0 };
    hero.slots = Object.keys(skins).filter((key) => hero.slots.includes(key) && hero.skins[key].owned).filter((key) => {
      const kind = isNormalHeroSkin(skins[key]) ? "normal" : "colorful";
      return ++used[kind] <= HERO_SLOTS[kind];
    });
  }

  function heroForced(hero) { // key -> minimum star forced by an owned colorful skin (or 1 for the worn skin)
    const skins = heroSkins(hero.name);
    const forced = {};
    if (hero.worn) forced[hero.worn] = 1;
    for (const [key, skin] of Object.entries(skins)) {
      if (!skin.requires || !hero.skins[key]?.owned) continue;
      for (const required of skin.requires) forced[required] = Math.max(forced[required] || 1, hero.skins[key].star);
    }
    return forced;
  }

  function buildingLocks(building, entry) { // skins locked by a slotted colorful skin
    const skins = buildSkins(building);
    return new Set(entry.slots.flatMap((key) => (skins[key].color === "colorful" && skins[key].requires) || []));
  }

  function normalizeBuilding(building, entry) {
    const skins = buildSkins(building);
    for (const key of Object.keys(entry.skins)) if (!skins[key]) delete entry.skins[key];
    for (const key of Object.keys(skins)) {
      const s = skinState(entry, key);
      s.star = clamp(s.star, 1, skins[key].maxStar);
    }
    const base = defaultBuildSkin(building);
    entry.skins[base] = { owned: true, star: 1 };
    if (!entry.worn || !skins[entry.worn]) entry.worn = base;
    entry.skins[entry.worn].owned = true;
    for (const [key, skin] of Object.entries(skins)) {
      if (!skin.requires || !entry.skins[key].owned) continue;
      for (const required of skin.requires) {
        const s = skinState(entry, required);
        s.owned = true;
        s.star = clamp(Math.max(s.star, entry.skins[key].star), 1, skins[required].maxStar);
      }
    }
    let slots = entry.slots.filter((key) => skins[key] && entry.skins[key].owned && BUILD_SLOTS[skins[key].slot]);
    const locked = buildingLocks(building, { slots });
    slots = slots.filter((key) => !locked.has(key));
    const used = { red: 0, gold: 0, special: 0 };
    entry.slots = slots.filter((key) => ++used[skins[key].slot] <= BUILD_SLOTS[skins[key].slot]);
  }

  function buildingForced(building, entry) {
    const skins = buildSkins(building);
    const forced = { [defaultBuildSkin(building)]: 1, [entry.worn]: 1 };
    for (const [key, skin] of Object.entries(skins)) {
      if (!skin.requires || !entry.skins[key]?.owned) continue;
      for (const required of skin.requires) forced[required] = Math.max(forced[required] || 1, entry.skins[key].star);
    }
    return forced;
  }

  function normalize() {
    if (state.heroes) state.heroes.forEach(normalizeHero);
    for (const [building] of BUILDINGS) if (state.buildings[building]) normalizeBuilding(building, state.buildings[building]);
  }

  function toProfile() {
    const profile = {};
    if (state.map) profile.map = { mode: "campaign", stage: state.map.stage };
    if (state.heroes) {
      profile.heroes = state.heroes.map((hero) => {
        if (!hero.custom) return hero.name;
        const skins = heroSkins(hero.name);
        const out = { name: hero.name };
        if (hero.worn) Object.assign(out, { skin: hero.worn, star: hero.skins[hero.worn].star });
        const owned = Object.keys(skins).filter((key) => key !== hero.worn && hero.skins[key]?.owned);
        if (owned.length) out.ownedSkins = Object.fromEntries(owned.map((key) => [key, hero.skins[key].star]));
        // Slot order: normal skins in config order, then the colorful one (skin-profile.js default order).
        out.slots = [
          ...hero.slots.filter((key) => isNormalHeroSkin(skins[key])),
          ...hero.slots.filter((key) => !isNormalHeroSkin(skins[key])),
        ];
        return out;
      });
    }
    if (state.traps) profile.traps = state.traps.map(({ name, level, star }) => ({ name, level, star }));
    if (state.pets) profile.pets = state.pets.map(({ name, level, star }) => ({ name, level, star }));
    if (state.spells) profile.spells = state.spells.map(({ name, star }) => ({ name, star }));
    const buildings = {};
    for (const [building] of BUILDINGS) {
      const entry = state.buildings[building];
      if (!entry) continue;
      const skins = buildSkins(building);
      const base = defaultBuildSkin(building);
      const out = {};
      if (entry.worn !== base) Object.assign(out, { skin: entry.worn, star: entry.skins[entry.worn].star });
      const owned = Object.keys(skins).filter((key) => key !== base && key !== entry.worn && entry.skins[key]?.owned);
      if (owned.length) out.ownedSkins = Object.fromEntries(owned.map((key) => [key, entry.skins[key].star]));
      out.slots = ["red", "gold", "special"].flatMap((slot) => entry.slots.filter((key) => skins[key].slot === slot));
      buildings[building] = out;
    }
    if (Object.keys(buildings).length) profile.buildings = buildings;
    if (state.goldenSkinsCount !== null) profile.goldenSkinsCount = state.goldenSkinsCount;
    return profile;
  }

  // Lenient import of a profile JSON (as written by toProfile or by hand). Unknown names throw.
  function fromProfile(profile, base = emptyState()) {
    const next = { ...emptyState(), battle: base.battle, seed: base.seed };
    const need = (group, name) => {
      if (!Object.hasOwn(dict[group], name)) throw new Error(`Không có ${group} "${name}" trong profile-dict.json`);
      return name;
    };
    const entryOf = (item) => (typeof item === "string" ? { name: item } : item || {});
    if (profile.map) next.map = { stage: Number(profile.map.stage) || dict.maps.campaign.minStage };
    if (Array.isArray(profile.heroes)) {
      next.heroes = profile.heroes.slice(0, LIMITS.heroes).map((item) => {
        const sel = entryOf(item);
        const hero = newHero(need("heroes", sel.name));
        const skins = heroSkins(hero.name);
        hero.custom = ["skin", "star", "ownedSkins", "slots"].some((key) => sel[key] !== undefined);
        if (!hero.custom) return hero;
        const skinName = (key) => {
          if (!skins[key]) throw new Error(`Hero ${hero.name} không có skin "${key}"`);
          return key;
        };
        for (const [key, star] of Object.entries(sel.ownedSkins || {})) Object.assign(skinState(hero, skinName(key)), { owned: true, star });
        if (sel.skin !== undefined) {
          hero.worn = skinName(sel.skin);
          Object.assign(skinState(hero, hero.worn), { owned: true, star: sel.star ?? 1 });
        }
        normalizeHero(hero); // raises required skins before default slots are picked
        hero.slots = sel.slots !== undefined ? sel.slots.map(skinName) : Object.keys(skins).filter((key) => hero.skins[key].owned);
        return hero;
      });
    }
    for (const group of ["traps", "pets"]) {
      if (Array.isArray(profile[group])) {
        next[group] = profile[group].slice(0, LIMITS[group]).map((item) => {
          const { name, level = 1, star = 1 } = entryOf(item);
          return { name: need(group, name), level, star };
        });
      }
    }
    if (Array.isArray(profile.spells)) {
      next.spells = profile.spells.slice(0, LIMITS.spells).map((item) => {
        const { name, star = 1 } = entryOf(item);
        return { name: need("spells", name), star };
      });
    }
    for (const [building, sel] of Object.entries(profile.buildings || {})) {
      if (!dict.buildings[building]) throw new Error(`Không có building "${building}"`);
      const skins = buildSkins(building);
      const skinName = (key) => {
        if (!skins[key]) throw new Error(`Building ${building} không có skin "${key}"`);
        return key;
      };
      const entry = newBuilding(building);
      for (const [key, star] of Object.entries(sel.ownedSkins || {})) Object.assign(skinState(entry, skinName(key)), { owned: true, star });
      if (sel.skin !== undefined) {
        entry.worn = skinName(sel.skin);
        Object.assign(skinState(entry, entry.worn), { owned: true, star: sel.star ?? 1 });
      }
      normalizeBuilding(building, entry);
      entry.slots = sel.slots !== undefined ? sel.slots.map(skinName) : defaultBuildingSlots(building, entry);
      next.buildings[building] = entry;
    }
    if (Number.isSafeInteger(profile.goldenSkinsCount)) next.goldenSkinsCount = profile.goldenSkinsCount;
    return next;
  }

  // build-skin-profile.js default: colorful first, then config order, filling 1 red / 2 gold / 1 special.
  function defaultBuildingSlots(building, entry) {
    const skins = buildSkins(building);
    const keys = Object.keys(skins).filter((key) => entry.skins[key]?.owned && BUILD_SLOTS[skins[key].slot]);
    keys.sort((a, b) => (skins[b].color === "colorful") - (skins[a].color === "colorful"));
    const chosen = [];
    const used = { red: 0, gold: 0, special: 0 };
    for (const key of keys) {
      if (buildingLocks(building, { slots: chosen }).has(key)) continue;
      if (used[skins[key].slot] >= BUILD_SLOTS[skins[key].slot]) continue;
      used[skins[key].slot]++;
      chosen.push(key);
    }
    const locked = buildingLocks(building, { slots: chosen });
    return chosen.filter((key) => !locked.has(key));
  }

  // ---------- capture prefill ----------

  async function capturedStart() {
    if (!state.battle) return null;
    if (!captures.has(state.battle)) {
      const response = await fetch(`/__sim/battle/${state.battle}.json`);
      captures.set(state.battle, response.ok ? (await response.json()).start : null);
    }
    return captures.get(state.battle);
  }

  const listItems = (list) => Array.from({ length: list?._length || 0 }, (_, i) => list[String(i)]);
  const nameByCode = (group, code) => Object.keys(dict[group]).find((key) => dict[group][key].code === code);

  async function prefill(group) {
    const start = await capturedStart();
    const player = start && listItems(start.playerInfos)[0];
    if (group === "map") return { stage: start?.level || dict.maps.campaign.minStage };
    if (!player) return [];
    const from = {
      heroes: () => listItems(player.heros).map((h) => nameByCode("heroes", h.code)).filter(Boolean).map(newHero),
      traps: () => listItems(player.organs).map((o) => ({ name: nameByCode("traps", o.code), level: o.level, star: o.star })),
      pets: () => listItems(player.summonCreatures).map((p) => ({ name: nameByCode("pets", p.code), level: p.level, star: p.star })),
      spells: () => listItems(player.daoists).map((d) => ({ name: nameByCode("spells", d.code), star: d.star })),
    }[group];
    return from().filter((item) => item.name).slice(0, LIMITS[group]);
  }

  // ---------- rendering ----------

  function el(tag, attrs = {}, ...children) {
    const node = document.createElement(tag);
    for (const [key, value] of Object.entries(attrs)) {
      if (value === undefined || value === null || value === false) continue;
      if (key.startsWith("on")) node.addEventListener(key.slice(2), value);
      else if (key === "class") node.className = value;
      else if (key in node && typeof value !== "string") node[key] = value;
      else node.setAttribute(key, value === true ? "" : value);
    }
    for (const child of children.flat()) if (child !== null && child !== undefined && child !== false) node.append(child);
    return node;
  }

  const clamp = (value, min, max) => Math.min(max, Math.max(min, Math.round(Number(value)) || min));
  const label = (item) => [item.name_vn || item.name, item.name_vn && item.name !== item.name_vn ? el("span", { class: "en" }, ` ${item.name}`) : null];
  const optionText = (item) => (item.name_vn && item.name_vn !== item.name ? `${item.name_vn} (${item.name})` : item.name);
  const colorTag = (color) => el("span", { class: `tag c-${color}` }, COLOR_LABEL[color] || color);

  function numberInput(value, min, max, onChange, disabled) {
    return el("input", {
      type: "number", value, min, max, step: 1, disabled,
      onchange: (e) => onChange(clamp(e.target.value, min, max)),
    });
  }

  // options: [value, text, disabled?]
  // options: [value, text, disabled?, group?]; consecutive options with a group go in one <optgroup>.
  function selectOf(options, value, onChange, attrs = {}) {
    const children = [];
    for (const [key, text, disabled, group] of options) {
      const option = el("option", { value: key, selected: key === value, disabled }, text);
      if (!group) { children.push(option); continue; }
      let last = children[children.length - 1];
      if (!last || last.tagName !== "OPTGROUP" || last.label !== group) children.push(last = el("optgroup", { label: group }));
      last.append(option);
    }
    return el("select", { ...attrs, onchange: (e) => onChange(e.target.value) }, children);
  }

  function section(title, hint, enabled, onToggle, body) {
    return el("section", { class: enabled ? "" : "off" },
      el("header", {},
        el("h2", {}, title),
        el("label", {}, el("input", { type: "checkbox", checked: enabled, onchange: (e) => onToggle(e.target.checked) }), "Ghi đè"),
        hint ? el("span", { class: "hint" }, hint) : null),
      el("div", { class: "body" }, enabled ? body() : []));
  }

  function commit() {
    normalize();
    try { localStorage.setItem(STORE_KEY, JSON.stringify({ battle: state.battle, seed: state.seed, profile: toProfile() })); } catch { /* storage off */ }
    render();
  }

  async function toggleWithPrefill(group, on) {
    state[group] = on ? await prefill(group) : null;
    commit();
  }

  function render() {
    $("form").replaceChildren(
      mapSection(), heroesSection(),
      ...["traps", "pets", "spells"].map(listSection),
      buildingsSection(), goldenSection());
    renderSide();
  }

  function mapSection() {
    const { minStage, maxStage } = dict.maps.campaign;
    return section("Màn chơi", "Campaign; tắt = stage của capture", !!state.map, (on) => toggleWithPrefill("map", on), () => [
      el("div", { class: "row" },
        el("label", {}, "Mode ", selectOf([["campaign", "Campaign"]], "campaign", () => {})),
        el("label", {}, `Stage (${minStage}–${maxStage}) `, numberInput(state.map.stage, minStage, maxStage, (v) => { state.map.stage = v; commit(); }))),
    ]);
  }

  function nameOptions(group, chosen, current) {
    const entries = Object.entries(dict[group]).map(([key, item]) => [key, optionText(item), key !== current && chosen.includes(key)]);
    if (!entries.some(([key]) => dict[group][key].color)) return entries;
    return RARITY_GROUPS.flatMap(([color, title]) => entries
      .filter(([key]) => dict[group][key].color === color)
      .map((entry) => [...entry, group === "heroes" && color === "red" ? `${title} (có skin)` : title]));
  }

  function addButton(group, make) {
    const list = state[group];
    const unused = Object.keys(dict[group]).find((key) => !list.some((item) => item.name === key));
    return el("button", {
      disabled: list.length >= LIMITS[group] || !unused,
      onclick: () => { list.push(make(unused)); commit(); },
    }, `+ Thêm (${list.length}/${LIMITS[group]})`);
  }

  function removeButton(group, index) {
    return el("button", { class: "x", title: "Bỏ", onclick: () => { state[group].splice(index, 1); commit(); } }, "×");
  }

  function listSection(group) {
    const catalog = dict[group];
    return section(LIST_TITLES[group], `tối đa ${LIMITS[group]}; tắt = giữ từ capture`, !!state[group], (on) => toggleWithPrefill(group, on), () => [
      ...state[group].map((item, i) => {
        const info = catalog[item.name];
        return el("div", { class: "row" },
          selectOf(nameOptions(group, state[group].map((x) => x.name), item.name), item.name, (v) => { item.name = v; commit(); }),
          info.maxLevel ? el("label", {}, "Level ", numberInput(item.level, 1, info.maxLevel, (v) => { item.level = v; commit(); })) : null,
          el("label", {}, "Sao ", numberInput(item.star, 1, info.maxStar, (v) => { item.star = v; commit(); })),
          el("span", { class: "note" }, `max lv ${info.maxLevel || "-"} / ${info.maxStar}★`),
          removeButton(group, i));
      }),
      el("div", { class: "row" }, addButton(group, (name) => (group === "spells" ? { name, star: 1 } : { name, level: 1, star: 1 }))),
    ]);
  }

  function heroesSection() {
    return section("Hero", "tối đa 5; tắt = đội hình capture", !!state.heroes, (on) => toggleWithPrefill("heroes", on), () => [
      ...state.heroes.map(heroCard),
      el("div", { class: "row" }, addButton("heroes", newHero)),
      el("div", { class: "note" }, "Hero có trong capture giữ chỉ số và skill gốc; hero khác dùng chỉ số level 1. " +
        "Không tick \"Tùy chỉnh skin\" thì giữ skin từ capture."),
    ]);
  }

  function heroCard(hero, index) {
    const skins = heroSkins(hero.name);
    const hasSkins = Object.keys(skins).length > 0;
    return el("div", { class: "card" },
      el("div", { class: "row" },
        el("strong", {}, `#${index + 1}`),
        selectOf(nameOptions("heroes", state.heroes.map((h) => h.name), hero.name), hero.name, (v) => {
          state.heroes[index] = newHero(v);
          commit();
        }),
        hasSkins
          ? el("label", {}, el("input", { type: "checkbox", checked: hero.custom, onchange: (e) => { hero.custom = e.target.checked; commit(); } }), "Tùy chỉnh skin")
          : el("span", { class: "note" }, "không có skin"),
        removeButton("heroes", index)),
      hero.custom && hasSkins ? heroSkinTable(hero) : null);
  }

  function heroSkinTable(hero) {
    const skins = heroSkins(hero.name);
    const forced = heroForced(hero);
    const count = (kind) => hero.slots.filter((key) => (isNormalHeroSkin(skins[key]) ? "normal" : "colorful") === kind).length;
    const wornOptions = [["", "model gốc"], ...Object.entries(skins).map(([key, skin]) => [key, optionText(skin)])];
    return el("div", {},
      el("div", { class: "row" },
        el("label", {}, "Đang mặc ", selectOf(wornOptions, hero.worn || "", (v) => { hero.worn = v || null; commit(); })),
        el("span", { class: "note" }, `Slot: ${count("normal")}/${HERO_SLOTS.normal} thường, ${count("colorful")}/${HERO_SLOTS.colorful} 7 màu`)),
      el("table", {},
        el("tr", {}, ["Skin", "Màu", "Sở hữu", "Sao", "Slot"].map((h) => el("th", {}, h))),
        Object.entries(skins).map(([key, skin]) => {
          const s = hero.skins[key];
          const kind = isNormalHeroSkin(skin) ? "normal" : "colorful";
          const slotted = hero.slots.includes(key);
          return el("tr", {},
            el("td", { class: "name" }, label(skin), skin.requires ? el("div", { class: "note" }, `cần: ${skin.requires.map((r) => skins[r].name_vn || skins[r].name).join(", ")}`) : null),
            el("td", {}, colorTag(skin.color)),
            el("td", {}, el("input", {
              type: "checkbox", checked: s.owned, disabled: key in forced,
              title: key in forced ? "Bắt buộc (đang mặc hoặc skin 7 màu yêu cầu)" : null,
              onchange: (e) => { s.owned = e.target.checked; if (!s.owned) hero.slots = hero.slots.filter((k) => k !== key); commit(); },
            })),
            el("td", {}, numberInput(s.star, forced[key] || 1, skin.maxStar, (v) => { s.star = v; commit(); }, !s.owned),
              el("span", { class: "note" }, ` /${skin.maxStar}`)),
            el("td", {}, el("input", {
              type: "checkbox", checked: slotted, disabled: !s.owned || (!slotted && count(kind) >= HERO_SLOTS[kind]),
              onchange: (e) => { hero.slots = e.target.checked ? [...hero.slots, key] : hero.slots.filter((k) => k !== key); commit(); },
            })));
        })),
      el("div", { class: "note" }, "Skin 7 màu cần 3 skin thường ở sao ≥ sao của nó; trang tự nâng. Skill đi theo slot, không theo skin đang mặc."));
  }

  function buildingsSection() {
    const any = BUILDINGS.some(([key]) => state.buildings[key]);
    return el("section", {},
      el("header", {}, el("h2", {}, "Skin building"), el("span", { class: "hint" }, "mỗi building bật riêng; tắt = giữ từ capture")),
      el("div", { class: "body" },
        BUILDINGS.map(([key, title]) => buildingCard(key, title)),
        any ? el("div", { class: "note" }, "Slot: 1 đỏ, 2 vàng, 1 loại 3. Skin 7 màu dùng slot vàng và khoá 3 skin yêu cầu khỏi mọi slot. " +
          "Chỉ số building (attr) và skill do server thêm vẫn giữ từ capture.") : null));
  }

  function buildingCard(building, title) {
    const entry = state.buildings[building];
    return el("div", { class: "card" },
      el("div", { class: "row" },
        el("strong", {}, title),
        el("label", {}, el("input", {
          type: "checkbox", checked: !!entry,
          onchange: (e) => { state.buildings[building] = e.target.checked ? newBuilding(building) : null; commit(); },
        }), "Ghi đè")),
      entry ? buildingSkinTable(building, entry) : null);
  }

  function buildingSkinTable(building, entry) {
    const skins = buildSkins(building);
    const forced = buildingForced(building, entry);
    const locked = buildingLocks(building, entry);
    const count = (slot) => entry.slots.filter((key) => skins[key].slot === slot).length;
    const wornOptions = Object.entries(skins).map(([key, skin]) => [key, optionText(skin)]);
    return el("div", {},
      el("div", { class: "row" },
        el("label", {}, "Đang mặc ", selectOf(wornOptions, entry.worn, (v) => { entry.worn = v; commit(); })),
        el("span", { class: "note" }, `Slot: ${count("red")}/1 đỏ, ${count("gold")}/2 vàng, ${count("special")}/1 loại 3`)),
      el("table", {},
        el("tr", {}, ["Skin", "Màu / slot", "Sở hữu", "Sao", "Slot"].map((h) => el("th", {}, h))),
        Object.entries(skins).map(([key, skin]) => {
          const s = entry.skins[key];
          const slotted = entry.slots.includes(key);
          const slottable = !!BUILD_SLOTS[skin.slot];
          const full = count(skin.slot) >= BUILD_SLOTS[skin.slot];
          return el("tr", {},
            el("td", { class: "name" }, label(skin), skin.requires ? el("div", { class: "note" }, `cần: ${skin.requires.map((r) => skins[r].name_vn || skins[r].name).join(", ")}`) : null),
            el("td", {}, colorTag(skin.color), slottable && skin.slot !== skin.color ? el("span", { class: "note" }, ` slot ${COLOR_LABEL[skin.slot] || skin.slot}`) : null),
            el("td", {}, el("input", {
              type: "checkbox", checked: s.owned, disabled: key in forced,
              onchange: (e) => { s.owned = e.target.checked; if (!s.owned) entry.slots = entry.slots.filter((k) => k !== key); commit(); },
            })),
            el("td", {}, numberInput(s.star, forced[key] || 1, skin.maxStar, (v) => { s.star = v; commit(); }, !s.owned || skin.default),
              el("span", { class: "note" }, ` /${skin.maxStar}`)),
            el("td", {}, !slottable ? el("span", { class: "note" }, "-") : locked.has(key) ? el("span", { class: "warn" }, "khoá") : el("input", {
              type: "checkbox", checked: slotted, disabled: !s.owned || (!slotted && full),
              onchange: (e) => { entry.slots = e.target.checked ? [...entry.slots, key] : entry.slots.filter((k) => k !== key); commit(); },
            })));
        })));
  }

  function goldenSection() {
    const on = state.goldenSkinsCount !== null;
    return section("goldenSkinsCount", "tăng sát thương pet; server tự tính, chưa rõ cách", on, (v) => { state.goldenSkinsCount = v ? 0 : null; commit(); }, () => [
      el("div", { class: "row" }, el("label", {}, "Số skin vàng ", numberInput(state.goldenSkinsCount, 0, 999, (v) => { state.goldenSkinsCount = v; commit(); }))),
    ]);
  }

  // ---------- side panel ----------

  function warnings(profile) {
    const out = [];
    if (profile.heroes && !profile.heroes.length) out.push("Cần ít nhất 1 hero (hoặc tắt Ghi đè).");
    if (!state.battle) out.push("Chưa có capture nào để làm trận gốc.");
    return out;
  }

  function renderSide() {
    const profile = toProfile();
    $("output").textContent = JSON.stringify(profile, null, 2);
    const problems = warnings(profile);
    const canPlay = typeof window.simPlay === "function";
    $("play").disabled = !canPlay || problems.length > 0;
    $("battle").value = state.battle;
    $("seed").value = state.seed;
    const seedArg = state.seed ? ` --seed ${state.seed}` : "";
    $("playHint").replaceChildren(...(canPlay ? [] : [
      "Nút Chơi chỉ chạy khi mở qua ", el("code", {}, "uv run python battle_sim/sandbox.py --setup"),
      ". Hoặc tải JSON rồi chạy: ",
      el("code", {}, `uv run python battle_sim/sandbox.py --battle ${state.battle || "<uuid>"} --play${seedArg} --profile <file>.json`),
    ]));
    if (problems.length) setStatus(problems.join(" "), "warn");
    else if ($("status").dataset.kind === "warn") setStatus("");
  }

  function setStatus(text, kind = "note") {
    $("status").textContent = text;
    $("status").className = `status ${kind}`;
    $("status").dataset.kind = kind;
  }

  function wireSide() {
    $("battle").replaceChildren(...battles.map((b) => el("option", { value: b.uuid },
      `${b.uuid.slice(0, 8)}… · capture ở Stage ${b.level} · ${b.ops} op`)));
    if (!battles.length) $("battle").append(el("option", { value: "" }, "(không có capture)"));
    $("battle").addEventListener("change", (e) => { state.battle = e.target.value; commit(); });
    $("seed").addEventListener("change", (e) => { state.seed = e.target.value; commit(); });
    $("download").addEventListener("click", () => {
      const blob = new Blob([JSON.stringify(toProfile(), null, 2) + "\n"], { type: "application/json" });
      const link = el("a", { href: URL.createObjectURL(blob), download: "profile.json" });
      link.click();
      setTimeout(() => URL.revokeObjectURL(link.href), 1000);
    });
    $("copy").addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(JSON.stringify(toProfile(), null, 2));
        setStatus("Đã sao chép profile.", "note");
      } catch (e) {
        setStatus(`Không sao chép được: ${e.message}`, "err");
      }
    });
    $("importBtn").addEventListener("click", () => $("importFile").click());
    $("importFile").addEventListener("change", async (e) => {
      const file = e.target.files[0];
      e.target.value = "";
      if (!file) return;
      try {
        state = fromProfile(JSON.parse(await file.text()), state);
        commit();
        setStatus(`Đã nhập ${file.name}.`, "note");
      } catch (err) {
        setStatus(`Không nhập được ${file.name}: ${err.message}`, "err");
      }
    });
    $("reset").addEventListener("click", () => {
      state = { ...emptyState(), battle: state.battle, seed: state.seed };
      commit();
    });
    $("play").addEventListener("click", async () => {
      $("play").disabled = true;
      setStatus("Đang lưu profile và mở trận…", "note");
      try {
        const saved = await window.simPlay({ battle: state.battle, seed: state.seed || null, profile: toProfile() });
        setStatus(`Đã lưu ${saved}. Đang mở trận…`, "note");
      } catch (err) {
        setStatus(`Không mở được trận: ${err.message}`, "err");
        $("play").disabled = false;
      }
    });
  }

  // ---------- boot ----------

  async function getJson(url) {
    const response = await fetch(url, { cache: "no-store" });
    if (!response.ok) throw new Error(`${url}: HTTP ${response.status}`);
    return response.json();
  }

  async function savedSetup() {
    try {
      const stored = JSON.parse(localStorage.getItem(STORE_KEY) || "null");
      if (stored) return stored;
    } catch { /* storage off */ }
    try { return await getJson("/__sim/last-setup.json"); } catch { return null; } // written by sandbox.py --setup
  }

  async function main() {
    [dict, battles] = await Promise.all([
      getJson("/__sim/profile-dict.json"),
      getJson("/__sim/battles.json").catch(() => []),
    ]);
    state = emptyState();
    const saved = await savedSetup();
    if (saved) {
      try {
        state = fromProfile(saved.profile || {}, { battle: saved.battle || "", seed: saved.seed || "" });
      } catch (err) {
        setStatus(`Bỏ qua profile đã lưu: ${err.message}`, "err");
      }
    }
    if (!battles.some((b) => b.uuid === state.battle)) state.battle = battles[0]?.uuid || "";
    wireSide();
    commit();
  }

  main().catch((err) => {
    $("form").replaceChildren(el("p", { class: "err" }, `Lỗi tải trang: ${err.message}`));
  });
})();
