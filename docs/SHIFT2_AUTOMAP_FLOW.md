# Business core: logic flow `Shift+2`

`Shift+2` kích hoạt auto-map battle và là business core của Haunted Room runner.
Tài liệu này là nguồn mô tả chính cho thứ tự ưu tiên, điều kiện và kết quả của
flow; README chỉ giới thiệu và dẫn tới đây.

## Điều kiện bắt đầu và kết thúc

Trước khi bấm `Shift+2`, người dùng đã vào map và bấm `start_battle` thủ công.
Flow chụp viewport liên tục, chạy các handler theo priority và chỉ xử lý tình
huống đầu tiên match trong mỗi vòng quét.

Flow kết thúc khi:

- map hoàn tất và màn hình home đã sẵn sàng;
- boss vào vùng critical, bot handoff để người dùng xử lý thủ công; hoặc
- người dùng bấm `Shift+0` để dừng mềm và đưa runner về idle.

## Priority loop

```text
capture viewport
      |
      v
1. level-spin interrupt
2. map end (throttle tối đa một lần mỗi 5 giây)
3. boss critical handoff
4. level up
5. build structure
6. hero level-up
      |
      +-- không handler nào match: chờ 600 ms rồi quét lại
      +-- handler đã xử lý: bắt đầu vòng quét mới từ priority 1
```

Priority là contract của flow. Handler ở trên được quyền preempt handler ở dưới;
khi thêm tình huống mới phải xác định rõ vị trí của nó trong danh sách này.

## Business rule theo phase

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

### 3. Boss critical handoff

- Tìm HP bar trước để phát hiện cả mini-boss lẫn final boss cần handoff.
- Sau khi HP match, phân loại bằng endpoint cố định `(400, 61, 409, 72)`
  của thanh progress trên cùng: ít nhất `85%` pixel vàng là final boss;
  progress chưa tới endpoint là mini-boss. Classifier không được dùng để
  short-circuit HP detection.
- Nhận diện các cạnh sọc dọc của `boss/boss_hp_bar.png` ở đúng kích thước
  cố định `61x11`, không phụ thuộc màu thanh HP.
- Candidate chỉ hợp lệ khi cả anchor trái và phải của toàn thanh đều match;
  prefix hoặc thanh bị che mất phần cuối sẽ bị loại.
- Chỉ tìm thanh HP trong upper battlefield region `(117, 120, 522, 308)`.
  Boss đi từ trên hoặc bên phải sẽ đưa toàn thanh HP qua region này trước
  khi tiến tới cửa. Giới hạn dưới `y2=308` loại HP của cửa ở khu vực phòng.
- Boss và mini-boss có thể dùng cùng hình học thanh HP, nên detector không
  phân loại chúng chỉ từ pixel của thanh. Scope hiện tại chấp nhận
  limitation này; nếu cần phân loại sau này phải thêm stage signal riêng.
- Không xử lý riêng khoảnh khắc thanh máu cuối cạn và chuyển đen; flow
  chấp nhận edge case này và handoff trong trạng thái boss thông thường còn thanh máu.
- Khi `rooms/exit_click.png` sẵn sàng, click đúng một lần rồi dừng auto-map để
  người dùng xử lý boss thủ công.
- Logic nhận diện và action boss hỗ trợ nằm trong
  `flows/automap_support/detectors.py` và `boss_action.py`.

### 4. Level up

- Nếu có nhiều match `automap/lv_up.png`, chọn match có `y` lớn nhất.
- Click level-up, chờ `800 ms`, rồi kiểm tra lại `lv_spin`.
- Nếu không có interrupt, click confirm tại `(430, 366)`.

### 5. Build structure

- Nếu có nhiều marker `automap/built.png`, chọn marker có `x` lớn nhất; nếu
  trùng `x`, chọn `y` lớn nhất.
- Sau khi mở menu, duyệt option từ trên xuống và click option đầu tiên có giá
  màu trắng.
- Giá màu đỏ hoặc vàng không được xem là available; nếu không có giá trắng thì
  bỏ qua phase này.

### 6. Hero level-up

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
- Nếu không template ưu tiên nào match, detector tìm layout 3, 2 hoặc 1 card và
  click card visible đầu tiên còn hợp lệ.

## Hot-reload khi phát triển

Chạy runner với:

```shell
uv run python tools/hauntedroom_runner.py --dev-reload
```

Vòng lặp phát triển là `Shift+0` → sửa code/template → `Shift+2`. Runner reload
`core.vision`, các module `flows.automap_support`, rồi `flows.automap` trong khi
giữ nguyên browser và session. Nếu reload lỗi syntax/import, runner vẫn mở ở
trạng thái idle để có thể sửa và thử lại.

## Vị trí code và test

- Orchestrator: `tools/hauntedroom/flows/automap.py`.
- Detector và rule hỗ trợ: `tools/hauntedroom/flows/automap_support/`.
- Template: `tools/rooms/automap/` và `tools/rooms/boss/`.
- Regression test: `tests/automap/`, `tests/hero_select/` và fixture trong
  `tests/fixtures/`.

Xem [TESTING.md](TESTING.md) để biết lệnh chạy test.
