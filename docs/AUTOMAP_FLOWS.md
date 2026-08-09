# Auto-map flows: `Shift+2` và `Shift+3`

`Shift+2` chạy business core auto-map cho một trận. `Shift+3` không có một
implementation auto-map riêng; nó là wrapper tự vào trận, gọi cùng business
core, chờ cooldown rồi lặp sang map tiếp theo. Tài liệu này là nguồn mô tả chính
cho thứ tự ưu tiên, điều kiện và kết quả của cả hai flow.

| Hành vi | `Shift+2` | `Shift+3` |
|---|---|---|
| Vào room và bắt đầu trận | Người dùng thực hiện trước | Tự chạy prefix action của `Shift+1` |
| Auto-map trong trận | Chạy `run_automap_flow()` một lần | Gọi cùng `run_automap_flow()` trong mỗi loop |
| Pause/resume bằng `Shift+3` | Không | Có |
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

- Tìm `automap/map_end.png` với threshold `0.90`; phép kiểm tra được throttle
  tối đa một lần mỗi 5 giây.
- Khi match, click để quay về home.
- Nếu thấy `automap/win_reward.png`, click match đầu tiên ở mép trên template
  rồi kiểm tra lại sau `2 giây` cho tới khi không còn reward icon.
- Sau khi reward icon biến mất, tìm `automap/reward_list_title.png` trong vùng
  title của popup reward-list; nếu match, click title đúng một lần rồi tiếp tục
  đợi home.
- Khi `rooms/start_home.png` xuất hiện, đánh dấu auto-map hoàn tất và về idle.

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

### 4. Boss critical handoff

- Tìm HP bar trước để phát hiện cả mini-boss lẫn final boss cần handoff.
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
- Không xử lý riêng khoảnh khắc thanh máu cuối cạn và chuyển đen; flow
  chấp nhận edge case này và handoff trong trạng thái boss thông thường còn thanh máu.
- Khi `CLICK_EXIT_ON_BOSS=True` trong `tools/hauntedroom/settings.py` và
  `rooms/exit_click.png` sẵn sàng, click đúng một lần rồi dừng auto-map để
  người dùng xử lý boss thủ công. Click này chỉ pause game; flow không bấm
  `exit_confirm`.
- Boss detection log loại boss, vị trí và score một lần khi thanh HP đi vào vùng
  search; log này không lặp theo từng frame trong cùng một lần HP hiện diện. Khi
  `CLICK_EXIT_ON_BOSS=False`, mini-boss chỉ log/no-op; final boss vẫn đi qua
  nhánh deploy pet nếu pet chưa được deploy trong flow hiện tại.
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
- Fallback chọn card tím hợp lệ đầu tiên; nếu không có card tím mới chọn card
  hợp lệ đầu tiên. Card priority `99` chỉ được dùng khi không còn lựa chọn khác.

## `Shift+2`: chạy một map

`Shift+2` gọi thẳng `run_automap_flow()`. Người dùng phải vào map và bấm
`start_battle` trước khi kích hoạt hotkey. Khi core hoàn tất hoặc dừng, runner
trở về idle và không tự bắt đầu map tiếp theo.

## `Shift+3`: start-auto loop

Khi runner idle, `Shift+3` bắt đầu chạy nhiều map liên tiếp. Trong lúc flow đang
chạy, bấm lại `Shift+3` để pause và bấm lần nữa để resume đúng state hiện tại;
flow không restart từ đầu. Khi đang chạy hoặc pause, `Shift+0` dừng hẳn flow.

Mỗi vòng chạy theo thứ tự:

1. Tái sử dụng các action của flow `Shift+1` từ đầu tới hết action click
   `start_battle.png`; các action exit không được chạy. Entry actions được thử
   tối đa 2 lần khi timeout và dừng ngay sau lần đầu tiên hoàn thành thành công.
2. Gọi `run_automap_flow()` để chạy trọn một lượt business core giống `Shift+2`.
3. Kiểm tra map có thất bại hay không.
4. Nếu chưa thất bại, chờ 2 giây rồi bắt đầu vòng tiếp theo.

Flow giữ `win_count` trong suốt một lần chạy `Shift+3`. Khi auto-map nhận diện
`win_reward.png` lần đầu tiên trong màn reward của một map, `win_count` tăng 1;
các reward còn lại trong cùng màn không làm tăng thêm count. Ngay trước log hoàn
thành auto-map, flow in tổng hiện tại theo format `>>> [total_win] win`.
Boss handoff không bị runner tự override theo số loop; muốn click nút pause/menu
khi gặp boss thì bật `CLICK_EXIT_ON_BOSS` trong `tools/hauntedroom/settings.py`.

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
orchestration đã tách gồm `map_completion.py`, `upgrade_action.py`,
`hero_action.py` và `boss_flow.py`; các detector/action nền vẫn nằm ở
`boss_detector.py`, `detectors.py`, `boss_action.py`, `gear_action.py` và
`hero_levelup.py`. Với `Shift+3`, action JSON cũng được load lại trước khi lấy
prefix `start_battle`. Nếu reload lỗi syntax/import/JSON, runner vẫn mở ở trạng
thái idle để có thể sửa và thử lại.

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
