# Skin trong profile playtest

Level của hero và sao của skin là hai thông số riêng. Ví dụ, Venom ngoài capture dùng
chỉ số hero level 1. Có thể mặc Colorful 5 sao mà level của Venom vẫn là 1.

Trong `heroes`, dùng tên hero để giữ skin từ capture hoặc dùng object để chọn skin.
Tên skin tra trong `skins` của hero tương ứng trong [profile-dict.json](web/profile-dict.json).

```json
{
  "name": "venom",
  "skin": "colorful",
  "star": 3,
  "ownedSkins": { "pf1": 1, "pf2": 4 },
  "slots": ["pf1", "pf2", "pf3", "colorful"]
}
```

- `skin`: skin đang mặc. Chỉ đổi model, không quyết định skill. Bỏ trường này thì hero
  mặc model gốc (`derma` 0).
- `star`: sao của skin đang mặc, mặc định 1.
- `ownedSkins`: các skin khác đã mở và số sao tương ứng, có thể bỏ.
- `slots`: các skin gắn vào slot skill, gồm tối đa 3 skin thường và 1 skin 7 màu. Bỏ
  trường này thì mọi skin đã mở đều vào slot: skin thường theo thứ tự trong config, rồi
  đến skin 7 màu.

Skin 7 màu yêu cầu cả 3 skin thường ở số sao ít nhất bằng sao của nó. Simulator tự nâng
các skin yêu cầu lên mức đó. Trong ví dụ trên, Colorful 3 sao, `pf1` được nâng từ 1 lên
3, `pf2` giữ 4 và `pf3` được bổ sung ở 3 sao. Sao vượt quá rank có trong config sẽ báo
lỗi. Dòng `profile skin ranks` trong log sandbox ghi từng skin, rank cuối và các slot.

## Rule của game

Đã đối chiếu với capture pmain `6af3d7da1d68f99b52631ef9` (Venom, Dark Lubu, Frosthealer):

- Mỗi skin trong slot thêm skill ở mã của số sao hiện tại. Các skill này nối sau skill
  gốc theo thứ tự slot, với `index` là vị trí 1-based trong list. Dark Lubu mặc skin đỏ
  vẫn có đủ skill của 3 skin.
- Hero nhận `selfAttr` của mọi skin đã mở. `attr` của skin (ví dụ 1015) không nằm trong
  chỉ số hero.
- Chọn 7 màu thì hero có 4 skill skin. `dermaIndex` của các skill này bật nhánh `PF2/PF3/PF4`
  trong perform BT, đây là cách skill 7 màu đổi hiệu ứng của skill cũ.

Chưa xác nhận vì chưa có capture của account có 7 màu: skill 7 màu đứng sau 3 skill
thường. Phần này nằm trong [skin-profile.js](web/battle/skin-profile.js).
