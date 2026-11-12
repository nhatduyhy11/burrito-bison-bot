# Đồ đi kèm hero: Dị Năng, Thánh Khí, Thần Khí

Phân tích từ capture pmain 2026-11-12 (`.tmp/battle_research/startgamep-6af56b662f05ea3f5834af6c.json`,
Stage 314, 5 hero) và các capture cũ của cùng account (`6af5394f`, `6af53985`, `6af3d7da`,
`6af3dacb`), config `sea_65380`, bundle 1377a. Index: [research.md](research.md).
Equip (`PutOnEquip`, 6 ô) đi theo Summoner, ưu tiên thấp nhất nên doc này chưa bàn tới.

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
- "Di Vật" (遗物) là `RelicLO` type 1 (`8101xxxx`, nguyên liệu kinh nghiệm), không gắn lên hero.

## Dị Năng: xong phần skill

- Mỗi hero đỏ (16 hero) có đúng 5 node skill (chapter 1–5). Mỗi node bật/tắt, đổi
  `_oldSkillCode → _skillcode` theo `AvatarUpGradeLO`. Server áp đúng quy tắc này (152 hero capture,
  không lệch chỗ nào). Engine trận chỉ nạp skill theo `code`.
- Simulator đã có: profile `avatar: N`, ô "Dị Năng (node skill)" trong form setup (commit `3101ef9`).
- Node chỉ số không mô phỏng, vì attr do server gộp sẵn vào `hero.attr`.
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

Catalog [artifact-dict.json](../../web/dict/artifact-dict.json) trích từ config `sea_65380`.
Tra `heroes[heroCode].variants` để lấy món theo phẩm và stage, rồi tra `entryPools[entryPool][entryCode]`
và `skills[skillCode]`. Có 240 biến thể cho 16 hero đỏ, 688 entry kỹ năng trong 16 pool
và 138 skill. Dict giữ 640 dòng buff có trị số và 48 dòng đặc kỹ rainbow.
Chỉ số gốc `ArtifactLO.attr` và 1.728 dòng roll chỉ số thường (`entryType=1`) đã bỏ
khỏi dict vì client nhận chỉ số trận trong `hero.attr`.

### Lên stage và mở kỹ năng

`HeroTrainMainPanel.updateArtifactInfo` và `ArtifactModule.getArtifactsByHeroCode` giới hạn món
theo `ArtifactLO.hero`. Mỗi món có UUID riêng, với một mã config cho mỗi cặp phẩm và stage.
Cả bốn phẩm của cùng hero dùng chung một pool. Số ô đã mở và số kỹ năng theo stage khớp
trên cả 240 biến thể.

| Phẩm món | Stage tối đa | Số ô roll theo stage | Số kỹ năng cố định theo stage |
|---|---:|---|---|
| 4 | 3 | 0 → 1 → 2 | 1 → 2 → 3 |
| 5 | 3 | 1 → 2 → 3 | 1 → 2 → 3 |
| 6 | 4 | 2 → 3 → 4 → 5 | 1 → 2 → 3 → 4 |
| 7 | 5 | 3 → 4 → 5 → 6 → 7 | 1 → 2 → 3 → 4 → 5 |

`ArtifactLO.skillList` là danh sách tích lũy. Mỗi stage thêm một mã và giữ nguyên các mã trước đó.
Ví dụ Giáo Tu La Giáng Thế của Hắc Lữ Bố `10806003` mở
`10130701000`, `10130702000`, `10130703000`.

- **Dị Năng** có cặp `oldSkillCode → skillcode` và kết quả thay skill đã nằm trong `hero.skills`
  từ server.
