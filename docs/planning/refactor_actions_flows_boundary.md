# Refactor ranh giới actions ↔ flows

## Bối cảnh

`actions/` sinh ra là action engine tầng runtime: action = cấu hình khai báo
("chờ template X ở region Y, click Z, timeout W, retry N") — không hiểu ngữ
cảnh game. Nhưng hiện tại nó đang chứa business:

- `ClickHeroSelectBattleAction` → `actions/hero_select_battle.py`: recovery
  loop của lobby_map (blocker priority, popup tabs, re-click entry) + click
  nút vàng kết thúc.
- `ClickPauseExitAction` + `ClickMapExitBackAction` → `actions/pause_exit.py`:
  business thoát trận (pause popup, exit confirm, map exit back).
- `actions/builder.py`: biết blocker priority, template path của từng
  màn hình — knowledge business, sống ở tầng engine.

Hệ quả rò rỉ layer:

1. Arch test phải mở exception ngược chiều —
   `actions/hero_select_battle.py` được phép import `hauntedroom.flows.hero_select`
   (`tests/test_hauntedroom_architecture.py`) — action phụ thuộc flow.
2. `flows/train_support/exit_flow.py` import `actions.pause_exit` — flow phải
   xin business từ tầng engine.
3. Mỗi phase mới có động cơ nhét vào actions (vì runner cho free
   retry/timeout) → exception ngày càng nhiều.

Fact mở đường: **3 smart action type không có trên JSON surface**. `loader.py`
chỉ parse 4 loại cơ giới (`click`, `click_template`, `clear_blockers`,
`wait`); `tools/json_macro/` không dùng type nào trong 3. Tức là chúng không
cần serialize — lý do tồn tại duy nhất là để runner bọc retry/timeout. Bỏ
type, giữ semantics = đủ.

## Kiến trúc đích

```text
actions/ — engine thuần (đợt này)        flows/ — business
  models.py (4 type cơ giới)               hero_select/ — phase thuần:
  loader.py / validation.py / defaults.py      find_battle_button + hàm click
  runner.py (retry/timeout loop)               nút vàng. HẾT. Không recovery
  runner_executor.py (4 branches)              của lobby nào.
  builder.py (tạm sống, chỉ lắp            lobby_map.py — lobby HOME: recovery
    mechanical list)                           (popup tabs, blocker priority,
                                               re-click entry) đến khi detector
                                               báo hero-select → bàn giao click.
  (hết business)                           battle_exit/ — submodule thoát trận:
                                               pause.py — dùng chung: cặp nút
                                                 đỏ/vàng + click đỏ
                                               exit_map_confirm.py — riêng map:
                                                 nút vàng post-exit
                                               exit_train_confirm.py — riêng train:
                                                 xác nhận thoát về train screen
                                           spawn_exit_lvup.py — ráp exit map
                                           train_support/ — lobby_train + exit
                                             flow ráp từ battle_exit/
                                           start_auto.py, new_account.py —
                                             composition
```

### Ranh giới bàn giao lobby → hero_select

- **Lobby (map lẫn train) chịu trách nhiệm tự recovery** cho đến khi shared
  detector xác nhận đã chuyển qua được screen hero_select (banner + nút vàng
  trong cùng frame).
- Từ điểm đó `flows/hero_select` tự làm phần còn lại: capture → detect →
  click nút vàng. Phase cung cấp `find_battle_button` + hàm
  wait-and-click (loop capture/detect/click với timeout/poll/settle) —
  không có recovery lẫn lộn gì trong đây.
- Blocker/recovery chỉ là chuyện của lobby HOME: cả ba consumer (Shift+1,
  Shift+9, new_account qua spawn_exit sequence) đều đi qua HOME entry, nên
  một bản recovery duy nhất ở `flows/lobby_map.py` phục vụ đủ cả ba.
  Blocker trong map (new_account map đầu, popup lubu) là business có sẵn của
  `automap_flow` (flag `new_account_lubu_popup_active`) — không thuộc đợt
  này. Train lobby không có blocker.
- Blocker pop sau khi signal đã thấy (click có thể trượt): hành vi giữ như
  hiện tại — hero-select không xác nhận → timeout → retry entry sequence,
  mà sequence bắt đầu bằng `ClearBlockersAction`. Robustness đến từ retry,
  không cần recovery xen vào lúc click.

### Pattern cho phase nhỏ mới

Đợt sau còn nhiều phase nhỏ cần xử lý (train_select, hero levelup picker,
...). Pattern chuẩn áp dụng từ đợt này:

- Phase = submodule thuần trong `flows/`: detection + click tối thiểu.
- Lobby/screen trước đó tự recovery đến khi detector báo sang được phase.
- Flow cấp keyboard (start_auto, spawn_exit_lvup, train, ...) ráp các phase.

### Dev reload

`runner/reload.py` reload `actions_loader` + `actions_runner` +
`flows.hero_select.detection`. Module mới ở flows (lobby_map, battle_exit,
spawn_exit_lvup, hero_select mở rộng) cần vào reload list theo pattern
`get_train_flow` — nếu không hot-reload mất tác dụng với phần business vừa
chuyển.

### Semantics retry/timeout giữ nguyên

Runner bọc cả chuỗi action trong một retry unit: timeout một action → restart
từ action đầu; 2 timeout liên tiếp → raise dừng flow; vòng hoàn thành →
reset count. Composition nào rời runner (start_auto, spawn_exit_lvup,
new_account) cũng giữ đúng semantics đó — kể cả cơ chế raise, không đổi
thành return False.

## Đề xuất commit

