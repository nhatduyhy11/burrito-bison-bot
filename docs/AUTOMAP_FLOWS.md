# Auto-map flows: `Shift+2` và `Shift+3`

`Shift+2` chạy business core auto-map cho một trận. `Shift+3` không có một
implementation auto-map riêng; nó là wrapper tự vào trận, gọi cùng business
core, chờ cooldown rồi lặp sang map tiếp theo. Tài liệu này là nguồn mô tả chính
cho thứ tự ưu tiên, điều kiện và kết quả của cả hai flow.

| Hành vi | `Shift+2` | `Shift+3` |
|---|---|---|
| Vào room và bắt đầu trận | Người dùng thực hiện trước | Tự chạy prefix action của `Shift+1` |
| Auto-map trong trận | Chạy `run_automap_flow()` một lần | Gọi cùng `run_automap_flow()` trong mỗi loop |
| Hotkey pause khi flow đang chạy | `Shift+1` ngay lập tức; `Shift+2` ở boss kế tiếp; `Shift+3` ở final boss | Giống `Shift+2` |
| Cooldown giữa map | Không | 2 giây |
| Đếm win xuyên nhiều map | Không | Có |
| Handoff đặc biệt ở loop 3 | Không | Có nếu hai loop đầu chưa ghi nhận win |

## Business core dùng chung

Trước khi core bắt đầu, trận đã được khởi động: người dùng làm thủ công khi dùng
`Shift+2`, còn wrapper của `Shift+3` tự chạy các entry action. Core chụp viewport
liên tục, chạy các handler theo priority và chỉ xử lý tình huống đầu tiên match
trong mỗi vòng quét.

Core kết thúc khi:

- map hoàn tất và màn hình home đã sẵn sàng;
- boss vào vùng critical, bot handoff để người dùng xử lý thủ công; hoặc
- người dùng bấm `Shift+0` để dừng mềm và đưa runner về idle.

### Priority loop

```text
capture viewport
      |
      v
1. level-spin interrupt
2. map end (throttle tối đa một lần mỗi 5 giây)
3. initial gear setup
4. boss critical handoff
5. level up
6. build structure
7. hero level-up
      |
      +-- không handler nào match: chờ 600 ms rồi quét lại
      +-- handler đã xử lý: bắt đầu vòng quét mới từ priority 1
```

Priority là contract của flow. Handler ở trên được quyền preempt handler ở dưới;
khi thêm tình huống mới phải xác định rõ vị trí của nó trong danh sách này.

### 1. Level-spin interrupt

- Chỉ tìm `automap/lv_spin.png` trong 25% phía dưới viewport.
- Match ở scale `1.0`, `0.8` hoặc `0.67`, threshold `0.58`.
- Click lệch trái `70 px` so với tâm match.
- Kiểm tra lại ngay sau khi click `lv_up` và trước bước confirm để interrupt
  không bị bỏ lỡ trong lúc chuyển phase.

### 2. Map end

Map-end không kết thúc ngay khi `automap/map_end.png` xuất hiện. Match này chỉ
bắt đầu **win-map completion bridge**: đóng toàn bộ reward/prompt/blocker, xác
nhận home đã thật sự sẵn sàng rồi mới cho `Shift+3` chạy map kế tiếp.

Xem [Map-completion bridge](MAP_COMPLETION_BRIDGE.md) để có call chain, state
machine đầy đủ và review các nhánh retry có thể làm bridge bị stuck.

- Tìm `automap/map_end.png` với threshold `0.90`; phép kiểm tra được throttle
  tối đa một lần mỗi 5 giây.
- Khi match, click để rời battle và chuyển quyền điều khiển sang
  `finish_map_from_home()`.
- Bridge trả `completed=True` chỉ khi `rooms/start_home.png` match threshold
  `0.90`. Việc đã thấy reward hoặc đã tăng win count không đủ để hoàn tất map.
