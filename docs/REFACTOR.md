# Refactor Review

## Kết luận

Structure hiện tại vẫn hợp lý cho một bot local: khoảng **7/10**. Ranh giới
`core / actions / control_events / flows` còn rõ, dependency direction vẫn sạch,
auto-map đã có support package riêng và test theo feature đã gọn hơn trước.

Chưa cần đổi kiến trúc tổng thể. Vấn đề hiện tại không phải thiếu layer lớn, mà
là một vài module đang trở thành điểm gom trách nhiệm: standby controller,
action loader/runner và một số flow còn thể hiện state bằng nested loop.

Bot chính hiện chạy xanh khi scope test vào `tests/`:

```shell
uv run --with pytest pytest tests -q
# 118 passed, 12 subtests passed
```

Full pytest collection từ repo root vẫn fail ở `ref_cv/tests` vì `ref_cv/` là
project tham khảo độc lập và test trong đó import theo local module `vision`.

## Structure hiện tại

```text
tools/hauntedroom/
├── core/                 # foundational runtime, CLI, template, vision
├── actions/              # JSON action loader/runner
├── control_events/       # blocker/new-tab handling
├── flows/                # hotkey business flows
│   ├── automap.py        # auto-map coordinator/public API/state
│   ├── automap_support/  # auto-map detectors/actions/phase helpers
│   ├── click_loop.py
│   └── research.py
└── settings.py           # source-level runtime switches
```

`hauntedroom_runner.py` vẫn là composition root: browser bootstrap, hotkey
controller, dev reload và flow routing đều bắt đầu tại đây. Điều này đúng chỗ,
nhưng file đang tăng nhanh.

## Các issue đang lớn lên

| Ưu tiên | Điểm nóng | Vị trí | Kích thước hiện tại | Vấn đề chính |
| --- | --- | --- | ---: | --- |
| Cao | `run_standby_controller` | `tools/hauntedroom_runner.py:208` | 162 dòng | Command routing, pause/resume, lifecycle task và dev reload dính vào cùng một loop |
| Cao | `run_actions` | `tools/hauntedroom/actions/runner.py:96` | 271 dòng | Dispatch action, retry policy, timeout, logging, template wait và click-repeat nằm chung |
| Cao | `load_actions` | `tools/hauntedroom/actions/loader.py:37` | 154 dòng | Parse/validate/resolve path/mutate raw dict cùng một pass; thêm action type sẽ tiếp tục phình |
| Trung bình | `run_research_flow` | `tools/hauntedroom/flows/research.py:23` | 120 dòng | State `available -> active -> available` nằm trong nested loop, khó mở rộng thêm trạng thái |
| Trung bình | `clear_blockers` | `tools/hauntedroom/control_events/blockers.py:21` | 81 dòng, 12 tham số | Signature dài; timeout semantics là inactivity timeout nhưng tên vẫn dễ hiểu nhầm là total timeout |
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
 345 ./tests/runner/test_standby_controller.py
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
- `test_standby_controller.py` mirror đúng vấn đề của production controller:
  hotkey, reload, lifecycle, pause/resume và click-loop cùng nằm trong một test
  module. Khi tách controller production, test này cũng nên tách theo behavior.
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
 452 ./tools/hauntedroom/flows/automap.py
 424 ./tools/hauntedroom_runner.py
 366 ./tools/hauntedroom/actions/runner.py
 302 ./tools/hauntedroom/flows/automap_support/boss_detector.py
 271 ./tools/hauntedroom/flows/automap_support/hero_levelup.py
 259 ./tools/hauntedroom/core/runtime.py
 223 ./tools/hauntedroom/flows/automap_support/gear_action.py
 190 ./tools/hauntedroom/actions/loader.py
 174 ./tools/hauntedroom/flows/automap_support/map_completion.py
 166 ./tools/debug_template_match.py
 162 ./tools/hauntedroom/core/template.py
 150 ./tools/hauntedroom/flows/automap_support/upgrade_action.py
 146 ./tools/hauntedroom/flows/automap_support/boss_action.py
 143 ./ref_cv/vision.py
 142 ./tools/hauntedroom/flows/research.py