Tiền đề: không — 2 đổi tên trong `refactor_lobby_hero_select.md` đã hạ xuống
backlog, ranh giới actions ↔ business ưu tiên trước.

### C1a — `refactor(flows): hero-select phase detect+click; lobby_map sở hữu recovery`

Chưa đụng engine; hành vi giữ nguyên theo quy ước bàn giao ở trên:

- `flows/hero_select/` bổ sung module click: hàm wait-and-click nút vàng
  (capture → find_battle_button → click, timeout/poll/settle riêng). Package
  vẫn chỉ import `core` + `vision`.
- Tạo `flows/lobby_map.py`: recovery loop (popup tabs, blocker priority,
  re-click entry) port từ `actions/hero_select_battle.py`, kết thúc ở bàn
  giao: detector báo hero-select → gọi hàm click của phase.
- `actions/hero_select_battle.py` mỏng còn shell executor-gọi được, delegate
  sang `flows/lobby_map` (type chưa drop).
- `train_support/entry.py::wait_and_click_hero_select_battle` delegate hàm
  click của phase.
- Arch test: mở allowlist exception cho shell import `flows.lobby_map`.
- Tests: wrapper test tách theo nhà mới (recovery → `flows/lobby_map`,
  click → phase); `tests/flows/test_phase_boundaries.py` cập nhật.

### C1b — `refactor(flows): start_auto entry composition thuộc flows`

- `run_start_automap_loop` nhận entry phase (mechanical + lobby_map recovery
  + click nút vàng) thay vì `(start_actions, action_runner)`;
  `commands.resolve_start_auto` + `reload_policy` wiring theo pattern
  `get_train_flow`.
- Type `ClickHeroSelectBattleAction` chưa drop — spawn list của Shift+9 và
  new_account vẫn spread `build_start_battle_actions`.

### C2 — `refactor(exit): battle_exit submodule; drop smart action types`

- Tạo `flows/battle_exit/`:
  - `pause.py` — dùng chung: `find_pause_exit_button` (cặp đỏ/vàng) +
    `click_pause_exit` (retry icon pause đã verify).
  - `exit_map_confirm.py` — `find_map_exit_back_button` + `click_map_exit_back`.
  - `exit_train_confirm.py — xác nhận riêng của train sau khi thoát (logic
    lấy từ `train_support/exit_flow.py` nếu có; khởi điểm có thể mỏng).
- `flows/spawn_exit_lvup.py` (mới) compose full sequence (entry phase +
  battle_exit) thành một retry unit; `new_account.py` dùng mode 1 vòng.
- Drop cả 3 smart type (hero-select, pause-exit, map-exit-back) khỏi
  models/runner/executor; xóa shell `actions/hero_select_battle.py` +
  `actions/pause_exit.py`; mọi importer còn lại của pause_exit rewire sang
  battle_exit. `build_spawn_exit_lvup_actions` giữ lại nhưng chỉ còn phần
  cơ giới.
- Tests: `tests/actions/test_pause_exit.py` → `tests/flows/test_battle_exit/`;
  suite liên quan cập nhật.

### C3 — `test(arch): rewrite dependency rules theo cấu trúc đích`

- Rewrite sạch `tests/test_hauntedroom_architecture.py`: bỏ các dict
  allowlist lịch sử, viết lại rules đúng cấu trúc mới —
  - `actions/` không import `hauntedroom.flows*` (assert tuyệt đối, không
    exception).
  - `flows/hero_select/` chỉ import `core` + `vision`.
  - `flows/battle_exit/`, `flows/lobby_map.py`, `flows/spawn_exit_lvup.py`:
    dependency khai báo rõ ràng từng module.
  - Ranh giới recovery: file nào chứa recovery của lobby chỉ được sống ở
    lobby module tương ứng.
- Không drag allowlist cũ theo — viết lại từ cấu trúc đích.

### Ngoài phạm vi đợt này

- Tan rã hoàn toàn `actions/builder.py` (chuyển hết mechanical-list assembly
  về flows) — ứng viên đợt sau, xem xét khi composition đã ổn định.
- Tách các phase nhỏ còn lại (train_select, hero levelup picker) — làm theo
  pattern ở trên, đợt riêng.

## Nguyên tắc

- Behavior-preserving: semantics retry/timeout ở trên là hợp đồng — không
  "nhân tiện" đổi timing, log format, return value của path nào.
- JSON surface không đổi: 4 mechanical type, loader/validation/test JSON
  không đụng tới.
- Phase thuần không chứa recovery; lobby không click nút của phase. Ai cần
  robustness giữa signal và click thì dùng retry cấp flow, không làm bẩn
  phase.
- Không tạo hook/callback trong engine để business chui ngược vào actions.
- Arch test rewrite một lần cuối theo cấu trúc đích (C3), không giữ allowlist
  lịch sử.
- Mỗi commit chạy độc lập, suite xanh.

## Điều kiện hoàn thành

- `grep hauntedroom.flows tools/hauntedroom/actions/` → rỗng; arch test mới
  assert tuyệt đối.
- `actions/` chỉ còn: models (4 type), loader, validation, defaults,
  runner, runner_executor, builder (chỉ lắp mechanical list).
- `flows/hero_select/` chỉ có detect + click, chỉ import `core` + `vision`;
  recovery chỉ tồn tại ở `flows/lobby_map.py` (map) và lobby_train.
- `flows/battle_exit/` split pause (chung) / exit_map_confirm /
  exit_train_confirm; hai flow exit tự ráp.
- Ba keyboard flow (Shift+1, Shift+9, new_account) hành vi không đổi.
- Regression phase-boundary tests khớp ranh giới mới và vẫn khóa
  "hero-select chỉ có một implementation dùng chung".
