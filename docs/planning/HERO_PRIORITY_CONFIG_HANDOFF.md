# Handoff: Hero Priority Configuration Refactor

Tài liệu bàn giao (Handoff) thiết kế và kế hoạch refactor cơ chế phân cấp ưu tiên (Priority) khi chọn thẻ Hero Level-up và Train Mode từ **Prefix tên file ảnh** sang **File cấu hình tường minh (Config-driven)** có thể tùy biến bằng tay.

---

## 1. Bối cảnh & Vấn đề hiện tại (Current Status & Problems)

Hiện tại, độ ưu tiên chọn thẻ Hero đang được suy ra tự động từ tiền tố số trong tên file asset (`tools/rooms/automap/hero_levelup/`):
- `00_hero_ascend.png`, `00_mage_king.png`, `01_dark_lubu.png`, `02_hanuman.png`...
- Hàm `_hero_template_priority()` đọc số trước dấu gạch dưới `_` để sort.
- Số `99_` được dùng làm magic number (`HERO_IGNORED_PRIORITY = 99.0`) để đánh dấu thẻ cần tránh (né trong fallback).

### Các hạn chế:
1. **Tight Coupling giữa Asset và Business Logic**: Muốn thay đổi thứ tự ưu tiên thì bắt buộc phải đổi tên file PNG trên disk -> tạo git rename churn và làm bẩn lịch sử commit.
2. **Dễ sinh lỗi ngầm (Silent Bugs)**: Trong [`vision/hero_levelup.py`](../../tools/hauntedroom/flows/automap_support/vision/hero_levelup.py), các biến cấu hình nhận diện (threshold) đang hardcode chuỗi tên file có prefix (như `"01_dark_lubu.png"` cho ngưỡng `0.69`). Nếu rename file thành `05_dark_lubu.png`, threshold riêng bị vô hiệu hóa mà không có cảnh báo nào.
3. **Thiếu tính linh hoạt (Customizability)**: Người dùng không thể tự cấu hình danh sách ưu tiên theo chiến thuật/meta hoặc chia nhiều profile build khác nhau mà không phải sao chép/đổi tên hàng loạt file ảnh.

---

## 2. Thiết kế mục tiêu (Target Design)

### 2.1. Tách bạch Asset và Config
- **Asset files**: Đổi tên bỏ tiền tố số, chỉ giữ tên định danh thẻ thuần túy:
  - `00_hero_ascend.png` -> `hero_ascend.png`
  - `00_mage_king.png` -> `mage_king.png`
  - `01_dark_lubu.png` -> `dark_lubu.png`
  - `02_hanuman.png` -> `hanuman.png`
  - `03_soul_spear.png` -> `soul_spear.png`
  - `04_thunder_trident.png` -> `thunder_trident.png`
  - `09_pinocchio.png` -> `pinocchio.png`
  - `10_prayer_box.png` -> `prayer_box.png`
  - `11_death.png` -> `death.png`
  - `11_underworld.png` -> `underworld.png`
  - `12_soul_reaper.png` -> `soul_reaper.png`
  - `99_mage_king.png` -> `mage_king_upgrade.png` (hoặc tên mô tả rõ ràng)

### 2.2. Cấu trúc File Cấu hình (`hero_priority.json`)
Lưu tại: `tools/hauntedroom/configs/hero_priority.json` (hoặc `tools/hauntedroom/settings.py` / `configs/`):

```json
{
  "ascend_template": "hero_ascend.png",
  "priority": [
    "mage_king.png",
    "dark_lubu.png",
    "hanuman.png",
    "soul_spear.png",
    "thunder_trident.png",
    "pinocchio.png",
    "prayer_box.png",
    "death.png",
    "underworld.png",
    "soul_reaper.png"
  ],
  "ignored": [
    "mage_king_upgrade.png"
  ],
  "fallback_colors": [
    "yellow",
    "purple",
    "red"
  ],
  "custom_thresholds": {
    "dark_lubu.png": 0.69,
    "hanuman.png": 0.70,
    "pinocchio.png": 0.70,
    "death.png": 0.70,
    "underworld.png": 0.70
  }
}
```

