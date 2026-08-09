# Refactor Review

## Kết luận

Structure hiện tại hợp lý hơn cho một bot local: khoảng **7.5/10**. Ranh giới
`core / actions / control_events / flows / runner` còn rõ, dependency direction
vẫn sạch, auto-map đã có support package riêng và runner entrypoint không còn là
controller monolith.

Chưa cần đổi kiến trúc tổng thể. Vấn đề hiện tại không phải thiếu layer lớn, mà
là một vài module còn đang gom trách nhiệm runtime cụ thể: action loader/runner
và một số flow còn thể hiện state bằng nested loop.

Bot chính hiện chạy xanh khi scope test vào `tests/`:

```shell
uv run --with pytest pytest tests -q
# 119 passed, 12 subtests passed
```

Full pytest collection từ repo root vẫn fail ở `ref_cv/tests` vì `ref_cv/` là
project tham khảo độc lập và test trong đó import theo local module `vision`.

## Structure hiện tại

```text
tools/hauntedroom/
├── core/                 # foundational runtime, CLI, template, vision
├── actions/              # JSON action loader/runner
├── control_events/       # blocker/new-tab handling
├── runner/               # hotkey standby, command specs, dev reload
├── flows/                # hotkey business flows
│   ├── automap.py        # auto-map coordinator/public API/state
│   ├── start_auto.py     # Shift+3 composite flow/wrapper
│   ├── automap_support/  # auto-map detectors/actions/phase helpers
│   ├── click_loop.py
│   └── research.py
└── settings.py           # source-level runtime switches
```

`hauntedroom_runner.py` vẫn là composition root nhưng hiện chỉ giữ browser
bootstrap, CLI composition và shutdown. Hotkey standby, dev reload và command
mapping nằm trong `tools/hauntedroom/runner/`; wrapper `Shift+3` nằm đúng layer
flow tại `tools/hauntedroom/flows/start_auto.py`.

## Các issue đang lớn lên

| Ưu tiên | Điểm nóng | Vị trí | Kích thước hiện tại | Vấn đề chính |
| --- | --- | --- | ---: | --- |
| Cao | `run_actions` | `tools/hauntedroom/actions/runner.py:96` | 271 dòng | Dispatch action, retry policy, timeout, logging, template wait và click-repeat nằm chung |
| Cao | `load_actions` | `tools/hauntedroom/actions/loader.py:37` | 154 dòng | Parse/validate/resolve path/mutate raw dict cùng một pass; thêm action type sẽ tiếp tục phình |
| Trung bình | `run_research_flow` | `tools/hauntedroom/flows/research.py:23` | 120 dòng | State `available -> active -> available` nằm trong nested loop, khó mở rộng thêm trạng thái |
| Trung bình | `clear_blockers` | `tools/hauntedroom/control_events/blockers.py:21` | 81 dòng, 12 tham số | Signature dài; timeout semantics là inactivity timeout nhưng tên vẫn dễ hiểu nhầm là total timeout |
| Thấp | `FLOW_COMMANDS` và resolver | `tools/hauntedroom/runner/commands.py` | 172 dòng | Command spec đã gom switch-case lặp, nhưng test nên tách thêm theo reload/standby/start-auto nếu file test tiếp tục lớn |
| Thấp | `wait_for_template` | `tools/hauntedroom/actions/runner.py:31` | 63 dòng, 11 tham số | Logic còn ổn, nhưng nên gom config nếu tiếp tục thêm option |

## Line-count audit

Line count không tự động đồng nghĩa over-responsibility. Vì test file lớn và
runtime file lớn có ý nghĩa khác nhau, audit được tách thành hai phần.

### Test files

Command:

```bash
find ./tests -type f -name '*.py' \
  ! -path '*/__pycache__/*' \
  -exec wc -l {} + |
  sort -nr |
  awk '$1 > 100 && $2 != "total" { printf "%4d %s\n", $1, $2 }' |
  head -10
```

Snapshot:

