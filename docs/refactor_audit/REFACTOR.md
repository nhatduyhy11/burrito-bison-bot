# Refactor Review

Lần review gần nhất: 2026-08-20, theo code tại commit `95c1caa`.

## Test baseline

Suite chính, chạy từ root:

```shell
uv run --with pytest pytest -q
```

Kết quả ngày 2026-08-20:

```text
222 passed, 4 skipped, 46 subtests passed in 12.31s
```

`pyproject.toml` đã đặt `testpaths = ["tests"]`, nên lệnh trên không còn collect
`ref_cv/tests/test_vision.py`.

Bốn test bị skip đều ở `tests/control_events/test_new_tab_blocker.py` vì
`ENABLE_SCRIPT_INJECTION = False`. Ba test happy-path injection và cả test mang
tên `test_script_injection_is_enabled_by_default` đang dùng
`@skipUnless(ENABLE_SCRIPT_INJECTION, ...)`. Suite đã xanh nhưng contract của
default-off chưa được assert trực tiếp và happy path chưa chạy trong baseline.

## Snapshot line-count (2026-08-20)

Runtime/non-test files từ 200 dòng trở lên:

```text
 513 tools/hauntedroom/flows/automap.py
 338 tools/hauntedroom/runner/standby.py
 320 tools/hauntedroom/flows/artifact.py
 311 tools/hauntedroom/actions/runner.py
 305 tools/hauntedroom/core/runtime.py
 271 tools/hauntedroom/flows/automap_support/vision/hero_levelup.py
 258 tools/hauntedroom/flows/automap_support/hero_action.py
 251 tools/hauntedroom/runner/commands.py
 250 tools/hauntedroom/actions/loader.py
 223 tools/hauntedroom/core/template_matching.py
 213 tools/hauntedroom/flows/automap_support/map_completion.py
 205 tools/hauntedroom/flows/train.py
```

Test files từ 200 dòng trở lên:

```text
 685 tests/runner/test_standby_controller.py
 447 tests/hero_select/test_hero_fallback.py
 404 tests/hero_select/test_hero_select.py
 299 tests/actions/test_runner.py
 276 tests/automap/test_map_reward.py
 262 tests/special_flow/test_artifact_flow.py
 249 tests/runner/test_start_automap_loop.py
 243 tests/automap/test_gear.py
 237 tests/automap/test_level_up.py
 222 tests/test_hauntedroom_vision.py
 205 tests/actions/test_loader.py
```

Line count không tự động đồng nghĩa over-responsibility. Runtime cần theo dõi
nhất là `automap.py`, `artifact.py`, `actions/runner.py`, `actions/loader.py` và
`runner/standby.py`. Chưa có bằng chứng đủ mạnh để tách chúng chỉ vì kích thước;
riêng `standby.py` đã tăng do thêm screen routing nên nên theo dõi boundary giữa
queue/lifecycle và dispatch policy.

## Backlog còn lại

### 1. Đóng contract test cho script injection default-off

`ENABLE_SCRIPT_INJECTION` được tắt có chủ đích và source documentation cũng mô
tả đây là runtime switch. Không nên bật lại setting hoặc bỏ guard chỉ để tránh
skip.

Nên patch module-level setting sang `True` bên trong ba happy-path test cần kiểm
tra injection, bỏ `skipUnless`, và đổi test default thành assert `False`. Mục
tiêu là giữ runtime default-off nhưng cả nhánh enabled lẫn disabled đều được test.

### 2. Mở rộng architecture guardrail

`tests/test_hauntedroom_architecture.py` chủ yếu dùng `glob("*.py")`, nên chưa
quét recursive toàn bộ `flows/automap_support/` và `completion_flow/`. Test cũng
chưa khóa dependency rule cho `runner/`, entrypoint hay module top-level mới
`screen_detect.py`.

