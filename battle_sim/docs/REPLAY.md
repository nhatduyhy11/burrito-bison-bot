# Replay trận đã capture

Chạy các lệnh từ gốc repo. Cần capture có cả `StartGameP` và `QuitRoom` cùng
cache tương ứng. Xem [cách chuẩn bị cache](../CACHE.md).

## Replay headless bằng Node

```bash
node battle_sim/replay.js
```

Không có tham số: replay mọi trận có đủ `StartGameP` + `QuitRoom` trong
`.tmp/battle_research/events-*.jsonl` (gộp trùng theo uuid), in chi tiết các trận lệch và một
bảng tổng kết. Exit code 1 nếu có trận lệch hoặc không đọc được capture.

```bash
node battle_sim/replay.js "<capture.jsonl>" "<uuid>"
```

Bỏ UUID để replay mọi trận trong file. Có thể truyền nhiều file, gồm cả file `played-*.jsonl`
do playtest lưu. Dùng `-v` để in đầy đủ chi tiết ở batch. Biến môi trường `MAX_TICK`
(mặc định 6000) giới hạn số tick.

Replay đối chiếu ba nhóm dữ liệu.

- **ver**: version bộ file sim nạp == version trong `StartGameP`.
- **TIER1**: `QuitRoom.extra` (bỏ qua `fightCap`, so result, resultReason, killNum, type2KillNum, totalHurt,
  totalOutput…) + endFrame (thua: game gửi endFrame 0 → so `totalTime`).
- **TIER2**: lịch quái (`waveSchedules`), mọi lần `randomCode` (option summon, 8 ô spin),
  tick chết của boss/mini boss.

### Cách áp thao tác

- Op được áp **trước** `logicTick` của tick bằng `operFrame` (đúng như chế độ `Local`:
  UI gọi `TDServer.handleClientRequest` ngay tại `curFrame`).
- Không cần chạy director/UI trong Node: mọi op game tự sinh (goToBed, mở spin, robot) đều nằm trong
  `QuitRoom.operations`.
- Game patch `JSON.parse` toàn cục (`""`/null → `[]`); thiếu patch này build level 1 sẽ ném lỗi.

## Kiểm tra boot browser

```bash
uv run python battle_sim/sandbox --headless
```

- `sandbox` tự chạy `serve.js` và mở Chromium với profile trống tạm thời (không cookie,
  không account, chặn service worker). Mọi request không phải `http://127.0.0.1:8090/` bị
  **chặn và ghi log**, WebSocket bị đóng.
- Trang được mở là `/sim.html` (`web/boot.html` + `web/boot.js`). Kết thúc, script in các
  bước boot, kết quả kiểm tra, request bị chặn, file 404 của mirror, lỗi console. Exit 0 chỉ
  khi trạng thái là `ready` và không có request nào bị chặn.
- `--keep` giữ cửa sổ mở (CDP `127.0.0.1:9334`); bỏ `--headless` để xem bằng mắt.
- `--size WxH`: viewport. Mặc định 720x1280 khi headless, 640x720 khi headed (giống runner).
  Game là màn dọc (`FIXED_WIDTH`), cửa sổ ngang chỉ hiện một dải 720×400 nên UI trông như bị
  phóng to.
- `--record <dir>`: quay trang thành `.webm` (lưu khi đóng cửa sổ), để xem lại một flow.
- `boot.js` làm lại `window.boot()` của game tới `cc.game.run`: engine, `settings`,
  `jsList`, bundle `internal`/`login`, rồi `main` (code game). Sau đó chạy **scene rỗng**
  thay cho launch scene, nên `Main` và `LoginMgr` không bao giờ chạy. Tiếp theo:
  - nạp config `.bin` từ cache bằng `ConfigParser` của game (query `?config=<ver>`, mặc định
    bản mới nhất);
  - nạp `lang_vi.bin` cùng phiên bản trước khi đọc config. Bản dịch của game áp dụng cho tên,
    mô tả và nhãn trong trận. Nếu cache thiếu gói này, simulator báo `language pack missing`
    và dùng chữ gốc của game.
  - nạp các bundle battle;
  - kiểm tra bảng config, tải prefab map qua engine, tải model ext-res qua
    `aswallow.extAssetMgr` (sau khi `await init()`).

Kết quả mong đợi là `ready`, 0 request bị chặn, 0 file 404 và 0 lỗi console.

Tải gói tiếng Việt vào cache một lần cho mỗi config version. Thay giá trị cuối lệnh bằng `configVersion` của capture.

```bash
node -e 'require("./battle_sim/lib/versions").ensureLanguage(process.argv[1], "vi").catch(e => { console.error(e.message); process.exitCode = 1; })' "<configVersion>"
```

## Replay có hình trong browser

Lấy UUID từ `StartGameP.uuid` trong capture. Nếu đã chạy `node battle_sim/serve.js`,
có thể xem danh sách tại `http://127.0.0.1:8090/__sim/battles.json`.

```bash
uv run python battle_sim/sandbox --battle "<uuid>" --keep --timeout 900
```

Để chạy không hiện cửa sổ và trả mã thoát theo kết quả so sánh:

```bash
uv run python battle_sim/sandbox --headless --battle "<uuid>" --timeout 900
```

Có thể thêm `--page "/sim.html?speed=6"` cho cả hai lệnh.

- `--battle <uuid>` mở `/sim.html?battle=<uuid>`. `boot.js` lấy capture (`/__sim/battle/<uuid>.json`,
  danh sách ở `/__sim/battles.json`), nạp config theo `StartGameP.configVersion`, boot như phần trên
  rồi giao cho `web/battle/` (entry `index.js`).
- `battle/setup.js` làm phần `Main` làm sau login, chỉ trong trang này:
  - `UIMgr.init`, `ResourceManager.init`, `BattleMgr.init`, driver gọi `UpdateMgr`/`GameMgr` mỗi
    frame;
  - `ModuleMgr` `onLoad` + `onEnterGame` cho các module, mỗi module chạy cô lập, lỗi thì ghi lại;
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
  Replay bỏ qua các lần pause này vì thời điểm áp op lấy từ log. Tới op `SelectElite`
  của người chơi thì đóng bảng vòng quay.
- `?speed=N` gọi `BattleMainLoop.setTimeScale` (nút tốc độ của game). Tốc độ thực tế
  còn phụ thuộc vào tốc độ render vì mỗi frame xử lý tối đa một tick logic.
- `?trace=Module.method,...`: bọc method để ghi stack khi throw (chẩn đoán lỗi bị game nuốt).
- Exit 0 khi trận kết thúc, `QuitRoom` khớp capture và không có request nào bị chặn.