```text
 573 ./tests/automap/test_boss.py
 398 ./tests/runner/test_standby_controller.py
 330 ./tests/hero_select/test_hero_fallback.py
 316 ./tests/automap/test_map_end.py
 267 ./tests/actions/test_runner.py
 249 ./tests/hero_select/test_hero_select.py
 237 ./tests/automap/test_level_up.py
 226 ./tests/runner/test_start_automap_loop.py
 159 ./tests/control_events/test_new_tab_blocker.py
 142 ./tests/test_hauntedroom_vision.py
```

Audit:

- Test lớn chủ yếu phản ánh nhiều scenario fixture-driven, không phải lỗi
  architecture runtime.
- `test_boss.py` đang gom detector, boss handoff, spell/pet action và final boss
  behavior; nếu review chậm, nên split theo `boss_detector`, `boss_action` và
  `boss_flow`.
- `test_standby_controller.py` đã bám theo package `runner/` mới, nhưng hiện vẫn
  gom reload, standby lifecycle, pause/resume và click-loop behavior trong một
  test module. Nếu review chậm, nên split thành `test_reload.py`,
  `test_standby.py` và `test_commands.py`.
- Các test automap/hero lớn còn lại có thể giữ nếu fixture setup dùng chung giúp
  đọc dễ hơn; chỉ split khi setup chung bắt đầu che intent của từng scenario.

### Non-test files

Command:

```bash
find . -type f -name '*.py' \
  ! -path './.git/*' \
  ! -path './.venv/*' \
  ! -path './__pycache__/*' \
  ! -path '*/__pycache__/*' \
  ! -path './tests/*' \
  ! -path './ref_cv/tests/*' \
  -exec wc -l {} + |
  sort -nr |
  awk '$1 > 100 && $2 != "total" { printf "%4d %s\n", $1, $2 }' |
  head -15
```

Snapshot:

```text
 440 ./tools/hauntedroom/flows/automap.py
 366 ./tools/hauntedroom/actions/runner.py
 302 ./tools/hauntedroom/flows/automap_support/boss_detector.py
 271 ./tools/hauntedroom/flows/automap_support/hero_levelup.py
 259 ./tools/hauntedroom/core/runtime.py
 223 ./tools/hauntedroom/flows/automap_support/gear_action.py
 190 ./tools/hauntedroom/actions/loader.py
 174 ./tools/hauntedroom/flows/automap_support/map_completion.py
 172 ./tools/hauntedroom/runner/commands.py
 166 ./tools/debug_template_match.py
 162 ./tools/hauntedroom/core/template.py
 150 ./tools/hauntedroom/flows/automap_support/upgrade_action.py
 149 ./tools/hauntedroom/runner/standby.py
 146 ./tools/hauntedroom/flows/automap_support/boss_action.py
 143 ./ref_cv/vision.py
 142 ./tools/hauntedroom/flows/research.py
```

Audit:

- `tools/hauntedroom_runner.py`: không còn là over-responsibility chính; file
  hiện khoảng 86 dòng và chỉ giữ composition root/browser lifecycle.
- `tools/hauntedroom/runner/commands.py`: command mapping đã data-driven thay vì
  switch-case lặp; kích thước chủ yếu do mỗi hotkey có resolver riêng. Chưa cần
  abstraction sâu hơn nếu số hotkey vẫn nhỏ.
- `tools/hauntedroom/runner/standby.py`: standby loop hiện cohesive hơn: hotkey
  queue, control command và lifecycle task. Nên theo dõi nếu thêm nhiều control
  command mới.
- `tools/hauntedroom/actions/runner.py`: over-responsibility rõ. `run_actions`
  gom dispatch, retry/timeout policy, template matching orchestration, logging và
  click-repeat behavior.
- `tools/hauntedroom/actions/loader.py`: đã hiện trong non-test top 15 và là issue
  architecture liên quan trực tiếp với runner vì contract vẫn là raw dict.
- `tools/hauntedroom/flows/automap.py`: dài nhưng chưa phải over-responsibility
  nghiêm trọng. Vai trò hiện là coordinator/state/public API; phase logic đã tách
  sang support modules.
- `boss_detector.py`, `hero_levelup.py`, `gear_action.py`, `map_completion.py`:
  dài chủ yếu vì CV heuristic và fixture-driven behavior; vẫn cohesive theo
  domain nhỏ.
