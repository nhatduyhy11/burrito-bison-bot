# Boss (mini / final)

Status 2026-11-10: xác minh runtime 1 map thắng (Stage 51, runner automap).
Main doc: [README.md](README.md). Wave: [creep_waves.md](creep_waves.md). Spin: [spin.md](spin.md).

## Kết luận

Boss là creep bình thường trong lịch quái do client sinh — **không có packet server riêng**
cho boss xuất hiện / chết. Mini và final boss chết đều mở spin qua cùng một đường
(`killedTrigger: OpenWheel`), spin của final boss **không có gì đặc biệt**.

## Mini boss

- Biến thể `CreepLO` code `…02` (`type 2`, tag `ElitePro|Boss`), cùng model với quái thường
  nhưng `fightScale 150`, life ×12.4, kháng/điểm yếu riêng (`specialAttr`).
- Stage 51: 3 con ở round 4/9/14 (frame 800/1800/2800), spawn tại born point thường.
  Bị giết frame 1197 (Gorilla), 2286 (Yeti), 3279 (Bell).

## Final boss

- Stage 51: Doom Doll `10070801` (`type 3`, tag `Boss|BigBoss`, model `Boss_012`, speed 90,
  `upAttr` atk×1.05 life×10, kháng Bleed/Frost/Frozen/Pull, yếu Paralysis).
- Spawn **frame 200** tại điểm riêng (1863, −2277) — phía đông, cùng chỗ "Enemy Fountain"
  `10080106` (`Witch_Building`, life ~2e9, không AI di chuyển) = căn cứ địch. Quái thường
  thì ra từ vùng phía trên (x 253–943). Hướng boss = từ căn cứ địch, cố định theo map.
- Bị giết frame 3898 (sau round 19), spin như mini boss; thắng khi hết round 20 và
  `EnemyAllDead` (frame 4469).

## Đo thực tế (Stage 97, Mummy Pharaoh `10071001`, tracker `boss.track`)

Tick = 0.1s. Boss tạo ở tick 279 (schedule frame 200) tại căn cứ giữa map (1863, −2047),
cạnh Enemy Fountain. Base player (camp 1): door (2484, −3496), bed (2346, −3770).

| tick | sự kiện |
|---|---|
| 279 | Boss spawn ở căn cứ giữa |
| 284 → ~1450 | Đi vòng săn base robot (camp 7–11) |
| ~1500 → 3682 | Đứng yên ở căn cứ (1810, −2035) |
| **3682** | Bắt đầu đi về base player = spawn + **340.3s** → khớp `init_cd 340` tính từ lúc spawn ("Boss Invasion!") |
| 3682 → 3849 | Đi **thẳng** tới cửa player, ~1480 đơn vị trong 16.7s ≈ 88.6 đ/s (≈ `speed 90`), không vòng, không teleport |
| 3849 → 3877 | Đứng cách cửa 113 đơn vị đánh cửa; chết ở tick 3877 |

- Không có cú nhảy vị trí nào (> 250 đơn vị / 0.5s) trong cả trận, dù boss có tag
  `Can_Teleport`.
- Kết luận: mốc giờ trong buff tính **từ lúc boss spawn**, không phải từ đầu trận.
- Lúc "Boss Invasion!" boss luôn đứng ở căn cứ (pha `Boss_Ready` có miễn dmg Fountain) →
  quãng đường = đường thẳng từ căn cứ tới cửa phòng player → **tính được**:
  `t_đến ≈ dist(căn cứ, cửa phòng player) / speed_boss` (speed `CreepLO.speed` ≈ đ/s).
  Không cần đổi vị trí base để đo; tọa độ cửa từng phòng lấy từ `unit.created` (Door) hoặc
  tilemap.
- Simulator: tại "Boss Invasion!" (spawn + 340s) có thể cho boss đi thẳng với speed config
  (hoặc teleport sau `t_đến`); base nào bắn được trên đường = base có tầm phủ đoạn thẳng
  đó (cần tầm bắn của tháp — chưa đo).
- Dump: `.tmp/battle_research/creepinfo-stage97.json`, tracker trong
  `events-runner-20261110-122739.jsonl` (trận thứ 2).

## Timeline final boss (từ code + config)

