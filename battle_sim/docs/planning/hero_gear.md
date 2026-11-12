# Đồ đi kèm hero: Dị Năng, Thánh Khí, Thần Khí

Phân tích từ capture pmain 2026-11-12 (`.tmp/battle_research/startgamep-6af56b662f05ea3f5834af6c.json`,
Stage 314, 5 hero) và các capture cũ của cùng account (`6af5394f`, `6af53985`, `6af3d7da`,
`6af3dacb`), config `sea_65380`, bundle 1377a. Index: [research.md](research.md).
Equip (`PutOnEquip`, 6 ô) đi theo Summoner, ưu tiên thấp nhất nên doc này chưa bàn tới.

## Thuật ngữ

| Tên VN | Tên gốc | Là gì | Field trong `heros[]` | Bảng config |
|---|---|---|---|---|
| Dị Năng | 异能 (神通) | cây node riêng của hero đỏ | `avatarCodes[{pointCode, level}]`, `avatarChapterCodes`, `avatarLevel` | `AvatarLO`, `AvatarUpGradeLO` |
| **Thánh Khí** | 圣器 | món đồ đeo vào ô Thánh Khí của hero, đổi qua lại giữa các hero được (vd Cuộn Cthulhu, Thánh Giá Cứu Rỗi) | `relic` (chỉ có code) | `RelicLO` (type 2), `RelicStarLO`, `RelicQualityUpLO` |
| Thần Khí | 神器 / 神兵 | vũ khí riêng của **một** hero, gắn cố định qua `ArtifactLO._hero` (vd Giáo Chiến Phong Lôi) | `artifact {code, uuid, battleEntryInfos?}` | `ArtifactLO`, `ArtifactEntryLO` |