- `tools/hauntedroom/core/runtime.py`: foundational helper hơi lớn nhưng chưa
  vượt responsibility rõ ràng; chỉ nên tách khi có nhóm API tự nhiên như
  screenshot persistence hoặc hotkey/click logging.
- `tools/hauntedroom/core/template.py`: foundational template helper, hiện vẫn
  cohesive.
- `upgrade_action.py` và `boss_action.py`: phase action modules vừa phải; chưa có
  dấu hiệu gom responsibility ngoài auto-map concern của chúng.
- `tools/hauntedroom/flows/research.py`: không quá dài nhưng state đang nằm trong
  nested loop; đây là issue maintainability nếu thêm trạng thái research mới.
- `ref_cv/vision.py`: thuộc project tham khảo `ref_cv/`, không tính là architecture
  runtime chính của bot.
- `tools/debug_template_match.py`: CLI debug độc lập, line count không ảnh hưởng
  nhiều tới architecture runtime.

## Đang làm tốt

- Dependency direction vẫn đúng theo ADR: `core` không import feature; `actions`
  và `flows` không import lẫn nhau; `runner` là layer nối hotkey với flow.
- `automap.py` đã đóng vai trò coordinator thay vì chứa toàn bộ phase logic.
- `automap_support/` đã tách các nhóm concern thực tế: map completion, upgrade,
  hero level-up, boss, detector và gear placement.
- `hauntedroom_runner.py` đã trở lại đúng vai trò composition root; runner
  runtime nằm trong `hauntedroom/runner/`.
- Flow command được gom vào `FLOW_COMMANDS`, nên thêm hotkey mới không còn phải
  sửa nhiều switch-case trong cùng controller.
- Test không còn là một file monolith; hiện đã chia theo `actions/`, `automap/`,
  `control_events/`, `hero_select/`, `research/`, `runner/`.
- README hiện khớp default `delay_ms = 400`, không còn drift cũ về `500`.
- `settings.py` đã gom các source-level switch như hero fallback screenshot,
  script injection và boss exit behavior.

## Các điểm cần cải thiện

### 1. Raw `dict` vẫn là contract giữa loader và runner

`load_actions` vẫn trả `list[dict]` và thêm internal key như `_template_path`,
`_blocker_paths`, `_until_template_path`. `run_actions` giả định các key này tồn
tại.

Validation đã tốt hơn trước, nhưng contract vẫn yếu:

- type checker không giúp nhiều
- loader mutate raw dictionary vừa parse từ JSON
- executor vẫn phải đọc default và ép kiểu ở nhiều nhánh
- thêm action type vẫn cần sửa cả validate branch và execute branch lớn

Nên chuyển sang dataclass hoặc discriminated union:

- `ClickAction`
- `ClickTemplateAction`
- `WaitAction`
- `ClearBlockersAction`

Nếu muốn bước nhỏ hơn, dùng `TypedDict` trước rồi refactor executor sau.

### 2. Validation đã cải thiện nhưng chưa normalize triệt để

Không còn đúng khi nói `load_actions` chỉ kiểm tra `wait.ms`. Hiện loader đã
validate threshold, timing âm, scales, priority, click position, click count và
boolean field.

Phần còn thiếu:

- `wait.ms` chưa chặn âm/sai kiểu rõ ràng.
- `click.x`, `click.y` chỉ được yêu cầu tồn tại, chưa normalize thành int trong
  loader.
- `button` chưa bị giới hạn vào các giá trị Playwright hợp lệ.
- runner vẫn phải gọi `int()`/`float()` thay vì nhận object đã chuẩn hóa.

### 3. Architecture test chưa quét sâu package con

`tests/test_hauntedroom_architecture.py` đang bảo vệ rule chính và pass. Nhưng
rule cho `flows` chỉ quét `flows/*.py`, chưa quét recursive trong
`flows/automap_support/*.py`, và chưa khóa dependency direction cho package
`runner/` mới.

