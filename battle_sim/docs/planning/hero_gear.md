# Đồ đi kèm hero: Dị Năng, Thánh Khí, Thần Khí

Phân tích từ capture pmain 2026-11-12 (`.tmp/battle_research/startgamep-6af56b662f05ea3f5834af6c.json`,
Stage 314, 5 hero) và các capture cũ của cùng account (`6af5394f`, `6af53985`, `6af3d7da`,
`6af3dacb`), config `sea_65380`, bundle 1377a. Index: [research.md](research.md).
Dị Vật và trang bị Summoner: xem mục riêng (capture 2026-11-18).

## Thuật ngữ

| Tên VN | Tên gốc | Là gì | Field trong `heros[]` | Bảng config |
|---|---|---|---|---|
| Dị Năng | 异能 (神通) | cây node riêng của hero đỏ | `avatarCodes[{pointCode, level}]`, `avatarChapterCodes`, `avatarLevel` | `AvatarLO`, `AvatarUpGradeLO` |
| **Thánh Khí** | 圣器 | đồ dùng chung, có thể chuyển giữa các hero, kể cả hero tím theo luồng trang bị của client. Các món phẩm 6–8 có tối đa 10 sao và hệ thanh tẩy (vd Cuộn Cthulhu, Thánh Giá Cứu Rỗi) | `relic` (chỉ có code) | `RelicLO` (type 2), `RelicStarLO`, `RelicQualityUpLO` |
| **Thần Khí** | 神器 / 神兵 | vũ khí dành riêng cho một mã hero qua `ArtifactLO._hero`. Trong config hiện tại chỉ hero đỏ có Thần Khí (vd Giáo Chiến Phong Lôi) | `artifact {code, uuid, battleEntryInfos?}` | `ArtifactLO`, `ArtifactEntryLO` |