Dependency rule hiện hành được mô tả trong `docs/ARCHITECTURE.md`. Khi mở rộng
test, dùng source tree và tài liệu sống này làm chuẩn; ADR chỉ là historical
decision record, không phải inventory của wiring hiện tại.

Khi mở rộng test, cần giữ các composite dependency đã được cho phép, đặc biệt
`train.py`, wiring trong `runner/`, và dependency có chủ đích từ
`screen_detect.py` sang detector boss-progress của auto-map.

### 3. Làm phẳng state loop của research

`run_research_flow` vẫn chứa các nested loop cho state
`available -> active -> available`. Nếu flow này tiếp tục có thêm state, nên tách
helper như `wait_for_research_available` và `drain_active_research`, rồi giữ
`run_research_flow` làm coordinator.

### 4. Chỉ tạo config object cho blocker khi signature tiếp tục lớn

`clear_blockers` có signature dài và `timeout_ms` hiện mang nghĩa inactivity
timeout vì deadline được reset sau mỗi blocker click. Nếu thêm option mới, nên
gom cấu hình vào `BlockerConfig` và đổi tên/docstring để semantics rõ ràng. Đây là
cleanup ưu tiên thấp, chưa cần làm độc lập ngay.

## Test organization còn có thể cải thiện

- `tests/runner/test_standby_controller.py` hiện cover `FlowControl`, command
  policy, reload policy, screen routing, standby orchestration, click loop và
  listener. Đây là ứng viên tách rõ nhất nếu tiếp tục thêm routing/policy.
- Hai file `tests/hero_select/test_hero_fallback.py` và
  `tests/hero_select/test_hero_select.py` nên được reorganize cùng nhau theo
  vision, choice policy, action behavior và thin `AutomapFlow` adapter; không nên
  tách riêng chỉ dựa trên line count.
- Các test scenario/fixture dài nhưng vẫn cohesive chưa cần tách tiếp.

## Auto-map boundary hiện tại

`AutomapFlow` giữ template loading, mutable state, handler priority và public
API. Logic chi tiết nằm trong:

- `map_completion.py`: map-end/home orchestration.
- `completion_flow/first_win.py`: daily-first-win lifecycle.
- `completion_flow/reward.py`: win reward, reward list và fallback clicks.
- `completion_flow/blocker.py`: post-map blocker detection/cleanup.
- `completion_flow/state.py`: result/state và runtime context dùng chung.
- `upgrade_action.py`: level spin, level-up confirm và build menu.
- `hero_action.py`: priority và thao tác hero level-up.
- `vision/hero_levelup.py`: template/calibration và hero visual queries.
- `boss_flow.py`, `boss_action.py` và `vision/boss_*.py`: boss orchestration,
  actions, controls, HP và progress detection.
- `gear_action.py` và `vision/gear.py`: gear placement/action và detection.

Boundary này hiện truyền khá nhiều callable/runtime dependency qua map completion
helpers. Nếu tiếp tục thêm phase, cân nhắc một runtime context/adapter nhỏ; chưa
cần registry tổng quát hay Clean Architecture đầy đủ.

## Thứ tự đề xuất

1. Đổi bốn script-injection test từ skip sang test rõ hai trạng thái on/off.
2. Mở rộng architecture test cho subtree, `runner/`, entrypoint và
   `screen_detect.py`; đồng bộ `docs/ARCHITECTURE.md` nếu boundary thay đổi.
3. Chỉ sau đó mới cân nhắc research helpers, tách test lớn hoặc `BlockerConfig`.

## Nguyên tắc khi refactor

- Giữ dependency rule trong `docs/ARCHITECTURE.md` và khóa invariant quan trọng
  bằng architecture test; không dùng ADR như tài liệu sống.
- Sau mỗi bước, chạy `uv run --with pytest pytest -q` từ root.
- Ưu tiên baseline không skip nhánh quan trọng và input boundary chặt hơn việc
  chia file theo line count.
- Mỗi thay đổi nên nhỏ và rollback độc lập được.
