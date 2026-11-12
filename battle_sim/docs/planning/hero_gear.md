# Đồ đi kèm hero: Dị Năng, Thánh Khí, Thần Khí

Phân tích từ capture pmain 2026-11-12 (`.tmp/battle_research/startgamep-6af56b662f05ea3f5834af6c.json`,
Stage 314, 5 hero), config `sea_65380`, bundle 1377a. Index: [research.md](research.md).
Equip (`PutOnEquip`, 6 ô) đi theo Summoner, ưu tiên thấp nhất nên doc này chưa bàn tới.

## Map tên ↔ dữ liệu

| Tên VN | Tên gốc | Field trong `heros[]` | Bảng config |
|---|---|---|---|
| Dị Năng | 异能 (神通) | `avatarCodes[{pointCode, level}]`, `avatarChapterCodes`, `avatarLevel` | `AvatarLO`, `AvatarUpGradeLO` |
| Thánh Khí | 圣器 | `relic` (chỉ có code) | `RelicLO` (type 2), `RelicStarLO`, `RelicLevelUpLO` |
| Thần Khí | 神器 / 神兵 | `artifact {code, uuid, battleEntryInfos?}` | `ArtifactLO`, `ArtifactEntryLO` |

`relic` trong code là Thánh Khí. "Di Vật" (遗物) là `RelicLO` type 1, không gắn lên hero.

## Từng loại đi vào trận như thế nào

**Dị Năng: server tính sẵn, client chỉ nhận kết quả.**
- Mỗi hero có cây node (`AvatarLO`: chapter/line/row; `_limit` = điều kiện mở). Mỗi level của một node
  (`AvatarUpGradeLO`) cộng `attr`.
- Node "KN Siêu Nhiên" thay skill: `_skillcode` thay `_oldSkillCode` (vd Hắc Lữ Bố
  10130101000 → 10130601000 → 10130602000…). `_skillUnlock` đòi đủ số đột phá.
- Kết quả đã nằm sẵn trong `hero.attr` và `hero.skills`. Battle code không đọc `avatarCodes`.

**Thánh Khí: server tính sẵn, client chỉ nhận kết quả.**
- `RelicLO` có `_base`/`_attrUp` theo level (tối đa 40); `RelicStarLO._attrUp` theo sao (0–10).
- Skill theo sao nằm trong `hero.skills` với `index 0`: `5206XXYY` + bậc (1–6 với sao 0–10, mỗi 2 sao
  lên 1 bậc). Thánh Khí màu vàng (quality 7) có thêm skill cố định `5207XXYY000`.
- `StartGameP` không gửi level/sao, chỉ gửi code; bậc của skill cho biết sao gần đúng.
- Battle code không đọc `hero.relic`.

**Thần Khí: client đọc lúc vào trận, đây là phần simulator phải tự mô phỏng.**
- `ArtifactLO` gắn với hero qua `_hero`. Mỗi hero có 5 stage, mỗi stage ứng với một code (vd
  10806003 = stage 3). Cột `_skillList` là skill của Thần Khí, vd stage 3 có 3 skill
  `10130701..703000`.
- **Các skill này không nằm trong `hero.skills`.** `TDBuildVO` tự thêm chúng vào
  `_atrifactSkillCodeList` từ `ArtifactLO`.
- `battleEntryInfos[{code, value}]` là các dòng chỉ số chiến đấu đã roll:
  - `ArtifactEntryLO.skillCode` cùng `_skillTemplateParams` (vd `Buff_Modifiers_Factor`) lấy
    `value` làm tham số.
  - Nơi xử lý: `ArtifactSkillHub`, được tạo trong `TDPlayerEntity`/`BattleUnitData` từ entry của
    mọi hero.
  - Riêng entry có `value == 0` thì được thêm thẳng vào skills của unit.
- Hero support: skill Thần Khí/entry mở khóa building skill (`subType2BuildSkillCfg`, cột `unlock`).
- Màn hình Thần Khí gọi `GetPlayerArtifact {playerId, uuid}`. Kết quả trả về có thêm
  `entryInfos` (mọi dòng), `lockEntryCodes`, `binding` và `exp`, nhưng `StartGameP` chỉ mang
  `battleEntryInfos`.

## Dị Năng: node skill (đã kiểm chứng 2026-11-12)

- Mỗi hero có Dị Năng (16 hero) đều có đúng 5 node skill (chapter 1–5). Mỗi node chỉ có level 1,
  tức là bật/tắt. Quy tắc nằm ở `AvatarUpGradeLO`: `_oldSkillCode → _skillcode` (`0` = thêm skill
  mới). Node 5 có thể thay chính skill node 3 vừa sinh ra (LB: 603 → 605).
- Server áp đúng quy tắc config này: cả 152 hero capture không lệch chỗ nào (11 node đang bật, 99
  node chưa bật).
- Engine trận nạp skill chỉ theo `code` (`BattleUnitData`: `SkillBaseLO` + `exclusionGroup` /
  `priority`). Nó không đọc `index`, `avatarCodes` hay `breakThrough`. `_skillUnlock` chỉ dùng cho UI.
- Headless: battle `6af2ab8a` (L51) với LB bật 0→5 node đều chạy hết, thắng, không lỗi. Output của
  LB: 23.1M → 35.0M (node 1) → 42.3M (node 2, đánh thường 3 tia ±10°) → ~42–43M.
- Đã có trong form setup (2026-11-12): ô "Dị Năng (node skill)" trong card hero khi tick "Tùy chỉnh",
  profile `avatar: N`. Chỉ có hero đỏ (16 hero, đúng bằng số hero có node).
- Chưa kiểm bằng hình trong trận. Cần xem: LB node 2 (3 tia) và Loli node 4
  (`10050201000 → 10050604000`), dùng skin mặc định.

## Ý nghĩa cho simulator

- Hero có trong capture thì giữ nguyên `hero` là đã đúng cả 3 loại (replay khớp hiện tại xác nhận).
- Hero mượn chỉ số (`web/battle/hero/build.js`) hiện bỏ relic/artifact. Feature có thể làm:
  1. **Thần Khí**: chọn stage (`ArtifactLO` theo `_hero`) và các dòng `battleEntryInfos` (code từ
     `_entryPool`, value trong `[_minValue, _maxValue]`). Đây là phần client tự áp dụng nên làm
     đúng theo game được.
  2. **Thánh Khí**: chọn Thánh Khí và sao, rồi tự thêm skill `index 0` theo `RelicStarLO`.
     Nếu muốn có cả attr thì phải tự cộng `_base`/`_attrUp`/`_starAttrUp`.
  3. **Dị Năng**: chọn tầng mở khóa, sau đó thay skill theo `AvatarUpGradeLO` và cộng `_attr`.
- Attr của Thánh Khí và Dị Năng đã được trộn vào `hero.attr`. Muốn tách hay chỉnh thì phải tự tính
  lại từ bảng, nhưng chưa kiểm chứng công thức của server (tỷ lệ, key attr 1xxxx so với 2010001…).

## Còn mở

- Skill `6000XX00100` ở `index 0` (vd "Tăng ST Bạo", "Choáng Tổn Thương") chưa rõ nguồn. Có thể từ
  Thần Khí stage cao, hoặc từ hệ khác.
- Skill `8004…` ở `index 5–9` là skill skin (đã xử lý trong `hero/skin.js`).
- Công thức server cộng attr của relic/avatar: cần so `hero.attr` giữa 2 capture khác nhau đúng
  một yếu tố.
