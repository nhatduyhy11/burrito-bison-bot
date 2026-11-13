# Thần Khí (神器 / 神兵, `artifact`)

Tách ra từ [hero_gear.md](hero_gear.md). Nguồn: bundle client 1377a, config `sea_65380`, các capture
`StartGameP` / `GetPlayerArtifactR` trong `.tmp/battle_research/`. Index: [research.md](research.md).

Thần Khí là vũ khí riêng của từng hero đỏ, gắn qua `ArtifactLO.hero`. Khác Dị Năng ở chỗ phần
tác động lên trận do **client** tự dựng từ snapshot `hero.artifact {code, uuid, battleEntryInfos}`.
Server chỉ giữ món và kết quả roll. Vì vậy sim chỉ cần đưa vào một snapshot hợp lệ, phần còn lại
để engine gốc xử lý.

## Thuật ngữ

| Từ | Field | Ý nghĩa |
|---|---|---|
| Phẩm món | `ArtifactLO.quality` | 4 tím, 5 cam, 6 đỏ, 7 vàng |
| Stage | `ArtifactLO.stage` | Bậc tiến hóa của món, **không phải level**. Mỗi cặp phẩm + stage là một mã config riêng |
| Exp / level | `artifactInfo.exp` | Chỉ ảnh hưởng chỉ số, đã nằm trong `hero.attr`, sim bỏ qua |
| Ô roll | `holeNum` / `maxHoleNum` | Số dòng Tôi Luyện đang mở / mở tối đa |
| Dòng (entry) | `ArtifactEntryLO` | Mỗi dòng có **phẩm riêng 3–8**, độc lập với phẩm món |
| Value | `battleEntryInfos[].value` | Trị số của dòng. Nếu `percent=1` thì `value/10000` là tỷ lệ (`704` = 7,04%); UI hiển thị `value/100` + `%` |

## Quy tắc config (đã kiểm)

Pass 1, kiểm src: client **không tự suy ra** các field này mà chỉ đọc từ dòng config:
- `ArtifactDetailView`, `ArtifactModule` đọc thẳng `holeNum` và `maxHoleNum`.
- `ArtifactStageView` và `ArtifactInfoDetailView.parseSkillList` lấy **phần tử cuối** của
  `skillList` làm skill mở ở stage đó. Điều này ngầm xác nhận `skillList` là danh sách tích lũy.
- Tên món lấy từ `ArtifactLO.name` của từng dòng.

Vì client chỉ đọc, các quy tắc dưới đây là quy tắc của **data**. Pass 2 đã kiểm trên toàn bộ
240 biến thể và 688 entry (16 hero), không lệch dòng nào. Công thức nằm trong
[web/artifacts.js](../../web/artifacts.js). `gen_profile_dict.js` kiểm mọi dòng config theo công
thức này và **dừng với lỗi** nếu có dòng sai, để config mới đổi rule thì phát hiện ngay.

| Quy tắc | Công thức |
|---|---|
| Biến thể | Mỗi hero có đúng 15 món: phẩm 4 và 5 có stage 1–3, phẩm 6 có stage 1–4, phẩm 7 có stage 1–5 |
| Mã món | `1<PP><QQ><SSS>`, với `PP` = slot hero 1–16 (`pool`), không phải đuôi mã hero (Hắc Lữ Bố `50000013` → slot 8 → `10806003`) |
| Tên | Phẩm 4–6 dùng chung một tên (cả EN lẫn VN); phẩm 7 có tên riêng (vd Giáo Tu La Giáng Thế → Giáo Thiêu Thiên Thái Sơ) |
| Skill cố định | Mỗi hero có 5 skill `10<NN>070K000` (K = 1..5, `NN` = đuôi mã hero). Stage s mở s skill đầu. Vì vậy số skill tối đa là 3 (phẩm 4–5), 4 (phẩm 6), 5 (phẩm 7) |
| Ô roll | `holeNum = phẩm − 4 + stage − 1`; `maxHoleNum` = `holeNum` ở stage cuối (2 / 3 / 5 / 7) |
| Pool | `entryPool = slot × 100000`. Mỗi hero một pool, mọi phẩm và stage dùng chung |
| Mã entry | `<slot><family:5><phẩm:2>`, vd `80003005` = slot 8, family 30, phẩm 5 |
| Buff đội | 10 family (24–31, 39, 40). `skillCode` và khoảng trị số **giống hệt nhau ở mọi pool**, chỉ khác tiền tố slot |
| Rainbow | Mỗi pool có đúng family 1/2/3 ở phẩm 8, value luôn 0, skill `10<NN>07<RR>000` với RR = 07/06/08 |