```

Audit:

- `tools/hauntedroom_runner.py`: over-responsibility rõ nhất. File gom bootstrap,
  hotkey routing, flow lifecycle, pause/resume, dev reload và command đặc biệt.
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
  và `flows` không import lẫn nhau.
- `automap.py` đã đóng vai trò coordinator thay vì chứa toàn bộ phase logic.
- `automap_support/` đã tách các nhóm concern thực tế: map completion, upgrade,
  hero level-up, boss, detector và gear placement.
- Test không còn là một file monolith; hiện đã chia theo `actions/`, `automap/`,
  `control_events/`, `hero_select/`, `research/`, `runner/`.
- README hiện khớp default `delay_ms = 400`, không còn drift cũ về `500`.
- `settings.py` đã gom các source-level switch như hero fallback screenshot,
  script injection và boss exit behavior.

## Các điểm cần cải thiện

### 1. Entrypoint đang thành controller framework mini

`hauntedroom_runner.py` vẫn đúng vai trò composition root, nhưng
`run_standby_controller` đã thành nơi gom nhiều policy:

- mapping hotkey sang flow
- stop/pause/resume
- task completion và exception handling
- dev reload từng nhóm module
- reload action JSON theo command
- special command như screenshot

Nên tách tối thiểu thành các helper nhỏ, chưa cần class framework:

- `resolve_command(command, dev_reload, actions_path)`
- `start_flow(command, page, actions, resolved_flow, stop_event, debug)`
- `handle_control_command(command, current_state)`

Mục tiêu là giảm cognitive load của loop chính, không phải tạo abstraction tổng
quát cho mọi runner.

### 2. Raw `dict` vẫn là contract giữa loader và runner

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

### 3. Validation đã cải thiện nhưng chưa normalize triệt để

Không còn đúng khi nói `load_actions` chỉ kiểm tra `wait.ms`. Hiện loader đã
validate threshold, timing âm, scales, priority, click position, click count và
boolean field.

Phần còn thiếu:

- `wait.ms` chưa chặn âm/sai kiểu rõ ràng.
- `click.x`, `click.y` chỉ được yêu cầu tồn tại, chưa normalize thành int trong
  loader.
- `button` chưa bị giới hạn vào các giá trị Playwright hợp lệ.
- runner vẫn phải gọi `int()`/`float()` thay vì nhận object đã chuẩn hóa.

### 4. Architecture test chưa quét sâu package con

`tests/test_hauntedroom_architecture.py` đang bảo vệ rule chính và pass. Nhưng
rule cho `flows` chỉ quét `flows/*.py`, chưa quét recursive trong
`flows/automap_support/*.py`.

Import thực tế hiện vẫn sạch, nhưng test chưa khóa đầy đủ boundary đã ghi trong
ADR. Nên đổi sang quét recursive và cho phép import ngang trong cùng feature
package `hauntedroom.flows.automap_support`.

### 5. Packaging/test discovery còn nhập nhằng

`pyproject.toml` đặt `package = false`, test tự thêm `tools` vào `sys.path`.
Điều này vẫn chấp nhận được nếu bot chỉ chạy local.

Điểm gây nhiễu thực tế là `ref_cv/` có `pyproject.toml`, lock file và test riêng.
Chạy pytest từ repo root sẽ collect cả `ref_cv/tests` và fail import. Nên chọn
một trong ba hướng:

- cấu hình pytest chỉ collect `tests/`
- chuyển `ref_cv/` sang `archive/` hoặc repo riêng
- làm `ref_cv/` thành project con có test command riêng, không lẫn với bot chính

### 6. Flow vẫn coupling trực tiếp với infrastructure

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

1. Tách bớt `run_standby_controller` để command routing và task lifecycle rõ hơn.
2. Chuyển action raw dict thành typed object hoặc `TypedDict`; sau đó chia
   executor theo action type.
3. Cập nhật architecture test để quét recursive package con.
4. Cấu hình test discovery để root pytest không collect nhầm `ref_cv/tests`.
5. Tách `run_research_flow` thành hai phase nhỏ: available và active.
6. Đổi `clear_blockers` sang `BlockerConfig` và document/rename timeout theo
   inactivity semantics.

## Không còn là issue chính

- Không cần chia test monolith nữa; việc này đã xong ở mức đủ tốt.
- README không còn sai default `delay_ms`.
- Validation action không còn quá sơ sài như snapshot cũ, chỉ còn thiếu normalize
  typed boundary.
- Auto-map không cần refactor lớn ngay; coordinator 452 dòng nhưng phase logic đã
  được tách theo feature và hiện chưa phải điểm nóng nhất.

## Nguyên tắc khi refactor

- Giữ dependency rule trong `docs/ADR_bot.md`.
- Refactor theo behavior hiện tại và giữ `uv run --with pytest pytest tests -q`
  xanh sau từng bước.
- Không tạo registry hoặc abstraction tổng quát khi mới chỉ có một consumer.
- Ưu tiên typed boundary và state rõ ràng hơn là chỉ chuyển code sang nhiều file.
- Mỗi bước nên đủ nhỏ để review và rollback độc lập.
