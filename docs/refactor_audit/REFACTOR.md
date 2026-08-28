# Refactor Audit

File này chỉ mô tả current state và các finding còn mở trên code hiện tại.

## Quy tắc duy trì file

- Đây không phải changelog, progress log, checklist hoàn thành hay nơi ghi nhận
  công việc đã làm.
- Chỉ giữ thông tin còn đúng và còn cần hành động trên code hiện tại.
- Finding được xử lý xong phải xóa toàn bộ khỏi file; không đánh dấu `done`, gạch
  ngang, chuyển sang mục completed hay để lại đoạn tổng kết kết quả.
- Khi current state thay đổi, cập nhật hoặc xóa snapshot cũ ngay trong cùng thay
  đổi; không giữ số liệu hay mô tả cũ để đối chiếu lịch sử.
- Lịch sử thay đổi thuộc về Git/commit/PR, không thuộc file này.

## Test baseline

Chạy từ repository root:

```shell
uv run --with pytest pytest -q
```

Baseline hiện tại:

```text
282 passed, 4 skipped, 105 subtests passed
```

Bốn test bị skip đều nằm trong
`tests/control_events/test_new_tab_blocker.py`. Nguyên nhân là runtime chủ đích đặt
`ENABLE_SCRIPT_INJECTION = False`, trong khi ba happy-path injection và test mang
`test_script_injection_is_enabled_by_default` cùng dùng
`@skipUnless(ENABLE_SCRIPT_INJECTION, ...)`. Suite đang xanh nhưng chưa thực thi
nhánh enabled và chưa assert trực tiếp contract default-off.

## Snapshot line count

Runtime/non-test Python files từ 200 dòng trở lên:

```text
 405 tools/hauntedroom/runner/commands.py
 382 tools/hauntedroom/flows/automap_support/flow.py
 346 tools/hauntedroom/runner/standby.py
 320 tools/hauntedroom/flows/artifact.py
 302 tools/hauntedroom/flows/automap_support/map/lifecycle.py
 277 tools/hauntedroom/flows/automap_support/vision/hero_levelup.py
 258 tools/hauntedroom/flows/automap_support/hero_action.py
 250 tools/hauntedroom/actions/loader.py
 232 tools/hauntedroom/screen_detect.py
 226 tools/hauntedroom/runner/reload.py
 223 tools/hauntedroom/core/template_matching.py
 223 tools/hauntedroom/actions/runner_executor.py
 215 tools/hauntedroom/actions/pause_exit.py
 211 tools/hauntedroom/core/runtime.py
 201 tools/hauntedroom/flows/diamond_collection.py
```

Test files từ 200 dòng trở lên:

```text
 423 tests/automap/test_map_reward.py
 412 tests/runner/test_standby_orchestration.py
 297 tests/runner/test_start_automap_loop.py
 286 tests/automap/test_flow.py
 275 tests/hero_select/test_hero_choice_policy.py
 262 tests/special_flow/test_artifact_flow.py
 251 tests/automap/test_level_up.py
 249 tests/automap/test_gear.py
 229 tests/hero_select/test_hero_action.py
 222 tests/test_hauntedroom_vision.py
 206 tests/actions/test_hero_select_battle.py
 205 tests/runner/test_standby_hotkeys.py
 205 tests/actions/test_runner.py
 205 tests/actions/test_loader.py
 202 tests/actions/test_runner_executor.py
```

Line count chỉ là tín hiệu để review, không tự động đồng nghĩa với
over-responsibility. Sau khi `actions/runner.py` được tách thành `runner.py`
(169 dòng) và `runner_executor.py` (223 dòng), `runner/commands.py` (405 dòng)
và `runner/standby.py` (346 dòng) trở thành hai điểm cần theo dõi chính trong
package `runner/`.

## Finding còn mở

### P1. Đóng contract test cho script injection default-off

Giữ runtime default-off. Trong ba happy-path test, patch setting của module
`hauntedroom.control_events.new_tab_blocker` sang `True` và bỏ `skipUnless`. Đổi
test default thành assert `False` mà không skip. Kết quả mong muốn là cả nhánh
enabled lẫn disabled đều chạy trong baseline.

### P1. Mở rộng architecture guardrail

`tests/test_hauntedroom_architecture.py` mới kiểm tra các Python file trực tiếp
trong `core/`, `actions/`, `control_events/`, `flows/`, `vision/` và riêng thư mục
`automap_support/vision/`. Test chưa quét recursive toàn bộ
`flows/automap_support/`, package `map/`, `runner/`, composition root và
`screen_detect.py`.

