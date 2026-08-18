# Refactor Review

Lần review gần nhất: 2026-08-19

## Kết luận

Structure hiện tại vẫn hợp lý cho một bot local, khoảng **7/10**. Ranh giới
`core / actions / control_events / flows / runner` rõ, dependency direction về
cơ bản đúng với `docs/ADR_bot.md`, và `hauntedroom_runner.py` là composition root
gọn (79 dòng).

Các đợt refactor gần đây đã hoàn tất những phần chính sau:

- Auto-map vision đã được chia theo concern trong `automap_support/vision/`.
- Map completion đã có orchestrator và owner riêng cho first-win, reward và
  blocker.
- Test boss và map completion đã được chia theo boundary tương ứng; file adapter
  còn lại lần lượt chỉ 43 và 90 dòng.
- Test `level_up` đã import constants từ `upgrade_action.py`, nên không còn lỗi
  collection cũ.

Các hạng mục đã hoàn tất không còn nằm trong backlog bên dưới.

## Test baseline

Suite chính:

```shell
uv run --with pytest pytest tests -q
```

Kết quả ngày 2026-08-19:

```text
4 failed, 210 passed, 23 subtests passed
```

Cả bốn failure đều ở `tests/control_events/test_new_tab_blocker.py`.
`tools/hauntedroom/settings.py` đặt `ENABLE_SCRIPT_INJECTION = False`, trong khi
ba happy-path test gọi guard mà không patch setting sang `True`, và test còn lại
vẫn yêu cầu default là `True`.

Chạy pytest từ root mà không chỉ định thư mục vẫn lỗi collection:

```shell
uv run --with pytest pytest -q
```

```text
ERROR collecting ref_cv/tests/test_vision.py
ModuleNotFoundError: No module named 'vision'
```

Nguyên nhân là root pytest collect cả project tham khảo độc lập `ref_cv/`.

## Structure hiện tại

```text
tools/hauntedroom/
├── core/                    # runtime, CLI, mouse, template, vision primitives
├── actions/                 # JSON loader/runner + typed action models
├── control_events/          # blocker/new-tab handling
├── runner/                  # hotkey standby, command specs, dev reload
├── flows/                   # hotkey business flows
│   ├── automap.py           # auto-map coordinator/public API/state
│   ├── automap_support/
│   │   ├── completion_flow/ # first-win, reward, blocker, shared state
│   │   └── vision/          # boss, build, gear, hero and train detectors
│   ├── start_auto.py        # Shift+3 composite flow
│   ├── train.py             # Shift+4 train + handoff sang auto-map
│   ├── exp_available.py     # Shift+5 EXP flow
│   ├── hero_up_available.py # Shift+6 breakthrough flow
│   ├── artifact.py          # Shift+Y artifact flow
│   ├── click_loop.py
│   └── research.py
└── settings.py              # source-level runtime switches
```

## Snapshot line-count (2026-08-19)

Runtime/non-test files từ 200 dòng trở lên:

```text
 516 tools/hauntedroom/flows/automap.py
 413 tools/hauntedroom/flows/artifact.py
 407 tools/hauntedroom/actions/runner.py
 319 tools/hauntedroom/actions/loader.py
 295 tools/hauntedroom/core/runtime.py
 276 tools/hauntedroom/runner/standby.py
 271 tools/hauntedroom/flows/automap_support/vision/hero_levelup.py
 254 tools/hauntedroom/flows/automap_support/hero_action.py
 230 tools/hauntedroom/runner/commands.py
 222 tools/hauntedroom/flows/automap_support/map_completion.py
 215 tools/hauntedroom/core/template.py
 209 tools/hauntedroom/runner/reload.py
 205 tools/hauntedroom/flows/train.py
```

Test files từ 200 dòng trở lên:

```text
 616 tests/runner/test_standby_controller.py
 449 tests/hero_select/test_hero_fallback.py
 404 tests/hero_select/test_hero_select.py
 286 tests/actions/test_runner.py
 274 tests/automap/test_map_reward.py
 262 tests/special_flow/test_artifact_flow.py
 243 tests/automap/test_gear.py
 241 tests/runner/test_start_automap_loop.py
 237 tests/automap/test_level_up.py
 222 tests/test_hauntedroom_vision.py
```

