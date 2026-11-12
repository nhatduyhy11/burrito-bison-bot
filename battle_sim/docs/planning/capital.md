# Capital battle (魔都争夺战 / GuildNavalWar)

Tra từ bundle `main.1377a` + config `sea_65380`, capture `events-runner-20261112-105619.jsonl`
(trận `6af53985…`, level 51701). Index: [research.md](research.md).

## Nhận diện

- `battleType 21` = `EBattleTypeGuildNavalWar`, UI `GuildPVP*`, director `BattleTDGuildPVPDirector`
  (kế thừa `BattleTD4Pick2Director`), room `GuildPVPBattleRoom`, frame sync `Local` như campaign.
- Bản tháng/liên server là `battleType 42` `GuildNavalWarMatch` (`GuildPvpPromotion*`), bảng riêng
  `GuildNavalMonthwar*LO`. Chưa capture.

## Level → config

`level = day*10000 + pos*100 + index`. Client tra `GuildNavalWarLO.get(day*10000 + pos*100)`:
**`index` bị bỏ qua**. `day = GetGuildNavalWarInfoR.day + 1` (`GuildPVPModule.matchDay`).
Sự kiện chạy 7 ngày (`endDt - startDt = 604800`). Capture Thứ 5 server trả `day 4` → bảng day 5.

`GuildNavalWarLO` có 133 dòng = 7 ngày × 19 phòng. Chỉ 4 trường khác nhau giữa các dòng:
`round`, `showCreep`, `battleGroundCode`, `id/day`. Mọi dòng giống nhau:
`limitTime 180`, `roundNum 20`, `initialNum 5`, `initBuild`, `bornPos`, level quái
(thường/elite atk 200 life 400 def 250, boss atk 300 life 400 def 250), `bossHPCount 1`,
mọi `attr_*` = 0. 133 `battleGroundCode` đều trỏ cùng map `ghz_ghz_001`.

## Loại phòng (GuildNavalWarMapLO)

| pos | Phòng | bedSpace | efficiency |
|---|---|---|---|
| 1–12 | Basic Soulite Hall | 2 | 120 |
| 13–18 | Standard Soulite Hall | 3 | 240 |
| 19 | Top Soulite Hall | 4 | 480 |
| 20–22 | Base (căn cứ 3 guild) | 0 | 0 |

Phòng to/nhỏ **không đổi chỉ số trận**. Chỉ đổi số chỗ ở và sản lượng. `additionMaps`
(+50% ở một số pos) cũng chỉ nhân sản lượng. Pool boss nghiêng theo cỡ phòng nhưng không
có quy tắc cứng (xem bảng boss).

## Boss

Boss là round `roundType 3` spawn ở giây 1. Life `upAttr 1e15` × 400. Sim đo được máu
4e17, atk 315, armor 500, giống nhau ở mọi phòng. Boss mất ~1,4e10 máu/s với account test.
Cả 17 boss trong round table có passive `10001405000` "Boss Death Immunity": không thể chết,
**về 1% máu thì hồi đầy**. Đây là lý do có người báo "giết được rồi boss hồi sinh". 16/17 boss
có `10001201000` "Immune to %DMG" (sát thương theo % máu không ăn).
`bossHPCount 1` / `bossProgress` chỉ là UI (số vạch thanh máu, mốc thanh tiến độ).
Trận là đua sát thương 180s (`getResultByEndReason` luôn Win; `QuitRoom.totalHurt`).
Ai cùng đánh một phòng thì so sát thương để chiếm phòng (chuỗi trong `GuildPVPChallengeView`).
Atk boss = `upAttr[1]` × 300 (1.05 → 315). Máu quái thường tăng theo round:
`lifeRatio` 1× → 300× (round 18–20), mini boss (`roundType 4`) ở round 4/9/14.

14 boss bản tuần, số lần xuất hiện trên 133 (ngày, phòng):

