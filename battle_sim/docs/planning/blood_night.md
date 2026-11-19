# Blood Night (组队副本血夜 / TeamExpedition16)

Tra từ bundle `index.7125c` + config `sea_66328`, capture `events-pmain-20261119.jsonl`
(trận `6afeadd7…`, level 1071, thua `GroupAllDead_0` ở giây 128). Index: [research.md](research.md).
Bead: `bbb-w0t` (epic), `bbb-x5u` (research này), `bbb-47c` (UI sandbox + test).

## Nhận diện

- `battleType 47` = `EBattleTypeTeamExpedition16`, module lobby `TeamExpeHighModule`
  (proxy `TeamExpedition16Proxy`), room `TeamExpeditionHighBattleRoom`, player entity
  `TDTeamHighPlayerEntity`, director `BattleTDTeamExpeHighDirector`, frame
  `TDBattleTeamHighFrame`, view `BattleTDTeamExpeHighView` (bundle `teamExpeHigh`).
- Bản solo là `battleType 48` `SingleTeamExpedition16` (view `BattleTDTeamExpeHighSingleView`),
  dùng cùng bảng. Chưa capture.
- Provider: `getFrameSyncType = AsynTcp` (campaign là `Local`), `needCheck = true`,
  `getResultByEndReason` rỗng. Trận vẫn **chạy hết trên client**: replay headless khớp
  TIER1 + TIER2 (`node battle_sim/replay.js <capture>`).
- Trận đi qua socket room riêng `wbattled` (`BuildRoomProxy`): `Auth` → `StartGameP` →
  `CommitOperation` (chỉ op của mình) / `UpdateDamage` mỗi ~30s / `SetSpeed`. Kết thúc vẫn là
  `BuildProxy.QuitRoom` trên socket chính như campaign.

## Level → config

`level` = id `TeamExpandLO` (1001–1080 = "Ải 1"–"Ải 80", 16 nhóm × 5 ải). Mỗi dòng có:

- `battleGroundCode` = `31000 + ải` (map riêng mỗi ải; ải 71 → `zd_xxhigh_001`).
- `round`: 94 mã round (62 mã khác nhau), tra `TeamExpandRoundLO`. `roundNum 20`.
- Level quái `atk/life/defence` × thường / elite / boss, `creep_lifeRatio` … theo round
  (`getRoundAttrCfg`). Ải 71: life thường 5.3e11, elite 2.9e12, boss 5e13 (× `lifeRatio` round).
- `bossWaitTime 10`, `bossProgress [60,110,160,200]` (mốc UI), `bossHPCount` (số vạch máu UI,
  12 ở ải 1 → 1358 từ ải 70).
- `showBoss`, `showCreep`, `winRewards`, `extraRewards` (ải chia hết cho 5), `helpRewards`
  `[[1,2,200]]` (thưởng cho người đi giúp).

## Đội và người thứ 2

- `StartGameP.playerInfos` có 2 người + `leaderId`. `initPlayerEnties` sắp xếp theo `playerId`,
  **chỉ đội trưởng chơi**: `TDTeamHighPlayerEntity.isSpectating = !isTeamLeader`, và
  `lottery`/`lotteryElite`/`createBuild` trả `{success:false}` nếu không phải đội trưởng.
- Người xem nhận camp `houseNum + 1` (capture: camp 2, bạn của camp 1, cùng địch camp 31) và
  `setReady` ngay. Không gửi op nào.
- Khi đội trưởng chọn phòng (`SetRoomId`), mọi người có `roomId 0` vào **cùng phòng**: đây
  là "giường đôi" (`moduleConfig.isDoubleBed`). Log: "阵营:2 躺下" rồi "阵营:1 躺下" cùng frame.
- Server **không** gửi attr riêng từng người. Hai `playerInfos` giống hệt nhau (chỉ khác
  `playerId`) và cùng chứa **đội hình chung của team** (`teamInfo.team.heroFormation`: 6 hero
  theo `uuid`, chọn từ hero của cả 2 thành viên). Mỗi hero mang `attr` của **chủ sở hữu**.
  Capture: đội trưởng Espada (fightCap 22.9M) + người giúp 弒神 (122.6M); 3 hero
  `50000001/03/13` là của 弒神 (atk ~1.5–1.66M), 3 hero `50000004/26/30` là của Espada
  (atk ~440–470k). `formationPlayerId`/`buildSkinPlayerId` = người giúp.
