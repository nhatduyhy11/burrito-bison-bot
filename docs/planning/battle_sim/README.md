# Battle simulator research — main

**Mục tiêu cuối:** mini game battle standalone, chạy local, có hình, mở khoá mọi thứ
(hero/skin/antique/organ max) để chơi cho vui. Chỉ dùng cá nhân, không phát tán và không
đụng server thật. Logic sim headless cùng replay và `snapshot.js` là công cụ test cho
mục tiêu này, không phải đích đến.

## Nguyên tắc an toàn (vùng xám, tránh dính ban)

Đi đường dài, từng bước, ưu tiên an toàn hơn tốc độ.

- **Không gửi gì khác thường lên server thật**: không gói giả, không sửa số, không replay
  hay tự tạo `QuitRoom`/`EnterRoom`. Session đang đăng nhập chỉ chơi bình thường.
- **Không can thiệp vào trang game live đang đăng nhập**: không chặn hay giả socket, không
  gọi thẳng hàm game để mở trận. Trên trang live chỉ được dùng hook **đọc thụ động**
  (capture như `hook.js`).
  - Lý do: chặn được socket nhưng còn HTTP/SDK/telemetry, logic reconnect và kiểm tra trận
    dở dang (`UnfinishedRoom`). Client có thể rơi vào trạng thái lệch với server, và chuyện
    đó có thể bị ghi nhận.
- **Simulator chạy cách ly hoàn toàn**: trang local, không đăng nhập, không mở kết nối nào
  tới server game, chỉ dùng asset công khai đã mirror. Việc giả socket chỉ được làm trong
  bản cách ly này, khi không có server nào ở đầu bên kia.
- **Mốc đầu tiên dùng đúng dữ liệu account**: `StartGameP` capture nguyên bản, không chỉnh
  số. Mở khoá hay sửa số chỉ làm sau khi bản y hệt đã được chứng minh, và cũng chỉ trong bản
  cách ly.

## Lộ trình mốc B (simulator có hình, cách ly)

1. ~~Mirror asset battle về local, serve tĩnh~~: **xong** 2026-11-10, gồm `battle_sim/mirror.js`
   và `serve.js`: 587MB, khớp từng byte với host (chi tiết trong `battle_sim/README.md`).
   Chưa biết file nào thật sự dùng; tới bước 2–3 thì đọc `misses.log` để biết thiếu gì, rồi
   tính chuyện cắt bớt.
2. ~~Trang local boot engine và bundle gốc, không qua login và lobby, không kết nối mạng
   game~~: **xong** 2026-11-10, gồm `battle_sim/sandbox.py` và `web/boot.js`. Browser chặn
   mọi request ra ngoài localhost. Boot tới scene rỗng, nạp config, các bundle battle, map và
   model ext-res. Không có request ra ngoài, không file 404.
   - Ghi chú cho bước 3: battle còn cần phần khởi tạo mà `Main` làm sau login (`UIMgr.init`,
     `ResourceManager.init`, `BattleMgr.init`, `AgentConfig`, `ModuleMgr`…). Làm từng phần
     một trong trang cách ly, có cần thì mới thêm.
3. Mở trận bằng `StartGameP` đã capture, replay op log có hình. So kết quả với `QuitRoom` và
   sim headless để chứng minh simulator khớp game.
4. Chơi tương tác với đúng đội hình của account.
5. Sau cùng mới tính mở khoá, chỉnh số, vẫn chỉ trong bản cách ly.

Status 2026-11-10: phase 1 (vào map, socket), 1b ([hero_option](hero_option.md)), 2
([spin](spin.md)), 3/3b ([creep_waves](creep_waves.md), [boss](boss.md)), 4 (thắng map,
`QuitRoom`) đã xác minh runtime. Asset: đã kiểm kê ([assets](assets.md)), chưa mirror. Mốc A logic sim headless: **xong**, replay khớp game tuyệt đối ([logic_sim_plan](logic_sim_plan.md), code `battle_sim/`).

Capture map thắng (runner automap + hook):
`.tmp/battle_research/events-runner-20261110-122739.jsonl` — `QuitRoom` result 1 `EnemyAllDead`,
endFrame 4469, 425 kill, 103 op, 29/29 `randomCode` replay khớp. Chạy lại:
`uv run python .tmp/battle_research/run_runner_hooked.py --dev-reload --profile .tmp/pspo`
(runner gốc + CDP 9333 + hook).

Doc phụ:
- [hero_option.md](hero_option.md) — 3 option Summon (trụ cột 1)
- [spin.md](spin.md) — vòng quay (trụ cột 2)
- [creep_waves.md](creep_waves.md) — lịch spawn quái
- [boss.md](boss.md) — mini / final boss
- [assets.md](assets.md) — bundle, ext-res, model, map cần cho battle
- [logic_sim_plan.md](logic_sim_plan.md) — mốc A: kết quả kiểm chứng + việc còn mở

Dữ liệu thô + script probe: `.tmp/battle_research/` (gitignored): `events-*.jsonl`,
`startgamep-<uuid>.json`, `hook.js`, `wrap_random.js`, `launch.py`, `cdp.py`, `driver.py`,
`decode.py`, `q_*.js`.

## Kết luận chính

