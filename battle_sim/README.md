# battle_sim — headless campaign battle (mốc A)

Chạy trận campaign offline trong Node bằng chính code logic của bundle game
(`TDServer` + `BattleEngineDelegate` + engine `battleground`), không render, không mạng.
Nghiên cứu nền: [docs/planning/battle_sim/](../docs/planning/battle_sim/README.md).

## Cần có (không commit, nằm trong `.tmp/`)

| File | Lấy từ |
|---|---|
| `.tmp/bundle/main.1377a/index.1377a.js` | `scripts/bundle/fetch_bundle.py` |
| `.tmp/battle_research/data/config.65380.bin`, `preload_config.65380.bin` | `https://mg-sea-cdnres.bighost.games/sea/remoteConfig/sea/<file>` |
| `.tmp/battle_research/data/maps/*.json` | `tools/fetch_bundle_imports.py battle <hash> <dir>` → `tools/extract_maps.py` |
| capture `events-*.jsonl` | `.tmp/battle_research/run_runner_hooked.py` (runner + research hook) |

Bundle hash, config version phải cùng đợt deploy với trận được capture
(`StartGameP.battleVersion/configVersion`).

## Chạy

```bash
node battle_sim/replay.js .tmp/battle_research/events-runner-20261110-122739.jsonl 6af2ab8a2f05ea3f58336962
```

`MAX_TICK` (env, mặc định 6000) giới hạn số tick. Trận ~4400 tick chạy ~30s.

Output: kết quả sim + so sánh với game
- **TIER1**: `QuitRoom.extra` (result, resultReason, killNum, type2KillNum, totalHurt,
  totalOutput…) + endFrame (thua: game gửi endFrame 0 → so `totalTime`).
- **TIER2**: lịch quái (`waveSchedules`), mọi lần `randomCode` (option summon, 8 ô spin),
  tick chết của boss/mini boss.

## Cấu trúc

- `lib/bundle_loader.js` — nạp bundle vào `vm` context, thay loader browserify bằng bảng
  module + `require` lười; áp patch `JSON.parse` giống `Main.onLoad` của game.
- `lib/stubs.js` — `cc.*`, `window`, `i18n` tối thiểu cho closure logic.
- `lib/config_loader.js` — `QuickLZ` → `BinaryReader` → `ConfigParser` / `PreloadConfigParser`.
- `lib/proto_rebuild.js` — dựng lại message proto thật (List/Dictionary) từ JSON capture theo `*_Def`.
- `lib/sim.js` — `Sim`: setup `StartGameP`, map Tiled, delegate; `run(ops)` áp op theo `operFrame` rồi `logicTick`.
- `lib/checkpoints.js` — recorder tier 2 trong sim + trích từ capture + so sánh.
- `tools/` — tải import của bundle, tách map/tileset.

## Ghi chú

- Op được áp **trước** `logicTick` của tick bằng `operFrame` (đúng như chế độ `Local`:
  UI gọi `TDServer.handleClientRequest` ngay tại `curFrame`).
- Không cần chạy director/UI: mọi op game tự sinh (goToBed, mở spin, robot) đều nằm trong
  `QuitRoom.operations`.
- Game patch `JSON.parse` toàn cục (`""`/null → `[]`); thiếu patch này build level 1 sẽ ném lỗi.