- Mỗi hero là object đầy đủ của chủ (`skills` gồm cả Thánh Khí/Dị Vật/Dị Năng, `avatarCodes`,
  `relic`, `artifact`, `attr` 34–41 key), **giống hệt** bản trong `refreshMemberInfosR` của chủ,
  chỉ khác `attr[6]` 100 → 0 và thêm `attr[10162] = 0`. Không có bước gộp/nhân attr theo đội:
  server chỉ chọn object hero đã gộp sẵn (gear, Thánh Khí, trang bị… như campaign).
- Phần không phải hero lấy từ ai (so với `refreshMemberInfosR` và campaign 11-18 của Espada):
  - Từ acc giúp (`formationPlayerId`): `support` (hero 50000031), `summonerInfos` (3 derma
    `dermaFormation` 20208/20210/20218, level theo `dermaList` của acc giúp; chỉ có
    `{code, level}`, không attr), `organs`, `daoists`, `summonCreatures`, `skinInfos`
    (`buildSkinPlayerId`).
  - Từ đội trưởng: `trainingInfos`, `mounts`/`mountCode`, `goldenSkinsCount`, `antiques` (khớp
    campaign trừ vài món đã nâng cấp sau đó).
  - `builds[].skills` theo `teamInfo.team.equipSkills` (cài đặt của đội), có cả 3 skill trang bị
    `9000x00000`. `builds[type 1].attr` khác campaign (HP 25665 vs 23991), chưa rõ nguồn.
- Vì chỉ đội trưởng chơi, sức mạnh của acc giúp vào trận qua các hero của nó trong đội hình đội
  trưởng. Replay từ `StartGameP` đã có đủ attr; setup UI muốn sửa thì phải biết hero nào của ai
  (lấy từ `refreshMemberInfosR.members[].moduleDatas.heros`).

## Luật riêng của mode

- Giường mode 47/48 có thêm skill `71000000001` "Phô Trương": chi phí tăng cấp và xây dựng
  công trình −50%. Model giường đổi `_cp` → `_srcp` (giường 2 người).
- View có virtual joystick (`RoleMoveSpeed`) cho nhân vật đội trưởng; người xem bị tắt joystick.
- Thua khi mất cửa: `GroupAllDead_0` = nhóm 0 chỉ có cửa của đội trưởng.

## Lịch quái (ải 71)

10 frame = 1 giây. 234 lượt spawn, từ frame 200 tới 2080.

| Frame (giây) | Round | Quái |
|---|---|---|
| 200 → 2080 | `1xxxxxx` | 3 loại quái nhỏ: La Hán Thô Tục `61083501`, Dị Thể Suy Tàn `61082901`, Tà Linh Ngoại Lai `61083701` |
| 400 (40s) | `4034004` | Mini boss `61083502` (life ×1.6) |
| 900 (90s) | `4028009` | Mini boss `61082902` (life ×3.3) |
| 1400 (140s) | `4036014` | Mini boss `61083702` (life ×5.5) |
| 1900 (190s) | `3024001` | Final boss Vô Diện Tử Thần `61072401` (`Boss_026`, life ×8.5, ~5e14) |

Passive boss: Boss Tập Kích một lần khi xuất hiện, ST elite/boss +200%, Bạo Nộ ở giây 120
(+100% chính xác, kháng khống chế), kháng Thiêu Đốt và Dịch Chuyển. Quái nhỏ ưu tiên đánh
người chơi và có "Diệt Nhanh Anh Hùng".

Boss của 80 ải lấy từ một pool ~20 boss `6107xx01` (U Linh Nhi, Tàn Đao Giả, Liên Hoa Hắc
Vực, …, Song Sinh, Khế Ước Quỷ Vương). Tra lại bằng `TeamExpandLO.showBoss` khi cần.

## Việc cho sandbox (bbb-47c)

- Mirror: đã thêm `teamExpeHigh` + `teamExpe` (tham chiếu chéo) vào `MODE_BUNDLES[47]` của
  `scripts/mirror.js`. Replay có hình hết 404 và khớp `QuitRoom`.
- Còn lỗi `p.speed is not a function` trong `_popAMsg` (~giây 66) sau `SetSpeed` trên
  `GameRoomSocket` (stub). Trận vẫn chạy tới cuối và khớp.
- `TeamExpeHighModule.battleRecived` chỉ vào trận nếu `amILeader()`, và đọc
  `teamInfo.team.members`. Sandbox cần một đội giả cục bộ (đội trưởng = mình, thành viên lấy
  từ `playerInfos`). Đã thử bản đầu trong `web/battle/setup.js` `ensureTeamState()`: qua được
  bước vào trận, sau đó đứng vì thiếu bundle ở trên.
- Setup UI: mode Đêm Đỏ + Teams Master/Guest, thiết kế ở [blood_night_setup.md](blood_night_setup.md).