`entryPool` chỉ được client dùng ở `ArtifactModule.getEntryInfoListBy`, để liệt kê các dòng một món
có thể roll (UI Tôi Luyện). Trận không đọc pool: `ArtifactSkillHub` và `createAddUnitData` đi
thẳng từ entry code sang `ArtifactEntryLO.skillCode`.

### Khoảng value buff đội theo phẩm dòng

| Family | Skill | P3 | P4 | P5 | P6 | P7 |
|---|---|---|---|---|---|---|
| 24, 27, 28, 29, 30 | `901000{2,5,6,7,8}1000` | – | 100–300 | 500–800 | 1000–1500 | 2000–2500 |
| 25, 26, 31 | `901000{4,3,9}1000` | – | 50–150 | 200–300 | 400–600 | 800–1000 |
| 39, 40 | `90100011000`, `90100101000` | 30–80 | 100–150 | 200–300 | 400–500 | – |

Ví dụ: 30 = Tăng ST Đội Chiến Đấu, 29 = ST Mất HP Đội Chiến Đấu.

## Dict đã gọn

[web/dict/artifact-dict.json](../../web/dict/artifact-dict.json) (từ 228KB xuống 45KB) gồm:
- `heroes[heroCode] = {pool, name, name_vn, name7, name7_vn}`;
- `buffs[family] = {skillCode, percent, ranges: {phẩm: [min, max]}}`;
- `skills[code]` chứa tên và mô tả của 138 skill: 80 skill cố định, 48 skill rainbow và 10 skill buff.

Mã món, `skillList`, số ô và skill rainbow được dựng lại bằng `web/artifacts.js`. Round-trip từ dict
mới ra 928 bản ghi của dict cũ đều khớp. Chỉ số gốc `ArtifactLO.attr` và các dòng chỉ số thường
(`entryType=1`) không đưa vào dict, vì trận nhận chúng qua `hero.attr`.

## Luồng trận (client)

- **`TDPlayerEntity`** gom `battleEntryInfos` của cả 5 hero rồi đưa vào `ArtifactSkillHub`.
  Hub giữ value lớn nhất **theo entry code**, thay `"%s"` trong `skillTemplateParams`, rồi dựng
  passive. `Buff_Modifiers_Factor` đổi value theo `/10000` (modifier %) hoặc `/100` (modifier tuyệt
  đối). Hub bỏ qua dòng có `value == 0`.
- **Rainbow (`value=0`)**: `BattleEngineDelegate` gọi `BattleUnitData.createAddUnitData(hero)`.
  Hàm này thêm skill của entry vào bản sao danh sách skill của hero đeo món.
- **Thẻ summon**: `TDBuildVO.initData` dựng `atrifactSkillCodeList` từ `ArtifactLO.skillList` và
  skill của `battleEntryInfos`. `TDPlayerEntity.isActiveAtrifactSkill` dùng danh sách này để lọc
  `BuildSummonLO.SpecialCondition`. Vd Hắc Lữ Bố có `[6,10130701000,0/1]`, nên khi có mã đó thì
  `300001013` được đổi sang `300002013`. Hero support có thêm nhánh `BuildSkillLO.unlock`.
- Skill cố định **không** được thêm vào `hero.skills`. Nó chỉ mở thêm lựa chọn thẻ trong trận.

Hệ quả: hub dedupe theo entry code, mà code có tiền tố slot. Vì vậy cùng một buff (vd family 30)
trên hai hero khác nhau là hai code khác nhau, **có vẻ cộng dồn**. Cần đối chiếu với một trận thật.

## Server và dữ liệu vào trận

Server quản lý món đang đeo và kết quả roll (`ArtifactEntryRedined`, `ArtifactRefinedReplace`, khóa
entry, đeo/tháo, lên stage đều là request/response). `GetPlayerArtifactR.artifactInfo` có các field
`entryInfos`, `tempEntryInfos`, `lockEntryCodes`, `exp`, `binding`, `battleEntryInfos`.
`StartGameP` chỉ gửi `{code, uuid, battleEntryInfos?}`. `battleEntryInfos` chứa các dòng
`entryType=2` đã lưu. Dòng chỉ số thường vắng mặt ở đây và nằm trong `hero.attr`.

### Đối chiếu capture

- Stage 314 (`6af47b9f…`): 5 món đều khớp hero/config, không mã `skillList` nào nằm trong
  `hero.skills`. `50000004` / `10406001` có `40002907: 2483` (ST Mất HP Đội, 24,83%). Hắc Lữ Bố /
  `10806003` có `80003005: 704` (Tăng ST Đội, 7,04%).