Dễ nhầm:
- Trong code, `relic` là **Thánh Khí** và `artifact` là **Thần Khí**.
- Gói tiếng Anh lại gọi Thánh Khí là "Artifact" (vd "Artifact Shard" = Mảnh Thánh Khí, "Artifact
  Skill" = KN Thánh Khí). Vì vậy khi gặp "Artifact" trong text EN thì phải xem code/bảng mới biết
  là loại nào.
- "Di Vật" (遗物) là `RelicLO` type 1 (`8101xxxx`, nguyên liệu kinh nghiệm), không gắn lên hero.

## Dị Năng: xong phần skill

- Mỗi hero đỏ (16 hero) có đúng 5 node skill (chapter 1–5). Mỗi node bật/tắt, đổi
  `_oldSkillCode → _skillcode` theo `AvatarUpGradeLO`. Server áp đúng quy tắc này (152 hero capture,
  không lệch chỗ nào). Engine trận chỉ nạp skill theo `code`.
- Simulator đã có: profile `avatar: N`, ô "Dị Năng (node skill)" trong form setup (commit `3101ef9`).
- Node chỉ số không mô phỏng, vì attr do server gộp sẵn vào `hero.attr`.
- Còn mở: chưa kiểm bằng hình trong trận LB node 2 (đánh thường 3 tia ±10°) và Loli node 4
  (`10050201000 → 10050604000`), dùng skin mặc định.

## Thánh Khí (đã kiểm chứng 2026-11-12)

Catalog: [web/dict/relic-dict.json](../../web/dict/relic-dict.json), sinh bằng
`gen_profile_dict.js`.

### Phân loại

- `RelicLO` type 2 có 37 Thánh Khí. Code là `82QQLL01`, trong đó `QQ` là phẩm và `LL` là dòng.
- Phẩm 1–5 (đến cam, 16 món) chỉ có chỉ số: không có sao, không có skill, nên dict bỏ qua.
- Dict không chứa chỉ số (`_base`, `_attrUp`, `_starAttrUp`, level), vì client không tính chỉ số
  Thánh Khí (xem mục Chỉ số bên dưới). Cần thì tra thẳng `RelicLO`/`RelicStarLO`.
- Phẩm 6–8 gồm 7 dòng, mỗi dòng có 3 mức thanh tẩy (`lines` trong dict):

| Dòng | Đỏ (06) | Vàng (07) | 7 màu (08) | Skill theo sao |
|---|---|---|---|---|
| 1 | Lửa Trừ Tà | Lửa Tịnh Thế | Quy Luật Thiêu Rụi | Đòn Phá Giáp |
| 2 | Thánh Giá Trắng | **Thánh Giá Cứu Rỗi** | Cổng Diệt Vong | Xuyên Thấu Thánh Quang |
| 3 | Vương Miện Gai | Vương Miện Thần | Vương Miện Kế Thừa | Thiên Thần Song Sinh |
| 4 | Chén Thánh Huyết | Chén Thánh Anh Linh | Hạt Giống Sự Sống | Liên Hoàn Đả Kích |
| 5 | Giáo Longinus | Giáo Định Đoạt | Nút Thắt Nhân Quả | Chém Quỷ Như Bùn |
| 6 | Lư Hương Vàng | Lò Thánh Dũ | Lò Luyện Ước Nguyện | Hương Thơm Tỉnh Thần |
| 7 | **Cuộn Cthulhu** | Tiếng Vọng Hư Không | Lời Răn Nghịch Nhãn | Lời Thì Thầm Của Cổ Thần |

### Skill của Thánh Khí

Mỗi Thánh Khí phẩm 6 trở lên có skill riêng, nằm trong `hero.skills` với `index 0`.
- **Skill theo sao:** `5206LL…`, có 6 bậc ứng với sao 0–1, 2–3, 4–5, 6–7, 8–9, 10. Dòng 1–4
  đánh số `5206LL01N00` (vd Thánh Giá: `52060201100…600`). Dòng 5–7 đánh số `5206LL0N000`
  (vd Cthulhu: `52060701000…6000`). Thanh tẩy giữ nguyên skill này.
- **Skill cố định của mức thanh tẩy:** vàng có `5207LL01000`, 7 màu có `5208LL01000`.
  Skill 7 màu thay cho skill vàng (không cộng dồn), là bản mạnh hơn. Vd dòng 2: vàng bỏ qua 90%
  Thủ Phép; 7 màu bỏ qua 95% Thủ Phép và ST Phép +30%.
- Danh sách skill lấy từ `RelicStarLO._skill` theo `(code, star)`. Engine trận nạp skill
  theo `code`, giống Dị Năng.

### Thanh tẩy (洗炼, `RelicQualityUpLO`)

- Có 2 lần thanh tẩy: đỏ → vàng, rồi vàng → 7 màu (UI gọi lần 2 là 炫彩洗礼). Mỗi lần tốn 1
  Nước Thần (`30000065`), sao được giữ (`starCode` `206LLSS → 207LLSS → 208LLSS`).
- Lần 2 chỉ mở khi account có ít nhất 5 Thánh Khí vàng (`relicAgainImproveColorRequite`).
- Thể hiện trong dữ liệu:
  - `hero.relic` đổi sang code khác (`8206LL01 → 8207LL01 → 8208LL01`).
  - `hero.skills` có thêm skill cố định của mức đó.
  - Chỉ số mỗi level và mỗi sao tăng ×2 (vàng) / ×3 (7 màu) so với đỏ (`_attrUp`,
    `_starAttrUp`). `_base` thì giữ nguyên.
  - Level tối đa vẫn là 40; từ vàng trở lên có thể nới thêm, trần là 50 (`relicImproveColorMaxLevel`).
- Không có field "đã thanh tẩy" riêng; mức thanh tẩy suy ra từ phẩm của `hero.relic`.

### Kiểm với account (51921435), 5 capture đều giống nhau

| Hero | `relic` | Skill Thánh Khí trong `hero.skills` | Khớp mô tả |
|---|---|---|---|
| Alice | 82060701 Cuộn Cthulhu (đỏ) | `52060701000` (bậc 1) | 0 sao, chưa thanh tẩy |
| Hắc Lữ Bố | 82070201 Thánh Giá Cứu Rỗi (vàng) | `52060201400` (bậc 4) + `52070201000` | 6 sao, thanh tẩy 1 lần |

### Chỉ số: server gộp sẵn, client không tự tính

- `StartGameP` chỉ gửi code `relic`, không gửi level/sao. Không module trận nào (`TD*`,
  `BattleUnitData`…) đọc `relic`. `BattleHUD.popRelic` là hàm rỗng và không có chỗ nào gọi.
- Thánh Khí cho các key %: `10001` Công%, `10002` HP%, `10012`/`10013` Thủ%, `2010001` Công
  Phép%. **`hero.attr` không có key nào trong số này**, tức là server đã quy đổi chúng vào chỉ số
  cuối (`1` Công, `2` HP…). Các key như `10112` Bạo, `10114` ST Bạo, `10130` Tăng ST trùng với
  key của `hero.attr` và đã được cộng sẵn.
- Kết luận: với simulator, **level Thánh Khí không có ý nghĩa** vì nó chỉ đổi chỉ số, và chỉ số đến
  qua `hero.attr` do server tính. Phần ảnh hưởng tới trận mà simulator tự làm được là:
  - sao → bậc skill theo sao;
  - mức thanh tẩy → skill cố định.
- Lưu ý khi đổi Thánh Khí cho hero lấy từ capture: `hero.attr` vẫn chứa chỉ số của Thánh Khí cũ.
  Muốn đúng chỉ số thì phải tự trừ/cộng theo bảng, nhưng chưa rõ công thức server dùng (tỷ lệ %,
  `_base + _attrUp × (lv−1)`?).

## Thần Khí (chưa làm)

- `ArtifactLO` gắn với hero qua `_hero`. Mỗi hero có 5 stage, mỗi stage ứng với một code (vd
  10806003 = stage 3). Cột `_skillList` là skill của Thần Khí, vd stage 3 có 3 skill
  `10130701..703000`.
- **Các skill này không nằm trong `hero.skills`.** `TDBuildVO` tự thêm chúng vào
  `_atrifactSkillCodeList` từ `ArtifactLO`. Đây là phần client tự áp dụng, nên simulator phải tự
  mô phỏng.
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

## Ý nghĩa cho simulator

- Hero có trong capture thì giữ nguyên `hero` là đã đúng cả 3 loại (replay khớp hiện tại xác nhận).
- Hero mượn chỉ số (`web/battle/hero/build.js`) hiện bỏ relic/artifact. Feature có thể làm:
  1. **Thánh Khí**: chọn dòng, mức thanh tẩy và sao từ `relic-dict.json`, rồi thay các skill
     `5206…`/`5207…`/`5208…` ở `index 0` và đặt `hero.relic`. Không cần level. Chỉ số giữ như
     capture (xem lưu ý ở trên).
  2. **Thần Khí**: chọn stage (`ArtifactLO` theo `_hero`) và các dòng `battleEntryInfos` (code từ
     `_entryPool`, value trong `[_minValue, _maxValue]`).

## Còn mở

- Skill `6000XX00100` ở `index 0` (vd "Choáng Tổn Thương" của Alice, "Tăng ST Bạo" của LB) chưa rõ
  nguồn. Không phải Thánh Khí (không có trong `RelicStarLO`). Có thể từ Thần Khí stage cao, hoặc từ
  hệ khác.
- Skill `8004…` ở `index 5–9` là skill skin (đã xử lý trong `hero/skin.js`).
- Công thức server cộng attr của Thánh Khí/Dị Năng: cần so `hero.attr` giữa 2 capture khác nhau
  đúng một yếu tố (vd cùng hero, trước và sau khi lên sao hoặc thanh tẩy).
