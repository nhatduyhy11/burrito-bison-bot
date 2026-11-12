# battle_sim — campaign battle offline

Chạy trận campaign offline bằng chính code và asset của game: headless trong Node để replay
(mốc A), và có hình trong browser cách ly để xem lại hoặc tự chơi (mốc B). Không kết nối
server game.

Mục tiêu, **nguyên tắc an toàn** và nghiên cứu cơ chế: [docs/planning/research.md](docs/planning/research.md).
Trạng thái và việc tiếp theo: [docs/planning/NEXT_STEP.md](docs/planning/NEXT_STEP.md).

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
node battle_sim/scripts/snapshot.js
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
node battle_sim/scripts/mirror.js plan
```

```bash
node battle_sim/scripts/mirror.js fetch
```

```bash
node battle_sim/serve.js
```

- `mirror.js` tải về `.tmp/battle_sim/mirror/<ClientVer>/`, giữ nguyên cấu trúc URL của
  host. Gồm:
  - file boot (`index.html`, manifest, engine, settings);
  - các bundle `internal`, `main`, `resources`, `login`, `battle`, `battleConfig`,
    `battleSkillRes`, `towerDefense`, `organ`, `hangup`, `summonCreature`, `hero` (config,
    script, import, native). Ba bundle cuối là UI ngoài trận nhưng UI battle vẫn load
    (`hero`: UI màn hero, không chứa model), nên mirror để không 404;
  - ext-res `model/` (bỏ biến thể vùng jp/kr/tw/us), `model_frame/`, `userProto/`, `data/`,
    và các thư mục icon UI battle `shuzhi/{head,icon,skillicon,TDBattle,shenbing,machine,half,build}/`
    (`machine` icon trap, `half` ảnh nửa người hero, `build` icon công trình).
- Chỉ là GET ẩn danh tới file tĩnh công khai, không đăng nhập. Chạy lại sẽ bỏ qua file đã có.
- Config bundle không ghi đuôi file native, nên mirror thử đuôi theo loại asset (quy tắc
  engine: `native/<xx>/<uuid>.<ver><ext>`, font dạng `<uuid>.<ver>/<tên>.ttf`). Không tìm thấy
  thì ghi vào `missing.json`.
- `serve.js` serve mirror trên `127.0.0.1:8090`, mặc định **offline**: thiếu file thì trả
  404, in ra màn hình và ghi `misses.log`. Thêm `--fill` để tải bù file thiếu từ host công
  khai (chỉ bật khi cố ý).

Mirror hiện tại (ClientVer 64467, kiểm tra 2026-11-11): 14 429 file, 693,3MB.
Tải bù 357 file so với cache 14 072 file: 17 icon trap, 263 ảnh nửa người hero
(bỏ biến thể vùng), 77 icon công trình. `shuzhi/build/` bổ sung cho các 404 runtime
`fdcs1_8ac14.png` và `zcm1_0af53.png` mà bộ lọc trước chưa lấy.
Các mục trong `missing.json` đều 404 ngay trên host: native `cc.Asset` thô (trận không load)
và 2 script boot (jquery, clipboard).

### Model hero trong trận

- Hero (và creep, boss, build) trong trận là spine ở ext-res
  `model/<tên>/<tên>_<hash>.{json,skel,atlas,png}`, kèm bản `_h`/`_l` (atlas độ phân giải
  cao/thấp). Không nằm trong bundle Cocos nào.
- Tên model lấy từ `HeroLO.model`; hero mặc skin thì lấy từ `DermaLO.deco` (vd `Hero_001_pf2`).
  Game load khi unit xuất hiện, qua `aswallow.extAssetMgr`, vào `GameSpine` ở node
  `$_DISPLAY_NODE` của unit.
- Mirror lấy **toàn bộ** `model/`, không lọc theo account: đổi account, hoặc chơi hero/skin
  khác bằng `--play`, không cần tải thêm. So với `ext-res/version_64467.json`: mirror có
  270/291 thư mục `model/Hero_*` (37 hero gốc, mọi skin `_pf1…_pf4`, `_ez`, `_sea`); 21 thư
  mục còn lại là biến thể vùng `_jp`/`_kr`, bản SEA không dùng.
- Bộ lọc vùng chỉ bỏ tên có hậu tố vùng ở cuối, nên vẫn lọt 46 thư mục dạng
  `Hero_001_kr_pf1`. Không ảnh hưởng gì, chỉ tốn dung lượng.

## Boot cách ly (mốc B, bước 2)

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

Kết quả đúng: `ready` sau ~2s (engine 2.4.15), 0 request bị chặn, 0 file 404, 0 lỗi.

Tải gói tiếng Việt vào cache một lần cho mỗi phiên bản config cần chạy:

```bash
node -e 'require("./battle_sim/lib/versions").ensureLanguage(process.argv[1], "vi").catch(e => { console.error(e.message); process.exitCode = 1; })' sea_65380
```

## Trận có hình trong trang cách ly (mốc B, bước 3)

```bash
uv run python battle_sim/sandbox --headless --battle 6af2ab8a2f05ea3f58336962 --page "/sim.html?speed=6" --timeout 900
```

```bash
uv run python battle_sim/sandbox --battle 6af2ab8a2f05ea3f58336962 --page "/sim.html?speed=6" --keep --timeout 900
```

- `--battle <uuid>` mở `/sim.html?battle=<uuid>`. `boot.js` lấy capture (`/__sim/battle/<uuid>.json`,
  danh sách ở `/__sim/battles.json`), nạp config theo `StartGameP.configVersion`, boot như bước 2
  rồi giao cho `web/battle/` (entry `index.js`).
- `battle/setup.js` làm phần `Main` làm sau login, chỉ trong trang này:
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

Cả 3 trận đã capture (Stage 51 thắng/thua, Stage 97) khớp `QuitRoom` tuyệt đối (result,
resultReason, killNum, type2KillNum, totalHurt, totalOutput, endFrame, totalTime), 0 op lỗi,
0 request bị chặn, 0 file 404, 330–470s headless mỗi trận. Bình thường log có vài op
`SelectElite` do bảng vòng quay tự commit muộn bị bỏ (op của log đã áp đúng frame) và ~40
lệnh lobby bị stub.

## Tự chơi trận với đội hình account (mốc B, bước 4)

```bash
uv run python battle_sim/sandbox --battle 6af2ab8a2f05ea3f58336962 --play
```

```bash
uv run python battle_sim/sandbox --battle 6af2ab8a2f05ea3f58336962 --play --seed random
```

```bash
uv run python battle_sim/sandbox --setup
```

- `--setup` mở trang setup (`/__sim/setup.html`, [web/setup.html](web/setup.html)) trong cửa
  sổ sandbox. Trên trang chọn capture gốc, seed và từng phần của profile. Phần nào không bật
  "Ghi đè" thì giữ từ capture. Nút "Chơi" lưu profile vào `.tmp/battle_sim/profiles/last.json`
  (dùng lại được với `--profile`) và `last-setup.json` (kèm capture và seed, trang nạp lại lần
  sau), rồi mở trận như `--play --profile`. Trang cũng tải, sao chép và nhập được file JSON.
  Có thể mở trang qua `serve.js` trong browser thường để soạn profile. Trang chỉ đọc
  `profile-dict.json` và capture, không nạp code game.
- `sandbox` chạy `serve.js` bằng `node` trên PATH. Shell không thấy node (ví dụ node cài
  qua nvm nhưng terminal mở trước đó) thì đặt `$env:BATTLE_SIM_NODE = '<đường dẫn node.exe>'`.

- `--play` mở `/sim.html?battle=<uuid>&play=1` trong cửa sổ thật (ngầm bật `--keep`, timeout
  3600s). Người chơi tự bấm UI battle gốc. Lấy `StartGameP` của trận đã capture (hero, build,
  organ… của account), không dùng op log.
- Op đi đúng đường `Local` của game: `TDServerProxy.commitClientRequest` gọi
  `TDServer.handleClientRequest` và ghi op vào `_clientOperationRecord`, không qua mạng. Robot
  đồng đội do director tự sinh op. Director pause trận khi có bảng chặn (chọn summon, vòng
  quay), như game thật.
- Thẻ tháng (chỉ trong trận `--play` của trang cách ly, `stubs.js` `unlockMonthCards`): giả lập
  đã mua cả 2 thẻ tháng, mọi loại trận. `UnlockLO` khoá 2 tính năng bằng điều kiện
  `PrivilgeMonthCard` (`MallModule.checkActVipCardIsBuy(NewMonthCard, 7|8)`): 9003 tăng tốc (thẻ 7,
  `BATTLE_SPEED_TIME_SCALE` [1, 1.6], nút x2 gửi op `SetSpeed`) và 9007 auto (thẻ 8, `HostingMgr`).
  Nút còn cần `ActivityModule.isOpen(MonthCardDict)`; nút auto bỏ điều kiện loại trận
  (`NeedAIBtnBattleType`) và level account ≥ 3 (9008, sandbox không có level). `HostingMgr.update`
  chỉ chạy khi đang trong phòng và socket kết nối, nên sandbox báo trạng thái đó riêng trong lúc
  update chạy. Hai nút hiện sau khi vào giường, như game. Kiểm tra: x2 đổi `frameSync.timeScale`
  thành 1.6; auto tự Upgrade/Select/Lottery; trận đã chơi replay headless khớp tuyệt đối.
  `window.__simBattleFrame` giữ frame trận để điều khiển qua CDP (chẩn đoán).
- `--seed`: `uuid` của `StartGameP` là seed RNG. Không truyền thì dùng uuid đã capture, trận
  giống bản capture cho tới op đầu tiên khác đi. `random` sinh 24 hex mới, ra trận mới.
  Chuỗi khác thì dùng nguyên chuỗi đó.
- `--profile battle_sim/profile.example.json`: mọi tuỳ chỉnh trận nằm trong file JSON này
  (trang setup `--setup` sinh ra file này). `map` chọn màn chơi, ví dụ
  `{ "mode": "campaign", "stage": 66 }`. Hiện chỉ có `campaign`, và config `sea_65380` có
  stage 1–400. Bỏ `map` thì chơi stage gốc của capture. Đội hình chọn theo tên trong
  [profile-dict.json](web/dict/profile-dict.json). `heroes` giữ chỉ số và skill gốc cho hero có
  trong capture. Khi có `heroes`, phải chọn đúng 5 hero khác nhau; setup luôn hiện 5 slot,
  không phụ thuộc chế độ màn chơi. Hero khác mượn tiến độ của các hero cùng độ hiếm trong capture (không có thì
  mọi hero): `attr` trung bình (đã trừ `selfAttr` của skin), level và `breakThrough` của hero
  trung vị, level skill riêng theo đa số từng slot. Relic/artifact không mượn. Kiểm tra bỏ-một-ra
  trên 2 capture: chỉ số lệch trong ±10% (Lu Bu lv100 duy nhất thì −20%). Hero cam/tím mượn
  từ hero đỏ khi capture không có hero cùng độ hiếm, chưa đối chiếu được.
  Xem [cấu hình skin](PROFILE_SKINS.md) để chọn skin, số sao và các skin yêu cầu.
  Khi Pháo Loli gắn skill skin `guns_n_roses` và Joker chưa nằm trong đội hình chính,
  trang setup mở Joker ở slot 6 với đầy đủ tùy chỉnh skin, sở hữu, sao và slot skill.
  JSON lưu riêng ở `summonedJoker`, cùng định dạng một hero, ví dụ
  `{ "name": "joker", "skin": "nocturnal_burglar", "star": 5 }`; chỉ áp dụng khi Joker được triệu hồi.
  Hero, Mount và Skill Summoner là ba accordion liên tiếp; thu gọn chỉ thay đổi hiển thị.
  `mounts: { "owned": ["azure_drone"], "selected": "azure_drone" }` cấu hình danh sách sở hữu
  và mount đang cưỡi; `selected: null` là không cưỡi. Bỏ `mounts` giữ dữ liệu capture.
  Catalog mount nằm ở `mounts` trong [profile-dict.json](web/dict/profile-dict.json). Mount mới dùng skill rank đầu tiên;
  mount có trong capture giữ skill cũ. Các chỉ số account do server tính vẫn lấy từ capture.
  `summonerSkins` là các skin Summoner đã tick: `{ "name", "star" }`, tối đa 3 skin có skill
  (`summonerInfos`). Skin sự kiện không có skill (`sanguin_dragoon`, chỉ cộng chỉ số) không chiếm
  slot và không vào `summonerInfos`: server thật không gửi, còn client sẽ lỗi khi parse skill rỗng.
  `summonerWorn` là skin đang mặc, chọn trong `summonerSkins` (`null` là model mặc định). Live
  game gửi nó ở `derma` của `SummonerInfoP` / base player info, không nằm trong `StartGameP`; sim
  đặt nó vào `PlayerModule.playerInfo.info.derma` để đổi model Summoner trong trận.

  Catalog Đồ Cổ nằm ở `antiques` trong [antique-dict.json](web/dict/antique-dict.json), kèm bảng màu, bộ sưu tập và chi phí nâng cấp.
  Mỗi `ranks[].code` là mã theo sao trong capture, ví dụ `300106` là `3001` ở 6 sao.
  `level` trong capture là giá trị tiến độ dùng để tính hiệu ứng, có giới hạn `haloLevelLimit`
  theo rank. Config `sea_65380` có tối đa 15 sao cho mỗi món và mốc bộ sưu tập cuối cũng là 15 sao.

  `traps` thay danh sách trap (tối đa 3): tên (level 1, 1 sao) hoặc
  `{ "name", "level", "star" }`, skill tra từ sao trong config game.
  `pets` thay danh sách pet (tối đa 3) theo cùng dạng. `skillCodes` lấy theo sao: mỗi loại
  skill trong `SummonCreatureLO.skill` lấy level cao nhất có `starRequire` ≤ sao.
  `buildings` chọn skin cửa, giường, chuột, mèo (`door`, `bed`, `generator`, `cat`). Xem
  [skin building](BUILD_SKINS.md#trong-profile-playtest). `goldenSkinsCount` (ảnh hưởng
  sát thương pet) đặt bằng tay vì chưa rõ server tính thế nào.
  `spells` thay spell (thần, `daoists`, tối đa 2 theo `DaoistFormationLO`): tên (1 sao)
  hoặc `{ "name", "star" }`, `skillCode` tra từ `DaoistStarLO`.
  Bỏ một trường để giữ giá trị từ capture. Hero support hiện vẫn lấy từ capture.
- `profile-dict.json`, `map-dict.json` và `antique-dict.json` được sinh từ config game bằng `node battle_sim/scripts/gen_profile_dict.js
  [configVersion]`. Key là slug tên tiếng Anh. `name` lấy từ `lang_en.<ver>.bin`, `name_vn`
  lấy từ `lang_vi.<ver>.bin` (tải một lần cạnh `config.bin`). Mục không có tên tiếng Anh dùng
  key `id_<mã>` (ví dụ skin 7 màu `id_10013`). Hero, trap và pet có `color` là độ hiếm (viền thẻ trong game: `purple` 4, `orange` 5,
  `red` 6, `gold` 7; spell không có). `map-dict.json` gồm `campaign` (khoảng stage) và `capital` (boss U Đô kèm các bộ quái). `antique-dict.json` gồm `antiques`, `antiqueColors`, `antiqueSuits`, `antiqueUpgradeCosts`. `profile-dict.json` gồm `heroes` (kèm `baseSkills` và `skins`), `traps`, `pets`, `spells`
  (`daoists`), `buildings` (door, bed, generator, cat, kèm skin), mỗi mục có `maxLevel` /
  `maxStar`. Không sửa tay; chạy lại script khi đổi config.
- Hết trận, `QuitRoom` được trả lời local (`clientReward: null`). Màn kết quả
  `BattleResultViewAdventure` vẫn hiện, chỉ không có reward. Script lưu trận vừa chơi vào
  `.tmp/battle_sim/played/played-<uuid>-<ts>.jsonl` (`StartGameP` + `QuitRoom` kèm op log, cùng
  định dạng capture). `node battle_sim/replay.js <file>` replay headless file đó và so `QuitRoom`.
- Nút pause: `SetPause` được trả lời local (`stubs.js` `stubPause`), bảng pause mở như game và
  director dừng trận khi bảng mở. "继续战斗" chơi tiếp, "退出战斗" bỏ trận (`Abandon`) → `QuitRoom`
  → màn kết quả.
- Đóng màn kết quả (nút "返回", tap nền hoặc tự đóng) sẽ đưa về lobby, mà trang cách ly không có
  lobby, nên `leaveOnResultClose` đặt `window.__simLeave` thay vào đó. Với `--setup`,
  `sandbox` mở lại trang setup để chơi trận khác; với `--play` thì kết thúc. Trận nào kết thúc
  (thắng, thua, bỏ) cũng được lưu `played-*.jsonl` trước.
- `--headless --play` là smoke test, không có ai bấm. Bảng vòng quay ở frame 1200 sẽ pause
  trận vô thời hạn.
- `battle/setup.js` sửa `Main Camera` của Canvas: chỉ render UI (bỏ group `battle_ground*`) và
  không xoá màu; một camera riêng depth -100 lo xoá khung hình. Nếu không, `Main Camera`
  (render mọi group, xoá màu, vẽ sau `camera_battle` depth -10) xoá hình battle rồi vẽ lại map
  không theo offset camera: chỉ thấy một vùng map tĩnh, không hero, không creep.
- `boot.js` gắn `cc.Widget` căn 4 cạnh cho Canvas. Engine 2.4 không tự set kích thước Canvas
  (scene của editor luôn có Widget này). Thiếu Widget thì Canvas là 0×0: UI battle lệch nửa
  màn hình và click không trúng nút (bước 3 không lộ vì replay không cần click).

## Replay headless (mốc A)

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
- `scripts/` — công cụ chạy riêng: `snapshot.js` (cache code bundle + map của deploy đang
  live), `mirror.js` (mirror asset battle), `gen_profile_dict.js` (sinh `profile-dict.json`).
- `serve.js` — serve mirror local offline (`/sim.html`,
  `/__sim/*` = `web/`, `/__sim_config/*` = config cache, `/__sim/last-setup.json`).
- `sandbox/` + `web/boot.{html,js}` — boot engine và code game trong browser cách ly.
- `web/setup.html` + `web/setup/` — trang setup profile (`sandbox --setup`), UI bằng Preact +
  htm, ES module gốc của browser (không build; import map trong `setup.html` trỏ `preact`,
  `preact/hooks`, `htm` về `web/vendor/`): `index.js` (entry: state một nguồn qua `update()` →
  `normalize`, prefill từ capture, boot), `skin-rules.js` (rule skin của input, không DOM, import
  được trong Node), `profile-io.js` (state ↔ profile JSON), `ui.js` (`html`, component nhỏ:
  Accordion, Section "Ghi đè", Select, NumberInput, Checkbox), `sections/` (mỗi khung form một file: `map`,
  `heroes`, `mounts`, `summoner`, `lists` cho trap/pet/spell, `buildings`, `golden`, `shared`), `side.js` (khung bên
  phải). Quy ước: handler đặt tên ở trên, template `html\`\`` không chứa hàm inline; `return html\``
  xuống dòng rồi mới viết nội dung, dấu backtick đóng nằm riêng một dòng (htm bỏ khoảng trắng có
  xuống dòng ở hai đầu nên DOM không đổi).
- `web/vendor/` — thư viện bên thứ ba vendor sẵn (sandbox chặn CDN): Preact 10.29.8 + hooks, htm
  3.1.1 (bản ES module). Nguồn, version, license: [web/vendor/README.md](web/vendor/README.md).
- `web/battle/` — mở trận đã capture trong trang cách ly, replay op log, so `QuitRoom`.
  `index.js` (entry, `window.__simBattle`), `setup.js` (giống `Main`), `stubs.js` (lỗi,
  stub mạng, `QuitRoom`), `replay.js` (op log, tick, pause, so kết quả), `profile.js` +
  `hero/` (`selection.js`, `build.js`, `skin.js`) + `map-profile.js` + `build-skin-profile.js` (chỉ load khi `--profile`).
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