- **Thần Khí trong Campaign** dùng `TDBuildVO.initData` để tạo `atrifactSkillCodeList` từ
  `ArtifactLO.skillList` và `skillCode` của các `battleEntryInfos`. Đây là danh sách điều kiện.
  `TDPlayerEntity.isActiveAtrifactSkill` kiểm tra hero đã được dựng trên bàn và có mã cần thiết
  để lọc thẻ summon theo `SpecialCondition`. Việc lên stage vì vậy mở thêm lựa chọn kỹ năng trong
  trận, thay vì đổi mã đánh thường hoặc tự gắn tất cả skill cố định vào `hero.skills`.
  `BuildSummonLO` có cặp thẻ Hắc Lữ Bố `300001013/300002013` với điều kiện
  `[6,10130701000,0/1]`. Có mã skill Thần Khí thì cặp này chọn biến thể thứ hai.
- Luồng hero support có nhánh chọn biến thể `BuildSkillLO` theo `unlock` và level.
  Nhánh tạo/nâng building dùng `ArtifactLO.skillList`, còn nhánh `HeroFinalSkill` dùng mã skill
  từ `battleEntryInfos`.

### Roll thuộc tính và dữ liệu vào trận

**Server quản lý món đang đeo và kết quả roll. Client áp hiệu ứng trận dựa trên snapshot server gửi.**
`ArtifactModule` gửi `ArtifactEntryRedined {uuid}` và UI đọc `tempEntryInfos` trong
`artifactInfo` trả về. Khi chọn giữ hoặc bỏ, client gửi `ArtifactRefinedReplace {uuid, replace}`,
rồi `ArtifactProxy` cập nhật món bằng `artifactInfo` mới. Khóa/mở khóa entry, đeo/tháo và lên stage
cũng đi qua request/response. `GetPlayerArtifactR.artifactInfo` dùng cùng schema, có các field
`entryInfos`, `tempEntryInfos`, `lockEntryCodes`, `exp`, `binding` và `battleEntryInfos`.

`StartGameP` quan sát được gửi `hero.artifact {code, uuid, battleEntryInfos?}`. Engine không đọc
`entryInfos` hoặc `tempEntryInfos` để roll lại. Nó dùng ngay `code/value` từ snapshot. Các loại
entry có đường xử lý khác nhau:

| Loại entry | Config | Đường xử lý |
|---|---|---|
| Chỉ số thường | `entryType=1`, có `attrId`, phẩm 3–7 | UI hiển thị bằng `getAttrNormalDesc`. Capture chi tiết Hắc Lữ Bố cho thấy hai dòng thường xuất hiện với đúng trị số trong `hero.attr` và vắng trong `battleEntryInfos`. Công thức quy đổi chỉ số % vẫn cần kiểm riêng. |
| Buff đội có trị số | `entryType=2`, phẩm 3–7, có `skillCode`, khoảng trị số dương | `TDPlayerEntity` gom entry của các hero, `ArtifactSkillHub` lấy **value lớn nhất theo entry code**, dựng passive rồi `BattleEngineDelegate` đưa vào hero. `Buff_Modifiers_Factor` đổi value theo `/10000` nếu là modifier phần trăm, `/100` nếu là modifier số tuyệt đối. |
| Kỹ năng riêng của Thần Khí | `entryType=2`, phẩm 8, `isRare=1`, `minValue=maxValue=0` | `BattleEngineDelegate` gọi `BattleUnitData.createAddUnitData(hero)` khi dựng hero trong Campaign. Hàm thêm skill của entry `value == 0` vào bản sao danh sách skill của hero đeo món. `TDBuildVO` cũng lấy mã skill để xét điều kiện thẻ. |

### Dòng rainbow trong Tôi Luyện

`ArtifactModule.getEntryInfoListBy` liệt kê cả pool của món. `ArtifactEntryInfoItem`
và hai component hiển thị dòng hiện tại/preview đọc `showType=2` để gắn nhãn
`神器特技` (đặc kỹ Thần Khí), và `quality=8` để dùng nền `sq_img_sxtiao_8`.
Đây là phẩm của dòng roll. Cả 16 pool đều có đúng ba dòng rainbow, kể cả khi món đang
ở phẩm đỏ. UI tính tỷ lệ hiển thị bằng `showWeight / tổng showWeight` của pool.
Pool Hắc Lữ Bố hiển thị 0,020%, 0,040% và 0,040%; đây là tỷ lệ UI cho từng dòng,
chưa xác minh thuật toán roll thực tế của server. Cờ `isRare` cũng có trên dòng phẩm 7.