### 2.3. Quy tắc hoạt động mới
1. **Ascend Check**: Kiểm tra template được chỉ định ở `ascend_template` (mặc định `hero_ascend.png`). Nếu có nhiều match, chọn thẻ ngoài cùng bên trái.
2. **Priority Matching**: Duyệt lần lượt theo danh sách `priority` từ trên xuống dưới. Match template nào thì chọn ngay (short-circuit).
3. **Ignored Marker**: Các template nằm trong mảng `ignored` được nhận diện để đưa vào danh sách `ignored_options`, giúp bước fallback né các vị trí này.
4. **Fallback By Color**: Duyệt màu theo thứ tự khai báo trong `fallback_colors` (`yellow` -> `purple` -> `red`), chọn thẻ hợp lệ đầu tiên từ trái sang phải không nằm trong `ignored_options`.

---

## 3. Phạm vi ảnh hưởng & Các file cần chỉnh sửa

| Thành phần | Đường dẫn | Thay đổi cần thực hiện |
|---|---|---|
| **Asset Directory** | `tools/rooms/automap/hero_levelup/` | Rename toàn bộ file ảnh PNG bỏ prefix số |
| **New Config** | `tools/hauntedroom/configs/hero_priority.json` | Tạo file config JSON chuẩn |
| **Vision** | `tools/hauntedroom/flows/automap_support/vision/hero_levelup.py` | Cập nhật `HERO_ASCEND_TEMPLATE_NAME`, load config/threshold động từ config thay vì hardcode tên cũ |
| **Action** | `tools/hauntedroom/flows/automap_support/hero_action.py` | Bỏ `_hero_template_priority()`, duyệt danh sách template theo thứ tự từ config, check `ignored` từ config |
| **Train Flow** | `tools/hauntedroom/flows/automap_support/train_select.py` | Cập nhật `TrainHeroMatcher` sử dụng cùng config priority/ignored |
| **Hot Reload** | `tools/hauntedroom/runner/reload.py` | Bổ sung file config vào danh sách theo dõi reload khi bật `--dev-reload` |
| **Tài liệu** | `tools/rooms/automap/hero_levelup/README.md` | Cập nhật tài liệu hướng dẫn cách chỉnh sửa priority qua JSON |
| **Tài liệu** | `docs/AUTOMAP_FLOWS.md`, `docs/ARCHITECTURE.md` | Cập nhật lại mô tả flow hero levelup |
| **Test Suite** | `tests/hero_select/` | Cập nhật tên template trong tất cả unit & integration tests (`test_hero_choice_policy.py`, `test_hero_vision.py`, `test_hero_action.py`, `test_train_select.py`, `test_hero_integration.py`) |

---

## 4. Kế hoạch triển khai (Step-by-Step Plan)

- [ ] **Bước 1: Tạo Config & Config Loader**
  - Viết module / dataclass đọc và validate `hero_priority.json` (hỗ trợ fallback default nếu file không tồn tại).
  - Tích hợp dev-reload cho file config này.
- [ ] **Bước 2: Refactor Vision & Action Logic**
  - Cập nhật [`vision/hero_levelup.py`](../../tools/hauntedroom/flows/automap_support/vision/hero_levelup.py) để dùng threshold từ config.
  - Cập nhật [`hero_action.py`](../../tools/hauntedroom/flows/automap_support/hero_action.py) và [`train_select.py`](../../tools/hauntedroom/flows/automap_support/train_select.py) loại bỏ hàm parse prefix số.
- [ ] **Bước 3: Rename Asset Files**
  - Đổi tên các file PNG trong `tools/rooms/automap/hero_levelup/`.
- [ ] **Bước 4: Cập nhật Test Suite & Fix Breakages**
  - Chạy `pytest tests/hero_select/` và cập nhật các mock/fixture test tương ứng với tên file mới.
  - Đảm bảo toàn bộ test suites `tests/` pass 100%.
- [ ] **Bước 5: Cập nhật Documentation**
  - Cập nhật bảng priority và hướng dẫn chỉnh sửa trong `tools/rooms/automap/hero_levelup/README.md`.

---

## 5. Tiêu chí hoàn thành (Definition of Done)

1. Tên file trong thư mục `rooms/automap/hero_levelup/` không còn chứa tiền tố số (`00_`, `01_`, `99_`).
2. Người dùng có thể tùy biến đổi thứ tự ưu tiên tướng chỉ bằng cách sửa file `hero_priority.json` mà không cần đổi tên file ảnh hay sửa code Python.
3. Khi chạy bot với cờ `--dev-reload`, thay đổi trong `hero_priority.json` được áp dụng ngay lập tức ở lần mở picker tiếp theo.
4. Toàn bộ test suite (`tests/hero_select/`, `tests/automap/`, `tests/runner/`) pass xanh hoàn toàn.
