# Boss (mini / final)

Xác minh runtime 2026-11-10 (Stage 51, Stage 97). Index: [research.md](research.md).
Wave: [creep_waves.md](creep_waves.md). Spin: [spin.md](spin.md).

## Kết luận

Boss là creep bình thường trong lịch quái do client sinh — **không có packet server riêng**
cho boss xuất hiện / chết. Mini và final boss chết đều mở spin qua cùng một đường
(`killedTrigger: OpenWheel`), spin của final boss không có gì đặc biệt.

## Mini boss

- Biến thể `CreepLO` code `…02` (`type 2`, tag `ElitePro|Boss`), cùng model với quái thường
  nhưng `fightScale 150`, life ×12.4, kháng/điểm yếu riêng (`specialAttr`).
- Spawn tại born point thường theo lịch (`roundCode 4xxxxxx`, xem [creep_waves.md](creep_waves.md)).

## Final boss

- Stage 51: Doom Doll `10070801` (`type 3`, tag `Boss|BigBoss`, model `Boss_012`, speed 90,
  `upAttr` atk×1.05 life×10, kháng Bleed/Frost/Frozen/Pull, yếu Paralysis). Stage 97: Mummy
  Pharaoh `10071001`.
- Spawn ở frame 200 tại căn cứ địch, cạnh "Enemy Fountain" `10080106` (`Witch_Building`, life
  ~2e9, không AI di chuyển). Quái thường thì ra từ vùng phía trên (x 253–943).
- Có tag `Can_Teleport` nhưng không thấy cú nhảy vị trí nào trong cả trận.

## Timeline final boss

Hành vi boss = passive skill theo mốc giờ (`CreepLO.pSkills` 10001501000…10001506000),
không phải AI tự do. Buff `TICKED` có `init_cd` tính **từ lúc boss spawn** (frame 200 = 20s
battle), đã đo ở Stage 97: boss bắt đầu đi ở spawn + 340.3s.

| Mốc (battle s) | Nguồn | Hành vi |
|---|---|---|
| 0 → 20 | `TDBossWaitTimeWidget`, `AdventuretdLevelLO.bossWaitTime = 20` | Banner "<boss> 已出现，即将行动" + đếm ngược 20s (từ op StartCreep). Hết giờ → `GhostTimeDone` + chuông |
| 20 (frame 200) | waveSchedules `3038001` | Boss spawn ở căn cứ địch |
| 20 → 340 | action `Custom_AI_Search_Robot` | **Săn base robot đồng đội**, không phải player. Buff `10001502000` (`When_Blood_Reduce_Target_Percent [30]`, IMMORTAL, cd 10): HP < 30% → bất tử/không chọn được 10s rồi quay lại săn robot. Hết robot để săn thì đứng yên ở căn cứ |
| 340 (init_cd 320) | buff `10001503000` group `Boss_Ready` | Unstoppable + miễn dmg Fountain + Untargetable 20s |
| 360 (init_cd 340) | `10001505000` + `10001506000` → `10001506100` | Hồi đầy máu; gỡ các miễn nhiễm; buff `Player_Search_AI` với `msg: "Boss Invasion!"` → **đi thẳng tới cửa player** (speed `CreepLO.speed` ≈ đơn vị/s, đo 88.6 với speed 90), có thể bị đánh trên đường, đứng cách cửa ~113 đơn vị để đánh |

Mọi sát thương lên boss trước 360s bị xoá bởi hồi đầy máu.

Dump: `.tmp/battle_research/creepinfo-stage97.json`; tracker `boss.track` (vị trí/HP mỗi
~0.5s) + `unit.created` trong `events-runner-20261110-122739.jsonl` (trận thứ 2).

## Mở

- Map khác: boss/vị trí có đổi theo `battleGroundCode` không.
