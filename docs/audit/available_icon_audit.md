# Available icon audit

Ngày rà soát: 2026-09-28.

## Phạm vi

Ghi nhận các nơi đang dùng icon thông báo available trong code hiện tại để có
thể rà soát lại sau. Các ngưỡng, scale và vùng tìm kiếm bên dưới là cấu hình
runtime, không phải số liệu thực nghiệm. Audit này không thay đổi implementation
và không ghi kết quả của các thử nghiệm crop hoặc transparent.

## Template và matcher dùng chung

- Asset: [`research_available.png`](../../tools/rooms/misc/research_available.png).
- Có ba consumer trực tiếp: Research, Artifact và Train. Tên file mang tên
  Research nhưng asset được dùng chung cho cả ba flow.
- [`core/template_matching.py`](../../tools/hauntedroom/core/template_matching.py):
  `load_template` đọc grayscale; `find_template` dùng `cv2.TM_CCOEFF_NORMED`,
  chọn match tốt nhất trong vùng tìm kiếm ở các scale được truyền vào.
- Matcher hiện tại không dùng alpha mask. `find_template_in_region` dùng cùng
  matcher và trả `None` khi score dưới ngưỡng.
- Với `bottom_left`, tọa độ click được tính từ góc trái dưới của khung template
  đã scale, hơi lùi vào trong. Với `center`, tọa độ là tâm khung template.

## Các nơi match hiện tại

| Flow / detector | Vùng tìm kiếm | Scale | Ngưỡng mặc định | Cách sử dụng kết quả |
| --- | --- | --- | --- | --- |
| Research — `run_research_flow`, pha available | Toàn screenshot | `1.0` | `0.60` | Click `bottom_left` của template để mở ô nghiên cứu |
| Artifact — `find_artifact_tabs` | Từng vùng trong `ARTIFACT_TAB_REGIONS` | `0.8` | `0.70` | Trả các tab có dấu, từ trái sang phải; click `bottom_left` |
| Artifact — `find_artifact_item` | `ARTIFACT_CONTENT_REGION` | `0.9` | `0.80` | Chọn một dấu trên card để mở popup; click `bottom_left` |
| Artifact — `find_artifact_activation` | `ARTIFACT_ACTIVATE_REGION` | `0.5` | `0.60` | Tìm dấu trên nút kích hoạt trong popup; click `bottom_left` |
| Train — `train_is_available` | Góc phải trên nút vàng: `(x+25, y-35, x+70, y+5)`, với `(x,y)` là tâm nút | `1.0` | `0.55` | Chỉ dùng score làm điều kiện cho phép hành động; click tâm nút vàng, không click tọa độ icon |

### Research

Source: [`flows/research.py`](../../tools/hauntedroom/flows/research.py).

- `RESEARCH_AVAILABLE_TEMPLATE_PATH` trỏ tới asset dùng chung. Hàm flow cho phép
  truyền đường dẫn template và ngưỡng khác với mặc định.
- Pha available quét toàn screenshot. Sau bốn lần không match liên tiếp, flow
  kết thúc và về idle. Khi match, flow chờ rồi click tọa độ tìm được.
- Sau đó chuyển sang pha active, dùng asset riêng `research_active.png`; đây
  không phải một consumer khác của `research_available.png`. Pha active click
  tại tâm match cộng offset `(-40, 5)`, rồi quay lại available khi mất active.

### Artifact

Sources: [`artifact_vision.py`](../../tools/hauntedroom/flows/artifact_vision.py),
[`artifact.py`](../../tools/hauntedroom/flows/artifact.py).

- `ARTIFACT_MARK_TEMPLATE_PATH` trỏ tới asset dùng chung; `run_artifact_flow`
  cho phép truyền đường dẫn khác.
- Bốn vùng tab: `(150,340,248,385)`, `(245,340,325,385)`,
  `(325,340,405,385)`, `(405,340,490,385)`.
- Vùng content: `(120,390,520,600)`. Vùng activation: `(220,540,420,620)`.
- Flow đi qua tab có dấu, mở card có dấu, xử lý kích hoạt và đóng popup.
  Nếu không còn tab có dấu, flow vẫn kiểm tra item trước khi xác nhận idle.
- Pha activation kiểm tra sự hiện diện của popup qua detector nút close dùng
  `lubu_close.png`. Trong bước xác nhận idle, flow cũng phân biệt popup với
  danh sách trước khi chọn detector tương ứng.

### Train

Sources: [`train_support/common.py`](../../tools/hauntedroom/flows/train_support/common.py),
[`train_support/entry.py`](../../tools/hauntedroom/flows/train_support/entry.py).

- `TRAIN_AVAILABLE_BADGE_PATH` trỏ tới asset dùng chung.
- `train_is_available` tìm nút vàng trước, rồi kiểm tra icon ở góc phải trên
  nút đó. Nút vàng được tìm trong `(120,600,520,690)` bằng màu và hình học.
  Đây là dấu hiệu UI cho phép hành động, không phải OCR đọc số lượt.
- `check_and_click_train_start`: không có tín hiệu available thì trả `False`.
- `wait_for_train_start_available`: có nút vàng nhưng không có tín hiệu available
  thì dừng; nếu chưa thấy nút thì tiếp tục polling.
- `start_train_battle`: kiểm tra available trong vòng quét và trên frame mới
  ngay trước click. Có nút nhưng thiếu dấu thì dừng. Vòng này có giới hạn mặc
  định sáu click, không tính click mở đầu ở helper trước đó.
- Khi hết nút vàng, flow chuyển sang chờ màn chọn đội; bước đó dùng banner
  riêng, không dùng icon available.
- Helper entry được dùng chung cho normal Train và các mode exit/ad-exit.
  [`train_support/__init__.py`](../../tools/hauntedroom/flows/train_support/__init__.py)
  chỉ re-export các symbol, không có logic match độc lập.

## Các hướng để khảo sát lại sau

Chỉ là đề xuất thử nghiệm, chưa phải quyết định thay đổi code hoặc template:

- Crop sát icon.
- Crop và làm nền transparent, kết hợp mask khi matching.
- Crop vùng icon và thử nhận diện màu đỏ.

Không đưa kết quả, score thử nghiệm hoặc đề xuất ngưỡng từ các hướng này vào
audit hiện trạng.