Campaign battle (`battleType=3`) **chạy hoàn toàn trên client**. `TDServer` là "server"
giả lập trong bundle; mọi random lấy từ 1 RNG `sfc32` (npm `rand-seed`) seed = chuỗi `uuid`
trận. Server thật chỉ: cấp state đầu trận, nhận damage định kỳ, nhận log operation + kết
quả cuối trận, trả reward (có thể replay để verify).

## Flow mạng

Socket chính (`SocketMgr`):
- `BuildProxy(82).EnterRoom {battleType, level, formationId, forceQuit, battleVersion, configVersion, mapVersion}`
- `EnterRoomR {authCode, addr: wss://…/ws?nodeName=wbattled…, frameInterval:3, pingInterval:30}`
- Cuối trận `QuitRoom {type, extra, endFrame, totalTime, operations[], battleType}`;
  `extra` = JSON `{result, resultReason, type2KillNum, killNum, bossNum, roundNum, totalOutput,
  myTotalOutput, buildUuidHub, fightCap}`. `QuitRoomR {result, clientReward, otherReward, extra}`
  — reward cả khi thua (`result 2`, `GroupAllDead_0`).

Battle-room socket (`GameRoomSocket`, `BuildRoomProxy(90)`):
- `Auth {authCode, playerId, platform}` → `AuthR`
- `StartGameP` (~24KB): `uuid, level, battleType, battleVersion, configVersion, mapVersion,
  playerInfos[]{playerId, heros, builds, summonCreatures, skinInfos, antiques, organs,
  trainingInfos, support, daoists, summonerInfos, mountCode, specialCode, roomCode,
  goldenSkinsCount}` — toàn bộ input của trận.
- Trong trận chỉ có `Ping` và `UpdateDamage {heroInfos[{heroCode,damage,atk,frame}], doorInfo{armor,blood}}`
  mỗi 30s (client tự báo). Summon / chọn option / spin: không packet.

`operations[]` lúc quit: `{operationType, playerId, operFrame, args(JSON), index}` — op người
chơi + robot đồng đội (playerId 11xxx). Loại đã thấy: 1 准备, 2 选择房间, 3 出怪, 9 大转盘选择,
10 召唤, 13 修改倍速 `{setTime}`, 14 设置所有玩家房间ID, chọn option, 大转盘召唤.

## Phase 1 — đầu trận

- Hero select (`Challenge`) → `EnterRoom` → room socket → `StartGameP` → `TDServer.onStartGamePPush`
  tạo `randSeed`, battle room (`AdvBattleRoom`), nạp `BuildRefreshLO` / `BuildRefreshEliteLO` /
  `BuildTurntableLO` / `BuildRefreshInitialLO` theo battleType.
- Settle base ~150 frame: robot chọn phòng 89–138, frame 150 set phòng cho người chơi,
  sinh lịch quái ([creep_waves](creep_waves.md)), op tốc độ.

## Simulator — hướng đề xuất

Đo closure module (bundle 1377a): logic battle từ `TDServer` = **220 module, 2.1MB minified,
93 bảng LO, 0 Proxy, 0 View**. Kèm render (`BattleMainLoop`) = 2711 module / 13.5MB (dính UI
framework, 114 Proxy, 656 View).

1. **Logic sim headless (nên làm trước)**: tách 220 module + loader config
   (`QuickLZ` → `BinaryReader` → `ConfigParser`) chạy Node; input = `StartGameP` + config
   `.bin`, output = state theo tick. Kiểm chứng bằng replay trận đã capture (op log trong
   `QuitRoom`) rồi so `extra` (killNum, totalOutput). Cắt server = stub `TDServerProxy` /
   `GameRoomSocket`, không cần viết lại logic.
2. **Bản "y hệt game" có hình**: không nên dựng lại renderer. Chạy chính bundle gốc với asset
   mirror local + stub mạng (`EnterRoom`→`EnterRoomR` giả, room socket→`StartGameP` đã lưu,
   `QuitRoom`→reward giả) = offline 100%, giống hệt vì là cùng code/asset.
3. **Beautify tên biến đầy đủ**: tên class/method/field đã giữ nguyên; chỉ biến local bị
   minify. Đáng làm cho file nóng (`TDServer`, `TDPlayerEntity`, `BaseBattleRoom`,
   `AdvBattleRoom`, `RandomSeed`) để đọc/sửa luật; rename toàn bộ 2.1MB thì chưa đáng.

## Lưu ý kỹ thuật khi probe

- KHÔNG `__require(...)` module game hay chạm `.Ins` trước khi login xong — đổi thứ tự init,
  hỏng UI (mất menu 2 bên lobby). Hook chờ `PlayerModule…serverId`; hook TD/room khi thấy
  `EnterRoomR` (trước khi room socket connect).
- `SocketMgr.log` / `GameRoomSocket.log` nhận object đã decode cả 2 chiều → điểm hook gọn nhất.
- Đứng yên không summon → thua (`GroupAllDead`), mất 5 năng lượng. `driver.py` (luôn chọn
  option đầu, spin thì skip) cũng thua Stage 51 sau 324s — muốn tới final boss (phase 3) cần
  bot automap thật (`run_runner_hooked.py`).
- RNG `sfc32` port sang Python khớp game (xem [spin.md](spin.md)) → simulator ngoài bundle khả thi.
