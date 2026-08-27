# Hero level-up selection

Thư mục này chứa các asset dùng để nhận diện option trong popup hero level-up.
`hero_action.py` hỏi vision theo business priority và dừng ngay khi chọn được
card. Vision chỉ trả lời từng query về card, màu hoặc template match. Vision sở
hữu template paths/calibration; hero picker train của `Shift+4` tái sử dụng cùng
danh sách asset.

## Flow selection

```text
level-up available
        |
        v
click (320, 640) để mở picker
        |
        v
chờ animation settle 1.500 ms
        |
        v
action hỏi vision và short-circuit:
  1. có ascend? -> chọn ascend bên trái nhất
  2. lần lượt từng template priority -> match thì chọn ngay
  3. priority 99 -> đánh dấu card cần tránh
  4. detect card fallback một lần -> vàng, rồi tím, rồi đỏ
```

Flow chỉ mở picker sau khi detector xác nhận vùng level-up sẵn sàng. Sau lần chờ
đầu tiên, flow poll tối đa 10 lần, cách nhau `200 ms`, nếu chưa tìm thấy option.
Sau khi click lựa chọn, flow chờ `600 ms` trước khi tiếp tục auto-map.

## Priority và asset

Action đọc prefix trước dấu gạch dưới dưới dạng số, luôn hỏi ascend trước rồi sort
các template còn lại tăng dần theo `(priority, filename)`. Vision chỉ match
template mà action đang hỏi; khi match, action không chạy các priority sau.

| Thứ tự | Priority | Asset | Nhận diện | Threshold | Hành vi |
|---:|---:|---|---|---:|---|
| 1 | 00 | `00_hero_ascend.png` | Góc cyan của card Thần Khí, không bắt chữ | `0.90` | Chọn card ascend bên trái nhất; click tâm panel dưới |
| 2 | 00 | `00_mage_king.png` | Vua Pháp Sư | `0.80` | Chọn ngay, trước mọi priority lớn hơn |
| 3 | 01 | `01_dark_lubu.png` | Hắc Lữ Bố | `0.70` | Chọn nếu không có match priority 00 |
| 4 | 02 | `02_hanuman.png` | Hanuman | `0.70` | Chọn nếu không có match priority 00–01 |
| 5 | 03 | `03_soul_spear.png` | Cây Giáo Hút Hồn | `0.80` | Chọn nếu không có match priority thấp hơn |
| 6 | 04 | `04_thunder_trident.png` | Đinh Ba Sấm Sét | `0.80` | Chọn nếu không có match priority thấp hơn |
| 7 | 09 | `09_pinocchio.png` | Từ “Pinocchio”, dùng chung cho card mới và tăng sao | `0.70` | Chọn nếu không có match priority thấp hơn |
| 8 | 10 | `10_prayer_box.png` | Hộp Cầu Nguyện | `0.80` | Chọn nếu không có match priority thấp hơn |
| 9 | 11 | `11_death.png` | Tử Thần trong card tăng sao | `0.70` | Chọn nếu không có match priority thấp hơn |
| 10 | 11 | `11_underworld.png` | U Minh Thần khi chưa được chọn | `0.70` | Chọn nếu không có match priority thấp hơn |
| 11 | 12 | `12_soul_reaper.png` | Liềm Đoạt Hồn | `0.80` | Chọn nếu không có match priority thấp hơn |
| 12 | 99 | `99_mage_king.png` | Variant Vua Pháp Sư/tăng sao cần tránh | `0.80` | Không chọn theo template; loại card gần match khỏi fallback nếu còn card khác |

`00_hero_ascend.png` là trường hợp đặc biệt: vision tìm tất cả match ở scale
`1.0` và dịch tâm match `-47 px` theo trục x về `y=632`; action chọn match ascend
bên trái nhất. Các asset còn lại dùng template matching grayscale ở scale `1.0`
trong vùng từ `y=460` trở xuống.

Train `Shift+4` tái sử dụng cùng danh sách priority ở scale cố định `0.8` trong
`automap_support/train_select.py`. Fallback train dựa trên cạnh card đỏ/tím và
chỉ tự chọn card tím chưa chọn; nó không dùng toàn bộ fallback panel của
auto-map.

## Fallback theo panel và màu

Khi không có template ưu tiên nào match, detector dùng panel dưới của card:

