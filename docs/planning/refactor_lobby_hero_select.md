# Refactor lobby và hero-select

## Bối cảnh

Hai flow chạy từ `Shift+1` đi qua các phase như sau:

```text
lobby_map   ──┐
              ├──> hero_select (chung) ──> battle/auto (map)
              │         │
              │         └─(chỉ train)──> train_select ──> auto_train
lobby_train ──┘
```

- **lobby_map**: HOME screen. Có popup blocker (`lubu_close`, `overlay_close`,
  `overlay_newbie`,...), entry qua `start_home`, và recovery khi transition bị
  ngắt (bị đá về entry screen).
- **lobby_train**: train screen (anchor bảng station). Không có template
  blocker. Entry qua availability badge + click chuỗi nút vàng dưới đáy màn
  hình (reward claim → claim popup → challenge).
- **hero_select**: cùng một màn hình cho cả hai flow — cùng điều kiện nhận diện
  (banner top + nút vàng), cùng thao tác click vào trận. Phải là một
  implementation duy nhất.
- **train_select**: chọn 2/4 card × 5 round. Chỉ train có, chạy NGAY SAU
  hero_select, trước khi vào auto_train. Không thuộc hero_select.
- **battle/auto**: hành vi hiện có, không đổi.

Vấn đề hiện tại:

1. Logic hero-select bị duplicate thành hai bản đã drift nhẹ số liệu.
2. Buz của lobby_map (clear blocker, popup tab, re-click entry) đang nằm
   trong implementation hero-select của actions.
3. `start_train_battle` gộp hai phase lobby_train + hero-select vào một hàm,
   nên ranh giới bàn giao không tồn tại trong code.

## Hiện trạng code (audit 2026-09-29)

### Hai bản copy hero-select đã drift

| | `actions/hero_select_battle.py` | `train_support/common.py` + `entry.py` |
| --- | --- | --- |
| Header region / threshold / scales | (210,10,430,90) / 0.80 / (1.0,) | giống hệt |
| Button region | (230,650,410,719) | giống hệt |
| HSV yellow (V min) | 90 (`vision/buttons.py`) | 80 (`common.py`) |
| Button geometry | area≥2400, w 95–130, h 28–45, fill 0.65 | giống hệt (bộ 2000/80–140/20–50 là `TRAIN_BOTTOM_BUTTON_PATTERN` — nút lobby, không phải hero-select) |
| Recovery trong loop | popup tabs + blocker + re-click entry | không có |

Consumer của bản actions: Action type `click_hero_select_battle` được build
trong `actions/builder.py::build_start_battle_actions()`, dùng bởi ba nơi:
start_auto (Shift+1), spawn_exit_lvup (Shift+9), new_account. JSON sample
`tools/json_macro/hauntedroom_actions.sample.json` không dùng type này — nó
`click_template` thẳng banner template nên không chịu ảnh hưởng.

Consumer của bản train: `train_support/entry.py::start_train_battle` — hàm này
vừa chạy chuỗi nút vàng của lobby_train, vừa wait + click hero-select.

### Train-select đang xé làm ba, hai mảnh nằm sai package

| Phase | Thời điểm | Code hiện tại |
| --- | --- | --- |
| Hero-select screen: detect banner, click nút vàng | Sau lobby, trước trận (cả hai flow) | `actions/hero_select_battle.py` + bản copy trong `train_support/common.py` — **phạm vi refactor này** |
| Train card options (train_select): chọn 2/4 card, 5 round | Ngay sau hero_select, chỉ train | `train_support/hero_selection.py`, `automap_support/train_select.py`, `automap_support/vision/train.py` |
| Hero level-up picker: chọn option khi lên cấp | Giữa trận automap | `automap_support/hero_action.py`, `automap_support/vision/hero_levelup.py` |

Train-select là logic thuần train nhưng hai mảnh detector/policy đang nằm trong
`automap_support` (hệ quả của việc tái dùng template asset với level-up
picker), và lệch này bị pin trong allowlist của
`tests/test_hauntedroom_architecture.py`. Trạng thái đích: toàn bộ về
`train_support`. **Ngoài phạm vi đợt này — làm đợt riêng sau khi ranh giới
hero-select ổn định.**

