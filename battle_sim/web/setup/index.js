// Setup page for local playtest profiles (served at /__sim/setup.html). Entry module.
//
// Builds the JSON that web/battle/profile.js reads (`sandbox --play --profile <file>`) from the
// catalogs in hero-dict.json + support-dict.json, map-dict.json, boss-dict.json, creeps-dict.json
// and antique-dict.json (scripts/gen_profile_dict.js). ES modules + Preact/htm from vendor/
// (import map in setup.html, no build step): skin-rules.js (skin input rules), profile-io.js
// (state <-> profile), ui.js (html`` + small components), sections/ (form sections), side.js (right
// column), capture.js (capture prefill), and this file (app state and boot).
//
// Opened through `sandbox --setup`, the page gets window.simPlay({battle, seed, profile}): sandbox
// saves the profile under .tmp/battle_sim/profiles/ and opens the battle with it.
import { render } from "preact";
import { useEffect, useMemo, useState } from "preact/hooks";
import { html } from "./ui.js";
import { capturedArtifact, prefill } from "./capture.js";
import { emptyState, fromProfile, normalize, toProfile } from "./profile-io.js";
import { forRegion } from "./region.js";
import { FormSections } from "./sections/index.js";
import { Side } from "./side.js";

const STORE_KEY = "battleSimSetup";

// ---------- app ----------

function App({ dict, maps, bossDict, creepsDict, antiqueDict, relicLines, artifactDict, battles, initial, initialStatus, region, captureByRegion, changeRegion }) {
  const [state, setState] = useState(initial);
  const capturesForSetup = { ...captureByRegion, [region]: state.battle };
  const [switchingRegion, setSwitchingRegion] = useState(false);
  const [regionError, setRegionError] = useState("");
  const switchRegion = async (nextRegion) => {
    if (switchingRegion || nextRegion === region) return;
    setSwitchingRegion(true);
    setRegionError("");
    try {
      await changeRegion(nextRegion, { ...state, region, captureByRegion: capturesForSetup, profile: toProfile(state, dict) });
    } catch (err) {
      setRegionError(`Không đổi được vùng: ${err.message}`);
      setSwitchingRegion(false);
    }
  };
  // Every change goes through here: fn edits a copy (or returns a replacement), then skin rules normalize it.
  const update = (fn) =>
    setState((prev) => {
      const draft = structuredClone(prev);
      const next = fn(draft) || draft;
      normalize(next, dict);
      return next;
    });
  const toggleWithPrefill = async (group, on) => {
    const value = on ? await prefill(dict, maps, region, state.battle, group) : null;
    update((s) => void (s[group] = value));
  };
  const profile = useMemo(() => toProfile(state, dict), [state]);

  useEffect(() => {
    try {
      localStorage.setItem(STORE_KEY, JSON.stringify({ region, battle: state.battle, captureByRegion: capturesForSetup, seed: state.seed, profile }));
    } catch {
      // storage off
    }
  }, [profile, state.battle, state.seed]);

  const capturedHeroArtifact = (heroCode) => capturedArtifact(region, state.battle, heroCode);
  const ctx = { state, region, switchRegion, switchingRegion, dict, maps, bossDict, creepsDict, antiqueDict, relicLines, artifactDict, update, toggleWithPrefill, capturedHeroArtifact };
  return html`
    <main id="form">
      ${regionError && html`<p class="err" role="alert">${regionError}</p>`}
      <${Side} ctx=${ctx} battles=${battles} profile=${profile} initialStatus=${initialStatus} />
      <${FormSections} ctx=${ctx} />
    </main>
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

function bindAccordionToggle(root) {
  const button = document.getElementById("toggle-accordions");
  const accordions = () => [...root.querySelectorAll("details.accordion")];
  const updateLabel = () => {
    button.textContent = accordions().some((panel) => panel.open) ? "Thu gọn tất cả" : "Mở tất cả";
  };
  button.addEventListener("click", () => {
    const panels = accordions();
    const open = panels.every((panel) => !panel.open);
    panels.forEach((panel) => { if (!(open && panel.dataset.skipExpandAll)) panel.open = open; });
    updateLabel();
  });
  root.addEventListener("toggle", updateLabel, true);
  updateLabel();
  button.disabled = false;
}

async function showRegion(root, region, saved, switching = false) {
  const suffix = `?region=${region}`;
  const [heroDict, supportDict, maps, bossDict, creepsDict, antiqueDict, relicDict, artifactDict, battles] = await Promise.all([
    ...["hero", "support", "map", "boss", "creeps", "antique", "relic", "artifact"].map((name) => getJson(`/__sim/dict/${name}-dict.json${suffix}`)),
    getJson(`/__sim/battles.json${suffix}`),
  ]);
  // One lookup table for both sides: hero-dict (heroes) + support-dict (the non-hero groups).
  const dict = { ...heroDict, ...supportDict };
  const captureByRegion = { ...saved?.captureByRegion };
  if (saved?.battle) captureByRegion[saved.region || "vn"] = saved.battle;
  const preferredCapture = captureByRegion[region];
  const battle = battles.some((b) => b.uuid === preferredCapture) ? preferredCapture : battles[0]?.uuid || "";
  let state = { ...emptyState(dict, antiqueDict), battle };
  let initialStatus = null;
  let profile = saved?.profile;
  if (profile) {
    try {
      const catalogs = { maps, bossDict, antiqueDict, relicLines: relicDict.lines };
      const adjusted = forRegion(profile, dict, catalogs);
      profile = adjusted.profile;
      if (adjusted.removed.length) {
        initialStatus = { text: `Vùng ${region.toUpperCase()} không có: ${adjusted.removed.join(", ")}.`, kind: "warn" };
      }
      state = fromProfile(profile, { battle, seed: saved.seed || "" }, dict, catalogs);
    } catch (err) {
      if (switching) throw err;
      initialStatus = { text: `Bỏ qua profile đã lưu: ${err.message}`, kind: "err" };
      profile = null;
    }
  }
  if (!profile?.heroes) state.heroes = await prefill(dict, maps, region, battle, "heroes");
  normalize(state, dict);
  const changeRegion = (next, current) => showRegion(root, next, current, true);
  // First mount adopts nothing from #app, so preact leaves the html placeholder ("đang tải…")
  // alive next to the rendered tree — drop it just before mounting (region switch diffs instead).
  if (!switching) root.textContent = "";
  render(html`<${App} key=${region} region=${region} captureByRegion=${captureByRegion} changeRegion=${changeRegion} dict=${dict} maps=${maps} bossDict=${bossDict} creepsDict=${creepsDict} antiqueDict=${antiqueDict} relicLines=${relicDict.lines} artifactDict=${artifactDict} battles=${battles} initial=${state} initialStatus=${initialStatus} />`, root);
  if (!switching) bindAccordionToggle(root);
  else root.dispatchEvent(new Event("toggle"));
}

const root = document.getElementById("app");
savedSetup().then((saved) => showRegion(root, saved?.region === "gat" ? "gat" : "vn", saved)).catch((err) => {
  root.textContent = ""; // same placeholder quirk on the error path
  render(html`<p class="err">${`Lỗi tải trang: ${err.message}`}</p>`, root);
});