| Code | Tên EN / VI | Lần | Phòng (B/S/T) | Yếu / kháng / đặc tính |
|---|---|---|---|---|
| 70070101 | Cursed Botchling / U Linh Nhi | 5 | 5/0/0 | không yếu; HP thấp thì rage tăng ASPD |
| 70070201 | Masked Spirit / Mặt Nạ Oán Linh | 24 | 22/2/0 | yếu Bleed; kháng Burn (Burn có thể hồi máu) |
| 70070301 | Voodoo Doll / Búp Bê Hắc Ám | 16 | 16/0/0 | yếu Paralysis; kháng Bleed/Frost; bị Knockback +25% RES |
| 70070401 | Hell Flytrap / Hắc Hoa U Vực | 16 | 10/6/0 | yếu Burn; kháng Paralysis; immune Stun |
| 70070501 | Master Dread / Tâm Khiếp Giả | 5 | 5/0/0 | yếu P.DMG; dính M.DMG thì miễn dmg 4s (cd 10) |
| 70070601 | Lady Boggart / Hắc Ám Phu Nhân | 19 | 10/9/0 | yếu M.DMG; né 25% P.DMG; khiên 10 hit mỗi 15s |
| 70070701 | Rotten Butcher / Tàn Đao Giả | 9 | 7/1/1 | yếu Bleed; Burn −100% và hồi máu |
| 70070801 | Doom Doll / Búp Bê Diệt Phạt | 12 | 4/7/1 | yếu Paralysis; Bleed −100%; Knockback +50% miễn dmg |
| 70070901 | Abyss Flytrap / Liên Hoa Hắc Vực | 8 | 3/4/1 | yếu Burn; Paralysis −100%; immune Bleed |
| 70071001 | Mummy Pharaoh / Cổ Thi | 1 | 0/0/1 | yếu P.DMG; dính M.DMG thì miễn dmg 6s |
| 70071101 | Nether Boggart / U Ảnh Phu Nhân | 9 | 1/7/1 | không yếu; khiên 15 hit mỗi 10s |
| 70071201 | Xenoqueen / Nữ Hoàng Alien | 2 | 1/0/1 | yếu Paralysis; chặn đạn; gọi 5 rắn |
| 70071301 | Grudge Cauldron / Oán Khí Chi Oa | 2 | 0/2/0 | yếu Bleed; hồi máu khi quái gần chết |
| 70071401 | Faceless Chomper / Vô Diện Giả | 5 | 0/4/1 | yếu Burn; mỗi 10s stun mọi hero 5s |

B/S/T = Basic/Standard/Top. Toàn bộ lịch (ngày, pos) → boss: script dump ở scratchpad
phiên 2026-11-12 (đọc `GuildNavalWarLO.round`, lấy round `roundType 3`).

Round table còn 3 boss không phòng nào dùng ở bản tuần: Headless Reaper `70072401`,
Maniac Clown `70072501`, Night Haunter `70072601`. Bản tháng (`GuildNavalMonthwarLO`, 402 dòng,
key `subType*1e6 + day*1e4 + pos*100`, `subType` chọn theo `GuildNavalMonthwarControlLO`)
dùng 27 boss, gồm cả 3 boss trên.

## Creep đi kèm

Không random. `showCreep = [boss, creepA, creepB, creepC]`, và `round` là hàm thuần của
`showCreep`. Mỗi (ngày, pos) có một preset cố định: 3 loại creep × 20 round mỗi 10s, mini
boss (`…02`) ở round 4/9/14. Chỉ vị trí spawn là random (RNG có seed). 71 preset trên 133 dòng.
Mỗi boss có 1–11 preset (Masked Spirit 11, Mummy Pharaoh và Grudge Cauldron 1).

Máu creep = 10 × 400 × `lifeRatio` (1× → 300×), tối đa ~1,2M. So với sát thương lên boss thì
không đáng kể (sim: `totalHurt` 756,25e9, boss mất 756,03e9). Creep vẫn ảnh hưởng gián tiếp:
- kinh tế: mỗi kill `killerBonus_pve 25`; Thief Zombie trộm Banknote, Antenna Zombie trộm
  Spark, Deathbringer giảm sản lượng khi có trên 8 con;