- Vùng tìm panel: `y=610..654`.
- Pixel panel hợp lệ khi saturation `>=80` và value `>=40` trong HSV.
- Một cột active khi ít nhất `75%` chiều cao vùng là pixel hợp lệ.
- Khe inactive được nối nếu rộng tối đa `3 px`; khoảng trống lớn giữa các card
  vẫn được giữ nguyên.
- Một span phải rộng ít nhất `80 px` mới được xem là card; điểm click nằm ở tâm
  span và `y=632`.

Để phân loại tím, detector đọc strip background phía dưới bên phải card:

```text
x = center_x + 43 .. center_x + 54
y = 610 .. 654
```

Sau khi bỏ pixel thiếu saturation/value, median hue trong khoảng `130..150`
được vision phân loại là tím và `10..25` là vàng. Action luôn chọn ascend trước,
sau đó tới các template priority còn lại. Nếu không template nào match, action
chọn card vàng hợp lệ đầu tiên từ trái sang phải, sau đó card tím, và chỉ chọn
card đỏ khi không có cả vàng lẫn tím. Log ghi rõ fallback về `purple`, `yellow`
hay `red`. Nếu mọi card đều bị priority `99` đánh dấu, action vẫn chọn một card
thay vì không xử lý popup.

Flow tái sử dụng live screenshot của `Shift+8` và lưu vào
`tests/fixtures/hauntedroom-captures/` khi detector thấy đủ đúng 3 card và
không card nào là vàng hoặc tím. Layout chỉ có 1/2 card, hoặc layout 3 card
có vàng/tím, đều không được capture. Có thể tắt/bật capture này
bằng `CAPTURE_HERO_FALLBACK_SCREENSHOTS` trong `tools/hauntedroom/settings.py`;
flag được đọc lại cho flow mới khi runner chạy `--dev-reload`.

## Quy ước khi thay đổi asset

- Giữ prefix priority dạng số, ví dụ `02_name.png`; runtime tự động load mọi
  file `*.png` trong thư mục này.
- Nếu nhiều asset có cùng priority, filename quyết định thứ tự thử.
- Priority `99` là marker loại khỏi fallback, không phải lựa chọn ưu tiên thấp.
- Khi thêm, xóa hoặc đổi priority asset, cập nhật bảng trên và regression test
  kiểm tra `HERO_LEVELUP_TEMPLATE_PATHS`.
- Ưu tiên crop vùng ít animation. Asset phụ thuộc chữ có thể không match khi đổi
  ngôn ngữ game; fallback panel/màu là lớp bảo vệ không phụ thuộc chữ.

## Code, test và tài liệu liên quan

- Vision queries và template: [`vision/hero_levelup.py`](../../../hauntedroom/flows/automap_support/vision/hero_levelup.py)
- Business decision/action: [`hero_action.py`](../../../hauntedroom/flows/automap_support/hero_action.py)
- Train matcher: [`train_select.py`](../../../hauntedroom/flows/automap_support/train_select.py)
- Orchestrator: [`automap.py`](../../../hauntedroom/flows/automap.py)
- Vision test: [`test_hero_vision.py`](../../../../tests/hero_select/test_hero_vision.py)
- Choice policy test: [`test_hero_choice_policy.py`](../../../../tests/hero_select/test_hero_choice_policy.py)
- Action behavior test: [`test_hero_action.py`](../../../../tests/hero_select/test_hero_action.py)
- Thin `AutomapFlow` adapter test: [`test_hero_flow_adapter.py`](../../../../tests/hero_select/test_hero_flow_adapter.py)
- Fixture integration regression: [`test_hero_integration.py`](../../../../tests/hero_select/test_hero_integration.py)
- Train selection test: [`test_train_select.py`](../../../../tests/hero_select/test_train_select.py)
- Fixture selection chuẩn: [`tests/fixtures/hauntedroom-captures/hero_select/`](../../../../tests/fixtures/hauntedroom-captures/hero_select/)
- Fixture từng bị capture sai: [`tests/fixtures/hauntedroom-captures/wrong_fallback/`](../../../../tests/fixtures/hauntedroom-captures/wrong_fallback/)
- Auto-map flow: [`AUTOMAP_FLOWS.md`](../../../../docs/AUTOMAP_FLOWS.md)
- Audit template phụ thuộc chữ: [`VISION_OCR_AUDIT.md`](../../../../docs/audit/VISION_OCR_AUDIT.md)