- Nếu bridge bị stop, một wait bị ngắt hoặc daily-first-win không hoàn thành,
  bridge trả `completed=False` và `Shift+3` dừng, không chạy entry action của
  map tiếp theo.

#### Thứ tự kiểm tra của win-map bridge

Mỗi vòng bridge chỉ xử lý nhánh đầu tiên match rồi chụp frame mới. Thứ tự này là
contract vì popup phía trên phải được dọn trước khi kiểm tra home phía dưới.

```mermaid
flowchart TD
    A[map_end match<br/>click rời battle] --> B[Chụp frame]
    B --> C{Win reward lần đầu?}
    C -- Có --> D[Ghi nhận win một lần<br/>click mép trên reward<br/>chờ 2 giây]
    D --> B
    C -- Không --> E{Daily first-win<br/>còn pending và đang hiện?}
    E -- Có --> F[Check/tick checkbox<br/>click decline]
    F --> B
    E -- Không --> G{Reward-list title<br/>đang hiện?}
    G -- Có --> H[Click title<br/>đánh dấu title seen<br/>chờ 2 giây]
    H --> B
    G -- Không --> I{Đã lưu vị trí reward<br/>nhưng chưa từng thấy title?}
    I -- Có --> J[Click lại vị trí reward cũ<br/>chờ 2 giây]
    J --> B
    I -- Không --> K{Title đã từng hiện<br/>và home đã sẵn sàng?}
    K -- Có --> Z[completed = true]
    K -- Không --> L{Đã đủ 2 fallback click?}
    L -- Chưa --> M[Chờ 3 giây<br/>click 220,560]
    M --> B
    L -- Đủ --> N{Có post-map blocker?}
    N -- Có --> O[Click blocker<br/>chờ poll interval]
    O --> B
    N -- Không --> P{Home đã sẵn sàng?}
    P -- Có --> Z
    P -- Không --> Q[Chờ poll interval]
    Q --> B
```

#### Các nhánh reward và fallback

| Tình huống | Hành vi | Ảnh hưởng tới loop kế tiếp |
|---|---|---|
| Thấy `win_reward.png` | Chỉ match đầu tiên được dùng; click ở mép trên template, lưu vị trí click và gọi `on_win()` đúng một lần trong map hiện tại. | Chưa được chạy map mới; bridge tiếp tục dọn reward-list và chờ home. |
| Reward đã click nhưng title chưa xuất hiện | Không scan/ghi nhận reward lần nữa; click lại vị trí reward đã lưu sau mỗi `2 giây`. | Giữ bridge ở map hiện tại cho tới khi title xuất hiện hoặc flow bị stop. |
| `reward_list_title.png` còn hiện | Tìm trong region `(180, 200, 460, 300)`, click top-middle, đánh dấu `title_seen` và kiểm tra lại sau `2 giây`. Nếu popup vẫn còn thì click lại. | Chỉ khi title biến mất mới tiến tới home/fallback check. |
| Không thấy reward và title | Chờ `3 giây` rồi click `(220, 560)`, tối đa hai lần. | Cho UI có cơ hội đóng animation/popup trước khi kiểm tra blocker và home. |
| Có post-map blocker | Sau hai fallback click, tìm các template trong `rooms/blocker/`, click blocker đầu tiên match rồi scan lại. `overlay_newbie.png` dùng vị trí `top_middle`; blocker khác dùng tâm. | Không đánh dấu hoàn tất khi blocker còn che home. |
| Home xuất hiện mà không thấy reward | Vẫn có thể trả `completed=True` sau fallback/blocker cleanup. `win_recorded` giữ `False`, vì vậy win count không tăng. | `Shift+3` vẫn có thể tiếp tục map sau vì completion và win-count là hai contract độc lập. |

#### Daily first-win

Daily-first-win là một sub-flow riêng trong
`flows/automap_support/completion_flow/first_win.py` và chỉ được kiểm tra khi
`first_win_done=False`.

