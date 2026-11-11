// Setup page for local playtest profiles (served at /__sim/setup.html). Entry module.
//
// Builds the JSON that web/battle/profile.js reads (`sandbox --play --profile <file>`) from the
// catalog in profile-dict.json (scripts/gen_profile_dict.js). ES modules + Preact/htm from vendor/
// (import map in setup.html, no build step): skin-rules.js (skin input rules), profile-io.js
// (state <-> profile), ui.js (html`` + small components), sections/ (form sections), side.js (right
// column), and this file (single state, capture prefill, boot).
//
// Opened through `sandbox --setup`, the page gets window.simPlay({battle, seed, profile}): sandbox
// saves the profile under .tmp/battle_sim/profiles/ and opens the battle with it.
import { render } from "preact";
import { useEffect, useMemo, useState } from "preact/hooks";
import { html } from "./ui.js";
import { LIMITS, emptyState, fromProfile, newHero, normalize, toProfile } from "./profile-io.js";
import { FormSections } from "./sections/index.js";
import { Side } from "./side.js";

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

// Turning a section on fills it from the base capture.
async function prefill(dict, battle, group) {
  const start = await capturedStart(battle);
  const player = start && listItems(start.playerInfos)[0];
  if (group === "map") return { stage: start?.level || dict.maps.campaign.minStage };
  if (!player) return [];
  const name = (group, code) => Object.keys(dict[group]).find((key) => dict[group][key].code === code);
  const from = {
    heroes: () => listItems(player.heros).map((h) => name("heroes", h.code)).filter(Boolean).map(newHero),
    traps: () => listItems(player.organs).map((o) => ({ name: name("traps", o.code), level: o.level, star: o.star })),
    pets: () => listItems(player.summonCreatures).map((p) => ({ name: name("pets", p.code), level: p.level, star: p.star })),
    spells: () => listItems(player.daoists).map((d) => ({ name: name("spells", d.code), star: d.star })),
    summonerSkins: () => listItems(player.summonerInfos).flatMap(({ code, level }) => {
      const key = name("summonerSkins", code);
      return dict.summonerSkins[key]?.skill ? [{ name: key, star: level }] : [];
    }),
  }[group];
  return from().filter((item) => item.name).slice(0, LIMITS[group]);
}

// ---------- app ----------

function App({ dict, battles, initial, initialStatus }) {
  const [state, setState] = useState(initial);
  // Every change goes through here: fn edits a copy (or returns a replacement), then skin rules normalize it.
  const update = (fn) =>
    setState((prev) => {
      const draft = structuredClone(prev);
      const next = fn(draft) || draft;
      normalize(next, dict);
      return next;
    });
  const toggleWithPrefill = async (group, on) => {
    const value = on ? await prefill(dict, state.battle, group) : null;
    update((s) => void (s[group] = value));
  };
  const profile = useMemo(() => toProfile(state, dict), [state]);

  useEffect(() => {
    try {
      localStorage.setItem(STORE_KEY, JSON.stringify({ battle: state.battle, seed: state.seed, profile }));
    } catch {
      // storage off
    }
  }, [profile, state.battle, state.seed]);

  const ctx = { state, dict, update, toggleWithPrefill };
  return html`
    <div class="layout">
      <main id="form"><${FormSections} ctx=${ctx} /></main>
      <aside class="side"><${Side} ctx=${ctx} battles=${battles} profile=${profile} initialStatus=${initialStatus} /></aside>
    </div>
  `;
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
  } catch {
    // storage off
  }
  try {
    return await getJson("/__sim/last-setup.json"); // written by sandbox --setup
  } catch {
    return null;
  }
}

async function main(root) {
  const [dict, battles] = await Promise.all([
    getJson("/__sim/profile-dict.json"),
    getJson("/__sim/battles.json").catch(() => []),
  ]);
  let state = emptyState();
  let initialStatus = null;
  const saved = await savedSetup();
  if (saved) {
    try {
      state = fromProfile(saved.profile || {}, { battle: saved.battle || "", seed: saved.seed || "" }, dict);
    } catch (err) {
      initialStatus = { text: `Bỏ qua profile đã lưu: ${err.message}`, kind: "err" };
    }
  }
  if (!battles.some((b) => b.uuid === state.battle)) state.battle = battles[0]?.uuid || "";
  normalize(state, dict);
  root.replaceChildren();
  render(html`<${App} dict=${dict} battles=${battles} initial=${state} initialStatus=${initialStatus} />`, root);
}

const root = document.getElementById("app");
main(root).catch((err) => {
  root.replaceChildren();
  render(html`<p class="err">${`Lỗi tải trang: ${err.message}`}</p>`, root);
});