Hành vi boss = passive skill theo mốc giờ (`CreepLO.pSkills` 10001501000…10001506000),
không phải AI tự do. Buff `TICKED` có `init_cd` tính từ lúc buff gắn (giả thuyết: lúc boss
spawn frame 200 → cộng 20s; khớp nhãn action "360s Boss" và `bossProgress [100,180,280,360]`).

| Mốc (battle s) | Nguồn | Hành vi |
|---|---|---|
| 0 → 20 | `TDBossWaitTimeWidget`, `AdventuretdLevelLO.bossWaitTime = 20` | Banner "<boss> 已出现，即将行动" + đếm ngược 20s (từ op StartCreep). Hết giờ → `GhostTimeDone` + chuông |
| 20 (frame 200) | waveSchedules `3038001` | Boss spawn ở căn cứ địch (1863, −2277) |
| 20 → 340 | action `Custom_AI_Search_Robot` | **Săn base robot đồng đội**, không phải player. Buff `10001502000` (`When_Blood_Reduce_Target_Percent [30]`, IMMORTAL, cd 10): HP < 30% → bất tử/không chọn được 10s rồi quay lại săn robot |
| 340 (init_cd 320) | buff `10001503000` group `Boss_Ready` | Unstoppable + miễn dmg Fountain + Untargetable 20s |
| 360 (init_cd 340) | `10001505000` + `10001506000` → `10001506100` | Hồi đầy máu; gỡ các miễn nhiễm; buff `Player_Search_AI` với `msg: "Boss Invasion!"` = thông báo trong game → **bắt đầu đi tới base player**, có thể bị đánh trên đường |

Hệ quả cho simulator:
- Mọi sát thương lên boss trước 360s bị xóa bởi hồi đầy máu → bỏ qua được (trừ khi boss chết
  trước 360s — chưa thấy).
- "Teleport khi có thông báo" = teleport lúc `Boss Invasion!` (360s) — bỏ mất đoạn đường
  từ vị trí boss lúc đó tới base player, đoạn này base trên đường **có** bắn được boss.
- Đường đi do pathfinding của engine trên tilemap + vị trí boss lúc 360s (phụ thuộc trận
  săn robot) → deterministic nhưng không tính tay được; logic sim chạy code gốc sẽ tự ra.
  Đo thực tế: tracker `boss.track` (vị trí/HP mỗi ~0.5s) + `unit.created` (vị trí building
  mọi phe) trong `extra_hooks.js`.

## Spin của boss

| frame | boss | lifeRatio | trúng |
|---|---|---|---|
| 1200 | Gorilla (mini) | 10000 | 400011001, 250010004 |
| 2290 | Yeti (mini) | 4794 | 400021001 |
| 3280 | Bell (mini) | 5340 | 400021013 |
| 3900 | Doom Doll (final) | 10000 | 400031003 |

- Cùng config `BuildRefreshEliteLO` (mọi index giống nhau: 8 ô, `refreshType [1,2,3,4,6,7]`).
  Ô về sau "xịn" hơn chỉ vì pool lọc theo level build hiện tại.
- `lifeRatio` = máu cửa ×10000 → ảnh hưởng filter `lifeRatio` của `BuildSummonLO`.
- Port `sfc32` tính lại số ô trúng 2/1/1/1 — khớp game.

## Mở

- Tầm bắn: có sẵn trong config — `SkillBaseLO.ranges` `[min, max]` (cùng đơn vị tọa độ map;
  `pvp_ranges` cho PvP). Skill của hero lấy từ `StartGameP.playerInfos[].heros[].skills`.
  Đội test: Hanuman / Archangel / Bride Wraith 540, Lu Bu 720, Frosthealer 9999 (heal,
  target SELF). Base bắn được boss trên đường ⇔ khoảng cách từ vị trí build hero (op `建造`
  `{x,y}`) tới đoạn thẳng căn cứ→cửa ≤ `max`. Chưa xét trap/organ (`organSkills`).
- Vì sao boss đứng yên ở căn cứ từ ~tick 1500 (hết robot để săn? Boss Flee?) — không ảnh
  hưởng vì hồi đầy máu lúc invasion.
- Map khác: boss/vị trí có đổi theo `battleGroundCode` không.