Line count không tự động đồng nghĩa over-responsibility. Runtime cần theo dõi
nhất là `automap.py`, `artifact.py`, `actions/runner.py` và `actions/loader.py`.
Hiện chưa có bằng chứng đủ mạnh để tách chúng chỉ vì kích thước.

## Backlog còn lại

### 1. Đồng bộ contract script injection để suite chính xanh

`ENABLE_SCRIPT_INJECTION` đã được đổi sang `False` có chủ đích từ 2026-08-11 và
source-level documentation cũng mô tả đây là runtime switch. Recommendation là
giữ default tắt, patch `True` trong ba happy-path test cần kiểm tra injection, và
đổi test default để assert `False`.

Không nên bật lại setting hoặc bỏ guard trong implementation chỉ để làm test
xanh.

### 2. Giới hạn pytest discovery ở root

`pyproject.toml` đang dùng `package = false`, các test chính tự thêm `tools` vào
`sys.path`; cách này vẫn phù hợp cho bot local. Tuy nhiên nên cấu hình pytest chỉ
collect `tests/` để `pytest` ở root không đi vào `ref_cv/tests`.

### 3. Mở rộng architecture guardrail

`tests/test_hauntedroom_architecture.py` chủ yếu dùng `glob("*.py")`, nên chưa
quét recursive toàn bộ `flows/automap_support/` và `completion_flow/`. Test cũng
chưa khóa dependency rule cho `runner/`.

Nên chuyển phần quét package sang recursive và thêm rule để các layer thấp không
import ngược `runner`/entrypoint. Khi làm cần giữ các composite dependency đã
được ADR cho phép, đặc biệt `train.py` và wiring trong `runner/`.

### 4. Đóng kín validation của action loader

`load_actions` đã trả `list[Action]` và runner hiện dùng typed fields trực tiếp,
không còn fallback ép kiểu trên raw dict. Phần còn thiếu nằm ở input boundary:

- `wait.ms` chưa chặn giá trị âm và chưa có lỗi sai kiểu rõ ràng.
- `click.x`/`click.y` ép bằng `int()` nhưng error message sai kiểu chưa thân thiện.
- `button` chưa giới hạn vào các giá trị Playwright hợp lệ.

### 5. Làm phẳng state loop của research

`run_research_flow` vẫn chứa hai nested loop cho state
`available -> active -> available`. Nếu flow này tiếp tục có thêm state, nên tách
helper như `wait_for_research_available` và `drain_active_research`, rồi giữ
`run_research_flow` làm coordinator.

### 6. Chỉ tạo config object cho blocker khi signature tiếp tục lớn

`clear_blockers` có signature dài và `timeout_ms` hiện mang nghĩa inactivity
timeout vì deadline được reset sau mỗi blocker click. Nếu thêm option mới, nên
gom cấu hình vào `BlockerConfig` và đổi tên/docstring để semantics rõ ràng. Đây là
cleanup ưu tiên thấp, chưa cần làm độc lập ngay.

## Test organization còn có thể cải thiện

- `tests/runner/test_standby_controller.py` có boundary rõ giữa `FlowControl`,
  command policy, reload policy, standby orchestration, click loop và listener;
  có thể tách khi file bắt đầu cản trở thay đổi.
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

1. Đồng bộ test với default tắt của `ENABLE_SCRIPT_INJECTION` và đưa
   `pytest tests -q` về xanh.
2. Cấu hình root pytest chỉ collect `tests/`.
3. Mở rộng architecture test sang package con và `runner/`.
4. Hoàn thiện validation tại action loader boundary.
5. Chỉ sau đó mới cân nhắc research helpers, tách test lớn hoặc `BlockerConfig`.

## Nguyên tắc khi refactor

- Giữ dependency rule trong `docs/ADR_bot.md`.
- Sau mỗi bước, chạy `uv run --with pytest pytest tests -q`.
- Ưu tiên baseline xanh và input boundary chặt hơn việc chia file theo line count.
- Mỗi thay đổi nên nhỏ và rollback độc lập được.