| Entry rainbow của Hắc Lữ Bố | Skill | Luồng Campaign trong config |
|---|---|---|
| `80000108` | `10130707000` Chiến Ý Bất Khuất | Passive có điều kiện `CommonWeaponLevel` đạt 3 trong trận, rồi tích ST Phép Trực Tiếp khi gây ST Xuyên Thấu. |
| `80000208` | `10130706000` Ma Lâm Thiên Hạ | Đổi thẻ Thức Tỉnh `700004013 → 700005013` theo `BuildSummonLO.SpecialCondition`. |
| `80000308` | `10130708000` Võ Thần Bá Thể | Passive tăng ST tất cả kỹ năng theo `CommonWeaponLevel` trong trận. |

Trong 48 dòng rainbow có đúng 16 mã dùng làm điều kiện thẻ, mỗi hero một mã. Với
Hắc Lữ Bố, đã kiểm offline bằng chính `createAddUnitData` của bundle: đưa từng mã entry
vào snapshot thử với `value=0` thì cả ba mã passive xuất hiện trong skills của unit.
Capture tài khoản hiện chưa có dòng rainbow đã roll để kiểm đầu cuối trên trận thật.

### Đối chiếu capture

Kiểm bốn `StartGameP` khác nhau còn trong `.tmp/battle_research/events-*.jsonl`. Stage 314
(`6af47b9f…`) có năm món, đều khớp hero/config và không có mã nào từ `ArtifactLO.skillList`
xuất hiện trong `hero.skills`. Ba món chỉ có `code/uuid`. Hai món có entry đều khớp pool và
khoảng trị số:

| Mã hero | Món | Entry từ server | Skill template |
|---|---|---|---|
| `50000004` | `10406001` | `40002907`, value `2483` | `90100071000`, ST Mất HP Đội Chiến Đấu (Duy nhất), 24,83% |
| `50000013` Hắc Lữ Bố | `10806003` | `80003005`, value `704` | `90100081000`, Tăng ST Đội Chiến Đấu (Duy nhất), 7,04% |

### Capture chi tiết và so thẻ Hắc Lữ Bố với Stage 51

Capture `events-pmain-20261112-204449.jsonl` có `GetPlayerArtifactR` của Hắc Lữ Bố và trận
`6af5c331…` ở **Stage 314**. Cả năm hero của người chơi đều có Thần Khí. Hắc Lữ Bố đeo
`10806003` (đỏ, stage 3). Cùng UUID ở lobby và trong trận, với cùng một dòng
`battleEntryInfos`, `80003005: 704`.

| Dòng đã lưu của Hắc Lữ Bố | Config | Dữ liệu trong trận |
|---|---|---|
| `80001905: 586` | `attrId=10170` | `hero.attr[10170] = 586` |
| `80003005: 704` | Buff đội `90100081000` | `battleEntryInfos` giữ nguyên code/value |
| `80003606: 2595` | `attrId=2010001` | Không có key thô `2010001` trong `hero.attr`; chưa cô lập được phần quy đổi |
| `80000604: 199` | `attrId=10250` | `hero.attr[10250] = 199` |

Response chi tiết của món `10406001` còn cho thấy hai dòng preview `tempEntryInfos`
tồn tại cùng lúc với hai dòng đã lưu `entryInfos`. `battleEntryInfos` của món đó giữ
buff đã lưu `40002907: 2483`. Capture này chưa có phản hồi roll mới hoặc bấm giữ kết quả.

