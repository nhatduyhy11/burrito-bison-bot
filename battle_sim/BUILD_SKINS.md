# Skin building (`BuildSkin`)

Tên dùng trong code client: hệ thống `BuildSkin` (`BuildSkinModule`, `BuildSkinLO`,
`BuildSkinProxy`), loại building lấy từ `EBuildType_Build_Enum`.

| `buildType` | Tên trong code | Tên game (CN) | Người chơi gọi | Vai trò |
|---|---|---|---|---|
| 1 | `Door` | 大门 | cửa | Chặn quái; skin thêm skill phòng thủ |
| 2 | `Bed` | 床 | giường | Nơi settle đầu trận; sinh tiền (钞票) |
| 3 | `WoodenFish` | 发电机 | chuột | Sinh điện (điện dùng cho spell, 60 điện mỗi lần cast) |
| 4 | `GoldenToad` | 招财猫 | mèo | Sinh tiền |

Tên enum `WoodenFish` và `GoldenToad` không khớp với hình ảnh trong game. Phải dựa vào
skill trong `BuildSkinLO` (发电机 / 招财猫) mới biết type 3 là chuột, type 4 là mèo.

## Config

`BuildSkinLO` có mã `skinId * 100 + star` (ví dụ `1000105` là skin 10001 ở 5 sao;
`TDServer.getSkinCfgByTypeAndLevel`). Các trường chính:

- `color`: 4 = skin mặc định (`isInit` 1), 6 = đỏ, 7 = vàng, 8 = 7 màu.
- `skillType`: loại slot, 1 = đỏ, 2 = vàng, 3 = slot riêng. Skin 7 màu dùng
  `skillType` 2. Skin `skillType` 3 hiện chỉ có bộ 龙血骑士 (10007, 20006).
- `skill`: mảng skill ở số sao đó (`SkillBaseLO`).
- `requirement`: chỉ có ở skin 7 màu, liệt kê 3 skin yêu cầu ở cùng số sao. Cửa có 2 skin
  7 màu: 10011 cần 10005/10008/10009, 10013 cần 10001/10009/10012. Giường: 20010 cần
  20002/20007/20008, 20012 cần 20005/20009/20011. Chuột và mèo chưa có skin 7 màu. 10013 và
  20012 chưa có tên tiếng Anh, dict dùng key `id_10013` / `id_20012`.
- `attr` / `addAttr`: chỉ số của skin.

## Quy tắc slot (`BuildSkinModule`, `BuildSkinEquipSkillPanel`)

- Mỗi building có các slot theo `skillType`: **1 slot đỏ, 2 slot vàng, 1 slot loại 3**
  (`_equipSkillTypeList = [1, 2, 3]`, `_skillPosList = [1, 2, 1]`). Slot vàng mở khi có
  skin vàng hoặc qua `BuildSKinEquipGoldSkill`. Slot loại 3 chỉ mở khi có skin loại 3.
- Skin 7 màu gắn vào slot vàng. Khi đó `checkEquipSkillSkinIsLock` **khoá 3 skin yêu cầu
  của nó**, không gắn được vào slot nào. Khác với hero: hero có slot 7 màu riêng nên vẫn
  giữ đủ 3 skill cũ.
- Skin đang mặc (`skinId`, `skinLevel`) chỉ quyết định model, giống hero. Ngoài ra có
  `huanHuaSkinId` (幻化, đổi ngoại hình).

## Dữ liệu trong `StartGameP`

- `playerInfos[].builds[]` với `type` 1–4: `skinId`, `skinLevel`, `skills` (skill của
  các skin trong slot, do server ghép sẵn) và `attr`. `TDBuildEntity` lấy thẳng `skills`
  từ đây.
- `playerInfos[].skinInfos`: mọi skin building đã sở hữu (`skinId`, `skinLevel`).
  `TDPlayerEntity` dùng để liệt kê skin theo `buildType`.