- Nếu checkbox đang unchecked, click checkbox, chờ `1 giây`, chụp lại và chỉ
  tiếp tục khi template checked đã được xác nhận.
- Nếu checkbox đã checked, không toggle lại; click nút decline theo offset từ
  label rồi trả quyền điều khiển cho win-map bridge.
- Nếu chưa nhận diện chắc chắn checked/unchecked, chỉ chờ và chụp lại, không
  click mù.
- Nếu reward xuất hiện mà daily prompt không xuất hiện, bridge đặt
  `first_win_done=True` để không tiếp tục tìm prompt trong process hiện tại.
- `FIRST_WIN_DONE` được giữ qua các map trong cùng process. `win_recorded` là state
  riêng của từng map và chỉ ngăn `on_win()` bị gọi nhiều lần trên cùng reward
  screen.

#### Điều kiện kết thúc và dữ liệu trả về

`MapCompletionOutcome` mang bốn giá trị về `AutomapFlow`:

| Field | Ý nghĩa |
|---|---|
| `completed` | Chỉ `True` khi home template đã match; đây là tín hiệu quyết định `Shift+3` có được nối sang map tiếp theo hay không. |
| `win_recorded` | Reward của map hiện tại đã gọi `on_win()` hay chưa. |
| `total_win` | Tổng win do wrapper `Shift+3` quản lý; không dùng để quyết định completion. |
| `first_win_done` | Không cần xử lý lại daily-first-win trong các map sau của process hiện tại. |

### 3. Initial gear setup

- Gear setup thuộc business core của `Shift+2`; `Shift+3` dùng cùng behavior vì
  gọi lại `run_automap_flow()` cho từng map.
- Flow chỉ thử setup gear sau khi đã unlock qua một upgrade milestone ổn định
  như level-up confirm hoặc chọn hero level-up option.
- Nếu gear chưa unlock, đã thử setup trong map hiện tại, hoặc không thấy gear
  button trên frame hiện tại thì handler no-op và priority loop tiếp tục như
  bình thường.
- Khi thấy gear button lần đầu sau unlock, flow đánh dấu đã attempt trước khi
  tương tác để tránh lặp vô hạn trên frame animation hoặc kéo nhầm control ở
  vòng quét sau.
- Logic nhận diện button, mở menu và kéo gear nằm trong
  `flows/automap_support/gear_action.py`.
- Nếu click gear nhưng menu chưa mở, flow click lại tối đa 3 lần trước khi bỏ
  placement của map hiện tại.

### 4. Manual boss pause control

- Tìm HP bar trước để phát hiện cả mini-boss lẫn final boss cần pause.
- Sau khi HP match, phân loại bằng endpoint cố định `(400, 61, 409, 72)`
  của thanh progress trên cùng: ít nhất `85%` pixel vàng là final boss;
  progress chưa tới endpoint là mini-boss. Classifier không được dùng để
  short-circuit HP detection.
- Nhận diện các cạnh sọc dọc của `boss/boss_hp_bar.png` ở đúng kích thước
  cố định `61x11`, không phụ thuộc màu thanh HP.
- Candidate rõ chỉ hợp lệ khi cả anchor trái và phải của toàn thanh đều match;
  nếu thanh bị chữ/effect che một phần, detector chỉ nhận khi template score
  còn gần ngưỡng và crop grayscale đó có khung tối dạng thanh HP đủ rộng.
- Chỉ tìm thanh HP trong upper battlefield region `(117, 120, 522, 318)`.
  Boss đi từ trên hoặc bên phải sẽ đưa toàn thanh HP qua region này trước
  khi tiến tới cửa. Giới hạn dưới `y2=318` loại HP của cửa ở khu vực phòng.
- Boss và mini-boss có thể dùng cùng hình học thanh HP, nên detector không
  phân loại chúng chỉ từ pixel của thanh. Scope hiện tại chấp nhận
  limitation này; nếu cần phân loại sau này phải thêm stage signal riêng.
