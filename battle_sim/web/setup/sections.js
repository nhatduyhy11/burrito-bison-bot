// Form sections of the setup page: stage, heroes (with the skin table), traps / pets / spells,
// building skins and goldenSkinsCount. formSections(ctx) builds them from ctx.state, where
// ctx = { state, dict, commit(), toggleWithPrefill(group, on) } (state is read on every call).
(function () {
  "use strict";
  const S = (window.SimSetup = window.SimSetup || {});
  const { el, label, optionText, colorTag, numberInput, selectOf, section } = S;

  const LIST_TITLES = { traps: "Trap", pets: "Pet", spells: "Spell (thần)" };
  // Rarity groups in the hero / trap / pet pickers (card border in game), highest first. Spells have none.
  const RARITY_GROUPS = [["gold", "Vàng"], ["red", "Đỏ"], ["orange", "Cam"], ["purple", "Tím"]];

  function formSections(ctx) {
    return [
      mapSection(ctx), heroesSection(ctx),
      ...["traps", "pets", "spells"].map((group) => listSection(ctx, group)),
      buildingsSection(ctx), goldenSection(ctx),
    ];
  }

  function mapSection(ctx) {
    const { state, dict, commit } = ctx;
    const { minStage, maxStage } = dict.maps.campaign;
    return section("Màn chơi", "Campaign; tắt = stage của capture", !!state.map, (on) => ctx.toggleWithPrefill("map", on), () => [
      el("div", { class: "row" },
        el("label", {}, "Mode ", selectOf([["campaign", "Campaign"]], "campaign", () => {})),
        el("label", {}, `Stage (${minStage}–${maxStage}) `, numberInput(state.map.stage, minStage, maxStage, (v) => { state.map.stage = v; commit(); }))),
    ]);
  }

  function nameOptions(dict, group, chosen, current) {
    const entries = Object.entries(dict[group]).map(([key, item]) => [key, optionText(item), key !== current && chosen.includes(key)]);
    if (!entries.some(([key]) => dict[group][key].color)) return entries;
    return RARITY_GROUPS.flatMap(([color, title]) => entries
      .filter(([key]) => dict[group][key].color === color)
      .map((entry) => [...entry, group === "heroes" && color === "red" ? `${title} (có skin)` : title]));
  }

  function addButton(ctx, group, make) {
    const list = ctx.state[group];
    const unused = Object.keys(ctx.dict[group]).find((key) => !list.some((item) => item.name === key));
    return el("button", {
      disabled: list.length >= S.LIMITS[group] || !unused,
      onclick: () => { list.push(make(unused)); ctx.commit(); },
    }, `+ Thêm (${list.length}/${S.LIMITS[group]})`);
  }

  function removeButton(ctx, group, index) {
    return el("button", { class: "x", title: "Bỏ", onclick: () => { ctx.state[group].splice(index, 1); ctx.commit(); } }, "×");
  }

  function listSection(ctx, group) {
    const { state, dict, commit } = ctx;
    const catalog = dict[group];
    return section(LIST_TITLES[group], `tối đa ${S.LIMITS[group]}; tắt = giữ từ capture`, !!state[group], (on) => ctx.toggleWithPrefill(group, on), () => [
      ...state[group].map((item, i) => {
        const info = catalog[item.name];
        return el("div", { class: "row" },
          selectOf(nameOptions(dict, group, state[group].map((x) => x.name), item.name), item.name, (v) => { item.name = v; commit(); }),
          info.maxLevel ? el("label", {}, "Level ", numberInput(item.level, 1, info.maxLevel, (v) => { item.level = v; commit(); })) : null,
          el("label", {}, "Sao ", numberInput(item.star, 1, info.maxStar, (v) => { item.star = v; commit(); })),
          el("span", { class: "note" }, `max lv ${info.maxLevel || "-"} / ${info.maxStar}★`),
          removeButton(ctx, group, i));
      }),
      el("div", { class: "row" }, addButton(ctx, group, (name) => (group === "spells" ? { name, star: 1 } : { name, level: 1, star: 1 }))),
    ]);
  }

  // ---------- heroes ----------

  function heroesSection(ctx) {
    const { state } = ctx;
    return section("Hero", "tối đa 5; tắt = đội hình capture", !!state.heroes, (on) => ctx.toggleWithPrefill("heroes", on), () => [
      ...state.heroes.map((hero, index) => heroCard(ctx, hero, index)),
      el("div", { class: "row" }, addButton(ctx, "heroes", S.newHero)),
      el("div", { class: "note" }, "Hero có trong capture giữ chỉ số và skill gốc; hero khác mượn chỉ số trung bình, level và level skill của các hero cùng độ hiếm trong capture (gần đúng, ±10%). " +
        "Không tick \"Tùy chỉnh skin\" thì giữ skin từ capture."),
    ]);
  }

  function heroCard(ctx, hero, index) {
    const { state, dict, commit } = ctx;
    const skins = S.heroSkins(dict, hero.name);
    const hasSkins = Object.keys(skins).length > 0;
    return el("div", { class: "card" },
      el("div", { class: "row" },
        el("strong", {}, `#${index + 1}`),
        selectOf(nameOptions(dict, "heroes", state.heroes.map((h) => h.name), hero.name), hero.name, (v) => {
          state.heroes[index] = S.newHero(v);
          commit();
        }),
        hasSkins
          ? el("label", {}, el("input", { type: "checkbox", checked: hero.custom, onchange: (e) => { hero.custom = e.target.checked; commit(); } }), "Tùy chỉnh skin")
          : el("span", { class: "note" }, "không có skin"),
        removeButton(ctx, "heroes", index)),
      hero.custom && hasSkins ? heroSkinTable(ctx, hero, skins) : null);
  }

  function heroSkinTable(ctx, hero, skins) {
    const { commit } = ctx;
    const forced = S.heroForced(hero, skins);
    const slotForced = S.heroSlotForced(hero, skins);
    const count = (kind) => hero.slots.filter((key) => S.heroSlotKind(skins[key]) === kind).length;
    const wornOptions = [["", "model gốc"], ...Object.entries(skins).map(([key, skin]) => [key, optionText(skin)])];
    return el("div", {},
      el("div", { class: "row" },
        el("label", {}, "Đang mặc ", selectOf(wornOptions, hero.worn || "", (v) => { hero.worn = v || null; commit(); })),
        el("span", { class: "note" }, `Slot: ${count("normal")}/${S.HERO_SLOTS.normal} thường, ${count("colorful")}/${S.HERO_SLOTS.colorful} 7 màu`)),
      el("table", {},
        el("tr", {}, ["Skin", "Màu", "Sở hữu", "Sao", "Slot"].map((h) => el("th", {}, h))),
        Object.entries(skins).map(([key, skin]) => {
          const s = hero.skins[key];
          const kind = S.heroSlotKind(skin);
          const slotted = hero.slots.includes(key);
          return el("tr", {},
            el("td", { class: "name" }, label(skin), requiresNote(skin, skins)),
            el("td", {}, colorTag(skin.color)),
            el("td", {}, el("input", {
              type: "checkbox", checked: s.owned, disabled: key in forced,
              title: key in forced ? "Bắt buộc (đang mặc hoặc skin 7 màu yêu cầu)" : null,
              onchange: (e) => { s.owned = e.target.checked; if (!s.owned) hero.slots = hero.slots.filter((k) => k !== key); commit(); },
            })),
            el("td", {}, numberInput(s.star, forced[key] || 1, skin.maxStar, (v) => { s.star = v; commit(); }, !s.owned),
              el("span", { class: "note" }, ` /${skin.maxStar}`)),
            el("td", {}, el("input", {
              type: "checkbox", checked: slotted, disabled: slotForced.has(key) || (!slotted && count(kind) >= S.HERO_SLOTS[kind]),
              title: slotForced.has(key) ? "Bắt buộc: skin 7 màu trong slot cần skin này" : null,
              onchange: (e) => {
                if (e.target.checked) s.owned = true;
                hero.slots = e.target.checked ? [...hero.slots, key] : hero.slots.filter((k) => k !== key);
                commit();
              },
            })));
        })),
      el("div", { class: "note" }, "Sở hữu: account có skin (cộng chỉ số). Slot: skill của skin vào trận. Skin 7 màu cần 3 skin thường ở sao ≥ sao của nó " +
        "(trang tự nâng); gắn slot 7 màu thì 3 skin đó cũng vào slot và bị khoá đến khi bỏ slot 7 màu."));
  }

  function requiresNote(skin, skins) {
    return skin.requires
      ? el("div", { class: "note" }, `cần: ${skin.requires.map((r) => skins[r].name_vn || skins[r].name).join(", ")}`)
      : null;
  }

  // ---------- buildings ----------

  function buildingsSection(ctx) {
    const any = S.BUILDINGS.some(([key]) => ctx.state.buildings[key]);
    return el("section", {},
      el("header", {}, el("h2", {}, "Skin building"), el("span", { class: "hint" }, "mỗi building bật riêng; tắt = giữ từ capture")),
      el("div", { class: "body" },
        S.BUILDINGS.map(([key, title]) => buildingCard(ctx, key, title)),
        any ? el("div", { class: "note" }, "Slot: 1 đỏ, 2 vàng, 1 loại 3. Skin 7 màu dùng slot vàng và khoá 3 skin yêu cầu khỏi mọi slot. " +
          "Chỉ số building (attr) và skill do server thêm vẫn giữ từ capture.") : null));
  }

  function buildingCard(ctx, building, title) {
    const { state, dict, commit } = ctx;
    const entry = state.buildings[building];
    return el("div", { class: "card" },
      el("div", { class: "row" },
        el("strong", {}, title),
        el("label", {}, el("input", {
          type: "checkbox", checked: !!entry,
          onchange: (e) => { state.buildings[building] = e.target.checked ? S.newBuilding(dict, building) : null; commit(); },
        }), "Ghi đè")),
      entry ? buildingSkinTable(ctx, entry, S.buildSkins(dict, building)) : null);
  }

  function buildingSkinTable(ctx, entry, skins) {
    const { commit } = ctx;
    const forced = S.buildingForced(entry, skins);
    const locked = S.buildingLocks(skins, entry.slots);
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
          const slottable = !!S.BUILD_SLOTS[skin.slot];
          const full = count(skin.slot) >= S.BUILD_SLOTS[skin.slot];
          return el("tr", {},
            el("td", { class: "name" }, label(skin), requiresNote(skin, skins)),
            el("td", {}, colorTag(skin.color), slottable && skin.slot !== skin.color ? el("span", { class: "note" }, ` slot ${S.COLOR_LABEL[skin.slot] || skin.slot}`) : null),
            el("td", {}, el("input", {
              type: "checkbox", checked: s.owned, disabled: key in forced,
              onchange: (e) => { s.owned = e.target.checked; if (!s.owned) entry.slots = entry.slots.filter((k) => k !== key); commit(); },
            })),
            el("td", {}, numberInput(s.star, forced[key] || 1, skin.maxStar, (v) => { s.star = v; commit(); }, !s.owned || skin.default),
              el("span", { class: "note" }, ` /${skin.maxStar}`)),
            el("td", {}, !slottable ? el("span", { class: "note" }, "-") : locked.has(key) ? el("span", { class: "warn" }, "khoá") : el("input", {
              type: "checkbox", checked: slotted, disabled: !slotted && full,
              onchange: (e) => {
                if (e.target.checked) s.owned = true;
                entry.slots = e.target.checked ? [...entry.slots, key] : entry.slots.filter((k) => k !== key);
                commit();
              },
            })));
        })));
  }

  function goldenSection(ctx) {
    const { state, commit } = ctx;
    const on = state.goldenSkinsCount !== null;
    return section("goldenSkinsCount", "tăng sát thương pet; server tự tính, chưa rõ cách", on, (v) => { state.goldenSkinsCount = v ? 0 : null; commit(); }, () => [
      el("div", { class: "row" }, el("label", {}, "Số skin vàng ", numberInput(state.goldenSkinsCount, 0, 999, (v) => { state.goldenSkinsCount = v; commit(); }))),
    ]);
  }

  S.formSections = formSections;
})();
