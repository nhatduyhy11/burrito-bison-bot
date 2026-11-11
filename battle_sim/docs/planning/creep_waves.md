# Creep waves (lịch spawn quái)

Xác minh runtime 2026-11-10 (Stage 51, uuid `6af2ab8a2f05ea3f58336962`). Index:
[research.md](research.md). Boss: [boss.md](boss.md).
Dump: `.tmp/battle_research/creepinfo-6af2ab8a2f05ea3f58336962.json`.

## Kết luận

Toàn bộ lịch quái (ai, khi nào, ở đâu, chỉ số) **client tự sinh 1 lần ở frame 150**, server
không gửi. Có `StartGameP` + config là tái tạo được (logic sim khớp 425/425 spawn).

## Sinh lịch

- Khi người chơi thật được set phòng (`AdvBattleRoom.setRoomId`, frame 150 sau settle), client
  commit op `CreepInfo` ("怪模板广播") gồm `waveSchedules` + `templateInfos`.
- Nguồn config: `AdventuretdLevelLO.get(level*10)` + `AdventuretdRoundLO.store` →
  `BaseBattleRoom.getTemplateInfoCfg` / `getWaveSchedule`.
- `templateInfos[]{creepInfo{code, attr}}`: 1 template / loại creep (Stage 51: 8). Chỉ số =
  `CreepLO` (`upAttr` × hệ số `attr_*` của level, speed, energy…) + CritHurt 5000,
  BlockIgnoreHurt 3000 mặc định.
- `waveSchedules[0].creepSchedule{frame: [{roundCode, code, roundIndex, frame, x, y}]}`.
  Vị trí = phần tử random (`randSeed.next`) trong born points của room
  (`tileMapData.getAllBornDataByRoomId(posSet[room-1])`) → mỗi con 1 điểm, lặp lại được.

## Cấu trúc Stage 51 (quan sát)

- 20 round, mỗi 200 frame: frame 200, 400, … 4000; trong round các con cách nhau 40 frame.
  1 frame = 0.1s.
- `roundCode` = `<nhóm><loại 3 số><round 3 số>`:
  - `1xxxxxx`: nhóm chính 5 con/round (10 con từ round 10–15 trở đi).
  - `2xxxxxx`: 1–2 con lẻ cùng frame đầu round.
  - `4xxxxxx`: mini boss — round 4 (frame 800), 9 (1800), 14 (2800).
  - `3038001`: final boss, frame 200. `9006000`: "Enemy Fountain", frame 200.
- Loại quái thêm dần: `10080901` Gorilla (từ r1), `10081101` Yeti (r3), `10081801` Bell (r6).
- Quái thường: atk 410 / life 19920; mini boss (`…02`) life 247750 (×12.4).
- Born points quái thường: x 253–943, y −1173…−1449 (1 vùng phía trên phòng, phòng ở
  y≈−2068). Boss/Fountain: điểm riêng ở căn cứ địch (1863, −2277).
- Kết thúc: "所有波已结束" sau round 20 → `EnemyAllDead` → thắng ở frame 4469 (~446s).
  `QuitRoom.extra.type2KillNum` `{6:1, 8:3, 9:421}` = boss / mini boss / thường.

## Mở

- Map `AdventuretdRoundLO` ↔ roundCode chi tiết; born point theo room khác nhau (robot room).
