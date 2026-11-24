# Tranh Bá liên server — battleType 42 (GuildNavalWarMatch)

Research 2026-11-21, bead `bbb-173`. Research ban đầu đọc capture, bundle và config. Sau đó đã triển khai catalog (bbb-1tx) và setup (bbb-svk).
So sánh với U Đô / Tranh Đoạt U Đô tuần (`battleType 21`), xem [capital.md](capital.md).

## Bằng chứng và phạm vi

- Capture `.tmp/battle_research/events-pmain-20261121-105022.jsonl`, có đủ `StartGameP` + `QuitRoom`.
- UUID `6b0115832f05ea7e79684b1d`, `battleType 42`, `level 2040401`.
- Bundle `index.7125c.js`: `2.3.1-2_E64067_P63528_C64067`; config `sea_66328`; map `trunk_61543`.
- Module tách tại `.tmp/bundle/index.7125c/modules/`. Bảng dump bằng runtime game tại
  `.tmp/battle_research/research-42-tables.json`; script `.tmp/battle_research/research-42.cjs`.
- Các file `.tmp` là cache gitignored. Tên module/method bên dưới là điểm tra lại trong bundle.

## Nhận diện và level

`EBattleTypeGuildNavalWarMatch = 42`, room `GuildPvpPromotionBattleRoom`, director
`BattleTDGuildPvpPromotionDirector`, prefab `guildPvpPromotion/prefabs/battleTDGuildPvpPromotionView`.
Director kế thừa `BattleTD4Pick2Director`, panel chọn hero chỉ đổi prefab so với panel chung.
Provider trong `BattleRoomHelper` dùng frame sync `Local`, cùng kiểu với type 21.

`GuildPvpPromotionChallengeView._onChallengeTap` dựng level:

```text
subType * 1_000_000 + ((matchDay - 3) % 7) * 10_000 + position * 100 + bedIndex
```

Room/director/provider bỏ `level % 100` khi tra `GuildNavalMonthwarLO`.
Trận này: subtype **2**, day-key **4**, position **4**, bed-index **1** → row **2040400**.
Đây là khóa ngày trong config, không phải ngày dương lịch. Room 4 là “Hồn Tinh Các Sơ”.

Config có 402 row: 3 subtype × 7 ngày × 19 phòng = 399, cộng 3 row sơ tuyển
`10000100/10000200/10000300`. `GuildPvpPromotionAuditionView` cũng vào type 42.
`GuildNavalMonthwarControlLO` có condition `[1,60]` cho subtype `[1]`, `[61,99999]`
cho `[2,3]`; chưa chốt ý nghĩa condition vì phần chọn do server cấp `myGuildWarInfo.subType`.
Không suy diễn subtype là độ khó chỉ từ các con số này.

`GuildPvpPromotionModule.getTimeState` phụ thuộc `ActivityModule` và `LoopPlayLO`;
không chỉ dựa vào thứ trong tuần. Code có stage sơ tuyển `stageDay <= 3` và các vòng sau.
Điều này phù hợp event có lịch riêng; capture hiện tại không chứa lịch server để chốt chu kỳ
tháng hay ngày mở tiếp theo. “Monthwar” là tên nội bộ, không đủ chứng minh mở hàng tháng.

## Boss và wave riêng

Toàn bộ event có **27 boss**: **24** trong vòng chiếm phòng, cộng **3** riêng sơ tuyển.
Mỗi subtype 1/2/3 dùng **19 boss**. Bản tuần có **14**; hai pool giao nhau 10 boss,
event có 17 boss không nằm trong lịch tuần, và thiếu 4 boss tuần: `70070701`,
`70070801`, `70070901`, `70071101`.

