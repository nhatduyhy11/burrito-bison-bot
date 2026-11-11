# Battle simulator — nghiên cứu và nguyên tắc

**Mục tiêu cuối:** mini game battle standalone, chạy local, có hình, mở khoá mọi thứ
(hero/skin/antique/organ max) để chơi cho vui. Chỉ dùng cá nhân, không phát tán và không
đụng server thật. Cách chạy và cơ chế của code: [battle_sim/README.md](../../README.md).
Trạng thái và bước tiếp theo: [NEXT_STEP.md](NEXT_STEP.md).

## Nguyên tắc an toàn (vùng xám, tránh dính ban)

Đi đường dài, từng bước, ưu tiên an toàn hơn tốc độ.

- **Không gửi gì khác thường lên server thật**: không gói giả, không sửa số, không replay
  hay tự tạo `QuitRoom`/`EnterRoom`. Session đang đăng nhập chỉ chơi bình thường.
- **Không can thiệp vào trang game live đang đăng nhập** (`.tmp/pspo`, `.tmp/pmain`): không
  chặn hay giả socket, không gọi thẳng hàm game để mở trận. Trên trang live chỉ được dùng hook
  **đọc thụ động** (capture như `hook.js`).
  - `.tmp/pmain` là account chính (chơi thật, có nạp). **Phải hỏi user trước mỗi lần mở**
    profile này, kể cả chỉ để đọc. Khi mở thì chỉ dùng `hook.js`, không dùng
    `wrap_random.js` (nó chạy lại `randomCode` trong game).
  - Lý do: chặn được socket nhưng còn HTTP/SDK/telemetry, logic reconnect và kiểm tra trận
    dở dang (`UnfinishedRoom`). Client có thể rơi vào trạng thái lệch với server, và chuyện
    đó có thể bị ghi nhận.
- **Simulator chạy cách ly hoàn toàn** (`sandbox.py`): trang local, không đăng nhập, không mở
  kết nối nào tới server game, chỉ dùng asset công khai đã mirror. Giả socket hay stub mạng
  **chỉ** làm trong bản cách ly này, khi không có server nào ở đầu bên kia.
- **Mốc đầu tiên dùng đúng dữ liệu account**: `StartGameP` capture nguyên bản, không chỉnh
  số. Mở khoá hay sửa số chỉ làm sau khi bản y hệt đã được chứng minh, và cũng chỉ trong bản
  cách ly.

## Doc cơ chế

- [hero_option.md](hero_option.md) — 3 option Summon
- [spin.md](spin.md) — vòng quay
- [creep_waves.md](creep_waves.md) — lịch spawn quái
- [boss.md](boss.md) — mini / final boss
- [assets.md](assets.md) — bundle, ext-res, map
- Skin: [PROFILE_SKINS.md](../../PROFILE_SKINS.md) (hero), [BUILD_SKINS.md](../../BUILD_SKINS.md)
  (building)

## Capture trận

Runner automap + research hook trên trang live (chỉ đọc):

```bash
uv run python .tmp/battle_research/run_runner_hooked.py --dev-reload --profile .tmp/pspo
```

Ra `.tmp/battle_research/events-*.jsonl` (`StartGameP` + `QuitRoom`). Dữ liệu thô và script
probe (gitignored) cũng ở `.tmp/battle_research/`: `startgamep-<uuid>.json`, `hook.js`,
`wrap_random.js`, `launch.py`, `cdp.py`, `driver.py`, `decode.py`, `q_*.js`.

## Kết luận chính

Campaign battle (`battleType=3`) **chạy hoàn toàn trên client**. `TDServer` là "server"
giả lập trong bundle; mọi random lấy từ 1 RNG `sfc32` (npm `rand-seed`) seed = chuỗi `uuid`
trận. Server thật chỉ: cấp state đầu trận, nhận damage định kỳ, nhận log operation + kết
quả cuối trận, trả reward (có thể replay để verify).

Logic battle từ `TDServer` = 220 module, 2.1MB minified, 93 bảng LO, 0 Proxy, 0 View (bundle
1377a). Tên class/method/field giữ nguyên, chỉ biến local bị minify.

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
  mỗi 30s (client tự báo). Summon / chọn option / spin / trap / pet / spell: không packet.

`operations[]` lúc quit: `{operationType, playerId, operFrame, args(JSON), index}` — op người
chơi + robot đồng đội (playerId 11xxx). Loại đã thấy:

| type | Op | args |
|---|---|---|
| 1 | 准备 (ready) | |
| 2 | 选择房间 (chọn base) | `{roomId}`, người chơi ở room 1 |
| 3 | 出怪 | |
| 4 | Create (thả trap / pet) | `type` 7 = trap, 10 = pet; `heroCode` = mã trap/pet |
| 9 | 大转盘选择 (`SelectElite`) | `{buildPos[], entityId}` |
| 10 | 召唤 (summon) | `{type, lifeRatio}` |
| 13 | 修改倍速 | `{setTime}` |
| 14 | 设置所有玩家房间ID | |
| 19 | Cast spell (thần trong `daoists`) | `{skillCode}`, tốn 60 điện (item 30600002) |

Ngoài ra có chọn option và 大转盘召唤. Các dòng "激活技能/神兵技能" trong log game là thẻ chọn từ
lượt quay (op 10 + 8), không phải spell.

## Đầu trận

- Hero select (`Challenge`) → `EnterRoom` → room socket → `StartGameP` → `TDServer.onStartGamePPush`
  tạo `randSeed`, battle room (`AdvBattleRoom`), nạp `BuildRefreshLO` / `BuildRefreshEliteLO` /
  `BuildTurntableLO` / `BuildRefreshInitialLO` theo battleType.
- Settle base ~150 frame: robot chọn phòng 89–138, frame 150 set phòng cho người chơi,
  sinh lịch quái ([creep_waves](creep_waves.md)), op tốc độ.

## Lưu ý khi probe trên trang live

- KHÔNG `__require(...)` module game hay chạm `.Ins` trước khi login xong — đổi thứ tự init,
  hỏng UI (mất menu 2 bên lobby). Hook chờ `PlayerModule…serverId`; hook TD/room khi thấy
  `EnterRoomR` (trước khi room socket connect).
- `SocketMgr.log` / `GameRoomSocket.log` nhận object đã decode cả 2 chiều → điểm hook gọn nhất.
- Đứng yên không summon → thua (`GroupAllDead`), mất 5 năng lượng. `driver.py` (luôn chọn
  option đầu, spin thì skip) thua Stage 51 sau 324s — muốn tới final boss cần bot automap
  thật (`run_runner_hooked.py`).
