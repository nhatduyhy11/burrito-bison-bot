# Refactor Review

Lần review gần nhất: 2026-08-19, theo code tại commit `de02453`.

## Kết luận

Structure hiện tại vẫn hợp lý cho một bot local, khoảng **7/10**. Ranh giới
`core / actions / control_events / flows / runner` nhìn chung rõ, dependency
direction cơ bản đúng, và `hauntedroom_runner.py` vẫn là composition root gọn
(80 dòng).

Các đợt refactor gần đây đã hoàn tất những phần chính sau:

- Auto-map vision đã được chia theo concern trong `automap_support/vision/`.
- Map completion đã có orchestrator và owner riêng cho first-win, reward và
  blocker.
- Test boss và map completion đã được chia theo boundary tương ứng.
- Root pytest đã được giới hạn vào `tests/`, không còn collect project tham khảo
  độc lập `ref_cv/`.
- Standby đã có screen auto-switch: `Shift+1` capture đúng một frame, nhận diện
  màn hình và dispatch flow tương ứng.
- Command definition đã dùng semantic key và metadata
  `uses_automap_controls`, không còn gắn policy auto-map vào các phím cứng
  `Shift+2`/`Shift+3`.
- Screenshot fallback đã được gom dưới `.tmp/hauntedroom-fallbacks/` và có test
  khóa đường dẫn.

Các hạng mục đã hoàn tất không còn nằm trong backlog bên dưới.

## Test baseline

Suite chính, chạy từ root:

```shell
uv run --with pytest pytest -q
```

Kết quả ngày 2026-08-19:

```text
217 passed, 4 skipped, 36 subtests passed in 24.99s
```

`pyproject.toml` đã đặt `testpaths = ["tests"]`, nên lệnh trên không còn collect
`ref_cv/tests/test_vision.py`.

Bốn test bị skip đều ở `tests/control_events/test_new_tab_blocker.py` vì
`ENABLE_SCRIPT_INJECTION = False`. Ba test happy-path injection và cả test mang
tên `test_script_injection_is_enabled_by_default` đang dùng
`@skipUnless(ENABLE_SCRIPT_INJECTION, ...)`. Suite đã xanh nhưng contract của
default-off chưa được assert trực tiếp và happy path chưa chạy trong baseline.

## Structure hiện tại

```text
tools/hauntedroom/
├── core/                    # runtime, CLI, mouse, template, vision primitives
├── actions/                 # JSON loader/runner + typed action models
├── control_events/          # blocker/new-tab handling
├── runner/                  # standby, command specs/wiring, navigation, reload
├── screen_detect.py         # screen enum, anchor detection và capture wrapper
├── flows/                   # business flows do command resolver khởi chạy
│   ├── automap.py           # auto-map coordinator/public API/state
│   ├── automap_support/
│   │   ├── completion_flow/ # first-win, reward, blocker, shared state
│   │   └── vision/          # boss, build, gear, hero và train detectors
│   ├── start_auto.py        # home -> start room -> auto-map loop
│   ├── train.py             # train + handoff sang auto-map
│   ├── exp_available.py
│   ├── hero_up_available.py
│   ├── artifact.py
│   ├── click_loop.py
│   └── research.py
└── settings.py              # source-level runtime switches
```

Screen routing hiện được chia thành ba phần:

- `screen_detect.py`: `ScreenName`, detector anchor và `detect_current_screen`.
- `runner/default_commands.py`: giữ toàn bộ semantic flow definition, public
  direct commands và mapping `ScreenName -> FlowCommand`.
- `runner/standby.py`: xử lý `Shift+1`, detect một lần rồi resolve/start flow;
  `train` và `unknown` hiện chỉ log, không dispatch.

Direct binding còn lại là `Shift+T` cho train và `Shift+5` cho fixed-position
click loop. Auto-map/start-auto do screen routing khởi chạy vẫn dùng bộ control
cấu hình trong `START_AUTO_HOTKEYS`.

## Snapshot line-count (2026-08-19)

Runtime/non-test files từ 200 dòng trở lên:

```text
 516 tools/hauntedroom/flows/automap.py
 413 tools/hauntedroom/flows/artifact.py
 407 tools/hauntedroom/actions/runner.py
 319 tools/hauntedroom/runner/standby.py
 319 tools/hauntedroom/actions/loader.py
 300 tools/hauntedroom/core/runtime.py
 271 tools/hauntedroom/flows/automap_support/vision/hero_levelup.py
 258 tools/hauntedroom/flows/automap_support/hero_action.py
 233 tools/hauntedroom/runner/commands.py
 222 tools/hauntedroom/flows/automap_support/map_completion.py
 215 tools/hauntedroom/core/template.py
 209 tools/hauntedroom/runner/reload.py
 205 tools/hauntedroom/flows/train.py
```

Test files từ 200 dòng trở lên:

```text
 652 tests/runner/test_standby_controller.py
 447 tests/hero_select/test_hero_fallback.py
 404 tests/hero_select/test_hero_select.py
 286 tests/actions/test_runner.py
 274 tests/automap/test_map_reward.py
 262 tests/special_flow/test_artifact_flow.py
 256 tests/runner/test_start_automap_loop.py
 243 tests/automap/test_gear.py
 237 tests/automap/test_level_up.py
 222 tests/test_hauntedroom_vision.py
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

### 2. Mở rộng architecture guardrail và đồng bộ ADR

`tests/test_hauntedroom_architecture.py` chủ yếu dùng `glob("*.py")`, nên chưa
quét recursive toàn bộ `flows/automap_support/` và `completion_flow/`. Test cũng
chưa khóa dependency rule cho `runner/`, entrypoint hay module top-level mới
`screen_detect.py`.

`docs/ADR_bot.md` vẫn mô tả hotkey và wiring cũ: `Shift+1` là action JSON,
auto-map/start-auto là `Shift+2`/`Shift+3`, và `standby.py` không import
`runner.commands`. Code hiện đã chuyển sang semantic flow definitions,
`SCREEN_FLOW_COMMANDS` và screen auto-switch. Cần cập nhật ADR cùng lúc với rule
test để rule được viết theo architecture hiện hành, không theo tên hotkey cũ.

Khi mở rộng test, cần giữ các composite dependency đã được cho phép, đặc biệt
`train.py`, wiring trong `runner/`, và dependency có chủ đích từ
`screen_detect.py` sang detector boss-progress của auto-map.

### 3. Đóng kín validation của action loader

`load_actions` đã trả `list[Action]` và runner dùng typed fields trực tiếp. Phần
còn thiếu nằm ở input boundary:

- `wait.ms` chưa chặn giá trị âm và lỗi sai kiểu vẫn rò trực tiếp từ `int()`.
- `click.x`/`click.y` ép bằng `int()` nhưng error message sai kiểu chưa thân thiện.
- `button` của `click` và `click_template` chưa giới hạn vào giá trị Playwright
  hợp lệ.
- Một số numeric field được ép kiểu trong cả `validate_timing_fields` và loader,
  tạo validation trùng và thông báo lỗi không đồng nhất.

### 4. Làm phẳng state loop của research

`run_research_flow` vẫn chứa các nested loop cho state
`available -> active -> available`. Nếu flow này tiếp tục có thêm state, nên tách
helper như `wait_for_research_available` và `drain_active_research`, rồi giữ
`run_research_flow` làm coordinator.

### 5. Chỉ tạo config object cho blocker khi signature tiếp tục lớn

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
2. Đồng bộ `docs/ADR_bot.md`, sau đó mở rộng architecture test cho subtree,
   `runner/`, entrypoint và `screen_detect.py`.
3. Hoàn thiện validation tại action loader boundary.
4. Chỉ sau đó mới cân nhắc research helpers, tách test lớn hoặc `BlockerConfig`.

## Nguyên tắc khi refactor

- Giữ dependency rule trong `docs/ADR_bot.md`, nhưng cập nhật ADR trước khi dùng
  nó làm guardrail cho screen-routing architecture mới.
- Sau mỗi bước, chạy `uv run --with pytest pytest -q` từ root.
- Ưu tiên baseline không skip nhánh quan trọng và input boundary chặt hơn việc
  chia file theo line count.
- Mỗi thay đổi nên nhỏ và rollback độc lập được.
