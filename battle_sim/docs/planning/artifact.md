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

## Hướng sim

Profile, cùng cách với `relic`:
```js
artifact: { quality: 6, stage: 3, entries: [{ code: 80003005, value: 704 }, { code: 80000208, value: 0 }] }
// null = tháo, bỏ field = giữ món trong capture
```
- Đã làm phần profile → trận: [web/battle/hero/artifact.js](../../web/battle/hero/artifact.js). Pool lấy
  từ `ArtifactLO.hero`, `code = artifactCode(pool, quality, stage)`. `uuid` giữ của capture hoặc tự sinh.
- `entries` đi thẳng vào `battleEntryInfos`. Không đổi `hero.attr`, cùng chính sách với Thánh Khí:
  chỉ số của món cũ vẫn nằm trong attr.
- Kiểm tối thiểu: số dòng ≤ `holeNum`, value trong range, rainbow value 0. Không chặn hay cảnh báo
  thêm (gacha, rainbow trên món phẩm thấp vẫn có). Nếu engine throw thì mới xem lại.

### UI ([web/setup/sections/hero-detail.js](../../web/setup/sections/hero-detail.js))

- Tab **Hero detail** nằm cạnh tab Summoner. Có 5 section ứng với 5 vị trí bên Teams. Tab này chỉ
  dùng để tùy chỉnh Thần Khí.
- Mặc định mỗi hero dùng món trong capture. Tick **Tùy chỉnh** thì section mở ra ngay, điền sẵn
  món trong capture (hero không có món thì bắt đầu ở Tím stage 1). Chỉ sau khi tick mới xuất hiện
  icon accordion. Hero không có Thần Khí hoặc ô chưa chọn hero thì section mờ, không có checkbox.
- **Không hiện tên món, tên skill hay mô tả**, kể cả với rainbow. Người dùng tự tra trong game,
  app không thay thế game. Ngoại lệ: dropdown buff đội dùng tên dòng (vd "Tăng ST Đội Chiến Đấu"),
  vì không có tên thì không phân biệt được 10 family. Rainbow dùng tên skill của hero (vd "Ma Lâm Thiên Hạ"), vẫn không có mô tả.
- Dropdown **Phẩm món** (Không đeo/Tím/Cam/Đỏ/Vàng; Không đeo = `artifact: null`), rồi dropdown **Stage** (số stage theo phẩm, xem bảng
  Quy tắc config).
- Bên dưới có đúng `holeNum` ô. Mỗi ô có dropdown **loại** (Buff đội / Skill rainbow); ô chưa chọn
  thì để trống (không đưa vào `battleEntryInfos`).
  - Buff đội: chọn family, rồi **phẩm dòng** (chỉ liệt kê các phẩm family đó có), rồi slider.
    Range slider đổi theo phẩm dòng đã chọn. Chọn family hoặc phẩm dòng thì value về max.
  - Rainbow: chọn 1 trong 3, không có slider (value 0).
- Đổi stage hoặc phẩm làm giảm số ô thì bỏ các ô cuối, không thông báo.

Thứ tự làm:
1. ~~Profile + `applyArtifact`~~ (xong). Đã kiểm trên trận thật:
   - Stage 314 `6af6d367…`: dựng lại 5 món capture từ profile → replay TIER1/TIER2 MATCH.
   - Stage 51 `6af2ab8a…`, lắp `10806003` + `80003005: 704` cho Hắc Lữ Bố → thẻ roll ra
     `300002013`, `400012013`, `400022013`, không còn bản cơ bản. Thêm rainbow `80000208` →
     thẻ Thức Tỉnh `700005013` thay `700004013`.
2. ~~UI tab Hero detail~~ (xong).
3. Kiểm bằng hình các rainbow passive (`80000108`, `80000308`) trong trận.

## Còn mở

- Buff cùng family trên hai hero khác nhau có cộng dồn không (xem mục Luồng trận).
- Công thức server quy đổi dòng chỉ số % (`2010001`) vào `hero.attr`.
- Ràng buộc roll thật: phẩm dòng so với phẩm món, rainbow trên món đỏ, thuật toán RNG.
