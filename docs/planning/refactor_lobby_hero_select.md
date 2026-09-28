# Refactor lobby và hero-select

## Bối cảnh

Hai flow chạy từ `Shift+1` đều đi qua các phase chính:

- lobby;
- hero-select;
- battle;
- cleanup.

Lobby và cleanup của automap và train có hành vi khác nhau. Ngược lại,
hero-select là cùng một màn hình, cùng điều kiện nhận diện và cùng thao tác bắt
đầu trận. Phần này cần có một implementation duy nhất để hai flow luôn giữ hành
vi giống nhau.

## Phân biệt các phase có tên "hero"

Codebase đang có ba thứ dễ nhầm tên. Refactor này chỉ thay đổi thứ nhất.

| Phase | Thời điểm | Code hiện tại |
| --- | --- | --- |
| Hero-select screen: detect banner, click nút vàng để vào trận | Sau lobby, trước trận (cả automap lẫn train) | `actions/hero_select_battle.py` và bản copy trong `train_support/common.py` |
| Train card options: chọn 2/4 card, 5 round | Đầu trận train, sau khi bấm nút vàng | `train_support/hero_selection.py`, `automap_support/train_select.py` |
| Hero level-up picker: chọn option khi hero lên cấp | Giữa trận automap | `automap_support/hero_action.py`, `automap_support/vision/hero_levelup.py` |

Phase thứ hai và thứ ba nằm ngoài phạm vi; chỉ đổi tên nếu cần để không
nhầm với phase thứ nhất.

## Lý do refactor

Logic hero-select hiện có nguy cơ bị lặp giữa automap và train. Khi detector,
threshold, timeout hoặc cách click được sửa ở một flow nhưng không được sửa ở
flow còn lại, hai flow sẽ dần có hành vi khác nhau dù đang xử lý cùng một phase.

Ranh giới trách nhiệm cũng chưa rõ: một số xử lý thuộc lobby đang nằm trong
hero-select, trong khi một số xử lý hero-select lại nằm trong entry/lobby của
train. Điều này làm retry và timeout của một phase có thể kéo theo logic của
phase khác.

Mục tiêu của refactor là áp dụng DRY cho hero-select, đồng thời giữ thay đổi nhỏ
nhất có thể. Refactor chỉ điều chỉnh điểm bàn giao giữa lobby và hero-select;
không mở rộng sang battle, cleanup hoặc các thay đổi không cần thiết khác.

## Kết quả mong muốn

- Automap lobby chỉ xử lý blocker, entry và recovery riêng của automap.
- Train lobby chỉ xử lý availability, reward và entry riêng của train.
- Cả hai lobby kết thúc khi màn hình hero-select đã sẵn sàng.
- Hai flow gọi cùng một hero-select implementation để detect, chờ, click và
  settle.
- Implementation dùng chung nằm trong `flows/hero_select/`, không nằm ở
  `vision/` hay `actions/`.
- Battle và cleanup tiếp tục dùng hành vi hiện có.
- Các API đang được consumer khác sử dụng được giữ lại bằng wrapper mỏng khi
  việc đó giúp giảm phạm vi thay đổi.

Luồng mong muốn ở mức overview:

```text
Automap lobby ──> flows/hero_select/ ──> existing automap battle/cleanup
Train lobby   ──> flows/hero_select/ ──> existing train selection/battle/cleanup
```

## Đề xuất commit

### Commit 1: `refactor(hero-select): consolidate shared behavior`

- Tạo một implementation dùng chung cho nhận diện và thao tác hero-select.
- Shared implementation nằm ở `flows/hero_select/`: hằng số anchor, detector
  và loop detect - chờ - click - settle.
- Cho code automap và train hiện tại delegate vào implementation này.
- Giữ `actions/hero_select_battle.py` làm wrapper mỏng: giữ nguyên Action
  type `click_hero_select_battle`, delegate vào `flows/hero_select/`.
- Giữ hành vi quan sát được hiện tại, bao gồm timeout, stop handling và click.
- Thêm hoặc chuyển các test detector/action sang kiểm tra implementation dùng
  chung.
- Cập nhật `tests/test_hauntedroom_architecture.py`: mở exception scoped cho
  riêng `actions/hero_select_battle.py` được import
  `hauntedroom.flows.hero_select` (cùng pattern với exception ngược chiều đã
  có ở `exit_flow.py`), và bổ sung allowlist import cho `train_support`.

Commit này chỉ loại bỏ duplication của hero-select, chưa thay đổi ranh giới
lobby.

### Commit 2: `refactor(lobby): hand off both flows at hero-select`

- Cho automap lobby kết thúc khi hero-select sẵn sàng.
- Cho train lobby kết thúc tại cùng điều kiện bàn giao.
- Cập nhật hai loop để gọi shared hero-select sau lobby.
- Giữ nguyên phần train card selection, battle và cleanup sau điểm bàn giao.
- Duy trì wrapper tương thích nếu có caller cũ vẫn gọi entry và hero-select như
  một thao tác kết hợp.

Commit này tạo boundary rõ giữa phần khác nhau và phần dùng chung, với thay đổi
tối thiểu trong coordinator.

### Commit 3: `test(flows): lock lobby and hero-select phase boundaries`

- Bổ sung regression test cho thứ tự `lobby -> shared hero-select -> battle` ở
  cả automap và train.
- Xác nhận hai flow gọi đúng cùng một shared implementation.
- Xóa test hoặc constant duplicate sau khi không còn consumer.
- Đổi tên `tests/hero_select/` thành `tests/hero_levelup/` để tên thư mục
  test không còn trùng với phase hero-select screen. Tùy chọn kèm đổi
  `train_support/hero_selection.py` thành `train_support/card_selection.py`
  vì lý do tương tự.
- Cập nhật dev reload hoặc tài liệu liên quan nếu shared implementation cần
  được nhận ở lần chạy flow tiếp theo.

Commit này khóa contract mới và loại bỏ phần compatibility không còn cần thiết,
nhưng không thực hiện cleanup ngoài phạm vi lobby/hero-select.

## Nguyên tắc triển khai

- Ưu tiên reuse code hiện có thay vì viết lại flow.
- Không thay đổi thuật toán nhận diện nếu không cần cho việc dùng chung.
- Không thay đổi timing chỉ để đồng nhất tên gọi; chọn hành vi hiện tại đã được
  test và giữ nó làm contract chung.
- Không trộn lobby-specific recovery vào shared hero-select.
- Không đưa train-specific selection vào shared hero-select.
- Mỗi commit phải chạy được độc lập và giữ test suite xanh.

## Điều kiện hoàn thành

- Chỉ còn một nguồn logic nhận diện và click hero-select.
- Automap và train đều gọi nguồn logic đó sau khi lobby hoàn tất.
- Shared hero-select không nhận tham số mang ý nghĩa riêng của map lobby hoặc
  train lobby.
- Không có thay đổi hành vi ngoài lobby/hero-select.
- Toàn bộ test hiện có và regression test mới đều pass.