Ngoài ra, allowed imports của `train.py` trong test kiến trúc đang bị stale
(vẫn chứa `actions.models`, `actions.runner`, `boss_action` dù code đã dọn sạch
sau khi hợp nhất train flow). Cần cập nhật rule và mở rộng test theo dependency
direction trong `docs/ARCHITECTURE.md`.

### P2. Tách action builders và flow resolvers khỏi `runner/commands.py`

`tools/hauntedroom/runner/commands.py` đã phình lên 405 dòng và đang gánh 3
trách nhiệm khác nhau:
1. Factory tạo fixed action list (`build_start_battle_actions`,
   `build_spawn_exit_lvup_actions`, `build_newbie_block_actions`) phụ thuộc trực
   tiếp template assets tại `ROOMS_DIR`.
2. 11 flow resolver closures chứa logic lặp (`MapRunState()`, async wrapper,
   reload lookup).
3. Định nghĩa FlowCommand metadata và registry builder `build_flow_commands`.

Cần tách action list builders và flow resolvers ra module riêng để `commands.py`
chỉ tập trung vào command registry và dispatch model.

### P2. Xóa coupling ngược từ `flows/new_account.py` sang `screen_detect.py`

`tools/hauntedroom/flows/new_account.py` đang import trực tiếp `ScreenName`,
`detect_screen` và `NEW_ACCOUNT_ACTION_CLICK` từ `hauntedroom.screen_detect`.
Theo dependency rule trong `docs/ARCHITECTURE.md`, tầng `flows` chỉ phụ thuộc
`core` (và support module nội bộ của flow), không phụ thuộc `screen_detect`.

Đồng thời, `screen_detect.py` (module nhận diện screen) đang sở hữu action
coordinate constant `NEW_ACCOUNT_ACTION_CLICK = (320, 630)` và detector
`find_new_account_action_click`. Cần chuyển action coordinate/detector về
flow helper hoặc vision vocabulary thích hợp và điều phối vòng lặp chuyển
screen qua runner/callback.

### P2. Chuẩn hóa boundary của `vision/` package trong tài liệu kiến trúc

Module `tools/hauntedroom/vision/buttons.py` đã được tạo để chia sẻ vocabulary màu
và hình học của button (`ButtonColor`, `ButtonGeometry`, `find_colored_button`)
giữa `actions` (`hero_select_battle.py`, `pause_exit.py`) và `flows` (`train.py`).
Tuy nhiên, `docs/ARCHITECTURE.md` chưa bổ sung `vision/` vào cây package boundaries
và ma trận dependency direction (`vision -> core`, `actions/flows -> vision`).

### P3. Chuẩn hóa dependency của map blocker với `control_events`

`tools/hauntedroom/flows/automap_support/map/blocker.py` đang import
`blocker_dismiss_click` từ `hauntedroom.control_events.blockers`. Trong kiến
trúc hiện tại, `flows` không phụ thuộc `control_events`. Semantics tính toán
dismiss coordinate của blocker nên thuộc về template matching / vision hoặc
được inject qua context để tránh tạo dependency chéo giữa business map flow và
control event layer.

### P3. Làm phẳng state loop của research khi sửa flow này

`run_research_flow` vẫn chứa hai nested loop cho chu kỳ
`available -> active -> available`. Khi flow cần thêm state hoặc có thay đổi hành
vi, tách `wait_for_research_available` và `drain_active_research`, giữ
`run_research_flow` làm coordinator. Chưa cần refactor riêng khi contract không
đổi.

### P3. Gom cấu hình blocker khi signature tiếp tục lớn

`clear_blockers` đang nhận nhiều tham số và `timeout_ms` thực chất là inactivity
timeout vì deadline được reset sau mỗi blocker click. Khi thêm option mới, gom
cấu hình vào `BlockerConfig` và đổi tên hoặc bổ sung docstring để semantics rõ
ràng. Chưa cần tạo abstraction riêng nếu signature không đổi.

## Guardrail khi xử lý backlog

- Dùng `docs/ARCHITECTURE.md` làm dependency rule sống và khóa invariant ổn định
  bằng architecture test.
- Sau mỗi thay đổi, chạy `uv run --with pytest pytest -q` từ repository root.
- Ưu tiên coverage cho nhánh quan trọng và input boundary chặt chẽ hơn việc chia
  file chỉ theo line count.
- Giữ mỗi thay đổi đủ nhỏ để review và rollback độc lập.