- Không xử lý riêng khoảnh khắc thanh máu cuối cạn và chuyển đen; flow chấp nhận
  edge case này và pause trong trạng thái boss thông thường còn thanh máu.
- Trong lúc flow `Shift+2` hoặc `Shift+3` đang chạy, `Shift+2` arm pause một lần ở
  boss bất kỳ; `Shift+3` arm pause một lần ở final boss. Khi boss match policy,
  flow click `rooms/exit_click.png` để pause game,
  rồi pause script bằng `FlowControl`. Flow vẫn sống và chờ manual resume, không
  bấm `exit_confirm`, không handoff và không trở về idle.
- Nếu không match được nút pause game hoặc click lỗi, script vẫn pause theo
  fail-safe và log cảnh báo để người dùng xử lý game thủ công.
- Boss detection log loại boss, vị trí và score một lần khi thanh HP đi vào vùng
  search; log này không lặp theo từng frame trong cùng một lần HP hiện diện. Khi
  không có boss pause policy đang được arm, mini-boss chỉ log/no-op; final boss
  vẫn đi qua nhánh deploy pet nếu pet chưa được deploy trong flow hiện tại.
- Logic nhận diện và action boss hỗ trợ nằm trong
  `flows/automap_support/boss_detector.py` và `boss_action.py`.

#### Final-boss pet activation

```mermaid
flowchart TD
    A[Final boss được nhận diện] --> B{Đã deploy pet<br/>trong flow này?}
    B -- Có --> Z[Bỏ qua pet đến hết flow]
    B -- Chưa --> C{Match pet_ready?}
    C -- Không --> R[Trả về automap] --> A
    C -- Có --> D[Click pet_ready]
    D --> E[Chờ 300 ms<br/>chụp lại viewport]
    E --> F{Match pet_active<br/>score >= 0.90?}
    F -- Chưa --> S{stop_event đã set?}
    S -- Chưa --> D
    S -- Có / Shift+0 --> X[Dừng retry]
    F -- Có --> G[Click pet_active đúng 1 lần]
    G --> H[Popup tự đóng<br/>vùng ready màu vàng biến mất]
    H --> I[final_boss_pet_deployed = True]
    I --> Z
```

Contract: chỉ final boss dùng nhánh này; mini-boss bỏ qua. Hai template là
`boss/pet_ready.png` và `boss/pet_active.png`; cờ deployed thuộc từng auto-map
flow. Retry mở menu không có timeout/max-attempt riêng và chỉ dừng khi summon
thành công hoặc nhận `stop_event`.

### 5. Level up

- Nếu có nhiều match `automap/lv_up.png`, chọn match có `y` lớn nhất.
- Click level-up, chờ `800 ms`, rồi kiểm tra lại `lv_spin`.
- Nếu không có interrupt, click confirm tại `(430, 366)`.

### 6. Build structure

- Nếu có nhiều marker `automap/built.png`, chọn marker có `x` lớn nhất; nếu
  trùng `x`, chọn `y` lớn nhất.
- Sau khi mở menu, duyệt option từ trên xuống và click option đầu tiên có giá
  màu trắng.
- Giá màu đỏ hoặc vàng không được xem là available; nếu không có giá trắng thì
  bỏ qua phase này.

### 7. Hero level-up

Danh sách asset, thứ tự sort, threshold và chi tiết fallback được giữ tại
[`tools/rooms/automap/hero_levelup/README.md`](../tools/rooms/automap/hero_levelup/README.md).

- Nếu popup chưa mở nhưng detector thấy vùng level-up sẵn sàng, click
  `(320, 640)` và poll tối đa 10 lần, mỗi lần `200 ms`.