Hai run Stage 51 cũ (`6af29854…`, `6af2ab8a…`) dùng Hắc Lữ Bố chưa đeo Thần Khí.
Log `rng.randomCode` ghi nhận cả ba mã thẻ cơ bản dưới đây. Khi đeo `10806003`,
`SpecialCondition` của `BuildSummonLO` cho phép ba mã tương ứng ở cột phải sau khi hero
được dựng. `BuildSkillLO.effect/params` xác nhận thay đổi hiệu ứng khi chọn thẻ.

| Mốc | Thẻ đã gặp ở Stage 51 | Biến thể mở bởi Thần Khí đỏ stage 3 |
|---:|---|---|
| 1 | `300001013`: Tuyệt Kỹ thêm 2 đường đạn, ST +5% | `300002013`: thêm 2 đường đạn, ST +30% |
| 2 | `400011013`: Công Thường thêm 2 đường đạn, ST −25% | `400012013`: thêm 2 đường đạn, ST +15% |
| 3 | `400021013`: Tuyệt Kỹ xuyên +2 | `400022013`: xuyên +4, ST +20% |

`TDLotteryItem.data` lấy mô tả từ `BuildSummonLO.minDesc || desc` của mã thẻ đã roll.
Khi đeo Thần Khí, nhóm thẻ `PutonTreasure/TreasureUpstar/TreasureFinal` dùng icon món
từ `ArtifactLO.icon`. Biến thể yêu cầu mã Thần Khí còn đổi nền sang
`mgzd_img_kpczz1/2`. Biểu tượng dòng kỹ năng phẩm 8 có nhánh hiển thị riêng. Capture
Hắc Lữ Bố chỉ có buff đội phẩm 5, nên thay đổi thẻ tím quan sát được khớp với ba mốc
skill cố định của món.

Repo có bundle client chứa `TDServer` chạy local, schema mạng và capture phản hồi từ server
thật. Còn thiếu mã backend, capture trước/sau khi lưu một lượt roll và log thẻ đã roll của
trận Stage 314 mới. Thuật toán RNG, quy tắc lọc entry đầy đủ, công thức cộng chỉ số % và
hành vi thực tế của từng dòng kỹ năng phẩm 8 vẫn cần kiểm riêng.

## Ý nghĩa cho simulator

- Hero có trong capture thì giữ nguyên `hero` là đã đúng cả 3 loại (replay khớp hiện tại xác nhận).
- Setup hỗ trợ **Thánh Khí** cho cả hero trong capture và hero mượn chỉ số. Chọn dòng,
  sao 0–10 và số lần thanh tẩy 0–2 ngay dưới Dị Năng. Profile dùng
  `relic: {name, star, purification}`, `relic: null` để tháo hoặc bỏ field để dùng món
  trong capture. Sim đặt `hero.relic` và thay các skill Thánh Khí ở `index 0`, giữ chỉ số
  đang có trên hero.
- **Thần Khí** đã có dict cho setup sau này. Phần mô phỏng lựa chọn skill/buff có thể dùng
  `hero.artifact.code` và `battleEntryInfos` đúng pool và khoảng giá trị, qua engine gốc.
  Việc đổi món chưa có công thức cập nhật `hero.attr`.

## Còn mở

- Skill `6000XX00100` ở `index 0` (vd "Choáng Tổn Thương" của Alice, "Tăng ST Bạo" của LB) chưa rõ
  nguồn. Hai bảng Thần Khí (`ArtifactLO.skillList`, `ArtifactEntryLO.skillCode`) và
  `RelicStarLO` đều không chứa các mã này.
- Skill `8004…` ở `index 5–9` là skill skin (đã xử lý trong `hero/skin.js`).
- Công thức server cộng attr của Thánh Khí/Dị Năng: cần so `hero.attr` giữa 2 capture khác nhau
  đúng một yếu tố (vd cùng hero, trước và sau khi lên sao hoặc thanh tẩy).
