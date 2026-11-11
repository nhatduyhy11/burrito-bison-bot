// Right column of the setup page: base capture + seed, actions (play, download, copy, import, reset),
// status line and the profile JSON. ctx is the same object the form sections get.
import { useEffect, useRef, useState } from "preact/hooks";
import { html, Select } from "./ui.js";
import { emptyState, fromProfile, toProfile } from "./profile-io.js";

const SEED_OPTIONS = [
  ["", "giống capture"],
  ["random", "ngẫu nhiên"],
];
const NO_STATUS = { text: "", kind: "note" };

function warnings(state, profile) {
  const out = [];
  if (profile.heroes?.length !== 5) out.push("Cần chọn đủ 5 hero.");
  if (new Set(profile.heroes?.map((hero) => typeof hero === "string" ? hero : hero.name)).size !== profile.heroes?.length) out.push("5 hero phải khác nhau.");
  if (!state.battle) out.push("Chưa có capture nào để làm trận gốc.");
  return out;
}

function saveFile(name, text) {
  const link = document.createElement("a");
  link.href = URL.createObjectURL(new Blob([text], { type: "application/json" }));
  link.download = name;
  link.click();
  setTimeout(() => URL.revokeObjectURL(link.href), 1000);
}

export function Side({ ctx, battles, profile, initialStatus }) {
  const { state, dict, update } = ctx;
  const [status, setStatus] = useState(initialStatus || NO_STATUS);
  const [playing, setPlaying] = useState(false);
  const fileInput = useRef(null);
  const problems = warnings(state, profile);
  const canPlay = typeof window.simPlay === "function";
  const json = () => JSON.stringify(toProfile(state, dict), null, 2);

  // Every state change shows the warnings, or clears a stale warning.
  useEffect(() => {
    if (problems.length) setStatus({ text: problems.join(" "), kind: "warn" });
    else setStatus((s) => (s.kind === "warn" ? NO_STATUS : s));
  }, [state]);

  const download = () => saveFile("profile.json", json() + "\n");
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(json());
      setStatus({ text: "Đã sao chép profile.", kind: "note" });
    } catch (e) {
      setStatus({ text: `Không sao chép được: ${e.message}`, kind: "err" });
    }
  };
  const openImport = () => fileInput.current.click();
  const importFile = async (e) => {
    const file = e.currentTarget.files[0];
    e.currentTarget.value = "";
    if (!file) return;
    try {
      const next = fromProfile(JSON.parse(await file.text()), state, dict);
      update(() => next);
      setStatus({ text: `Đã nhập ${file.name}.`, kind: "note" });
    } catch (err) {
      setStatus({ text: `Không nhập được ${file.name}: ${err.message}`, kind: "err" });
    }
  };
  const reset = () => update((s) => ({ ...emptyState(), battle: s.battle, seed: s.seed }));
  const play = async () => {
    setPlaying(true);
    setStatus({ text: "Đang lưu profile và mở trận…", kind: "note" });
    try {
      const saved = await window.simPlay({ battle: state.battle, seed: state.seed || null, profile: toProfile(state, dict) });
      setStatus({ text: `Đã lưu ${saved}. Đang mở trận…`, kind: "note" });
    } catch (err) {
      setStatus({ text: `Không mở được trận: ${err.message}`, kind: "err" });
      setPlaying(false);
    }
  };
  const setBattle = (v) => update((s) => void (s.battle = v));
  const setSeed = (v) => update((s) => void (s.seed = v));

  const battleOptions = battles.length
    ? battles.map((b) => [b.uuid, `${b.uuid.slice(0, 8)}… · capture ở Stage ${b.level} · ${b.ops} op`])
    : [["", "(không có capture)"]];
  const playDisabled = playing || !canPlay || problems.length > 0;
  const seedArg = state.seed ? ` --seed ${state.seed}` : "";
  const playCommand = `uv run python battle_sim/sandbox --battle ${state.battle || "<uuid>"} --play${seedArg} --profile <file>.json`;
  const playHint = canPlay
    ? null
    : html`
        Nút Chơi chỉ chạy khi mở qua <code>uv run python battle_sim/sandbox --setup</code>. Hoặc tải JSON rồi
        chạy: <code>${playCommand}</code>
      `;
  return html`
    <section>
      <header><h2>Account gốc</h2></header>
      <div class="body">
        <div class="row">
          <label>Capture <${Select} id="battle" options=${battleOptions} value=${state.battle} onChange=${setBattle} /></label>
        </div>
        <div class="note">
          Trận đã capture chỉ dùng làm nguồn dữ liệu account: chỉ số và level hero, attr building, hero support, đồng
          đội robot, và mọi phần không bật Ghi đè. Stage ghi ở đây là màn của trận capture; màn sẽ chơi do mục "Màn
          chơi" quyết định (tắt thì dùng màn này).
        </div>
        <div class="row">
          <label>Seed <${Select} id="seed" options=${SEED_OPTIONS} value=${state.seed} onChange=${setSeed} /></label>
        </div>
        <div class="row">
          <button id="play" class="primary" disabled=${playDisabled} onClick=${play}>Chơi</button>
          <button id="download" onClick=${download}>Tải JSON</button>
          <button id="copy" onClick=${copy}>Sao chép</button>
          <label>
            <button id="importBtn" onClick=${openImport}>Nhập JSON</button>
            <input id="importFile" ref=${fileInput} type="file" accept=".json,application/json" hidden onChange=${importFile} />
          </label>
          <button id="reset" onClick=${reset}>Xoá hết</button>
        </div>
        <div id="playHint" class="note">${playHint}</div>
        <div id="status" class=${`status ${status.kind}`}>${status.text}</div>
      </div>
    </section>
    <section>
      <header><h2>Profile JSON</h2></header>
      <pre id="output">${JSON.stringify(profile, null, 2)}</pre>
    </section>
  `;
}
