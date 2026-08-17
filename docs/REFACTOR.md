# Refactor Review

Lần review gần nhất: 2026-08-15

## Kết luận

Structure hiện tại vẫn hợp lý cho một bot local: khoảng **7/10**. Ranh giới
`core / actions / control_events / flows / runner` còn khá rõ, dependency
direction về cơ bản vẫn đúng ADR, và `hauntedroom_runner.py` đã về đúng vai trò
composition root.

Baseline full suite chưa xanh: còn một module test import hai constant cũ từ
`hauntedroom.flows.automap` sau đợt tách owner sang `automap_support/`. Các flow
train, EXP available và hero breakthrough đã nằm đúng trong package `flows/`,
được nối qua command resolver và có test riêng.

Command hiện tại:

```shell
uv run --with pytest pytest tests -q
```

Kết quả hiện tại:

```text
1 collection error
```

Lỗi còn lại nằm ở `tests/automap/test_level_up.py`: module này import
`LV_SPIN_CLICK_OFFSET_X` và `UPGRADE_CONFIRM_CLICK` từ
`hauntedroom.flows.automap`, nhưng owner hiện tại là
`hauntedroom.flows.automap_support.upgrade_action`.

Trước khi refactor thêm, nên restore test/code contract để có baseline xanh.

## Structure hiện tại

```text
tools/hauntedroom/
├── core/                 # foundational runtime, CLI, template, vision
├── actions/              # JSON action loader/runner + typed action models
├── control_events/       # blocker/new-tab handling
├── runner/               # hotkey standby, command specs, dev reload
├── flows/                # hotkey business flows
│   ├── automap.py        # auto-map coordinator/public API/state
│   ├── start_auto.py     # Shift+3 composite flow/wrapper
│   ├── automap_support/  # auto-map detectors/actions/phase helpers
│   ├── train.py          # Shift+4 train + handoff sang auto-map
│   ├── exp_available.py  # Shift+5 EXP detector/click loop
│   ├── hero_up_available.py # Shift+6 breakthrough detector/click loop
│   ├── click_loop.py
│   └── research.py
└── settings.py           # source-level runtime switches
```

`tools/hauntedroom_runner.py` hiện khoảng 80 dòng và chỉ giữ browser bootstrap,
CLI composition và shutdown. Hotkey standby, dev reload và command mapping nằm
trong `tools/hauntedroom/runner/`. Wrapper `Shift+3` nằm tại
`tools/hauntedroom/flows/start_auto.py`.

## Snapshot line-count hiện tại

Runtime/non-test files trên 100 dòng:

```text
 515 ./tools/hauntedroom/flows/automap.py
 417 ./tools/hauntedroom/flows/automap_support/map_completion.py
 403 ./tools/hauntedroom/actions/runner.py
 302 ./tools/hauntedroom/flows/automap_support/boss_detector.py
 299 ./tools/hauntedroom/actions/loader.py
 250 ./tools/hauntedroom/flows/automap_support/hero_levelup_vision.py
 259 ./tools/hauntedroom/core/runtime.py
 223 ./tools/hauntedroom/flows/automap_support/gear_action.py
 211 ./tools/hauntedroom/runner/commands.py
 203 ./tools/hauntedroom/flows/train.py
 184 ./tools/hauntedroom/flows/automap_support/train_select.py
 166 ./tools/debug_template_match.py
 162 ./tools/hauntedroom/core/template.py
 158 ./tools/hauntedroom/runner/standby.py
 157 ./tools/hauntedroom/runner/reload.py
 150 ./tools/hauntedroom/flows/automap_support/upgrade_action.py
 149 ./tools/hauntedroom/flows/hero_up_available.py
 145 ./tools/hauntedroom/flows/automap_support/boss_action.py
 142 ./tools/hauntedroom/flows/research.py
 131 ./tools/hauntedroom/flows/exp_available.py
 127 ./tools/hauntedroom/control_events/new_tab_blocker.py
 110 ./tools/hauntedroom/flows/automap_support/detectors.py
 255 ./tools/hauntedroom/flows/automap_support/hero_action.py
 101 ./tools/hauntedroom/control_events/blockers.py
```

Test files trên 100 dòng:

```text
 573 ./tests/automap/test_boss.py
 563 ./tests/automap/test_map_end.py
 458 ./tests/runner/test_standby_controller.py
 333 ./tests/hero_select/test_hero_select.py
 332 ./tests/hero_select/test_hero_fallback.py
 274 ./tests/actions/test_runner.py
 237 ./tests/automap/test_level_up.py
 202 ./tests/runner/test_start_automap_loop.py
 181 ./tests/special_flow/test_hero_up_available_flow.py
 161 ./tests/special_flow/test_exp_available_flow.py
 159 ./tests/control_events/test_new_tab_blocker.py
 142 ./tests/test_hauntedroom_vision.py
 121 ./tests/runner/test_train_flow.py
 120 ./tests/automap/test_gear.py
 105 ./tests/automap/test_build.py
```

Line count không tự động đồng nghĩa over-responsibility. Test lớn chủ yếu là
fixture/scenario-driven. Runtime file lớn đang cần theo dõi nhất là
`automap.py`, `automap_support/map_completion.py`, `actions/runner.py` và
`actions/loader.py`; các special flow mới vẫn là module độc lập, kích thước vừa.

## Đang làm tốt

- Dependency direction vẫn sạch ở mức chính: `core` không import feature;
  `actions` không depend vào `flows`; `runner` là layer nối hotkey với flow.
- `automap.py` hiện là coordinator/state/public API, không còn chứa toàn bộ
  phase logic.
- `automap_support/` đã tách các concern rõ: map completion, upgrade, hero
  level-up, boss, detector, gear placement và train selection.
- `actions/models.py` đã tạo typed boundary cho action JSON; runner không còn
  chạy trên raw dict làm contract chính.
- `hauntedroom_runner.py` không còn là controller monolith.
- Command mapping đã được gom qua command spec/default wiring, dễ thêm hotkey
  mới mà không phải sửa một switch-case lớn.

## Drift và issue hiện tại

### 1. Một test contract còn drift sau khi tách auto-map support modules

Các constants đã được chuyển sang module đúng concern:

- `AUTOMAP_POLL_MS`, `LV_SPIN_CLICK_OFFSET_X`, `UPGRADE_CONFIRM_CLICK` nằm ở
  `tools/hauntedroom/flows/automap_support/upgrade_action.py`.
- `MAP_END_CHECK_INTERVAL_SEC`, `WIN_REWARD_*`,
  `REWARD_LIST_TITLE_TEMPLATE_THRESHOLD` nằm ở
  `tools/hauntedroom/flows/automap_support/map_completion.py`.
- `HERO_LEVELUP_OPEN_CLICK`, `HERO_FALLBACK_SCREENSHOT_DIR` nằm ở
  `tools/hauntedroom/flows/automap_support/hero_action.py`.

Phần lớn test đã chuyển sang module owner hoặc dùng symbol được re-export có chủ
đích. Riêng `tests/automap/test_level_up.py` vẫn import
`LV_SPIN_CLICK_OFFSET_X` và `UPGRADE_CONFIRM_CLICK` từ `automap.py`, nên
collection fail. Cần quyết định đây là public compatibility hay internal test
drift:

- Nếu các constants này là public API: re-export có chủ đích trong `automap.py`.
- Nếu chỉ là internal implementation detail: sửa test import trực tiếp từ module
  owner hiện tại.

Recommendation: sửa test import theo module owner hiện tại. Re-export constants
từ `automap.py` sẽ làm coordinator tiếp tục thành dumping ground.

### 2. Architecture test chưa khóa hết boundary hiện tại

`tests/test_hauntedroom_architecture.py` đang quét bằng `glob("*.py")`, nên chưa
quét recursive các package con như `flows/automap_support/*.py`. Test cũng chưa
có rule riêng cho package `runner/`.

Import thực tế hiện có vẻ sạch, nhưng guardrail chưa bao phủ hết structure đã
được refactor.

### 3. Action loader đã typed, nhưng validation chưa normalize hết

`load_actions` hiện trả `list[Action]`, gồm:

- `ClickAction`
- `ClickTemplateAction`
- `WaitAction`
- `ClearBlockersAction`

Loader đã validate threshold, timing âm, scales, priority, click position,
click count và boolean field. Tuy nhiên còn thiếu:

- `wait.ms` chưa chặn âm/sai kiểu rõ ràng.
- `click.x`, `click.y` mới `int()` lúc load, nhưng error message sai kiểu chưa
  thân thiện.
