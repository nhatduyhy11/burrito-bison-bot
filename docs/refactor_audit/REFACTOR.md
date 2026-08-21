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
233 passed, 4 skipped, 82 subtests passed
```

Bốn test bị skip đều nằm trong
`tests/control_events/test_new_tab_blocker.py`. Nguyên nhân là runtime chủ đích đặt
`ENABLE_SCRIPT_INJECTION = False`, trong khi ba happy-path injection và test mang
tên `test_script_injection_is_enabled_by_default` cùng dùng
`@skipUnless(ENABLE_SCRIPT_INJECTION, ...)`. Suite đang xanh nhưng chưa thực thi
nhánh enabled và chưa assert trực tiếp contract default-off.

## Snapshot line count

Runtime/non-test Python files từ 200 dòng trở lên:

```text
 339 tools/hauntedroom/runner/standby.py
 321 tools/hauntedroom/runner/commands.py
 320 tools/hauntedroom/flows/artifact.py
 317 tools/hauntedroom/actions/runner.py
 301 tools/hauntedroom/flows/automap_support/flow.py
 272 tools/hauntedroom/flows/automap_support/map/lifecycle.py
 271 tools/hauntedroom/flows/automap_support/vision/hero_levelup.py
 258 tools/hauntedroom/flows/automap_support/hero_action.py
 250 tools/hauntedroom/actions/loader.py
 223 tools/hauntedroom/core/template_matching.py
 212 tools/hauntedroom/flows/train.py
 209 tools/hauntedroom/core/runtime.py
```

Test files từ 200 dòng trở lên:

```text
 359 tests/runner/test_standby_orchestration.py
 342 tests/actions/test_runner.py
 277 tests/automap/test_map_reward.py
 262 tests/special_flow/test_artifact_flow.py
 258 tests/runner/test_start_automap_loop.py
 258 tests/hero_select/test_hero_choice_policy.py
 249 tests/automap/test_gear.py
 244 tests/automap/test_level_up.py
 229 tests/hero_select/test_hero_action.py
 222 tests/test_hauntedroom_vision.py
 205 tests/actions/test_loader.py

Line count chỉ là tín hiệu để review, không tự động đồng nghĩa với
over-responsibility. Điểm cần theo dõi rõ nhất là boundary transport/dispatch/task
lifecycle trong `runner/standby.py`. Các module auto-map lớn hiện thuộc boundary
scheduler hoặc map lifecycle tương ứng.

## Finding còn mở

### P1. Đóng contract test cho script injection default-off

Giữ runtime default-off. Trong ba happy-path test, patch setting của module
`hauntedroom.control_events.new_tab_blocker` sang `True` và bỏ `skipUnless`. Đổi
test default thành assert `False` mà không skip. Kết quả mong muốn là cả nhánh
enabled lẫn disabled đều chạy trong baseline.

### P1. Mở rộng architecture guardrail

`tests/test_hauntedroom_architecture.py` mới kiểm tra các Python file trực tiếp
trong `core/`, `actions/`, `control_events/`, `flows/` và riêng thư mục
`automap_support/vision/`. Test chưa quét recursive toàn bộ
`flows/automap_support/`, package `map/`, `runner/`, composition root và
`screen_detect.py`.

Mở rộng guard theo dependency rule trong `docs/ARCHITECTURE.md`. Cần biểu diễn rõ
các dependency composite được phép, gồm wiring trong `runner/`, `train.py` và
dependency có chủ đích từ `screen_detect.py` tới detector boss-progress. ADR chỉ
là historical decision record, không dùng làm inventory của wiring hiện tại.

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
