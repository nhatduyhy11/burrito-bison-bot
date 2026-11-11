// Setup page for local playtest profiles (served at /__sim/setup.html). Entry point, loaded last.
//
// Builds the JSON that web/battle/profile.js reads (`sandbox.py --play --profile <file>`) from the
// catalog in profile-dict.json (scripts/gen_profile_dict.js). UI is Preact + htm (vendor/, UMD
// globals, no build step). Modules (window.SimSetup): skin-rules.js (skin input rules), ui.js
// (html`` + small components), profile-io.js (state <-> profile), sections.js (form sections), then
// this file (state, capture prefill, side panel, boot).
//
// Opened through `sandbox.py --setup`, the page gets window.simPlay({battle, seed, profile}): sandbox
// saves the profile under .tmp/battle_sim/profiles/ and opens the battle with it.
(function () {
  "use strict";
  const S = window.SimSetup;
  const { html, Select } = S;
  const { render } = window.preact;
  const { useState, useEffect, useMemo, useRef } = window.preactHooks;

  const STORE_KEY = "battleSimSetup";

  // ---------- capture prefill ----------

  const captures = new Map(); // uuid -> StartGameP

  async function capturedStart(battle) {
    if (!battle) return null;
    if (!captures.has(battle)) {
      const response = await fetch(`/__sim/battle/${battle}.json`);
      captures.set(battle, response.ok ? (await response.json()).start : null);
    }
    return captures.get(battle);
  }

  const listItems = (list) => Array.from({ length: list?._length || 0 }, (_, i) => list[String(i)]);
  const nameByCode = (dict, group, code) => Object.keys(dict[group]).find((key) => dict[group][key].code === code);

  // Turning a section on fills it from the base capture.
  async function prefill(dict, battle, group) {
    const start = await capturedStart(battle);
    const player = start && listItems(start.playerInfos)[0];
    if (group === "map") return { stage: start?.level || dict.maps.campaign.minStage };
    if (!player) return [];
    const name = (group, code) => nameByCode(dict, group, code);
    const from = {
      heroes: () => listItems(player.heros).map((h) => name("heroes", h.code)).filter(Boolean).map(S.newHero),
      traps: () => listItems(player.organs).map((o) => ({ name: name("traps", o.code), level: o.level, star: o.star })),
      pets: () => listItems(player.summonCreatures).map((p) => ({ name: name("pets", p.code), level: p.level, star: p.star })),
      spells: () => listItems(player.daoists).map((d) => ({ name: name("spells", d.code), star: d.star })),
    }[group];
    return from().filter((item) => item.name).slice(0, S.LIMITS[group]);
  }

  // ---------- app ----------

  function App({ dict, battles, initial, initialStatus }) {
    const [state, setState] = useState(initial);
    // Every change goes through here: fn edits a copy (or returns a replacement), then skin rules normalize it.
    const update = (fn) => setState((prev) => {
      const draft = structuredClone(prev);
      const next = fn(draft) || draft;
      S.normalize(next, dict);
      return next;
    });
    const toggleWithPrefill = async (group, on) => {
      const value = on ? await prefill(dict, state.battle, group) : null;
      update((s) => { s[group] = value; });
    };
    const profile = useMemo(() => S.toProfile(state, dict), [state]);

    useEffect(() => {
      try { localStorage.setItem(STORE_KEY, JSON.stringify({ battle: state.battle, seed: state.seed, profile })); } catch { /* storage off */ }
    }, [profile, state.battle, state.seed]);

    const ctx = { state, dict, update, toggleWithPrefill };
    return html`<div class="layout">
      <main id="form"><${S.FormSections} ctx=${ctx} /></main>
      <aside class="side"><${Side} ctx=${ctx} battles=${battles} profile=${profile} initialStatus=${initialStatus} /></aside>
    </div>`;
  }

  // ---------- side panel ----------

  function warnings(state, profile) {
    const out = [];
    if (profile.heroes && !profile.heroes.length) out.push("Cần ít nhất 1 hero (hoặc tắt Ghi đè).");
    if (!state.battle) out.push("Chưa có capture nào để làm trận gốc.");
    return out;
  }

  function Side({ ctx, battles, profile, initialStatus }) {
    const { state, dict, update } = ctx;
    const [status, setStatus] = useState(initialStatus || { text: "", kind: "note" });
    const [playing, setPlaying] = useState(false);
    const fileInput = useRef(null);
    const problems = warnings(state, profile);
    const canPlay = typeof window.simPlay === "function";
    const json = () => JSON.stringify(S.toProfile(state, dict), null, 2);

    // Like the old commit(): every state change shows the warnings, or clears a stale warning.
    useEffect(() => {
      if (problems.length) setStatus({ text: problems.join(" "), kind: "warn" });
      else setStatus((s) => (s.kind === "warn" ? { text: "", kind: "note" } : s));
    }, [state]);

    const download = () => {
      const link = document.createElement("a");
      link.href = URL.createObjectURL(new Blob([json() + "\n"], { type: "application/json" }));
      link.download = "profile.json";
      link.click();
      setTimeout(() => URL.revokeObjectURL(link.href), 1000);
    };
    const copy = async () => {
      try {
        await navigator.clipboard.writeText(json());
        setStatus({ text: "Đã sao chép profile.", kind: "note" });
      } catch (e) {
        setStatus({ text: `Không sao chép được: ${e.message}`, kind: "err" });
      }
    };
    const importFile = async (e) => {
      const file = e.currentTarget.files[0];
      e.currentTarget.value = "";
      if (!file) return;
      try {
        const next = S.fromProfile(JSON.parse(await file.text()), state, dict);
        update(() => next);
        setStatus({ text: `Đã nhập ${file.name}.`, kind: "note" });
      } catch (err) {
        setStatus({ text: `Không nhập được ${file.name}: ${err.message}`, kind: "err" });
      }
    };
    const play = async () => {
      setPlaying(true);
      setStatus({ text: "Đang lưu profile và mở trận…", kind: "note" });
      try {
        const saved = await window.simPlay({ battle: state.battle, seed: state.seed || null, profile: S.toProfile(state, dict) });
        setStatus({ text: `Đã lưu ${saved}. Đang mở trận…`, kind: "note" });
      } catch (err) {
        setStatus({ text: `Không mở được trận: ${err.message}`, kind: "err" });
        setPlaying(false);
      }
    };

    const battleOptions = battles.length
      ? battles.map((b) => [b.uuid, `${b.uuid.slice(0, 8)}… · capture ở Stage ${b.level} · ${b.ops} op`])
      : [["", "(không có capture)"]];
    const seedArg = state.seed ? ` --seed ${state.seed}` : "";
    return html`
      <section>
        <header><h2>Account gốc</h2></header>
        <div class="body">
          <div class="row"><label>Capture <${Select} id="battle" options=${battleOptions} value=${state.battle}
            onChange=${(v) => update((s) => { s.battle = v; })} /></label></div>
          <div class="note">Trận đã capture chỉ dùng làm nguồn dữ liệu account: chỉ số và level hero, attr
            building, hero support, đồng đội robot, và mọi phần không bật Ghi đè. Stage ghi ở đây là
            màn của trận capture; màn sẽ chơi do mục "Màn chơi" quyết định (tắt thì dùng màn này).</div>
          <div class="row"><label>Seed <${Select} id="seed" options=${[["", "giống capture"], ["random", "ngẫu nhiên"]]}
            value=${state.seed} onChange=${(v) => update((s) => { s.seed = v; })} /></label></div>
          <div class="row">
            <button id="play" class="primary" disabled=${playing || !canPlay || problems.length > 0} onClick=${play}>Chơi</button>
            <button id="download" onClick=${download}>Tải JSON</button>
            <button id="copy" onClick=${copy}>Sao chép</button>
            <label><button id="importBtn" onClick=${() => fileInput.current.click()}>Nhập JSON</button><input id="importFile"
              ref=${fileInput} type="file" accept=".json,application/json" hidden onChange=${importFile} /></label>
            <button id="reset" onClick=${() => update((s) => ({ ...S.emptyState(), battle: s.battle, seed: s.seed }))}>Xoá hết</button>
          </div>
          <div id="playHint" class="note">${canPlay ? null : html`Nút Chơi chỉ chạy khi mở qua <code>uv run python battle_sim/sandbox.py --setup</code>. Hoặc tải JSON rồi chạy: <code>${`uv run python battle_sim/sandbox.py --battle ${state.battle || "<uuid>"} --play${seedArg} --profile <file>.json`}</code>`}</div>
          <div id="status" class=${`status ${status.kind}`}>${status.text}</div>
        </div>
      </section>
      <section>
        <header><h2>Profile JSON</h2></header>
        <pre id="output">${JSON.stringify(profile, null, 2)}</pre>
      </section>`;
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

  async function main(root) {
    const [dict, battles] = await Promise.all([
      getJson("/__sim/profile-dict.json"),
      getJson("/__sim/battles.json").catch(() => []),
    ]);
    let state = S.emptyState();
    let initialStatus = null;
    const saved = await savedSetup();
    if (saved) {
      try {
        state = S.fromProfile(saved.profile || {}, { battle: saved.battle || "", seed: saved.seed || "" }, dict);
      } catch (err) {
        initialStatus = { text: `Bỏ qua profile đã lưu: ${err.message}`, kind: "err" };
      }
    }
    if (!battles.some((b) => b.uuid === state.battle)) state.battle = battles[0]?.uuid || "";
    S.normalize(state, dict);
    root.replaceChildren();
    render(html`<${App} dict=${dict} battles=${battles} initial=${state} initialStatus=${initialStatus} />`, root);
  }

  const root = document.getElementById("app");
  main(root).catch((err) => {
    root.replaceChildren();
    render(html`<p class="err">${`Lỗi tải trang: ${err.message}`}</p>`, root);
  });
})();
