// Form sections of the setup page (Preact components): stage, heroes (with the skin table),
// traps / pets / spells, building skins and goldenSkinsCount. Each takes ctx =
// { state, dict, update(fn), toggleWithPrefill(group, on) }; update(fn) runs fn on a copy of the
// state (fn may also return a replacement), normalizes it with skin-rules and re-renders.
// Handlers are named consts above each template; templates only reference them.
(function () {
  "use strict";
  const S = (window.SimSetup = window.SimSetup || {});
  const { html, label, optionText, colorTag, NumberInput, Checkbox, Select, Section } = S;

  const LIST_TITLES = { traps: "Trap", pets: "Pet", spells: "Spell (thần)" };
  // Rarity groups in the hero / trap / pet pickers (card border in game), highest first. Spells have none.
  const RARITY_GROUPS = [
    ["gold", "Vàng"],
    ["red", "Đỏ"],
    ["orange", "Cam"],
    ["purple", "Tím"],
  ];
  const MODE_OPTIONS = [["campaign", "Campaign"]];
  const HERO_HEADERS = ["Skin", "Màu", "Sở hữu", "Sao", "Slot"];
  const BUILDING_HEADERS = ["Skin", "Màu / slot", "Sở hữu", "Sao", "Slot"];
  const noop = () => {};

  function headerRow(titles) {
    const cells = titles.map((t) => html`<th>${t}</th>`);
    return html`<tr>${cells}</tr>`;
  }
  const without = (list, key) => list.filter((k) => k !== key);

  function FormSections({ ctx }) {
    const lists = ["traps", "pets", "spells"].map(
      (group) => html`<${ListSection} key=${group} ctx=${ctx} group=${group} />`,
    );
    return html`
      <${MapSection} ctx=${ctx} />
      <${HeroesSection} ctx=${ctx} />
      ${lists}
      <${BuildingsSection} ctx=${ctx} />
      <${GoldenSection} ctx=${ctx} />
    `;
  }

  // ---------- stage ----------

  function MapSection({ ctx }) {
    const onToggle = (on) => ctx.toggleWithPrefill("map", on);
    return html`<${Section}
      title="Màn chơi"
      hint="Campaign; tắt = stage của capture"
      enabled=${!!ctx.state.map}
      onToggle=${onToggle}
    >
      <${MapBody} ctx=${ctx} />
    <//>`;
  }

  function MapBody({ ctx }) {
    const { state, dict, update } = ctx;
    const { minStage, maxStage } = dict.maps.campaign;
    const setStage = (v) => update((s) => void (s.map.stage = v));
    return html`<div class="row">
      <label>Mode <${Select} options=${MODE_OPTIONS} value="campaign" onChange=${noop} /></label>
      <label>
        ${`Stage (${minStage}–${maxStage}) `}
        <${NumberInput} value=${state.map.stage} min=${minStage} max=${maxStage} onChange=${setStage} />
      </label>
    </div>`;
  }

  // ---------- traps / pets / spells ----------

  function nameOptions(dict, group, chosen, current) {
    const entries = Object.entries(dict[group]).map(([key, item]) => [
      key,
      optionText(item),
      key !== current && chosen.includes(key),
    ]);
    if (!entries.some(([key]) => dict[group][key].color)) return entries;
    return RARITY_GROUPS.flatMap(([color, title]) =>
      entries
        .filter(([key]) => dict[group][key].color === color)
        .map((entry) => [...entry, group === "heroes" && color === "red" ? `${title} (có skin)` : title]),
    );
  }

  function AddButton({ ctx, group, make }) {
    const list = ctx.state[group];
    const unused = Object.keys(ctx.dict[group]).find((key) => !list.some((item) => item.name === key));
    const disabled = list.length >= S.LIMITS[group] || !unused;
    const add = () => ctx.update((s) => void s[group].push(make(unused)));
    return html`<button disabled=${disabled} onClick=${add}>${`+ Thêm (${list.length}/${S.LIMITS[group]})`}</button>`;
  }

  function RemoveButton({ ctx, group, index }) {
    const remove = () => ctx.update((s) => void s[group].splice(index, 1));
    return html`<button class="x" title="Bỏ" onClick=${remove}>×</button>`;
  }

  const newListItem = (group) => (name) => (group === "spells" ? { name, star: 1 } : { name, level: 1, star: 1 });

  function ListSection({ ctx, group }) {
    const onToggle = (on) => ctx.toggleWithPrefill(group, on);
    return html`<${Section}
      title=${LIST_TITLES[group]}
      hint=${`tối đa ${S.LIMITS[group]}; tắt = giữ từ capture`}
      enabled=${!!ctx.state[group]}
      onToggle=${onToggle}
    >
      <${ListBody} ctx=${ctx} group=${group} />
    <//>`;
  }

  function ListBody({ ctx, group }) {
    const rows = ctx.state[group].map(
      (item, index) => html`<${ListRow} key=${index} ctx=${ctx} group=${group} item=${item} index=${index} />`,
    );
    return html`
      ${rows}
      <div class="row"><${AddButton} ctx=${ctx} group=${group} make=${newListItem(group)} /></div>
    `;
  }

  function ListRow({ ctx, group, item, index }) {
    const { state, dict, update } = ctx;
    const info = dict[group][item.name];
    const options = nameOptions(dict, group, state[group].map((x) => x.name), item.name);
    const edit = (fn) => update((s) => void fn(s[group][index]));
    const setName = (v) => edit((x) => (x.name = v));
    const setLevel = (v) => edit((x) => (x.level = v));
    const setStar = (v) => edit((x) => (x.star = v));
    const level = info.maxLevel
      ? html`<label>Level <${NumberInput} value=${item.level} min=${1} max=${info.maxLevel} onChange=${setLevel} /></label>`
      : null;
    return html`<div class="row">
      <${Select} options=${options} value=${item.name} onChange=${setName} />
      ${level}
      <label>Sao <${NumberInput} value=${item.star} min=${1} max=${info.maxStar} onChange=${setStar} /></label>
      <span class="note">${`max lv ${info.maxLevel || "-"} / ${info.maxStar}★`}</span>
      <${RemoveButton} ctx=${ctx} group=${group} index=${index} />
    </div>`;
  }

  // ---------- heroes ----------

  function HeroesSection({ ctx }) {
    const onToggle = (on) => ctx.toggleWithPrefill("heroes", on);
    return html`<${Section}
      title="Hero"
      hint="tối đa 5; tắt = đội hình capture"
      enabled=${!!ctx.state.heroes}
      onToggle=${onToggle}
    >
      <${HeroesBody} ctx=${ctx} />
    <//>`;
  }

  function HeroesBody({ ctx }) {
    const cards = ctx.state.heroes.map(
      (hero, index) => html`<${HeroCard} key=${index} ctx=${ctx} hero=${hero} index=${index} />`,
    );
    return html`
      ${cards}
      <div class="row"><${AddButton} ctx=${ctx} group="heroes" make=${S.newHero} /></div>
      <div class="note">
        Hero có trong capture giữ chỉ số và skill gốc; hero khác mượn chỉ số trung bình, level và level skill của các
        hero cùng độ hiếm trong capture (gần đúng, ±10%). Không tick "Tùy chỉnh skin" thì giữ skin từ capture.
      </div>
    `;
  }

  function HeroCard({ ctx, hero, index }) {
    const { state, dict, update } = ctx;
    const skins = S.heroSkins(dict, hero.name);
    const hasSkins = Object.keys(skins).length > 0;
    const options = nameOptions(dict, "heroes", state.heroes.map((h) => h.name), hero.name);
    const edit = (fn) => update((s) => void fn(s.heroes[index]));
    const setName = (v) => update((s) => void (s.heroes[index] = S.newHero(v)));
    const setCustom = (on) => edit((h) => (h.custom = on));
    const custom = hasSkins
      ? html`<label><${Checkbox} checked=${hero.custom} onChange=${setCustom} />Tùy chỉnh skin</label>`
      : html`<span class="note">không có skin</span>`;
    const table = hero.custom && hasSkins ? html`<${HeroSkinTable} hero=${hero} skins=${skins} edit=${edit} />` : null;
    return html`<div class="card">
      <div class="row">
        <strong>${`#${index + 1}`}</strong>
        <${Select} options=${options} value=${hero.name} onChange=${setName} />
        ${custom}
        <${RemoveButton} ctx=${ctx} group="heroes" index=${index} />
      </div>
      ${table}
    </div>`;
  }

  function HeroSkinTable({ hero, skins, edit }) {
    const forced = S.heroForced(hero, skins);
    const slotForced = S.heroSlotForced(hero, skins);
    const count = (kind) => hero.slots.filter((key) => S.heroSlotKind(skins[key]) === kind).length;
    const wornOptions = [["", "model gốc"], ...Object.entries(skins).map(([key, skin]) => [key, optionText(skin)])];
    const setWorn = (v) => edit((h) => (h.worn = v || null));
    const slotNote = `Slot: ${count("normal")}/${S.HERO_SLOTS.normal} thường, ${count("colorful")}/${S.HERO_SLOTS.colorful} 7 màu`;
    const rows = Object.entries(skins).map(([key, skin]) => {
      const kind = S.heroSlotKind(skin);
      const slotted = hero.slots.includes(key);
      return html`<${HeroSkinRow}
        key=${key}
        skinKey=${key}
        skin=${skin}
        skins=${skins}
        state=${hero.skins[key]}
        forcedStar=${forced[key]}
        slotted=${slotted}
        slotLocked=${slotForced.has(key)}
        slotFull=${!slotted && count(kind) >= S.HERO_SLOTS[kind]}
        edit=${edit}
      />`;
    });
    return html`<div>
      <div class="row">
        <label>Đang mặc <${Select} options=${wornOptions} value=${hero.worn || ""} onChange=${setWorn} /></label>
        <span class="note">${slotNote}</span>
      </div>
      <table>
        <tbody>
          ${headerRow(HERO_HEADERS)}
          ${rows}
        </tbody>
      </table>
      <div class="note">
        Sở hữu: account có skin (cộng chỉ số). Slot: skill của skin vào trận. Skin 7 màu cần 3 skin thường ở sao ≥ sao
        của nó (trang tự nâng); gắn slot 7 màu thì 3 skin đó cũng vào slot và bị khoá đến khi bỏ slot 7 màu.
      </div>
    </div>`;
  }

  function HeroSkinRow({ skinKey: key, skin, skins, state, forcedStar, slotted, slotLocked, slotFull, edit }) {
    const isForced = forcedStar !== undefined;
    const setOwned = (on) =>
      edit((h) => {
        h.skins[key].owned = on;
        if (!on) h.slots = without(h.slots, key);
      });
    const setStar = (v) => edit((h) => (h.skins[key].star = v));
    const setSlotted = (on) =>
      edit((h) => {
        if (on) h.skins[key].owned = true;
        h.slots = on ? [...h.slots, key] : without(h.slots, key);
      });
    const ownedTitle = isForced ? "Bắt buộc (đang mặc hoặc skin 7 màu yêu cầu)" : null;
    const slotTitle = slotLocked ? "Bắt buộc: skin 7 màu trong slot cần skin này" : null;
    return html`<tr>
      <td class="name">${label(skin)}${requiresNote(skin, skins)}</td>
      <td>${colorTag(skin.color)}</td>
      <td><${Checkbox} checked=${state.owned} disabled=${isForced} title=${ownedTitle} onChange=${setOwned} /></td>
      <td>
        <${NumberInput}
          value=${state.star}
          min=${forcedStar || 1}
          max=${skin.maxStar}
          disabled=${!state.owned}
          onChange=${setStar}
        /><span class="note">${` /${skin.maxStar}`}</span>
      </td>
      <td>
        <${Checkbox}
          checked=${slotted}
          disabled=${slotLocked || slotFull}
          title=${slotTitle}
          onChange=${setSlotted}
        />
      </td>
    </tr>`;
  }

  function requiresNote(skin, skins) {
    if (!skin.requires) return null;
    const names = skin.requires.map((r) => skins[r].name_vn || skins[r].name).join(", ");
    return html`<div class="note">${`cần: ${names}`}</div>`;
  }

  // ---------- buildings ----------

  function BuildingsSection({ ctx }) {
    const any = S.BUILDINGS.some(([key]) => ctx.state.buildings[key]);
    const cards = S.BUILDINGS.map(
      ([key, title]) => html`<${BuildingCard} key=${key} ctx=${ctx} building=${key} title=${title} />`,
    );
    const note = any
      ? html`<div class="note">
          Slot: 1 đỏ, 2 vàng, 1 loại 3. Skin 7 màu dùng slot vàng và khoá 3 skin yêu cầu khỏi mọi slot. Chỉ số building
          (attr) và skill do server thêm vẫn giữ từ capture.
        </div>`
      : null;
    return html`<section>
      <header><h2>Skin building</h2><span class="hint">mỗi building bật riêng; tắt = giữ từ capture</span></header>
      <div class="body">
        ${cards}
        ${note}
      </div>
    </section>`;
  }

  function BuildingCard({ ctx, building, title }) {
    const { state, dict, update } = ctx;
    const entry = state.buildings[building];
    const edit = (fn) => update((s) => void fn(s.buildings[building]));
    const setEnabled = (on) => update((s) => void (s.buildings[building] = on ? S.newBuilding(dict, building) : null));
    const table = entry
      ? html`<${BuildingSkinTable} entry=${entry} skins=${S.buildSkins(dict, building)} edit=${edit} />`
      : null;
    return html`<div class="card">
      <div class="row">
        <strong>${title}</strong>
        <label><${Checkbox} checked=${!!entry} onChange=${setEnabled} />Ghi đè</label>
      </div>
      ${table}
    </div>`;
  }

  function BuildingSkinTable({ entry, skins, edit }) {
    const forced = S.buildingForced(entry, skins);
    const locked = S.buildingLocks(skins, entry.slots);
    const count = (slot) => entry.slots.filter((key) => skins[key].slot === slot).length;
    const wornOptions = Object.entries(skins).map(([key, skin]) => [key, optionText(skin)]);
    const setWorn = (v) => edit((e) => (e.worn = v));
    const slotNote = `Slot: ${count("red")}/1 đỏ, ${count("gold")}/2 vàng, ${count("special")}/1 loại 3`;
    const rows = Object.entries(skins).map(([key, skin]) => {
      const slotted = entry.slots.includes(key);
      return html`<${BuildingSkinRow}
        key=${key}
        skinKey=${key}
        skin=${skin}
        skins=${skins}
        state=${entry.skins[key]}
        forcedStar=${forced[key]}
        slotted=${slotted}
        locked=${locked.has(key)}
        slotFull=${!slotted && count(skin.slot) >= S.BUILD_SLOTS[skin.slot]}
        edit=${edit}
      />`;
    });
    return html`<div>
      <div class="row">
        <label>Đang mặc <${Select} options=${wornOptions} value=${entry.worn} onChange=${setWorn} /></label>
        <span class="note">${slotNote}</span>
      </div>
      <table>
        <tbody>
          ${headerRow(BUILDING_HEADERS)}
          ${rows}
        </tbody>
      </table>
    </div>`;
  }

  function BuildingSkinRow({ skinKey: key, skin, skins, state, forcedStar, slotted, locked, slotFull, edit }) {
    const slottable = !!S.BUILD_SLOTS[skin.slot];
    const setOwned = (on) =>
      edit((e) => {
        e.skins[key].owned = on;
        if (!on) e.slots = without(e.slots, key);
      });
    const setStar = (v) => edit((e) => (e.skins[key].star = v));
    const setSlotted = (on) =>
      edit((e) => {
        if (on) e.skins[key].owned = true;
        e.slots = on ? [...e.slots, key] : without(e.slots, key);
      });
    const slotLabel =
      slottable && skin.slot !== skin.color
        ? html`<span class="note">${` slot ${S.COLOR_LABEL[skin.slot] || skin.slot}`}</span>`
        : null;
    let slotCell = html`<${Checkbox} checked=${slotted} disabled=${slotFull} onChange=${setSlotted} />`;
    if (!slottable) slotCell = html`<span class="note">-</span>`;
    else if (locked) slotCell = html`<span class="warn">khoá</span>`;
    return html`<tr>
      <td class="name">${label(skin)}${requiresNote(skin, skins)}</td>
      <td>${colorTag(skin.color)}${slotLabel}</td>
      <td><${Checkbox} checked=${state.owned} disabled=${forcedStar !== undefined} onChange=${setOwned} /></td>
      <td>
        <${NumberInput}
          value=${state.star}
          min=${forcedStar || 1}
          max=${skin.maxStar}
          disabled=${!state.owned || skin.default}
          onChange=${setStar}
        /><span class="note">${` /${skin.maxStar}`}</span>
      </td>
      <td>${slotCell}</td>
    </tr>`;
  }

  // ---------- goldenSkinsCount ----------

  function GoldenSection({ ctx }) {
    const { state, update } = ctx;
    const onToggle = (on) => update((s) => void (s.goldenSkinsCount = on ? 0 : null));
    const setCount = (v) => update((s) => void (s.goldenSkinsCount = v));
    return html`<${Section}
      title="goldenSkinsCount"
      hint="tăng sát thương pet; server tự tính, chưa rõ cách"
      enabled=${state.goldenSkinsCount !== null}
      onToggle=${onToggle}
    >
      <div class="row">
        <label>Số skin vàng <${NumberInput} value=${state.goldenSkinsCount} min=${0} max=${999} onChange=${setCount} /></label>
      </div>
    <//>`;
  }

  S.FormSections = FormSections;
})();