Dễ nhầm:
- Trong code, `relic` là **Thánh Khí** và `artifact` là **Thần Khí**.
- Gói tiếng Anh lại gọi Thánh Khí là "Artifact" (vd "Artifact Shard" = Mảnh Thánh Khí, "Artifact
  Skill" = KN Thánh Khí). Vì vậy khi gặp "Artifact" trong text EN thì phải xem code/bảng mới biết
  là loại nào.
- "Dị Vật" (遗物) là `BeautyBag` (6 ô mỗi hero), không phải `RelicLO` type 1 (`8101xxxx` chỉ là
  nguyên liệu EXP). Xem mục Dị Vật bên dưới.

## Dị Năng: xong phần skill

- Mỗi hero đỏ (16 hero) có đúng 5 node skill (chapter 1–5). Mỗi node bật/tắt, đổi
  `_oldSkillCode → _skillcode` theo `AvatarUpGradeLO`. Server áp đúng quy tắc này (152 hero capture,
  không lệch chỗ nào). Engine trận chỉ nạp skill theo `code`.
- Simulator đã có: profile `avatar: N`, ô "Dị Năng (node skill)" trong form setup (commit `3101ef9`).
- Node chỉ số không mô phỏng, vì attr do server gộp sẵn vào `hero.attr`.
- `AvatarUpGradeLO._skillUnlock` = `[mã, bậc đột phá]` có ở 27 node: bằng mốc trong `SkillReplaceLO`
  của skill mà node thay (hoặc node nối tiếp nó). Client không đọc, server áp. Sim chặn bằng
  `minBreakThrough` trong `avatarNodes`: hero có `breakThrough` thấp hơn thì bỏ qua node, kể cả
  node thêm skill (Alice node 2, Sát Thương Choáng, cần đột phá 6). Account pmain đột phá ≥ 11 nên
  không node nào bị chặn; chưa có capture hero đột phá thấp để kiểm server.
- Còn mở: chưa kiểm bằng hình trong trận LB node 2 (đánh thường 3 tia ±10°) và Loli node 4
  (`10050201000 → 10050604000`), dùng skin mặc định.

## Thánh Khí

Catalog: [web/dict/relic-dict.json](../../web/dict/relic-dict.json), sinh bằng
`gen_profile_dict.js`.

### Hero nào đeo được

- Trong bundle `1377a`, `HeroTrainMainPanel._udpateYwInfo` mở ô Thánh Khí khi tính năng
  `Relic` đã mở, kể cả với hero tím. `RelicEquipView` lấy danh sách từ
  `RelicModule.getAllRelicList(heroUuid)`. `RelicEquipListItem.onOperationBtnClick` dùng
  `PutOnRelicRequest({heroUuid, uuid})` để đeo hoặc chuyển món từ hero khác. Luồng này
  không lọc theo màu hay mã hero, kể cả với Thánh Khí phẩm 6–8.
- Đối chiếu 4 trận `StartGameP` khác nhau trong `.tmp/battle_research/events-*.jsonl`:
  các hero tím xuất hiện đều chưa đeo Thánh Khí. Khả năng đeo trên hero tím được xác nhận
  ở client, chưa có capture cho thấy server đã nhận và trả món đó trong trận.

### Phân loại

- `RelicLO` type 2 có 37 Thánh Khí. Code là `82QQLL01`, trong đó `QQ` là phẩm và `LL` là dòng.
- Phẩm 1–5 (đến cam, 16 món) chỉ có chỉ số: không có sao, không có skill, nên dict bỏ qua.
- Dict không chứa chỉ số (`_base`, `_attrUp`, `_starAttrUp`, level), vì client không tính chỉ số
  Thánh Khí (xem mục Chỉ số bên dưới). Cần thì tra thẳng `RelicLO`/`RelicStarLO`.
- Phẩm 6–8 gồm 7 dòng, mỗi dòng có 3 mức thanh tẩy (`lines` trong dict). Mỗi mức có sao 0–10
  trong `RelicStarLO`. `RelicStartUpView` cho nâng khi `star < 10`.

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
- Lần 2 yêu cầu ít nhất 5 Thánh Khí phẩm 7 trở lên
  (`RelicQualityUpView` đếm `quality >= 7` theo ngưỡng `relicAgainImproveColorRequite`).
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

## Thần Khí

Đã tách sang [artifact.md](artifact.md): quy tắc phẩm/stage/skill/ô roll, dict đã gọn, luồng trận
phía client, đối chiếu capture và hướng sim.

## Ý nghĩa cho simulator

- Hero có trong capture thì giữ nguyên `hero` là đã đúng cả 3 loại (replay khớp hiện tại xác nhận).
- Setup hỗ trợ **Thánh Khí** cho cả hero trong capture và hero mượn chỉ số. Chọn dòng,
  sao 0–10 và số lần thanh tẩy 0–2 ngay dưới Dị Năng. Profile dùng
  `relic: {name, star, purification}`, `relic: null` để tháo hoặc bỏ field để dùng món
  trong capture. Sim đặt `hero.relic` và thay các skill Thánh Khí ở `index 0`, giữ chỉ số
  đang có trên hero.
- **Thần Khí**: xem hướng sim trong [artifact.md](artifact.md).

## Dị Vật (遗物 = `BeautyBag`) và Trang bị Summoner (`Equipment`)

Nguồn: capture pmain 2026-11-18 (`.tmp/battle_research/events-pmain-20261118.jsonl`, config
`sea_66328`, có `PutOnEquip` ×4, `PutOnBeautyBag` ×3 trước trận, bỏ trận sau 24s). So với
`startgamep-6af56b66…` (11-12). Bảng tra trên config `sea_65553` (bản đã cache).

### Dị Vật = `BeautyBag`, không phải `RelicLO` type 1

- Icon của `BeautyBagLO` là `yiwu/…` (遗物). Request là `PutOnBeautyBag {uuid, heroUUID, pos}`:
  6 ô mỗi hero (`heroBeautyBagList[].posToUUID` 1–6). `RelicLO` type 1 (`8101xxxx`) chỉ là nguyên
  liệu EXP, bảng Thuật ngữ ở trên ghi nhầm.
- Bảng: `BeautyBagLO` (750 dòng; `_type` 1–10, `_suitType`, `_color` 3–7, `_level`, `_suitSkill`),
  `BeautyBagTypeLO` (10 hệ: V.Lý, Phép, Thiêu Đốt, Mất HP, Tê Liệt, Bạo, Choáng, Đẩy Lùi,
  Băng Sương, Tốc Công → `suitType` 101–110), `BeautyBagSuitLO` (150 dòng = 10 bộ × level 1–15,
  `_requireNum` 4, `_attr`, `_isSkill`, `_desc`), cùng các bảng Level/Color/Score/Unlock/Reach.
- **Skill bộ 4 món → `6000TT00N00`** (TT = type 01–10, N = bậc 1–3). Đây là nguồn của các skill
  `6000XX00100` ở `index 0`. `BeautyBagSuitLO._skill` luôn bằng 0: dòng có `_isSkill=1` ở level
  1/5/10 chỉ mang `_desc` của bậc N=1/2/3 (vd bộ Phép 102: "+60% / +120% / +240% ST lên địch HP
  < 50%" = `60000200100/200/300`). Các level còn lại cộng attr bộ (vd `[[10160, 400·k]]`). Ánh xạ
  suit → mã skill do server làm, client không có bảng nối.
- **Skill món đặc biệt → `6000TT10N00`**: 10 món màu 7, `_subType` 701–710 (`suitType` 201–210,
  vd "Chén Tụ Hồn" 702), có `_suitSkill` theo level (N = 1–3, giá trị bằng nửa skill bộ). Chưa thấy
  trong capture nào. Quan hệ với bộ: xem mục "Bộ đỏ và món vàng" bên dưới.

### Bộ đỏ và món vàng (bbb-4g0.3, phân tích tĩnh `sea_66328` + bundle 1377a/7125c)

- **Màu**: `BeautyBagColorLO` 3 Thường, 4 Quý, 5 Hiếm, 6 Thần (đỏ), 7 Phẩm Thánh (vàng, `Epic`).
  Mỗi hệ (type 1–10) có đúng 1 món cho mỗi màu: màu 3–6 thuộc `suitType` 10T, màu 7 thuộc 20T.
- **Ô**: hero có 8 ô (`BeautyBagUnlockLO`). Ô 1–6 chỉ nhận món màu < 7, ô 7–8 chỉ nhận món màu 7
  (`BeautyBagHeroEquipPanel`: `_curSelPos > 6` lọc `color >= Epic`). Ô 7 mở khi `beautyBagLevel` 500,
  ô 8 khi 1500 (kèm điều kiện unlock loại 3 = 60, chưa tra loại 3 là gì).
- **Bộ đỏ** = bộ 4 món thường (`BeautyBagUtil.getBeautyBagSuitTypeDataByList`). Chỉ đếm món màu < 7.
  Bộ kích hoạt khi đủ `_requireNum` 4 món cùng `suitType`, tức đủ 4 màu 3/4/5/6 của một hệ. Sao bộ là
  sao **thấp nhất** trong các món đó. 6 ô chỉ chứa được 1 bộ.
- **Món vàng không phải bộ độc lập**, nó là "cường hoá" của bộ đỏ cùng hệ:
  `BeautyBagSuitLO._enhanceSubType` 10T → 70T, và `suitUnlock` của món vàng là `[10T, sao]`
  ("Bộ cần đạt N sao"). Client coi món vàng có hiệu lực khi hero đang kích hoạt đúng bộ đó
  (`checkBeautyBagEnhanceActive`). Từng mốc sao của món vàng chỉ có hiệu lực khi sao bộ ≥ mốc đó
  (`BeautyBagSuitTypeEnhanceItem`). Đeo món vàng mà không có bộ cùng hệ thì UI không bật hiệu lực.
- **Trong trận là 2 skill riêng, cộng dồn**: `6000TT10N00` là skill đầy đủ trong `SkillBaseLO`, có action
  và buff riêng (vd `60000210100`: buff `Making_Credit_CondsTargetBloodPercent_Improvise` [50, LESS_THAN]
  giống `60000200100`, khác id, `group_id` None, `exclusionGroup` 0). Engine không gộp hai buff này.
  "Lượng Tăng ST Bộ +30%" nghĩa là cộng thêm cùng hiệu ứng với nửa giá trị (bộ +60% → tổng +90%).
  Ngoại lệ: `60001000N00` (Khúc Ca) có 2 action, bản vàng `60001010N00` chỉ có 1.
- **Bậc N**: `BeautyBagSuitLO._isSkill` = 1 ở level 1/5/10 cho cả 10 bộ, nên bộ: 1–4 → N1, 5–9 → N2,
  10–15 → N3. Món vàng chỉ có sao 1–10, `_suitSkill` ghi sẵn N theo sao: 1–4 → N1, 5–9 → N2, 10 → N3.
  Nếu tính theo luật client, N của món vàng = N của min(sao vàng, sao bộ).
- **Client không đọc `_suitSkill`** và không có bảng nối suit → mã skill. Server tự chọn mã: skill
  vàng lấy từ `_suitSkill`, skill bộ theo quy luật `6000TT00N00`.
- **Capture xác nhận** (`events-pmain-20261119.jsonl`, rednight): Hanuman có `60000500200` (bộ Tê Liệt
  N2) + `60000510100` (vàng Tê Liệt N1); Pháp Sư Sương có `60000900200` + `60000910100`; Hắc Lữ Bố có
  `60000200200`. Skill bộ và skill vàng nằm riêng trên `index 0`, bậc N2 xuất hiện đúng mã. 5 bộ trên
  acc user (sao bộ < 5) đều ra N1 (user xác nhận 2026-11-19). N3 chưa thấy, suy theo cùng quy luật.
- `dressNum` (theo sao: 1→1, 4→2, 6→3, 8→4, ≥10→9999) là số hero dùng chung được một món
  (`heroUUIDList`). Capture khớp: món sao 7 có 3 hero.
- `BeautyBagLappingLO` (nâng cấp cấp tài khoản) có skill `19010301000` từ mốc 0.6. Mã này không có trong
  `SkillBaseLO` và chưa thấy trong capture. Không thuộc phạm vi bộ/món vàng.
- Capture xác nhận: hero 50000026 sau khi đổi dị vật ô 1/5/6 có thêm `60000200100` ("Tăng ST HP
  Thấp", bộ Phép bậc 1) ở `index 0`, trước đó không có. Các hero khác giữ nguyên.

### Trang bị Summoner = `EquipmentLO`, skill gắn vào build giường

- 6 ô (`PutOnEquip {uuid}` → `equipPosList[pos 1–6]` có `level`, `enchantLevel`, `starLevel`).
  Bảng: `EquipmentLO` (1074), `EquipmentEntryLO` (2592 dòng entry; `_entryPool`, `_skillCode` hoặc
  `_attrId` + min/max), cùng các bảng UpGrade/Enchant/Cui/Master.
- Chỉ có 3 skill entry, đều ghi "(Duy nhất)", nằm ở entry pool phẩm 5–7:
  `90000100000` Tăng Cường Ngân Phiếu (Mèo Chiêu Tài +5), `90000200000` Tăng Cường Điện Năng
  (Trạm Sạc +1), `90000300000` Tiêu Diệt Hồi Nộ (hero hạ địch hồi Nộ +25).
- Trong `StartGameP` các skill này nằm ở `builds[type 2].skills` (giường), không nằm trên
  `summonerInfos` hay hero. Capture mới thêm `90000200000` sau khi đổi đồ. Chỉ số entry/cường
  hoá do server gộp, không thấy field riêng.
- Tẩy luyện: mỗi món roll `_entryNum` (1–3) dòng từ `_entryPool`. Pool có 1 skill (tỉ lệ 50 ở
  phẩm 7), 1 attr hiếm (vd 11262) và khoảng 10 attr thường (tỉ lệ 550–1200). Chỉ Mũ/Giáp/Giày có
  skill, nên tối đa 3 skill. Client tô mọi dòng theo màu phẩm của món
  (`COLOR_2_FONT_COLOR[quality]`), ngôi sao = `isRare`. Vì vậy dòng vàng/đỏ phần lớn là attr,
  không phải skill.
- Attr của dòng do server gộp: bundle trận không đọc mã attr của pool (11164, 11262, 1101001…),
  `StartGameP` cũng không có key này. Không theo đuổi việc truy ra chỗ gộp (bbb-27n.3, closed
  won't-do): tổng attr gồm nhiều yếu tố (tẩy luyện, cường hoá, sao…) cộng logic server không có
  trong bundle nên capture không tách được; sim bỏ qua attr đi kèm, chỉ nạp 3 skill `9000x00000`.

### Hướng sim

- Hero hoặc build có trong capture thì giữ nguyên `skills` là đủ. Engine nạp skill theo code.
- Muốn chỉnh trong setup: dị vật = thêm/bỏ `6000TT00N00` (bộ) và `6000TT10N00` (món đặc biệt)
  ở `index 0` của hero. Trang bị = thêm/bỏ `9000x00000` ở build type 2. Attr đi kèm không tự
  tính được (giống Thánh Khí).

## Còn mở

- Tra bảng trên `sea_65553`. Capture là `sea_66328`, chưa đối chiếu lại bảng trên bản mới.
- Skill `8004…` ở `index 5–9` là skill skin (đã xử lý trong `hero/skin.js`).
- Công thức server cộng attr của Thánh Khí/Dị Năng: cần so `hero.attr` giữa 2 capture khác nhau
  đúng một yếu tố (vd cùng hero, trước và sau khi lên sao hoặc thanh tẩy).


## Đối chiếu GAT `trunk_66196` và VN `sea_65553`

- Dị Năng có cùng 688 dòng `AvatarLO` và 6.160 dòng `AvatarUpGradeLO`.
- Thánh Khí có cùng `RelicLO`, `RelicStarLO` và `RelicQualityUpLO`. Catalog có
  cùng 7 dòng và các mã skill theo sao/tẩy.
- Thần Khí có cùng 16 hero, 240 biến thể, 10 nhóm buff và 48 dòng Đa Sắc.
  Generator kiểm tra mã, skill, lỗ và giá trị entry trên cả hai config.
  `ArtifactEntryLO` giống nhau. Khác biệt trong `ArtifactLO` nằm ở tên, icon
  và animation.
- GAT có cùng 36 hero. Hulk và Cô Dâu có thêm skin Đa Sắc; Hulk còn có config
  triệu hồi và hiệu ứng trong bundle GAT. Setup đọc dữ liệu từ
  `web/dict/gat-overrides.json` cùng catalog chung. Logic trận đọc config GAT.