- Chỉ tìm template hero từ `y=460` trở xuống.
- Tên file trong `rooms/automap/hero_levelup/` bắt đầu bằng số priority; số nhỏ
  hơn được ưu tiên:
  - `00_hero_ascend.png`: viền phát sáng trên đầu card Thần Khí; luôn ưu tiên
    card chứa pattern này và click tại vùng option phía dưới của cùng card.
  - `00_mage_king.png`: Vua Pháp Sư mới, override các priority sau.
  - `01`: Hắc Lữ Bố.
  - `02`: Hanuman.
  - `03`: Cây Giáo Hút Hồn.
  - `04`: Đinh Ba Sấm Sét.
- Template `99_*.png` đánh dấu card nên bỏ qua, ví dụ card tăng sao. Card này bị
  loại khỏi fallback khi còn lựa chọn khác.
- Nếu không template ưu tiên nào match, detector tìm layout 3, 2 hoặc 1 card từ
  panel màu phía dưới. Các khe nhiễu dọc rộng tối đa `3 px` được nối trước khi
  đo chiều rộng để không làm mất card.
- Detector đọc hue từ strip background sạch ở cạnh phải phía dưới mỗi card.
  Card có median hue trong khoảng `130..150` được phân loại là tím.
- Card có median hue trong khoảng `10..25` được phân loại là vàng.
- Matcher luôn kiểm tra ascend trước, sau đó mới tới các template priority còn
  lại. Khi không template nào match, fallback ưu tiên card vàng hợp lệ đầu tiên,
  rồi card tím, cuối cùng mới chọn card đỏ. Log ghi rõ màu fallback đã chọn.
  Card priority `99` chỉ được dùng khi không còn lựa chọn khác.

## `Shift+2`: chạy một map

`Shift+2` gọi thẳng `run_automap_flow()`. Người dùng phải vào map và bấm
`start_battle` trước khi kích hoạt hotkey. Trong lúc chạy, flow nhận cùng bộ
hotkey pause/resume, pause-at-boss, screenshot và stop như `Shift+3`. Khi core
hoàn tất hoặc dừng, runner trở về idle và không tự bắt đầu map tiếp theo.

## `Shift+3`: start-auto loop

Khi runner idle, `Shift+3` bắt đầu chạy nhiều map liên tiếp. Trong lúc flow đang
chạy, `Shift+1` pause ngay và bấm lại để resume đúng state hiện tại; `Shift+2`
đặt pause một lần khi nhận diện boss bất kỳ; `Shift+3` đặt pause một lần khi
nhận diện final boss. Hai policy boss có thể thay thế nhau trước khi trigger.
`Shift+8` vẫn chụp screenshot, `Shift+0` dừng hẳn flow, còn các Shift+digit khác
bị ignore cho tới khi flow kết thúc. Flow không restart từ đầu sau khi resume.
Các control trên hoạt động giống nhau khi `Shift+2` hoặc `Shift+3` đang chạy.
Các số này là giá trị của dict `START_AUTO_HOTKEYS` trong
`tools/hauntedroom/settings.py`, nên có thể remap mà không sửa controller.

Mỗi vòng chạy theo thứ tự:

1. Tái sử dụng các action của flow `Shift+1` từ đầu tới hết action click
   `start_battle.png`; các action exit không được chạy. Entry actions được thử
   tối đa 2 lần khi timeout và dừng ngay sau lần đầu tiên hoàn thành thành công.
2. Gọi `run_automap_flow()` để chạy trọn một lượt business core giống `Shift+2`.
   Khi map-end match, lời gọi này chỉ trả thành công sau khi win-map completion
   bridge đã dọn UI và xác nhận home.
3. Nếu completion bridge trả `False`, dừng toàn bộ start-auto loop ngay; không
   chạy loss check, cooldown hoặc entry action mới.
4. Nếu completion bridge trả `True`, kiểm tra map có thất bại hay không. Nếu
   `win_count` không tăng trong map vừa xong, coi đó là một loss và tự arm policy
   pause một lần ở boss đầu tiên cho map kế tiếp (tương đương `Shift+2`).