- chắn đạn bắn vào boss: Shield Zombie, Bell Zombie (chặn đạn xuyên), Coffin Zombie (chặn 10 hit);
- đánh Door/hero.

## Thay đổi theo thời gian

- Lịch boss cố định theo (ngày trong tuần sự kiện, pos). Tuần nào cũng lặp lại, trừ khi
  config đổi. Code không có chiều tuần: client tự dựng `level` từ `matchDay` (server `day`)
  và pos, rồi tra bảng local. Server chỉ góp số `day`.
- `config.65380.bin` có Last-Modified 2026-11-06 trên CDN. Tuần sự kiện bắt đầu 2026-11-09,
  nên mới quan sát được 1 tuần trên config này. Chưa có config cũ để so.
- Cách xác minh: (1) mỗi khi capture có `configVersion` mới, diff 3 bảng
  `GuildNavalWarLO/RoundLO/MapLO` với bản cũ; (2) capture `GetGuildNavalWarInfoR` ở cùng thứ
  của tuần sau, xem `day` có giữ nguyên không.
- Chỉ số và lịch chỉ đổi khi có `configVersion` mới (patch). Server có thể gửi
  `s2c.curLife` (máu boss còn lại) vào `getTemplateInfoCfg`. Capture này `curLife` rỗng.

## Mô phỏng

- `replay.js` đã chạy được trận này. Wave schedule 354 spawn và RNG 8/8 khớp (tier2 MATCH).
  Tier1 lệch vì người chơi bỏ cuộc ở frame 211 nhưng replay chạy tiếp tới khi Door chết. Cần
  dừng replay tại `QuitRoom.endFrame` khi `resultReason = Abandon` (lỗi này có cả ở campaign).
- Trang setup: mục "Màn chơi" → Mode "U Đô" → Boss → Bộ quái. Data lấy từ `capital`
  trong `web/dict/map-dict.json` (`gen_profile_dict.js`, tách riêng khỏi `profile-dict.json`). Profile ghi `map: {mode: "capital", boss, level}`.
  `web/battle/map-profile.js` đổi `battleType` thành 21, đặt `level`, và chỉ giữ người chơi đầu tiên
  (capital không có robot). Capture gốc là campaign hay capital đều dùng được. Campaign thì bắt
  buộc capture gốc là campaign.
- View trận U Đô là prefab `guildPVP/prefabs/battleTDGuildPVPView`. Prefab này tham chiếu chéo
  vài hình/spine trong bundle `worldBoss` và `climbTower`, nên Cocos tự tải cả hai khi mở view.
  Vì vậy `scripts/mirror.js` có thêm 3 bundle này (~16 MB, file tĩnh công khai). Logic trận không
  cần chúng: replay/sim Node chạy được mà không có.
- Đã chạy sandbox (2026-11-12): bảng "Tranh Đoạt U Đô" hiện boss + 3 quái, chọn hero xong thì
  trận chạy, có thanh máu boss, "Tích lũy ST" và "Thống Kê ST".
- Engine tự làm phần còn lại: đặt 5 hero, dựng `initBuild`, sinh boss và quái theo preset, rồi
  kết thúc ở 180s (`TimeArrived`, Win). Sim Node (bỏ op ready 1 và 3) cho thấy: không thao tác gì
  thì Door vỡ ở ~102s (`GroupAllDead_0`).
- Cần thêm 1 capture đánh đủ 180s (không bỏ cuộc) để xác minh tier1 và `UpdateDamage`.

## Mở

- Quy tắc `day` của server: Thứ 5 trả `day 4`, không khớp cách đếm từ Thứ 2 = 0. Cần thêm
  capture ở ngày khác để chốt.
- `bossProgress [1,21,41,61,81]` → `moduleConfig.timeCfg`: chưa tra ý nghĩa (nhiều khả năng là
  mốc thanh máu/tiến độ boss trên UI).
