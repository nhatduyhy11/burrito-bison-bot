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

Chuyển sang máy khác: các cache trên đều bị gitignore. Cần copy gì và kiểm tra ra sao, xem
[CACHE.md](CACHE.md).

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
    `battleSkillRes`, `towerDefense`, `organ`, `hangup`, `summonCreature` (config, script,
    import, native); hai bundle cuối được thêm ở bước 3 vì UI battle load chúng;
  - ext-res `model/` (bỏ biến thể vùng jp/kr/tw/us), `model_frame/`, `userProto/`, `data/`,
    và các thư mục icon UI battle `shuzhi/{head,icon,skillicon,TDBattle,shenbing}/`.
- Chỉ là GET ẩn danh tới file tĩnh công khai, không đăng nhập. Chạy lại sẽ bỏ qua file đã có.
- Config bundle không ghi đuôi file native, nên mirror thử đuôi theo loại asset (quy tắc
  engine: `native/<xx>/<uuid>.<ver><ext>`, font dạng `<uuid>.<ver>/<tên>.ttf`). Không tìm thấy
  thì ghi vào `missing.json`.
- `serve.js` serve mirror trên `127.0.0.1:8090`, mặc định **offline**: thiếu file thì trả
  404, in ra màn hình và ghi `misses.log`. Thêm `--fill` để tải bù file thiếu từ host công
  khai (chỉ bật khi cố ý).

Lần chạy 2026-11-10 (ClientVer 64467): 10 316 file, 587MB (ext-res 362MB, `login` 90MB,
`battleSkillRes` 72MB). 74/74 file mẫu khớp từng byte với host. 42 mục thiếu: 40 native
`cc.Asset` thô và 2 script boot (jquery, clipboard), tất cả đều 404 ngay trên host. Sau
khi thêm phần cho bước 3: 13 592 file, 662MB.

## Boot cách ly (mốc B, bước 2)

```bash
uv run python battle_sim/sandbox.py --headless
```

- `sandbox.py` tự chạy `serve.js` và mở Chromium với profile trống tạm thời (không cookie,
  không account, chặn service worker). Mọi request không phải `http://127.0.0.1:8090/` bị
  **chặn và ghi log**, WebSocket bị đóng.
- Trang được mở là `/sim.html` (`web/boot.html` + `web/boot.js`). Kết thúc, script in các
  bước boot, kết quả kiểm tra, request bị chặn, file 404 của mirror, lỗi console. Exit 0 chỉ
  khi trạng thái là `ready` và không có request nào bị chặn.
- `--keep` giữ cửa sổ mở (CDP `127.0.0.1:9334`); bỏ `--headless` để xem bằng mắt.
- `boot.js` làm lại `window.boot()` của game tới `cc.game.run`: engine, `settings`,
  `jsList`, bundle `internal`/`login`, rồi `main` (code game). Sau đó chạy **scene rỗng**
  thay cho launch scene, nên `Main` và `LoginMgr` không bao giờ chạy. Tiếp theo:
  - nạp config `.bin` từ cache bằng `ConfigParser` của game (query `?config=<ver>`, mặc định
    bản mới nhất);
  - nạp các bundle battle;
  - kiểm tra bảng config, tải prefab map qua engine, tải model ext-res qua
    `aswallow.extAssetMgr` (sau khi `await init()`).

Lần chạy 2026-11-10: `ready` sau 1.8s; engine 2.4.15; config `sea_65380`; 6 bundle; 36 hero;
prefab `td_bgs_002`; `model/Boss_014` load được. 0 request bị chặn, 0 file 404, 0 lỗi.

## Trận có hình trong trang cách ly (mốc B, bước 3)

```bash
uv run python battle_sim/sandbox.py --headless --battle 6af2ab8a2f05ea3f58336962 --page "/sim.html?speed=6" --timeout 900
```

```bash
uv run python battle_sim/sandbox.py --battle 6af2ab8a2f05ea3f58336962 --page "/sim.html?speed=6" --keep --timeout 900
```

- `--battle <uuid>` mở `/sim.html?battle=<uuid>`. `boot.js` lấy capture (`/__sim/battle/<uuid>.json`,
  danh sách ở `/__sim/battles.json`), nạp config theo `StartGameP.configVersion`, boot như bước 2
  rồi giao cho `web/battle.js`.
- `battle.js` làm phần `Main` làm sau login, chỉ trong trang này:
  - `UIMgr.init`, `ResourceManager.init`, `BattleMgr.init`, driver gọi `UpdateMgr`/`GameMgr` mỗi
    frame;
  - `ModuleMgr` `onLoad` + `onEnterGame` cho cả 96 module, mỗi module chạy cô lập, lỗi thì ghi lại;
  - global của `index.html` (`getLocalAgent` = `localConfig` trong index.html đã mirror,
    `getRemoteAgent` = `{}`, `getUrlKV` = `{}`) nằm trong `boot.js`.
- Stub mạng (chỉ trong trang cách ly, không có socket thật):
  - `SocketMgr`/`GameRoomSocket.send` chỉ ghi log, không gửi;
  - `PlayerModule.getMultiPlayerData` resolve ngay, `playerId` lấy từ `StartGameP`;
  - `BuildProxy.QuitRoomRequest` ghi lại request rồi tự trả lời bằng chính kết quả của client.
- Vào trận đúng như khi room socket nhận push: `TDModule.onStartGamePPush(s2c)` (s2c dựng bằng
  `lib/proto_rebuild.js`, file này dùng chung với Node). `HangUpModule` tự đăng ký battle
  config và director.
