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
  20002/20007/20008, 20012 cần 20005/20009/20011. Chuột: 30006 星穹舰主 (Hạm Chủ Tinh Không)
  cần 30002/30004/30003. Mèo: 40006 造物圣猫 (Thánh Miêu Tạo Vật) cần 40002/40004/40003.
  10013 và 20012 chưa có tên tiếng Anh, dict dùng key `id_10013` / `id_20012`.
- Skill skin chuột/mèo 7 màu (80060601000–05 环宙逐光, 80050601000–05 环宇猫瞳) và skin 05
  (8006050x 炽尾喷射, 8005050x 放纵狂宴) **chỉ có trong `SkillBaseLO` của GAT** (`trunk_66196`,
  kèm desc). SEA `sea_65553` và `sea_66328` có dòng `BuildSkinLO` (tên VN/EN) nhưng thiếu
  các skill này trong `SkillBaseLO` → không có tên/desc skill. Desc GAT (★1 → ★5):
  - Chuột: +1 số lượng xây; mỗi máy phát điện mỗi cấp +2%→4% ST toàn đội; mỗi 200 điện còn
    dư +2%→4% công và +4%→8% ST chí mạng toàn đội, tối đa 20%→40% / 40%→80%. Từ ★2 +1 giới
    hạn cấp, ★5 thêm +20% sản lượng cơ bản.
  - Mèo: +1 số lượng xây; mỗi mèo chiêu tài mỗi cấp +2%→4% ST toàn đội; mỗi 2500 ngân phiếu
    còn dư +2%→4% tốc đánh và chí mạng toàn đội, tối đa 20%→40%. Từ ★2 +1 giới hạn cấp, ★5
    thêm +20% sản lượng cơ bản.
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
- `playerInfos[].goldenSkinsCount`: tổng sao skin vàng **hero** (không phải skin building),
  xem mục dưới.

### `goldenSkinsCount`

- **Đếm gì:** tổng **số sao** của các skin vàng hero (`DermaLO` `color` 7, `heroCode` > 0)
  account đã sở hữu (trong 图鉴/BST). Server tính, client chỉ đọc. Bằng chứng:
  `SkillConstLO.SummonCreatureDamageAddStep.constDesc` bản gốc (config GAT 66196) ghi
  "总增伤 = 图鉴武将金皮总星数 * 这个常量 / 100". Bản dịch VN chỉ ghi "Số lượng Skin Vàng
  trong BST Tướng", thiếu chữ "sao" (星数).
  Kiểm chứng với pmain (playerId 51921435), `GetDermaListR` chụp 16/11: skin vàng hero
  5000203★2, 5000302★1, 5000902★1, 5001302★1, 5001303★1, tổng 6 sao, khớp `goldenSkinsCount`
  6 (chụp 11–13/11). Account này có đúng 1 skin vàng lên 2 sao và 1 skin vàng Summoner
  (20214★1). Vì vậy cách đếm "số skin vàng hero + Summoner" cũng ra 6, data chưa phân biệt
  được hai cách. Theo mô tả gốc thì chọn cách tổng sao. Skin 7 màu (`color` 8) có được tính
  không thì chưa kiểm.
- **Dùng ở đâu:** chỉ một chỗ, nhánh tạo `SummonCreatureLO` (pet) trong
  `BattleEngineDelegate`. Không có skill/đồ cổ/thần khí nào khác đọc giá trị này.

  ```js
  if (JSON.parse(ConstLO.get("SummonCreatureLevelUpBattleType")?.constValue).includes(this._battleType)) {
    hero.skills.push({ code: { 4: 1701000, 5: 1801000, 6: 1901000, 7: 2001000 }[cfg.color] });
    var K = playerInfo.goldenSkinsCount;                          // 【召唤兽】金皮数量记录
    var Y = SkillConstLO.get("SummonCreatureDamageAddStep").constValue || 1; // 150
    hero.attr.add(FinalHurtAdd /* 10153 */, (hero.attr.getValue(FinalHurtAdd) || 0) + K * Y);
  }
  ```

  Pet được thêm skill 打伤害玩法增伤 ("Lối chơi Tăng ST") theo màu pet và cộng
  `FinalHurtAdd` (最终增伤, attr percent) = `goldenSkinsCount` × 150. Đây không phải skill
  riêng scale theo số skin mà là chỉ số cộng thẳng. Code này giống hệt nhau ở bundle VN và
  GAT (`cda14`, `bc1d2`).
- **Gate theo vùng:**
  - **GAT** (live 18/11: ClientVer 66241, main `bc1d2`, config `trunk_66196`): `ConstLO`
    có `SummonCreatureLevelUpBattleType = [21,37,38,42,43]`, tức GuildNavalWar (U Đô),
    WorldBoss, GuildCoBoss, GuildNavalWarMatch và WorldBossMonthly (Ác Mộng). Ở các mode này
    bonus **có tác dụng**.
  - **SEA/VN** (`sea_65553`, 777 dòng `ConstLO`): **không có** key này. `JSON.parse` bản sửa
    của game trả `[]` cho `undefined`, nên điều kiện luôn sai và `goldenSkinsCount` không ảnh
    hưởng trận nào.

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
`buildings.<tên>.skins` của [support-dict.json](web/dict/support-dict.json). Code nằm trong
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
- Skill `90000300000` (击杀回怒, +25 nộ khi hero giết quái) trên giường không thuộc skin
  nào trong `BuildSkinLO`. Server thêm vào, chưa rõ nguồn.
- Thứ tự skill do server sắp: cửa xếp vàng trước đỏ, giường xếp đỏ trước vàng. Có thể
  là thứ tự slot của account.
- Cách `attr` của skin cộng vào `builds[].attr`.
- Chưa có account có skin 7 màu để xác nhận.
