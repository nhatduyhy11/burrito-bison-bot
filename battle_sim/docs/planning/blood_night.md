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
- Trong capture, `playerInfos[1]` là bản sao đội hình đội trưởng (cùng hero/organ/antique,
  cùng `support.uuid`), chỉ khác `attr` của hero và `playerId`. Vì người xem không xây gì nên
  dữ liệu này không ảnh hưởng trận.

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

- Mirror thiếu bundle view `teamExpeHigh` (404 `assets/teamExpeHigh/{config,index}.0ba3f.js`)
  → thêm vào `BUNDLES` của `scripts/mirror.js` như `guildPVP`/`worldBossMatch`. Bundle có thể
  tham chiếu chéo bundle khác.
- `TeamExpeHighModule.battleRecived` chỉ vào trận nếu `amILeader()`, và đọc
  `teamInfo.team.members`. Sandbox cần một đội giả cục bộ (đội trưởng = mình, thành viên lấy
  từ `playerInfos`). Đã thử bản đầu trong `web/battle/setup.js` `ensureTeamState()`: qua được
  bước vào trận, sau đó đứng vì thiếu bundle ở trên.
- Setup UI chưa có mode này (`web/setup/capture.js` chỉ phân biệt campaign / capital).