Import thực tế hiện vẫn sạch, nhưng test chưa khóa đầy đủ boundary đã ghi trong
ADR. Nên đổi sang quét recursive, cho phép import ngang trong cùng feature
package `hauntedroom.flows.automap_support`, và assert `runner` chỉ phụ thuộc
`core`, `actions`, `flows`, `control_events`, `settings` hoặc sibling runner
modules.

### 4. Packaging/test discovery còn nhập nhằng

`pyproject.toml` đặt `package = false`, test tự thêm `tools` vào `sys.path`.
Điều này vẫn chấp nhận được nếu bot chỉ chạy local.

Điểm gây nhiễu thực tế là `ref_cv/` có `pyproject.toml`, lock file và test riêng.
Chạy pytest từ repo root sẽ collect cả `ref_cv/tests` và fail import. Nên chọn
một trong ba hướng:

- cấu hình pytest chỉ collect `tests/`
- chuyển `ref_cv/` sang `archive/` hoặc repo riêng
- làm `ref_cv/` thành project con có test command riêng, không lẫn với bot chính

### 5. Flow vẫn coupling trực tiếp với infrastructure

Các flow gọi trực tiếp Playwright page, OpenCV helper và `print`. Với bot local,
đây là trade-off ổn. Chỉ nên thêm abstraction mỏng khi có nhu cầu thật như replay
screenshot, simulator hoặc integration test ổn định hơn.

Nếu cần, abstraction nên nhỏ theo behavior:

- capture frame
- click/wait
- log
- save diagnostic screenshot

Chưa nên dựng Clean Architecture đầy đủ.

## Auto-map hiện tại

Auto-map không còn là monolith nguyên khối. `run_automap_flow` chỉ build
`AutomapConfig` rồi chạy `AutomapFlow`; coordinator giữ template loading, mutable
state, handler priority và public API.

Các phase chính đang nằm trong:

- `map_completion.py`: map end, win reward, reward list title, home detection.
- `upgrade_action.py`: level-spin interrupt, level-up confirm, build menu.
- `hero_action.py`: mở/chọn hero level-up option.
- `hero_levelup.py`: detect và rank hero option.
- `boss_flow.py`, `boss_action.py`, `boss_detector.py`: boss handoff/pet/detection.
- `gear_action.py`: initial gear placement.

Phần auto-map có thể giữ như hiện tại. Nếu tiếp tục thêm phase hoặc state mới,
bước refactor hợp lý nhất là tạo context/runtime adapter nhỏ để giảm số callable
dependency truyền qua helper, không phải tạo handler registry tổng quát.

## Thứ tự refactor đề xuất

1. Chuyển action raw dict thành typed object hoặc `TypedDict`; sau đó chia
   executor theo action type.
2. Cập nhật architecture test để quét recursive package con.
3. Cấu hình test discovery để root pytest không collect nhầm `ref_cv/tests`.
4. Tách `run_research_flow` thành hai phase nhỏ: available và active.
5. Đổi `clear_blockers` sang `BlockerConfig` và document/rename timeout theo
   inactivity semantics.

## Không còn là issue chính

- Không cần chia test monolith nữa; việc này đã xong ở mức đủ tốt.
- README không còn sai default `delay_ms`.
- Validation action không còn quá sơ sài như snapshot cũ, chỉ còn thiếu normalize
  typed boundary.
- Auto-map không cần refactor lớn ngay; coordinator khoảng 440 dòng nhưng phase logic đã
  được tách theo feature và hiện chưa phải điểm nóng nhất.
- Entrypoint/controller mini đã được xử lý: `hauntedroom_runner.py` chỉ còn
  browser bootstrap; standby/reload/command nằm trong `tools/hauntedroom/runner/`,
  còn start-auto nằm trong `tools/hauntedroom/flows/start_auto.py`.

## Nguyên tắc khi refactor

- Giữ dependency rule trong `docs/ADR_bot.md`.
- Refactor theo behavior hiện tại và giữ `uv run --with pytest pytest tests -q`
  xanh sau từng bước.
- Không tạo registry hoặc abstraction tổng quát khi mới chỉ có một consumer.
- Ưu tiên typed boundary và state rõ ràng hơn là chỉ chuyển code sang nhiều file.
- Mỗi bước nên đủ nhỏ để review và rollback độc lập.
