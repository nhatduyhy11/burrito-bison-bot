# battle_sim — headless campaign battle (mốc A)

Chạy trận campaign offline trong Node bằng chính code logic của bundle game
(`TDServer` + `BattleEngineDelegate` + engine `battleground`), không render, không mạng.
Nghiên cứu nền: [docs/planning/battle_sim/](../docs/planning/battle_sim/README.md).

## Version / cache

Mỗi trận chạy đúng bộ file khớp version trong `StartGameP` (`lib/versions.js`), cache ở
`.tmp/battle_sim/` (không commit):

| `StartGameP` | Ý nghĩa | Cache | Nguồn |
|---|---|---|---|
| `battleVersion` `2.3.1-2_E63294_P63528_C63583` | `BATTLE_ENGINE_VERSION` + `ENGINE_BRIDGE_VERSION` in trong code bundle | `bundles/index.<hash>.js` (quét cả `.tmp/bundle/main.*/`) | `snapshot.js` |
| `configVersion` `sea_65380` | `ConfigParser.branch_version` | `config/<ver>/{config,preload_config}.bin` | tự tải từ CDN khi thiếu (CDN giữ bản cũ) |
| `mapVersion` `trunk_61543` | `resources/tiledBgVersion.json` | `maps/<ver>/*.json` | `snapshot.js` |

Host chỉ còn code bundle và map của **deploy đang live**. Vì vậy mỗi khi game cập nhật, phải
chạy `snapshot.js` trước khi capture trận muốn replay. Bundle hoặc map không có trong cache
thì replay báo lỗi, không chạy với bộ file sai.

```bash
node battle_sim/snapshot.js
```

Chỉ dùng HTTP, không cần browser: đọc `index.html` (`ClientVer`) → `manifest.<ver>.js` →
`src/settings.<h>.js` (`bundleVers`), rồi tải `main/index.<h>.js` và tách map/tileset từ
bundle `battle`.

Capture trận (`events-*.jsonl`, chứa `StartGameP` + `QuitRoom`):
`.tmp/battle_research/run_runner_hooked.py` (runner + research hook).

## Mirror asset (mốc B, bước 1)

```bash
node battle_sim/mirror.js plan
```

```bash
node battle_sim/mirror.js fetch
```

```bash
node battle_sim/serve.js
```

- `mirror.js` tải về `.tmp/battle_sim/mirror/<ClientVer>/`, giữ nguyên cấu trúc URL của
  host. Gồm:
  - file boot (`index.html`, manifest, engine, settings);
  - các bundle `internal`, `main`, `resources`, `login`, `battle`, `battleConfig`,
    `battleSkillRes`, `towerDefense`, `organ` (config, script, import, native);
  - ext-res `model/` (bỏ biến thể vùng jp/kr/tw/us), `model_frame/`, `userProto/`, `data/`.
- Chỉ là GET ẩn danh tới file tĩnh công khai, không đăng nhập. Chạy lại sẽ bỏ qua file đã có.
- Config bundle không ghi đuôi file native, nên mirror thử đuôi theo loại asset (quy tắc
  engine: `native/<xx>/<uuid>.<ver><ext>`, font dạng `<uuid>.<ver>/<tên>.ttf`). Không tìm thấy
  thì ghi vào `missing.json`.
- `serve.js` serve mirror trên `127.0.0.1:8090`, mặc định **offline**: thiếu file thì trả
  404, in ra màn hình và ghi `misses.log`. Thêm `--fill` để tải bù file thiếu từ host công
  khai (chỉ bật khi cố ý).

Lần chạy 2026-11-10 (ClientVer 64467): 10 316 file, 587MB (ext-res 362MB, `login` 90MB,
`battleSkillRes` 72MB). 74/74 file mẫu khớp từng byte với host. 42 mục thiếu: 40 native
`cc.Asset` thô và 2 script boot (jquery, clipboard), tất cả đều 404 ngay trên host.

## Chạy

```bash
node battle_sim/replay.js
```

Không có tham số: replay mọi trận có đủ `StartGameP` + `QuitRoom` trong
`.tmp/battle_research/events-*.jsonl` (gộp trùng theo uuid), in chi tiết các trận lệch và một
bảng tổng kết. Exit code 1 nếu có trận lệch. Một trận: `replay.js <capture.jsonl> [uuid]`
(`-v` để in đủ chi tiết ở batch). `MAX_TICK` (env, mặc định 6000) giới hạn số tick. Một trận
~4400 tick chạy ~22s.

So sánh:
- **ver**: version bộ file sim nạp == version trong `StartGameP`.
- **TIER1**: `QuitRoom.extra` (result, resultReason, killNum, type2KillNum, totalHurt,
  totalOutput…) + endFrame (thua: game gửi endFrame 0 → so `totalTime`).
- **TIER2**: lịch quái (`waveSchedules`), mọi lần `randomCode` (option summon, 8 ô spin),
  tick chết của boss/mini boss.

## Cấu trúc

- `replay.js` — replay + so sánh, 1 hoặc nhiều trận.
- `snapshot.js` — cache code bundle + map của deploy đang live.
- `mirror.js` / `serve.js` — mirror asset battle, serve local offline.
- `lib/deploy.js` — đọc ClientVer / manifest / `bundleVers` của deploy live.
- `lib/versions.js` — chọn bundle/config/map theo version, tải config.
- `lib/cocos_bundle.js` — đọc config/import của asset bundle Cocos 2.4 từ host.
- `lib/http.js` — GET/tải file. Dùng TLS của Node vì curl Windows (schannel) lỗi revocation với CDN.
- `lib/bundle_loader.js` — nạp bundle vào `vm` context, thay loader browserify bằng bảng
  module + `require` lười; áp patch `JSON.parse` giống `Main.onLoad` của game.
- `lib/stubs.js` — `cc.*`, `window`, `i18n` tối thiểu cho closure logic.
- `lib/config_loader.js` — `QuickLZ` → `BinaryReader` → `ConfigParser` / `PreloadConfigParser`.
- `lib/proto_rebuild.js` — dựng lại message proto thật (List/Dictionary) từ JSON capture theo `*_Def`.
- `lib/sim.js` — `Sim`: setup `StartGameP`, map Tiled, delegate; `run(ops)` áp op theo `operFrame` rồi `logicTick`.
- `lib/checkpoints.js` — recorder tier 2 trong sim + trích từ capture + so sánh.

## Ghi chú

- Op được áp **trước** `logicTick` của tick bằng `operFrame` (đúng như chế độ `Local`:
  UI gọi `TDServer.handleClientRequest` ngay tại `curFrame`).
- Không cần chạy director/UI: mọi op game tự sinh (goToBed, mở spin, robot) đều nằm trong
  `QuitRoom.operations`.
- Game patch `JSON.parse` toàn cục (`""`/null → `[]`); thiếu patch này build level 1 sẽ ném lỗi.
