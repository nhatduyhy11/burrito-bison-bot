# Split `tests/runner/test_standby_orchestration.py` thành 3 file

- Ngày: 2026-09-04
- Status: Draft — chờ review

## Bối cảnh

- `tests/runner/test_standby_orchestration.py` dài 457 dòng, 10 test trong một class
  `StandbyOrchestrationTest` — file test lớn nhất trong `tests/runner/` (xem snapshot
  line count trong `docs/refactor_audit/REFACTOR.md`).
- 10 test đang phủ ba responsibility khác nhau của `run_standby_controller`:
  hành vi khi idle, dispatch command → flow, và lifecycle của flow đang chạy.
- `tests/runner/test_standby_hotkeys.py` đã tách sẵn phần hotkey config/remap từ trước;
  phần còn lại đúng là orchestration loop.

## Mục tiêu

- Tách thành 3 file theo responsibility, mỗi file 2-4 test (không atomic quá mức).
- Pure mechanical move: giữ nguyên thân test, không đổi assertion, không đổi tên test
  method. Module, class và fully-qualified test ID sẽ đổi theo cấu trúc file mới.
- Tổng số test giữ nguyên: 10.

## Non-goals

- Không extract helper / shared base class. Pattern lặp
  `save_live_screenshot.side_effect = RuntimeError("stop test loop")` và
  `enqueue_commands` chỉ 1-2 dòng mỗi test, không đáng thêm một module helper.
- Không sửa runtime code (`tools/hauntedroom/runner/standby.py`).
- Không đổi `test_standby_hotkeys.py`.

## Cấu trúc mới

### 1. `tests/runner/test_standby_idle.py` — class `StandbyIdleTest`

Hành vi khi idle, gồm các trường hợp chưa có flow hoặc không thể start flow:

| Test | Nội dung |
| --- | --- |
| `test_shift_8_saves_live_screenshot_and_accepts_the_next_command` | Phím `8` lưu screenshot rồi quay lại idle |
| `test_unknown_screen_stays_idle_and_accepts_the_next_command` | Screen `UNKNOWN` không start flow, giữ idle |
| `test_resolver_failure_keeps_idle_and_accepts_the_next_command` | Resolver lỗi trước khi start flow → giữ idle |

### 2. `tests/runner/test_standby_dispatch.py` — class `StandbyDispatchTest`

Mỗi hotkey route tới đúng flow với đúng arguments:

| Test | Nội dung |
| --- | --- |
| `test_shift_1_on_home_starts_combined_loop_with_automap` | HOME: start automap loop kèm `AutomapRuntime` |
| `test_shift_t_starts_train_ad_exit_flow` | `T` start train ad-exit flow |
| `test_shift_e_starts_train_immediate_exit_flow_without_pet_and_ad` | `E` start immediate exit, `pet_and_ad=False` |
| `test_shift_1_on_train_starts_train_then_automap_flow` | TRAIN: start train flow rồi automap |

### 3. `tests/runner/test_standby_flow_lifecycle.py` — class `StandbyFlowLifecycleTest`

Flow đang chạy: control và cách thoát về idle:

| Test | Nội dung |
| --- | --- |
| `test_auto_switched_home_flow_can_pause_resume_and_stop` | `FlowControl` pause / resume / stop qua hotkey |
| `test_completed_flow_returns_idle_and_accepts_the_next_command` | Flow hoàn tất → về idle |
| `test_busy_runner_rejects_a_second_flow` | Flow đang chạy, hotkey thứ hai bị từ chối |

## Imports theo file

Header `sys.path.insert` giữ nguyên ở cả ba file. Imports prune theo usage:

| File | Imports cần giữ | Bỏ |
| --- | --- | --- |
| `test_standby_idle.py` | `IsolatedAsyncioTestCase`, `AsyncMock`, `Mock`, `patch`, `FlowCommand`, `ScreenName`, `FLOW_COMMANDS`, `run_standby_controller` | `asyncio`, `Path` (ngoài header), `FlowControl`, `ResolvedFlow`, `AutomapRuntime` |
| `test_standby_dispatch.py` | `IsolatedAsyncioTestCase`, `AsyncMock`, `Mock`, `patch`, `Path`, `AutomapRuntime`, `ScreenName`, `FLOW_COMMANDS`, `run_standby_controller` | `asyncio`, `FlowControl`, `FlowCommand`, `ResolvedFlow` |
| `test_standby_flow_lifecycle.py` | `asyncio`, `IsolatedAsyncioTestCase`, `AsyncMock`, `Mock`, `patch`, `FlowControl`, `FlowCommand`, `ResolvedFlow`, `AutomapRuntime`, `ScreenName`, `FLOW_COMMANDS`, `run_standby_controller` | `Path` (ngoài header) |

Lý do dispatch không cần `asyncio`: bốn test chỉ dùng async def local
(`enqueue_commands`, `wait_until_stopped`) do framework chạy, không gọi trực tiếp
module `asyncio`.

## Docs cập nhật

- `docs/TESTING.md` (khối "Chạy một module", dòng 55): đổi
  `tests.runner.test_standby_hotkeys tests.runner.test_standby_orchestration` thành
  `tests.runner.test_standby_hotkeys tests.runner.test_standby_idle tests.runner.test_standby_dispatch tests.runner.test_standby_flow_lifecycle`.
- `docs/refactor_audit/REFACTOR.md` và `docs/audit/COLORIZE_AUDIT.md`: snapshot/audit
  lịch sử, giữ nguyên.

## Verification

1. `uv run python -m unittest tests.runner.test_standby_idle tests.runner.test_standby_dispatch tests.runner.test_standby_flow_lifecycle -v` → 10 tests, tất cả pass.
2. `uv run --with pytest pytest tests/runner/test_standby_idle.py tests/runner/test_standby_dispatch.py tests/runner/test_standby_flow_lifecycle.py -q` → 10 passed (pytest discovery class unittest).
3. `uv run --with pytest pytest tests -q` → toàn bộ suite pass, không có test bị
   duplicate hoặc mất khỏi discovery.
4. `git grep -n standby_orchestration -- ':!__pycache__' ':!docs/planning/2026-09-04-standby-orchestration-test-split-design.md'`
   → chỉ còn match trong `REFACTOR.md` và `COLORIZE_AUDIT.md` (lịch sử), không còn
   path sống. File plan được exclude vì có nhắc tên module cũ để mô tả thay đổi.
5. Ghi nhận baseline 10 test trước khi tạo file mới; sau khi split và xoá file cũ,
   xác nhận ba module mới vẫn được discovery đúng tổng cộng 10 test.