| Code | Tên VI | Pool event | Có trong tuần |
|---|---|---|---|
| 70070101 | U Linh Nhi | 1, 2, 3 | có |
| 70070201 | Mặt Nạ Oán Linh | 1, 2, 3 | có |
| 70070301 | Búp Bê Hắc Ám | 1, 2, 3 | có |
| 70070401 | Hắc Hoa U Vực | 1, 2, 3 | có |
| 70070501 | Tâm Khiếp Giả | 1, 2, 3 | có |
| 70070601 | Hắc Ám Phu Nhân | 1, 2, 3 | có |
| 70071001 | Cổ Thi | 2, 3 | có |
| 70071201 | Nữ Hoàng Alien | 1, 2 | có |
| 70071301 | Oán Khí Chi Oa | 1, 2, 3 | có |
| 70071401 | Vô Diện Giả | 1, 2, 3 | có |
| 70071501 | Ẩn Diện Kỵ Sĩ | 1, 2, 3 | — |
| 70071601 | Hắc Linh Cưa Giả | 1, 2, 3 | — |
| 70071801 | Cổ Thần | 1, 2, 3 | — |
| 70071901 | Hắc Hạm | 1, 3 | — |
| 70072001 | Hắc Nữ Tăng Ca | 1, 2, 3 | — |
| 70072101 | Hắc Trảo | 1, 2, 3 | — |
| 70072201 | Khỉ Điên Đánh Trống | 1 | — |
| 70072301 | Bạch Y Nữ | 1, 2 | — |
| 70072401 | Vô Diện Tử Thần | 1, 3 | — |
| 70072501 | Gã Hề Điên | sơ tuyển | — |
| 70072601 | Hồi Chuông Đêm | sơ tuyển | — |
| 70072701 | Đồ Tể Thối Rữa | sơ tuyển | — |
| 70072801 | Bọ Cạp Hoàng Tuyền | 1, 2, 3 | — |
| 70072901 | Khế Ước Quỷ Vương | 3 | — |
| 70073001 | Song Sinh | 2 | — |
| 70073101 | Tướng Quân Phần Cốt | 3 | — |
| 70073201 | Búp Bê Da | 2 | — |

Trận capture dùng boss **Hắc Hoa U Vực `70070401`**, đi kèm **Minh Hoa Hoán Thi `70081501`**,
**Zombie Khiên `70081601`**, **Quỷ Sai `70081901`**. Boss xuất hiện ở giây 1; preset có
20 round, mini boss ở round 4/9/14, giống cấu trúc bản tuần.

`GuildNavalMonthwarRoundLO` có 1.354 row. **Toàn bộ 1.337 row chung với
`GuildNavalWarRoundLO` giống nhau từng field**; 17 row thêm phục vụ boss khác/sơ tuyển.
Đây là lịch/pool riêng, không phải tăng hệ số toàn bộ wave so với tuần.

Cả 27 boss có passive `10001405000` “BOSS Bất Tử” (còn 1% HP thì hồi máu).
26/27 có `10001201000` miễn sát thương theo %; ngoại lệ **Vô Diện Tử Thần `70072401`**.
Không nên áp một bộ kháng chung cho tất cả boss.

## Buff / chỉ số đầu trận

Chưa tìm thấy **buff riêng tự động cộng chỉ vì battleType 42** trong đường chạy đã trace:

- `GuildPvpPromotionBattleRoom` gần như bản type 21 đổi bảng: `GuildNavalMonthwarLO/RoundLO`.
  Cùng dựng Door/Bed max, 5 hero theo `bornPos` và 8 công trình theo `initBuild`.
- Các field chiến đấu của level (ngoài id/ngày/lịch/pool/map) giống bản tuần:
  `limitTime 180`, `initialNum 5`, `initLevel`, `bornPos`, `initBuild`; quái thường/elite
  atk/life/def 200/400/250, boss 300/400/250; mọi `attr_*` trên level đều **0**.
- `BaseBattleRoom.getCreepInfos` chỉ đọc các `attr_*` này để cộng chỉ số quái;
  không có nhánh buff event riêng. Provider type 42 trả `null` cho cả
  `getRoundAttrCfg` và `getFinalAttrFixCfg`.
- Round có `attr_HeroUpStarHurtAdd` 10000 hoặc 50000, nhưng bản tuần có **cùng dữ liệu**;
  đây không phải bằng chứng về buff mới của event.
