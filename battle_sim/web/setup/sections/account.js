// "Account gốc": base capture (account data source) + seed. First section of the form.
import { html, Select } from "../ui.js";

const SEED_OPTIONS = [
  ["", "giống capture"],
  ["random", "ngẫu nhiên"],
];

// Capital (U Đô) level = day*10000 + room*100 + index.
const captureWhere = (b) => b.battleType === 21
  ? `capture U Đô ngày ${Math.floor(b.level / 10000)} phòng ${Math.floor((b.level % 10000) / 100)}`
  : `capture ở Stage ${b.level}`;

export function AccountSection({ ctx, battles }) {
  const { state, update } = ctx;
  const setBattle = (v) => update((s) => void (s.battle = v));
  const setSeed = (v) => update((s) => void (s.seed = v));
  const battleOptions = battles.length
    ? battles.map((b) => [b.uuid, `${b.uuid.slice(0, 8)}… · ${captureWhere(b)} · ${b.ops} op`])
    : [["", "(không có capture)"]];
  return html`
    <section>
      <header><h2>Account gốc</h2></header>
      <div class="body">
        <div class="row">
          <label>Capture <${Select} id="battle" options=${battleOptions} value=${state.battle} onChange=${setBattle} /></label>
          <label>Seed <${Select} id="seed" options=${SEED_OPTIONS} value=${state.seed} onChange=${setSeed} /></label>
        </div>
        <div class="note">
          Trận đã capture chỉ dùng làm nguồn dữ liệu account: chỉ số và level hero, attr building, hero support, đồng
          đội robot, và mọi phần không bật Ghi đè. Stage ghi ở đây là màn của trận capture; màn sẽ chơi do mục "Màn
          chơi" quyết định (tắt thì dùng màn này).
        </div>
      </div>
    </section>
  `;
}