- `playerInfos[].goldenSkinsCount`: số skin vàng. `BattleEngineDelegate` dùng số này
  nhân với `SummonCreatureDamageAddStep` để tăng sát thương pet.

Account pmain (capture `6af3d7da…` và `6af3dacb…`):

| Building | Đang mặc | Skill trong trận (skin ★) | Skin sở hữu |
|---|---|---|---|
| Cửa | 10010 | 10009 (vàng), 10010 (vàng), 10001★5 (đỏ) | 10001★5, 10002, 10004, 10005, 10006★4, 10009, 10010 |
| Giường | 20009 | 20001★5 (đỏ), 20007 (vàng), 20009 (vàng), `90000300000` | 20001★5, 20002, 20004, 20005, 20007, 20008, 20009 |
| Chuột | 30003★4 | 30002 (vàng), 30003★4 (đỏ) | 30001★2, 30002, 30003★4 |
| Mèo | 40003 | 40004 (vàng), 40002 (vàng), 40003 (đỏ) | 40001, 40002, 40003, 40004 |

Cả 4 building đều theo đúng 1 đỏ + tối đa 2 vàng. Skin mặc định (10000, 20000, 30000,
40000) không có skill.

## Trong profile playtest

`buildings` trong profile ánh xạ tên building tới skin chọn. Tên skin lấy trong
`buildings.<tên>.skins` của [profile-dict.json](web/profile-dict.json). Code nằm trong
[build-skin-profile.js](web/battle/build-skin-profile.js).

```json
"buildings": {
  "door": {
    "skin": "grand_circus",
    "star": 1,
    "ownedSkins": { "ironfist_door": 5, "aureate_domain": 1 },
    "slots": ["aureate_domain", "grand_circus", "ironfist_door"]
  },
  "bed": { "skin": "fortune_bed", "star": 2 }
}
```

- `skin` và `star`: skin đang mặc. Bỏ `skin` thì dùng skin mặc định. Skin mặc định luôn
  được tính là đã sở hữu.
- `ownedSkins`: các skin khác đã mở kèm số sao. Skin 7 màu tự nâng 3 skin yêu cầu lên số
  sao của nó.
- `slots`: skin gắn slot, tối đa 1 đỏ, 2 vàng, 1 loại 3. Skill nối theo đúng thứ tự trong
  mảng. Gắn 7 màu thì 3 skin yêu cầu của nó không được nằm trong slot. Bỏ `slots` thì tự
  chọn: ưu tiên 7 màu, sau đó theo thứ tự config, xếp đỏ → vàng → loại 3.
- Building không có trong `buildings` giữ nguyên từ capture. `skinInfos` chỉ thay phần
  của building được chọn. `builds[].attr` và skill không thuộc skin nào (như
  `90000300000`) giữ từ capture.

Kiểm tra: dựng lại profile từ 5 capture (cả pmain `6af3d7da…` và `6af3dacb…`) cho ra
`builds[]` type 1–4, `skinInfos` và `summonCreatures` khớp tuyệt đối khi dùng `slots` theo
thứ tự của account.

Còn mở:
- `goldenSkinsCount` của pmain là 6, không khớp số skin vàng building đã sở hữu (8) hay số
  skin vàng của hero trong đội hình (4). Có thể là tổng skin vàng hero của cả account.
  Profile đặt bằng tay qua `goldenSkinsCount`; bỏ trường này thì giữ giá trị capture.
- Skill `90000300000` (击杀回怒, +25 nộ khi hero giết quái) trên giường không thuộc skin
  nào trong `BuildSkinLO`. Server thêm vào, chưa rõ nguồn.
- Thứ tự skill do server sắp: cửa xếp vàng trước đỏ, giường xếp đỏ trước vàng. Có thể
  là thứ tự slot của account.
- Cách `attr` của skin cộng vào `builds[].attr`.
- Chưa có account có skin 7 màu để xác nhận.