5. Chờ 2 giây rồi bắt đầu vòng tiếp theo.

Contract nối loop là:

```text
start battle
    -> run_automap_flow()
    -> finish_map_from_home()
       -> completed=False: stop Shift+3
       -> completed=True: loss check
          -> không thấy reward: arm pause ở boss đầu tiên của map kế
          -> cooldown 2 giây -> start battle kế tiếp
```

Flow giữ `win_count` trong suốt một lần chạy `Shift+3`. Khi auto-map nhận diện
`win_reward.png` lần đầu tiên trong màn reward của một map, `win_count` tăng 1;
các reward còn lại trong cùng màn không làm tăng thêm count. Ngay trước log hoàn
thành auto-map, flow in tổng hiện tại theo format `>>> [total_win] win`.
`win_count` không phải điều kiện nối loop: map chỉ cần completion bridge xác nhận
home. Tuy nhiên, nếu reward không được nhận diện và count không tăng, runner coi
map đó là loss và arm `PAUSE_AT_ANY_BOSS` cho map kế tiếp. Khi boss đầu tiên được
nhận diện, flow click pause trong game rồi pause script; người dùng xử lý game và
resume script bằng hotkey `pause_resume` (mặc định `Shift+1`). Policy này là
one-shot và được consume khi boss match.

Trước log cooldown giữa hai map có một dòng gạch ngang để phân cách log. Detector
thất bại hiện là placeholder `map_was_lost()` và luôn trả về `False`; vì vậy flow
hiện chỉ kết thúc khi bị dừng, auto-map không hoàn tất hoặc có lỗi.

## Hot-reload khi phát triển

Chạy runner với:

```shell
uv run python tools/hauntedroom_runner.py --dev-reload
```

Vòng lặp phát triển là `Shift+0` → sửa code/template/action JSON → bắt đầu lại
flow. Runner giữ nguyên browser và session, nhưng reload module Python liên quan
tới flow mới. Với `Shift+2`/`Shift+3`, runner reload `core.vision`, action
support, các module `flows.automap_support`, rồi `flows.automap`. Các phase
`map_completion.py` giữ priority orchestration tổng cùng home detection. Package
nội bộ `completion_flow/` chứa `first_win.py`, `reward.py`, `blocker.py` và
`state.py`; file `state.py` gom shared state/result cùng các runtime context để
tránh sinh thêm module quá nhỏ. Các helper này chỉ được map-completion consume.
Các phase khác gồm
`upgrade_action.py`, `hero_action.py` và `boss_flow.py`; detector/action nền vẫn
nằm ở `boss_detector.py`, `detectors.py`, `boss_action.py`, `gear_action.py` và
`hero_levelup_vision.py`. Với `Shift+3`, action JSON cũng được load lại trước khi
lấy prefix `start_battle`. Nếu reload lỗi syntax/import/JSON, runner vẫn mở ở
trạng thái idle để có thể sửa và thử lại.

## Vị trí code và test

- Auto-map coordinator/public API: `tools/hauntedroom/flows/automap.py`.
- Wrapper/composite flow `Shift+3`: `tools/hauntedroom/flows/start_auto.py`.
- Hotkey standby/controller: `tools/hauntedroom/runner/standby.py`.
- Command spec factory: `tools/hauntedroom/runner/commands.py`.
- Default command wiring: `tools/hauntedroom/runner/default_commands.py`.
- Detector, action và phase rule hỗ trợ:
  `tools/hauntedroom/flows/automap_support/`.
- Template: `tools/rooms/automap/` và `tools/rooms/boss/`.
- Regression test: `tests/automap/`, `tests/hero_select/`, `tests/runner/` và
  fixture trong `tests/fixtures/`.

Xem [TESTING.md](TESTING.md) để biết lệnh chạy test.