- Boss dùng chung `CreepLO` và bộ skill, không có bản clone chỉ số riêng cho type 42.
  Hắc Hoa U Vực có yếu Thiêu Đốt, kháng Tê Liệt/Đẩy Lùi/Choáng; đây là đặc tính boss.
- `StartGameP` chỉ có roster/trang bị/skin/support thông thường, không có field buff/spell
  event riêng trong trận này. Chỉ số hero do server gửi sẵn vẫn có thể đã gộp hiệu ứng;
  một capture không đủ loại trừ mọi buff từ phía server hoặc event khác.

`GuildNavalMonthwarSpellLO` có 4 thẻ: Ác Linh Xuất Thế (trục xuất), Đoạt Hồn
(trộm 30% lợi ích trong 7200s), Bảo Vệ Thanh Tẩy (bảo vệ 7200s), Thánh Quang (xóa hiệu ứng).
Đường dùng trong `GuildPvpPromotionChallengeView` là bảo vệ phòng/sản lượng/quyền khiêu chiến,
không phải cộng ATK/HP lúc vào battle. Không thấy bảng Spell được engine/room tiêu thụ.

## Replay kiểm chứng

```bash
node battle_sim/replay.js .tmp/battle_research/events-pmain-20261121-105022.jsonl
```

**TIER1 MATCH**: đúng cả 3 version, 57/57 thao tác thành công, hết ở frame 1800 = 180s,
`TimeArrived`, kill 293, `totalHurt 5265139972864`, `myTotalOutput 5190390578948`;
mọi field kết quả được replay đối chiếu đều khớp (trừ fightCap vốn được loại khỏi phép so).
Provider luôn trả Win cho type này; đây là trận đua sát thương, quyền chiếm phòng được xử lý ngoài trận.

Capture chỉ ghi StartGameP/QuitRoom; không có waveSchedule/randomCode/bossKills checkpoint.
Do đó dòng “TIER2 MATCH” của CLI **không chứng minh** các checkpoint ấy khớp: cả 3 đều `not in capture`.

## Hướng mô phỏng sau research

Engine headless replay được type 42 nguyên bản, không cần sửa logic chiến đấu.
`gen_naval_dict.js` sinh catalog riêng `naval-boss-dict.json` gồm 24 boss/399 preset vòng chiếm phòng,
giữ subtype/ngày/phòng. Từ 2026-11-24 (bbb-tlf), generator bỏ toàn bộ 3 boss và preset sơ tuyển
(subType 0); số liệu 27 boss/402 row ở phần research bên trên mô tả config game đầy đủ.
Setup có mode **Tranh Bá liên server**:
chọn boss rồi chọn preset, profile `{mode: "naval", boss, level}`. Prefill từ capture type 42
chọn đúng preset; import/export kiểm tra level thuộc boss; battle kiểm tra lại config thật.
`mirror.js` có bundle `guildPvpPromotion` và sandbox có fallback đăng ký battle config type42.
Chưa xác nhận server có gộp buff vào attr hero.


## Kiểm chứng sau triển khai (2026-11-21)

- Chạy lại Node replay trận gốc: TIER1 MATCH, 57/57 op, frame 1800.
- Browser replay đầy đủ: QuitRoom MATCH, không lỗi thao tác, lỗi module hay lỗi trang;
  0 request ngoài localhost, 0 asset 404. Report: `.tmp/battle_research/naval-browser-replay.json`.
- UI chọn Vô Diện Tử Thần `70072401`, preset `1011601` (nhóm 1/ngày 1/phòng 16),
  import/export giữ nguyên lựa chọn rồi bấm Chơi. Seed ngẫu nhiên riêng, không dùng op log gốc.
- Tự chọn 5 lượt đầu trận, đổi tốc độ và chọn vòng quay; smoke đến frame 373 (~37s),
  `totalHurt 45163503104`, không lỗi. Ảnh `.tmp/battle_research/naval-play-short.png`,
  report `.tmp/battle_research/naval-play-short.json`. Smoke ngắn, không khẳng định thắng cả trận.
- `node --test battle_sim/tests/*.test.mjs`: 23 tests pass, gồm round trip đủ 402 preset,
  chặn boss/level sai và prefill từ capture type42.
