// Setup page for local playtest profiles (served at /__sim/setup.html). Entry point, loaded last.
//
// Builds the JSON that web/battle/profile.js reads (`sandbox.py --play --profile <file>`) from the
// catalog in profile-dict.json (scripts/gen_profile_dict.js). Modules (window.SimSetup):
// skin-rules.js (skin input rules), dom.js (DOM helpers), profile-io.js (state <-> profile),
// sections.js (form sections), then this file (state, capture prefill, side panel, boot).
//
// Opened through `sandbox.py --setup`, the page gets window.simPlay({battle, seed, profile}): sandbox
// saves the profile under .tmp/battle_sim/profiles/ and opens the battle with it.
(function () {
  "use strict";
  const S = window.SimSetup;
  const { el } = S;

  const STORE_KEY = "battleSimSetup";
  let dict, battles = [], state;
  const captures = new Map(); // uuid -> StartGameP
  const $ = (id) => document.getElementById(id);

  const ctx = {
    get state() { return state; },
    get dict() { return dict; },
    commit,
    toggleWithPrefill,
  };

  function commit() {
    S.normalize(state, dict);
    const profile = S.toProfile(state, dict);
    try { localStorage.setItem(STORE_KEY, JSON.stringify({ battle: state.battle, seed: state.seed, profile })); } catch { /* storage off */ }
    $("form").replaceChildren(...S.formSections(ctx));
    renderSide(profile);
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

  // Turning a section on fills it from the base capture.
  async function prefill(group) {
    const start = await capturedStart();
    const player = start && listItems(start.playerInfos)[0];
    if (group === "map") return { stage: start?.level || dict.maps.campaign.minStage };
    if (!player) return [];
    const from = {
      heroes: () => listItems(player.heros).map((h) => nameByCode("heroes", h.code)).filter(Boolean).map(S.newHero),
      traps: () => listItems(player.organs).map((o) => ({ name: nameByCode("traps", o.code), level: o.level, star: o.star })),
      pets: () => listItems(player.summonCreatures).map((p) => ({ name: nameByCode("pets", p.code), level: p.level, star: p.star })),
      spells: () => listItems(player.daoists).map((d) => ({ name: nameByCode("spells", d.code), star: d.star })),
    }[group];
    return from().filter((item) => item.name).slice(0, S.LIMITS[group]);
  }

  async function toggleWithPrefill(group, on) {
    state[group] = on ? await prefill(group) : null;
    commit();
  }

  // ---------- side panel ----------

  function warnings(profile) {
    const out = [];
    if (profile.heroes && !profile.heroes.length) out.push("Cần ít nhất 1 hero (hoặc tắt Ghi đè).");
    if (!state.battle) out.push("Chưa có capture nào để làm trận gốc.");
    return out;
  }

  function renderSide(profile) {
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
      const blob = new Blob([JSON.stringify(S.toProfile(state, dict), null, 2) + "\n"], { type: "application/json" });
      const link = el("a", { href: URL.createObjectURL(blob), download: "profile.json" });
      link.click();
      setTimeout(() => URL.revokeObjectURL(link.href), 1000);
    });
    $("copy").addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(JSON.stringify(S.toProfile(state, dict), null, 2));
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
        state = S.fromProfile(JSON.parse(await file.text()), state, dict);
        commit();
        setStatus(`Đã nhập ${file.name}.`, "note");
      } catch (err) {
        setStatus(`Không nhập được ${file.name}: ${err.message}`, "err");
      }
    });
    $("reset").addEventListener("click", () => {
      state = { ...S.emptyState(), battle: state.battle, seed: state.seed };
      commit();
    });
    $("play").addEventListener("click", async () => {
      $("play").disabled = true;
      setStatus("Đang lưu profile và mở trận…", "note");
      try {
        const saved = await window.simPlay({ battle: state.battle, seed: state.seed || null, profile: S.toProfile(state, dict) });
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
    state = S.emptyState();
    const saved = await savedSetup();
    if (saved) {
      try {
        state = S.fromProfile(saved.profile || {}, { battle: saved.battle || "", seed: saved.seed || "" }, dict);
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
