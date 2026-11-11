// Form sections of the setup page (Preact components): stage, heroes (with the skin table),
// traps / pets / spells, building skins and goldenSkinsCount. Each takes ctx =
// { state, dict, update(fn), toggleWithPrefill(group, on) }; update(fn) runs fn on a copy of the
// state (fn may also return a replacement), normalizes it with skin-rules and re-renders.
(function () {
  "use strict";
  const S = (window.SimSetup = window.SimSetup || {});
  const { html, label, optionText, colorTag, NumberInput, Checkbox, Select, Section } = S;

  const LIST_TITLES = { traps: "Trap", pets: "Pet", spells: "Spell (thần)" };
  // Rarity groups in the hero / trap / pet pickers (card border in game), highest first. Spells have none.
  const RARITY_GROUPS = [["gold", "Vàng"], ["red", "Đỏ"], ["orange", "Cam"], ["purple", "Tím"]];

  function FormSections({ ctx }) {
    return html`
      <${MapSection} ctx=${ctx} />
      <${HeroesSection} ctx=${ctx} />
      ${["traps", "pets", "spells"].map((group) => html`<${ListSection} key=${group} ctx=${ctx} group=${group} />`)}
      <${BuildingsSection} ctx=${ctx} />
      <${GoldenSection} ctx=${ctx} />`;
  }

  function MapSection({ ctx }) {
    const { state, dict, update } = ctx;
    const { minStage, maxStage } = dict.maps.campaign;
    return html`<${Section} title="Màn chơi" hint="Campaign; tắt = stage của capture" enabled=${!!state.map}
      onToggle=${(on) => ctx.toggleWithPrefill("map", on)}
      body=${() => html`<div class="row">
        <label>Mode <${Select} options=${[["campaign", "Campaign"]]} value="campaign" onChange=${() => {}} /></label>
        <label>${`Stage (${minStage}–${maxStage}) `}<${NumberInput} value=${state.map.stage} min=${minStage} max=${maxStage}
          onChange=${(v) => update((s) => { s.map.stage = v; })} /></label>
      </div>`} />`;
  }

  function nameOptions(dict, group, chosen, current) {
    const entries = Object.entries(dict[group]).map(([key, item]) => [key, optionText(item), key !== current && chosen.includes(key)]);
    if (!entries.some(([key]) => dict[group][key].color)) return entries;
    return RARITY_GROUPS.flatMap(([color, title]) => entries
      .filter(([key]) => dict[group][key].color === color)
      .map((entry) => [...entry, group === "heroes" && color === "red" ? `${title} (có skin)` : title]));
  }

  function AddButton({ ctx, group, make }) {
    const list = ctx.state[group];
    const unused = Object.keys(ctx.dict[group]).find((key) => !list.some((item) => item.name === key));
    return html`<button disabled=${list.length >= S.LIMITS[group] || !unused}
      onClick=${() => ctx.update((s) => { s[group].push(make(unused)); })}>${`+ Thêm (${list.length}/${S.LIMITS[group]})`}</button>`;
  }

  function RemoveButton({ ctx, group, index }) {
    return html`<button class="x" title="Bỏ" onClick=${() => ctx.update((s) => { s[group].splice(index, 1); })}>×</button>`;
  }

  function ListSection({ ctx, group }) {
    const { state, dict, update } = ctx;
    const catalog = dict[group];
    const edit = (index, fn) => update((s) => fn(s[group][index]));
    return html`<${Section} title=${LIST_TITLES[group]} hint=${`tối đa ${S.LIMITS[group]}; tắt = giữ từ capture`} enabled=${!!state[group]}
      onToggle=${(on) => ctx.toggleWithPrefill(group, on)}
      body=${() => html`
        ${state[group].map((item, i) => {
          const info = catalog[item.name];
          return html`<div class="row" key=${i}>
            <${Select} options=${nameOptions(dict, group, state[group].map((x) => x.name), item.name)} value=${item.name}
              onChange=${(v) => edit(i, (x) => { x.name = v; })} />
            ${info.maxLevel ? html`<label>Level <${NumberInput} value=${item.level} min=${1} max=${info.maxLevel}
              onChange=${(v) => edit(i, (x) => { x.level = v; })} /></label>` : null}
            <label>Sao <${NumberInput} value=${item.star} min=${1} max=${info.maxStar} onChange=${(v) => edit(i, (x) => { x.star = v; })} /></label>
            <span class="note">${`max lv ${info.maxLevel || "-"} / ${info.maxStar}★`}</span>
            <${RemoveButton} ctx=${ctx} group=${group} index=${i} />
          </div>`;
        })}
        <div class="row"><${AddButton} ctx=${ctx} group=${group}
          make=${(name) => (group === "spells" ? { name, star: 1 } : { name, level: 1, star: 1 })} /></div>`} />`;
  }

  // ---------- heroes ----------

  function HeroesSection({ ctx }) {
    const { state } = ctx;
    return html`<${Section} title="Hero" hint="tối đa 5; tắt = đội hình capture" enabled=${!!state.heroes}
      onToggle=${(on) => ctx.toggleWithPrefill("heroes", on)}
      body=${() => html`
        ${state.heroes.map((hero, index) => html`<${HeroCard} key=${index} ctx=${ctx} hero=${hero} index=${index} />`)}
        <div class="row"><${AddButton} ctx=${ctx} group="heroes" make=${S.newHero} /></div>
        <div class="note">Hero có trong capture giữ chỉ số và skill gốc; hero khác mượn chỉ số trung bình, level và level skill của các hero cùng độ hiếm trong capture (gần đúng, ±10%). Không tick "Tùy chỉnh skin" thì giữ skin từ capture.</div>`} />`;
  }

  function HeroCard({ ctx, hero, index }) {
    const { state, dict, update } = ctx;
    const skins = S.heroSkins(dict, hero.name);
    const hasSkins = Object.keys(skins).length > 0;
    const edit = (fn) => update((s) => fn(s.heroes[index]));
    return html`<div class="card">
      <div class="row">
        <strong>${`#${index + 1}`}</strong>
        <${Select} options=${nameOptions(dict, "heroes", state.heroes.map((h) => h.name), hero.name)} value=${hero.name}
          onChange=${(v) => update((s) => { s.heroes[index] = S.newHero(v); })} />
        ${hasSkins
          ? html`<label><${Checkbox} checked=${hero.custom} onChange=${(on) => edit((h) => { h.custom = on; })} />Tùy chỉnh skin</label>`
          : html`<span class="note">không có skin</span>`}
        <${RemoveButton} ctx=${ctx} group="heroes" index=${index} />
      </div>
      ${hero.custom && hasSkins ? html`<${HeroSkinTable} hero=${hero} skins=${skins} edit=${edit} />` : null}
    </div>`;
  }

  function HeroSkinTable({ hero, skins, edit }) {
    const forced = S.heroForced(hero, skins);
    const slotForced = S.heroSlotForced(hero, skins);
    const count = (kind) => hero.slots.filter((key) => S.heroSlotKind(skins[key]) === kind).length;
    const wornOptions = [["", "model gốc"], ...Object.entries(skins).map(([key, skin]) => [key, optionText(skin)])];
    return html`<div>
      <div class="row">
        <label>Đang mặc <${Select} options=${wornOptions} value=${hero.worn || ""} onChange=${(v) => edit((h) => { h.worn = v || null; })} /></label>
        <span class="note">${`Slot: ${count("normal")}/${S.HERO_SLOTS.normal} thường, ${count("colorful")}/${S.HERO_SLOTS.colorful} 7 màu`}</span>
      </div>
      <table><tbody>
        <tr>${["Skin", "Màu", "Sở hữu", "Sao", "Slot"].map((h) => html`<th>${h}</th>`)}</tr>
        ${Object.entries(skins).map(([key, skin]) => {
          const s = hero.skins[key];
          const kind = S.heroSlotKind(skin);
          const slotted = hero.slots.includes(key);
          return html`<tr key=${key}>
            <td class="name">${label(skin)}${requiresNote(skin, skins)}</td>
            <td>${colorTag(skin.color)}</td>
            <td><${Checkbox} checked=${s.owned} disabled=${key in forced}
              title=${key in forced ? "Bắt buộc (đang mặc hoặc skin 7 màu yêu cầu)" : null}
              onChange=${(on) => edit((h) => {
                h.skins[key].owned = on;
                if (!on) h.slots = h.slots.filter((k) => k !== key);
              })} /></td>
            <td><${NumberInput} value=${s.star} min=${forced[key] || 1} max=${skin.maxStar} disabled=${!s.owned}
              onChange=${(v) => edit((h) => { h.skins[key].star = v; })} /><span class="note">${` /${skin.maxStar}`}</span></td>
            <td><${Checkbox} checked=${slotted} disabled=${slotForced.has(key) || (!slotted && count(kind) >= S.HERO_SLOTS[kind])}
              title=${slotForced.has(key) ? "Bắt buộc: skin 7 màu trong slot cần skin này" : null}
              onChange=${(on) => edit((h) => {
                if (on) h.skins[key].owned = true;
                h.slots = on ? [...h.slots, key] : h.slots.filter((k) => k !== key);
              })} /></td>
          </tr>`;
        })}
      </tbody></table>
      <div class="note">Sở hữu: account có skin (cộng chỉ số). Slot: skill của skin vào trận. Skin 7 màu cần 3 skin thường ở sao ≥ sao của nó (trang tự nâng); gắn slot 7 màu thì 3 skin đó cũng vào slot và bị khoá đến khi bỏ slot 7 màu.</div>
    </div>`;
  }

  function requiresNote(skin, skins) {
    return skin.requires
      ? html`<div class="note">${`cần: ${skin.requires.map((r) => skins[r].name_vn || skins[r].name).join(", ")}`}</div>`
      : null;
  }

  // ---------- buildings ----------

  function BuildingsSection({ ctx }) {
    const any = S.BUILDINGS.some(([key]) => ctx.state.buildings[key]);
    return html`<section>
      <header><h2>Skin building</h2><span class="hint">mỗi building bật riêng; tắt = giữ từ capture</span></header>
      <div class="body">
        ${S.BUILDINGS.map(([key, title]) => html`<${BuildingCard} key=${key} ctx=${ctx} building=${key} title=${title} />`)}
        ${any ? html`<div class="note">Slot: 1 đỏ, 2 vàng, 1 loại 3. Skin 7 màu dùng slot vàng và khoá 3 skin yêu cầu khỏi mọi slot. Chỉ số building (attr) và skill do server thêm vẫn giữ từ capture.</div>` : null}
      </div>
    </section>`;
  }

  function BuildingCard({ ctx, building, title }) {
    const { state, dict, update } = ctx;
    const entry = state.buildings[building];
    const edit = (fn) => update((s) => fn(s.buildings[building]));
    return html`<div class="card">
      <div class="row">
        <strong>${title}</strong>
        <label><${Checkbox} checked=${!!entry}
          onChange=${(on) => update((s) => { s.buildings[building] = on ? S.newBuilding(dict, building) : null; })} />Ghi đè</label>
      </div>
      ${entry ? html`<${BuildingSkinTable} entry=${entry} skins=${S.buildSkins(dict, building)} edit=${edit} />` : null}
    </div>`;
  }

  function BuildingSkinTable({ entry, skins, edit }) {
    const forced = S.buildingForced(entry, skins);
    const locked = S.buildingLocks(skins, entry.slots);
    const count = (slot) => entry.slots.filter((key) => skins[key].slot === slot).length;
    const wornOptions = Object.entries(skins).map(([key, skin]) => [key, optionText(skin)]);
    return html`<div>
      <div class="row">
        <label>Đang mặc <${Select} options=${wornOptions} value=${entry.worn} onChange=${(v) => edit((e) => { e.worn = v; })} /></label>
        <span class="note">${`Slot: ${count("red")}/1 đỏ, ${count("gold")}/2 vàng, ${count("special")}/1 loại 3`}</span>
      </div>
      <table><tbody>
        <tr>${["Skin", "Màu / slot", "Sở hữu", "Sao", "Slot"].map((h) => html`<th>${h}</th>`)}</tr>
        ${Object.entries(skins).map(([key, skin]) => {
          const s = entry.skins[key];
          const slotted = entry.slots.includes(key);
          const slottable = !!S.BUILD_SLOTS[skin.slot];
          const full = count(skin.slot) >= S.BUILD_SLOTS[skin.slot];
          return html`<tr key=${key}>
            <td class="name">${label(skin)}${requiresNote(skin, skins)}</td>
            <td>${colorTag(skin.color)}${slottable && skin.slot !== skin.color
              ? html`<span class="note">${` slot ${S.COLOR_LABEL[skin.slot] || skin.slot}`}</span>` : null}</td>
            <td><${Checkbox} checked=${s.owned} disabled=${key in forced}
              onChange=${(on) => edit((e) => {
                e.skins[key].owned = on;
                if (!on) e.slots = e.slots.filter((k) => k !== key);
              })} /></td>
            <td><${NumberInput} value=${s.star} min=${forced[key] || 1} max=${skin.maxStar} disabled=${!s.owned || skin.default}
              onChange=${(v) => edit((e) => { e.skins[key].star = v; })} /><span class="note">${` /${skin.maxStar}`}</span></td>
            <td>${!slottable ? html`<span class="note">-</span>`
              : locked.has(key) ? html`<span class="warn">khoá</span>`
              : html`<${Checkbox} checked=${slotted} disabled=${!slotted && full}
                  onChange=${(on) => edit((e) => {
                    if (on) e.skins[key].owned = true;
                    e.slots = on ? [...e.slots, key] : e.slots.filter((k) => k !== key);
                  })} />`}</td>
          </tr>`;
        })}
      </tbody></table>
    </div>`;
  }

  function GoldenSection({ ctx }) {
    const { state, update } = ctx;
    return html`<${Section} title="goldenSkinsCount" hint="tăng sát thương pet; server tự tính, chưa rõ cách"
      enabled=${state.goldenSkinsCount !== null}
      onToggle=${(on) => update((s) => { s.goldenSkinsCount = on ? 0 : null; })}
      body=${() => html`<div class="row"><label>Số skin vàng <${NumberInput} value=${state.goldenSkinsCount} min=${0} max=${999}
        onChange=${(v) => update((s) => { s.goldenSkinsCount = v; })} /></label></div>`} />`;
  }

  S.FormSections = FormSections;
})();