## Kiến trúc đích

Quyết định đã chốt: hero_select là một phase business, nằm trong `flows/`,
không thuộc `actions`. Flow là tầng cao, action engine là tầng con; flow không
import action, và logic business không nhét vào action engine — nên phần dùng
chung phải sống ở `flows/hero_select/`.

```text
Automap:  lobby_map (blocker + entry + recovery) ──┐
                                                   ├──> flows/hero_select ──> battle/auto (map)
Train:    lobby_train (badge + bottom strip) ──────┘
                                                   └──> train_select (chỉ train) ──> auto_train
```

### `flows/hero_select/` — phase chung, thuần

- Hằng số anchor + detector + async loop chờ — click — settle. Expose detector
  + click primitive tách khỏi loop để wrapper actions có thể nhét recovery
  giữa các poll (wrapper không gọi nguyên loop).
- **Thuần**: không chứa clear blocker, không chứa `close_profile_popup_tabs`,
  không chứa re-click entry. Đó là buz của lobby_map; lobby_train không cần.
- Không nhận tham số mang ý nghĩa riêng của lobby nào.
- Threshold dùng bộ combined duy nhất (bảng dưới).

### `actions/hero_select_battle.py` — wrapper mỏng riêng cho lobby_map

- Giữ nguyên Action type `click_hero_select_battle` để ba consumer không đổi
  wiring (ràng buộc "hạn chế codechange").
- Loop giữ recovery của lobby_map (popup tabs, blocker paths, re-click entry)
  — vì nó là entry point duy nhất của lobby_map — nhưng detector và thao tác
  click delegate vào `flows/hero_select/`.
- `tests/test_hauntedroom_architecture.py` mở exception scoped cho đúng file
  này được import `hauntedroom.flows.hero_select`, cùng pattern với exception
  ngược chiều đã có ở `exit_flow.py`.

Hướng "sạch" hơn — bỏ hẳn Action type, ba consumer gọi flow trực tiếp — là
non-goal của đợt này vì phải đụng builder + wiring của spawn_exit_lvup và
new_account; cân nhắc làm đợt sau nếu cần.

### `train_support/entry.py` — tách hai phase

- `start_train_battle` tách thành: phần lobby_train (chuỗi nút vàng dưới đáy)
  và phần bàn giao gọi shared hero-select. Lobby_train kết thúc khi shared
  detector phát hiện hero-select; không có recovery blocker ở đây.

### Ranh giới lobby — định nghĩa bàn giao

Cả hai lobby kết thúc tại **cùng một điều kiện**: shared hero-select detector
phát hiện signal (header banner + nút vàng trong cùng frame). Từ điểm đó, mọi
thao tác (chờ ổn định, click nút vàng) thuộc hero_select phase; lobby không
click.

Lưu ý race: giữa lúc signal xuất hiện và lúc click, một blocker mới có thể pop
(với lobby_map). Không mất robustness hiện có vì wrapper vẫn chạy recovery
blocker của lobby_map ngay trước thao tác click trong cùng loop.

### Threshold combined (mức vừa phải, gộp hai bộ)

Chỉ phần detector là combined; timeout/poll/settle giữ nguyên theo từng caller
(không đồng nhất timing chỉ vì tên gọi).

| Tham số | actions | train | Chọn chung |
| --- | --- | --- | --- |
| Header region / threshold / scales | (210,10,430,90) / 0.80 / (1.0,) | giống | giữ nguyên |
| Button region | (230,650,410,719) | giống | giữ nguyên |
| Button geometry | area≥2400, w 95–130, h 28–45, fill 0.65 | giống | giữ nguyên |
| HSV yellow V min | 90 | 80 → đã đổi sang `vision/buttons` | **90** (palette chung) |

