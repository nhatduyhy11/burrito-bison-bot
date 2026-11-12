# Skin trong profile playtest

Level của hero và sao của skin là hai thông số riêng. Ví dụ, Venom ngoài capture dùng
chỉ số hero level 1. Có thể mặc Colorful 5 sao mà level của Venom vẫn là 1.

Trong `heroes`, dùng tên hero để giữ skin từ capture hoặc dùng object để chọn skin.
Tên skin tra trong `skins` của hero tương ứng trong [profile-dict.json](web/dict/profile-dict.json)
(mỗi skin có `code`, `name`, `color`, `maxStar`, và `requires` với skin 7 màu).

```json
{
  "name": "spiker",
  "skin": "sanguine_landing",
  "star": 3,
  "ownedSkins": { "beach_party": 1, "undead_king": 4 },
  "slots": ["beach_party", "undead_king", "machine_rampage", "sanguine_landing"]
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
các skin yêu cầu lên mức đó. Trong ví dụ trên, Sanguine Landing (7 màu) 3 sao,
`beach_party` được nâng từ 1 lên 3, `undead_king` giữ 4 và `machine_rampage` được bổ
sung ở 3 sao. Sao vượt quá rank có trong config sẽ báo
lỗi. Dòng `profile skin ranks` trong log sandbox ghi từng skin, rank cuối và các slot.

## Rule của game

Nguồn: `HeroDermaModule` trong bundle, đối chiếu với capture pmain `6af3d7da1d68f99b52631ef9`
(Venom, Dark Lubu, Frosthealer; `.tmp/battle_research/events-skin3-20261111.jsonl`):

- Mỗi hero có 3 skin thường: 1 đỏ (color 6) và 2 vàng (color 7). Skin 7 màu (color 8) yêu
  cầu cả 3 skin thường ở số sao ≥ sao của 7 màu.
- Skill skin đi theo **slot**, không theo skin đang mặc. Mỗi hero (theo `subType`) có 3 slot
  thường (`HeroDermaSkill.skills`) và 1 slot 7 màu riêng (`colorSkills`). `derma` chỉ là
  model đang mặc.
- `StartGameP` gắn skill của mọi skin trong slot, mỗi skill ở mã của số sao hiện tại. Các
  skill này nối sau skill gốc theo thứ tự slot, với `index` là vị trí 1-based trong list.
  Ví dụ Dark Lubu mặc 5001301 (đỏ) vẫn có cả 3 skill 8004131x/8004132x/8004130x.
- Hero nhận `selfAttr` của mọi skin đã mở. `attr` của skin (ví dụ 1015) không nằm trong
  chỉ số hero.
- `dermaIndex` của skill skin (2 = vàng 1, 3 = vàng 2, 4 = 7 màu) đi vào
  `reserved.dermaIndexsCond`. Perform BT kiểm tra bằng điều kiện `PF2/PF3/PF4`
  (`ToggleConditionBtNodeParser`): đây là cách skill 7 màu đổi hiệu ứng của skill cũ. Không
  skill skin nào dùng `exclusionGroup`, nên phần logic không bị thay thế.

Chưa xác nhận vì chưa có capture của account có 7 màu: skill 7 màu đứng sau 3 skill
thường. Phần này nằm trong [skin-profile.js](web/battle/skin-profile.js).
