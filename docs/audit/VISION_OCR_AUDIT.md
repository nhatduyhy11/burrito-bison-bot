# Vision/OCR audit

Ngày rà soát: 2026-08-27

## Phạm vi

Haunted Room không dùng OCR engine. Các dependency được audit ở đây là template
matching trên crop có chứa chữ hoặc tên hiển thị, nên có thể fail khi đổi ngôn
ngữ, font hoặc glyph dù layout game không đổi.

File này chỉ liệt kê template có issue và vẫn còn được code hoặc JSON macro tham
chiếu. Template không còn được sử dụng và detector đã language-agnostic không
thuộc phạm vi audit.

## Template flow/UI còn phụ thuộc chữ

| Flow | Template/chữ đang bắt | Reference | Ảnh hưởng khi đổi ngôn ngữ | Mức độ |
|---|---|---|---|---|
| HOME entry / spawn-exit / auto-map — blocker | `tools/rooms/blocker/overlay_close.png`: "Nhấn khu vực trống để đóng" | `runner/commands.py`, `vision/template_config.py`, JSON macro mẫu | Không đóng được overlay; action hoặc map-completion cleanup có thể timeout | Cao |
| HOME entry / spawn-exit / auto-map — blocker | `tools/rooms/blocker/overlay_close_2.png`: cùng nội dung trên | `runner/commands.py`, `vision/template_config.py`, JSON macro mẫu | Không đóng được overlay; action hoặc map-completion cleanup có thể timeout | Cao |
| Train (`Shift+T`) — bắt đầu | `tools/rooms/start_battle.png`: "Khiêu chiến" | `flows/train.py`, JSON macro mẫu | Không vào được train battle | Rất cao |
| Auto-map / start-auto / train handoff — kết thúc map | `tools/rooms/automap/map_end.png`: "Quay lại" | `vision/template_config.py` | Không nhận ra map đã kết thúc; auto-map tiếp tục polling | Rất cao |
| Auto-map / start-auto / train handoff — reward fallback | `tools/rooms/automap/map_win/reward_list_title.png`: phần chữ "mừng" | `vision/template_config.py` | Mất compatibility fallback khi primary panel detector không xác nhận được popup | Trung bình |
| Auto-map / start-auto / train handoff — daily first win | `tools/rooms/automap/map_win/daily_first_win.png`: "Không nhắc lại hôm nay" | `vision/template_config.py` | Không vào isolated flow để tick/confirm prompt; cleanup reward có thể không hoàn tất | Cao |

Các path trong `vision/template_config.py` được load qua
`tools/hauntedroom/flows/automap_support/templates.py`. Phần xử lý tương ứng nằm
trong `map/lifecycle.py`, `map/reward.py` và `map/first_win.py`.

## Template hero selection còn phụ thuộc tên hiển thị

Các template dưới đây nằm trong `tools/rooms/automap/hero_levelup/` và match tên
hero hiển thị. Auto-map dùng ở scale `1.0`; train tái sử dụng ở scale `0.8`.
Chúng có thể fail khi tên hero, ngôn ngữ hoặc font thay đổi:

- `00_mage_king.png`
- `01_dark_lubu.png`
- `02_hanuman.png`
- `03_soul_spear.png`
- `04_thunder_trident.png`
- `09_pinocchio.png`
- `10_prayer_box.png`
- `11_death.png`
- `11_underworld.png`
- `12_soul_reaper.png`
- `99_mage_king.png`

## Template chữ còn được JSON macro cũ tham chiếu

Fixed Python spawn/exit không dùng hai template này, nhưng
`tools/json_macro/hauntedroom_actions.sample.json` vẫn tham chiếu nên chúng vẫn
là issue hợp lệ của audit:

| Template | Chữ đang bắt | Ảnh hưởng khi đổi ngôn ngữ |
|---|---|---|
| `tools/rooms/exit_confirm.png` | "Thoát" | JSON macro không xác nhận được thao tác thoát |
| `tools/rooms/exit_back.png` | "Quay" | JSON macro không nhận ra nút quay về HOME |