- Replay: trước mỗi `logicTick`, áp các op có `operFrame` ≤ tick (như sim headless). Op do
  UI/director tự commit (`TDServerProxy.commitClientRequest`):
  - nếu trùng op kế tiếp trong log (cùng type + player, đã tới hạn) thì áp op của log thay vào
    (ví dụ op ready/start ở frame 0);
  - ngược lại bị bỏ và ghi lại.
- Director pause trận khi có bảng chặn đang mở (`checkBlockTick`: vòng quay, chọn summon…).
  Khi replay thì bỏ qua các lần pause này, vì log đã quyết định thời điểm: game thật mở bảng
  vòng quay ở frame 1200 nhưng op chọn ở frame 1220, do pause chỉ có hiệu lực sau khi load xong
  prefab. Tới op `SelectElite` của người chơi thì đóng bảng vòng quay.
- `?speed=N` gọi `BattleMainLoop.setTimeScale` (nút tốc độ của game). Giới hạn 1 tick logic mỗi
  frame, nên headless (~10 fps, render bằng CPU) chạy gần như tốc độ thật (~8 phút một trận);
  cửa sổ thật có GPU thì nhanh hơn.
- `?trace=Module.method,...`: bọc method để ghi stack khi throw (chẩn đoán lỗi bị game nuốt).
- Exit 0 khi trận kết thúc, `QuitRoom` khớp capture và không có request nào bị chặn.

Lần chạy 2026-11-10, Stage 51 thắng `6af2ab8a…`: hết trận ở tick 4469 sau 467s headless;
103/103 op, 0 lỗi; `QuitRoom` (result, resultReason, killNum 425, type2KillNum, totalHurt,
totalOutput, endFrame 4469, totalTime 446) khớp tuyệt đối. 0 request bị chặn. Có 4 op
`SelectElite` do bảng vòng quay tự commit muộn bị bỏ (op của log đã được áp đúng frame). Có
40 lệnh mạng bị stub, đều là lệnh lobby lấy dữ liệu.

Cả 3 trận đã capture đều khớp `QuitRoom` tuyệt đối:

| Trận | Kết thúc | Op | Thời gian headless |
|---|---|---|---|
| Stage 51 thắng `6af2ab8a…` | tick 4469 | 103/103 | 467s |
| Stage 51 thua `6af29854…` | tick 3248 (totalTime) | 30/30 | 331s |
| Stage 97 thắng `6af2b568…` | tick 4339 | 96/96 | 444s |

Cả 3 trận đều 0 op lỗi, 0 request bị chặn, 0 file 404 (sau khi thêm `summonCreature` và
`shuzhi/shenbing`).

## Tự chơi trận với đội hình account (mốc B, bước 4)

```bash
uv run python battle_sim/sandbox.py --battle 6af2ab8a2f05ea3f58336962 --play
```

```bash
uv run python battle_sim/sandbox.py --battle 6af2ab8a2f05ea3f58336962 --play --seed random
```

- `--play` mở `/sim.html?battle=<uuid>&play=1` trong cửa sổ thật (ngầm bật `--keep`, timeout
  3600s). Người chơi tự bấm UI battle gốc. Lấy `StartGameP` của trận đã capture (hero, build,
  organ… của account), không dùng op log.
- Op đi đúng đường `Local` của game: `TDServerProxy.commitClientRequest` gọi
  `TDServer.handleClientRequest` và ghi op vào `_clientOperationRecord`, không qua mạng. Robot
  đồng đội do director tự sinh op. Director pause trận khi có bảng chặn (chọn summon, vòng
  quay), như game thật.
- `--seed`: `uuid` của `StartGameP` là seed RNG. Không truyền thì dùng uuid đã capture, trận
  giống bản capture cho tới op đầu tiên khác đi. `random` sinh 24 hex mới, ra trận mới.
  Chuỗi khác thì dùng nguyên chuỗi đó.
- Hết trận, `QuitRoom` được trả lời local (`clientReward: null`). Màn kết quả
  `BattleResultViewAdventure` vẫn hiện, chỉ không có reward. Script lưu trận vừa chơi vào
  `.tmp/battle_sim/played/played-<uuid>-<ts>.jsonl` (`StartGameP` + `QuitRoom` kèm op log, cùng
  định dạng capture). `node battle_sim/replay.js <file>` replay headless file đó và so `QuitRoom`.
- `--headless --play` là smoke test, không có ai bấm. Bảng vòng quay ở frame 1200 sẽ pause
  trận vô thời hạn.
- `boot.js` gắn `cc.Widget` căn 4 cạnh cho Canvas. Engine 2.4 không tự set kích thước Canvas
  (scene của editor luôn có Widget này). Thiếu Widget thì Canvas là 0×0: UI battle lệch nửa
  màn hình và click không trúng nút (bước 3 không lộ vì replay không cần click).

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
- `mirror.js` / `serve.js` — mirror asset battle, serve local offline (`/sim.html`,
  `/__sim/*` = `web/`, `/__sim_config/*` = config cache).
- `sandbox.py` + `web/boot.{html,js}` — boot engine và code game trong browser cách ly.
- `web/battle.js` — mở trận đã capture trong trang cách ly, replay op log, so `QuitRoom`.
- `lib/capture.js` — đọc trận (`StartGameP` … `QuitRoom`) từ `events-*.jsonl`.
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