- `button` chưa giới hạn vào các giá trị Playwright hợp lệ.
- Runner vẫn còn vài `int()`/`float()` fallback, nghĩa là typed boundary chưa
  đóng kín hoàn toàn.

### 4. `run_research_flow` vẫn là nested state loop

`tools/hauntedroom/flows/research.py` không quá dài, nhưng state
`available -> active -> available` đang nằm trong nested loop. Nếu thêm state
research mới, flow này sẽ khó mở rộng và khó test hơn.

Nên tách thành các helper nhỏ như `wait_for_research_available`,
`drain_active_research`, và giữ `run_research_flow` làm coordinator.

### 5. `clear_blockers` signature và timeout semantics cần dọn lại

`tools/hauntedroom/control_events/blockers.py` vẫn là điểm cần theo dõi:
signature dài và timeout là inactivity timeout, không phải total timeout. Nếu
thêm option nữa, nên gom vào `BlockerConfig` và đặt tên/docstring rõ hơn.

### 6. Test discovery/package boundary còn nhập nhằng

`pyproject.toml` đặt `package = false`, test tự thêm `tools` vào `sys.path`.
Điều này chấp nhận được cho bot local.

Nhưng repo có `ref_cv/` là project tham khảo độc lập, cũng có `pyproject.toml`
và test riêng. Sau khi fix collection của `tests/`, nên thêm config pytest để
root pytest chỉ collect `tests/`, hoặc tách/di chuyển `ref_cv/` rõ hơn.

## Auto-map hiện tại

Auto-map chưa cần refactor lớn tiếp. `AutomapFlow` giữ template loading, mutable
state, handler priority và public API. Phase logic nằm trong:

- `map_completion.py`: map end, win reward, reward list title và home detection.
- `map_first_win.py`: daily-first-win prompt và checkbox confirmation.
- `upgrade_action.py`: level spin, level-up confirm, build menu.
- `hero_action.py`: business priority, mở/chọn/click hero level-up option.
- `hero_levelup_vision.py`: sở hữu template/calibration và trả lời từng query về
  card, màu, template match; action điều khiển thứ tự và short-circuit.
- `boss_flow.py`, `boss_action.py`, `boss_detector.py`: boss handoff/pet/detect.
- `gear_action.py`: initial gear placement.

Nếu tiếp tục thêm phase/state mới, bước hợp lý là tạo context/runtime adapter nhỏ
để giảm số dependency callable truyền qua helper. Chưa nên tạo registry tổng quát
hay Clean Architecture đầy đủ.

## Next step đề xuất

1. **Restore test baseline.** Sửa hai import còn lại trong
   `tests/automap/test_level_up.py` sang `automap_support/upgrade_action.py`,
   hoặc re-export có chủ đích nếu muốn giữ public compatibility từ `automap.py`.
   Chạy lại:

   ```shell
   uv run --with pytest pytest tests -q
   ```

2. **Mở rộng architecture guardrail.** Đổi architecture test sang quét recursive
   package con và thêm rule cho `hauntedroom.runner`.

3. **Chốt pytest discovery.** Thêm config để root pytest chỉ collect `tests/`,
   tránh collect nhầm `ref_cv/tests`.

4. **Đóng kín typed action boundary.** Normalize/validate `wait.ms`, `click.x/y`
   và `button` trong loader; giảm ép kiểu trong runner.

5. **Tách `run_research_flow` thành phase helper.** Làm sau khi test baseline đã
   xanh, vì đây là refactor behavior-preserving.

6. **Sau cùng mới xem `clear_blockers` config object.** Đây là cleanup tốt,
   nhưng chưa khẩn cấp bằng test drift và guardrail.

## Không nên làm ngay

- Chưa nên refactor lớn `automap.py`; file dài nhưng cohesive với vai trò
  coordinator.
- Chưa cần tách tiếp các test lớn nếu chúng vẫn đọc được theo scenario.
- Chưa nên thêm abstraction tổng quát cho Playwright/CV/log nếu chưa có consumer
  thứ hai như replay simulator hoặc integration harness.

## Nguyên tắc khi refactor

- Giữ dependency rule trong `docs/ADR_bot.md`.
- Sau mỗi bước, chạy `uv run --with pytest pytest tests -q`.
- Ưu tiên baseline xanh và typed boundary hơn là chỉ chia file.
- Mỗi PR/commit nên nhỏ, rollback được độc lập.