Drift V min đã được giải quyết bằng cách train dùng chung `find_colored_button`
+ palette vàng của `vision/buttons` (V min 90); fixture train vẫn detect đúng
nút battle ở cùng tọa độ. Các giá trị còn lại hai bản đã giống hệt — giữ
nguyên. Fixture test của cả hai flow phải chạy qua một bộ constant duy nhất.

## Đề xuất commit

### Commit 1: `refactor(hero-select): shared phase in flows, thin lobby_map wrapper`

- Tạo `flows/hero_select/`: constants (bộ combined), detector, async
  `wait_and_click_battle` (loop chờ signal → click → settle, TimeoutError kèm
  screenshot).
- `actions/hero_select_battle.py` delegate detector + click vào shared; giữ
  recovery lobby_map trong wrapper.
- `train_support/common.py`: xoá constants + `find_hero_select_battle_click`
  copy; `entry.py` gọi shared detector/click.
- Chuyển test detector/action (`tests/actions/test_hero_select_battle.py`,
  phần detector trong `tests/runner/test_train_flow.py`) sang kiểm tra shared
  implementation, giữ nguyên fixture.
- Cập nhật arch test: exception scoped `actions/hero_select_battle.py` →
  `hauntedroom.flows.hero_select`; dọn allowlist `train_support/common.py`
  theo import mới.

Commit này chỉ DRY phần nhận diện + click; chưa đổi ranh giới lobby.

### Commit 2: `refactor(lobby): both lobbies hand off at hero_select signal`

- Tách `start_train_battle` thành lobby_train (chuỗi nút vàng) + hero-select
  đã xong: `wait_and_click_hero_select_battle` trong `entry.py`. Việc còn lại
  là đổi thân hàm đó sang gọi shared hero-select khi nó tồn tại.
- Đảm bảo lobby_map kết thúc tại cùng signal (wrapper gọi shared sau
  recovery); không đổi wiring của ba consumer.
- Không đụng train_select, battle, cleanup.
- Duy trì wrapper cho caller cũ vẫn gọi entry + hero-select liền nhau.

Commit này tạo boundary rõ giữa phần khác nhau (lobby) và phần dùng chung
(hero_select).

### Commit 3: `test(flows): lock lobby and hero-select phase boundaries`

- Regression test thứ tự `lobby -> shared hero-select -> (train_select) ->
  battle` ở cả hai flow; xác nhận hai flow gọi cùng một shared implementation.
- Đổi tên `tests/hero_select/` thành `tests/hero_levelup/` để thư mục test
  không còn trùng tên với phase hero-select screen. Tùy chọn đổi
  `train_support/hero_selection.py` thành `train_support/card_selection.py`
  vì lý do tương tự.
- Bổ sung `flows/hero_select` vào dev reload list (`runner/reload.py`) nếu
  cần nhận module mới khi reload.
- Xoá constant/test duplicate sau khi không còn consumer.

## Nguyên tắc triển khai

- DRY là mục tiêu số một: một nguồn duy nhất cho nhận diện + click
  hero-select.
- Hạn chế codechange: giữ Action type, giữ wiring ba consumer, không đụng
  builder trừ khi bắt buộc.
- Buz lobby (blocker, popup tab, re-click entry) không được lọt vào shared
  hero-select.
- Shared hero-select không nhận tham số mang ý nghĩa riêng của lobby nào.
- Chỉ detector constants là combined; timing (timeout/poll/settle) giữ theo
  caller hiện tại.
- Không đụng train_select, battle, cleanup.
- Mỗi commit chạy được độc lập và giữ test suite xanh.

## Điều kiện hoàn thành

- Chỉ còn một nguồn logic nhận diện + click hero-select, với một bộ threshold
  combined.
- Automap và train đều đi qua cùng implementation sau khi lobby hoàn tất.
- Cả hai lobby kết thúc tại signal hero-select; shared phase thuần, không
  chứa recovery của lobby nào.
- Không có thay đổi hành vi ngoài lobby/hero-select (trừ detection bounds
  theo bảng combined).
- Toàn bộ test hiện có và regression test mới pass.