- `events-pmain-20261112-204449.jsonl`: `GetPlayerArtifactR` của Hắc Lữ Bố, món đỏ stage 3 (4 ô):

| Dòng đã lưu | Config | Trong trận |
|---|---|---|
| `80001905: 586` | `attrId=10170` | `hero.attr[10170] = 586` |
| `80003005: 704` | buff đội `90100081000` | `battleEntryInfos` giữ nguyên |
| `80003606: 2595` | `attrId=2010001` | không có key thô; chưa cô lập phần quy đổi |
| `80000604: 199` | `attrId=10250` | `hero.attr[10250] = 199` |

- Stage 51 (`6af29854…`, `6af2ab8a…`): Hắc Lữ Bố chưa đeo Thần Khí. Thẻ gặp được và biến thể
  sẽ mở khi đeo `10806003`:

| Mốc | Thẻ cơ bản | Biến thể khi có Thần Khí |
|---:|---|---|
| 1 | `300001013` Tuyệt Kỹ +2 đường đạn, ST +5% | `300002013` +2 đường đạn, ST +30% |
| 2 | `400011013` Công Thường +2 đường đạn, ST −25% | `400012013` +2 đường đạn, ST +15% |
| 3 | `400021013` Tuyệt Kỹ xuyên +2 | `400022013` xuyên +4, ST +20% |

### Rainbow trong Tôi Luyện

UI gắn nhãn `神器特技` cho `showType=2` và dùng nền phẩm 8. Tỷ lệ hiển thị là
`showWeight / tổng showWeight` của pool (Hắc Lữ Bố: 0,020% / 0,040% / 0,040%); thuật toán roll thật
của server chưa xác minh. Đã chạy offline `createAddUnitData` với từng mã rainbow của Hắc Lữ Bố
(value 0): cả ba skill đều vào unit. Chưa có capture nào có dòng rainbow thật.

| Entry | Skill | Hiệu ứng |
|---|---|---|
| `80000108` | `10130707000` Chiến Ý Bất Khuất | Khi `CommonWeaponLevel` đạt 3, tích ST Phép Trực Tiếp mỗi lần gây ST Xuyên Thấu |
| `80000208` | `10130706000` Ma Lâm Thiên Hạ | Đổi thẻ Thức Tỉnh `700004013 → 700005013` |
| `80000308` | `10130708000` Võ Thần Bá Thể | Tăng ST mọi kỹ năng theo `CommonWeaponLevel` |

## Hướng sim (đề xuất)

Profile, cùng cách với `relic`:
```js
artifact: { quality: 6, stage: 3, entries: [{ code: 80003005, value: 704 }, { code: 80000208, value: 0 }] }
// null = tháo, bỏ field = giữ món trong capture
```
- `quality + stage` + `heroes[code].pool` → `code` (`artifactCode`). `uuid` giữ của capture hoặc tự sinh.
- `entries` đi thẳng vào `battleEntryInfos`. Không đổi `hero.attr`, cùng chính sách với Thánh Khí:
  chỉ số của món cũ vẫn nằm trong attr.
- Kiểm: số dòng ≤ `holeNum` (dòng chỉ số thường cũng chiếm ô, nên đây là trần trên); value trong
  range; rainbow ép value 0; mỗi family chỉ một dòng. Những ràng buộc chưa chắc server cho phép
  (rainbow trên món phẩm thấp, phẩm dòng cao hơn phẩm món) thì **cảnh báo, không chặn**.
- UI: đặt dưới Thánh Khí, chỉ hiện với hero đỏ, thu gọn thành một dòng tóm tắt và bấm vào mới mở.
  Chi tiết gồm phẩm và stage, danh sách skill cố định đã mở, các ô dòng (family hoặc rainbow + phẩm
  dòng + value, mặc định max) và nút "max hết". Thêm một dòng tổng buff đội ở cấp đội hình.

Thứ tự làm:
1. `applyArtifact` trong `web/battle/hero/`, chưa có UI. Kiểm bằng hai cách: dựng lại món trong
   capture thì replay phải khớp từng bit; lắp `10806003` cho Hắc Lữ Bố ở Stage 51 thì
   `rng.randomCode` phải ra các biến thể ở bảng trên.
2. Làm UI.
3. Kiểm dòng rainbow bằng hình trong trận.

## Còn mở

- Buff cùng family trên hai hero khác nhau có cộng dồn không (xem mục Luồng trận).
- Công thức server quy đổi dòng chỉ số % (`2010001`) vào `hero.attr`.
- Ràng buộc roll thật: phẩm dòng so với phẩm món, rainbow trên món đỏ, thuật toán RNG.
