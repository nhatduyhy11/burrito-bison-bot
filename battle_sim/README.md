# battle_sim — campaign battle offline

Chạy trận campaign offline bằng chính code và asset của game: headless trong Node để replay
(mốc A), và có hình trong browser cách ly để xem lại hoặc tự chơi (mốc B). Không kết nối
server game.

Mục tiêu, **nguyên tắc an toàn** và nghiên cứu cơ chế: [docs/planning/research.md](docs/planning/research.md).

## Cache và asset

Replay cần bundle, config và map khớp version của capture. Chạy snapshot khi deploy
còn live để giữ bundle và map. Nếu dùng sandbox browser, chuẩn bị thêm mirror asset.
Xem [CACHE.md](CACHE.md) để tạo và chuyển cache.

## Replay

Replay mọi capture hoàn chỉnh trong cache bằng Node:

```bash
node battle_sim/replay.js
```

Để chọn trận, xem lại trong browser hoặc đọc kết quả so sánh, xem
[hướng dẫn replay](docs/REPLAY.md).

## Tự chơi trận offline

```bash
uv run python battle_sim/sandbox --battle "<uuid>" --play
```

```bash
uv run python battle_sim/sandbox --battle "<uuid>" --play --seed random
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
  `hero-dict.json` + `support-dict.json` và capture, không nạp code game.
- `sandbox` chạy `serve.js` bằng `node` trên PATH. Shell không thấy node (ví dụ node cài
  qua nvm nhưng terminal mở trước đó) thì đặt `$env:BATTLE_SIM_NODE = '<đường dẫn node.exe>'`.

- `--play` mở trận mẫu theo UUID trong cửa sổ sandbox để tự chơi bằng UI của game.
  Phiên tự chơi mặc định giữ cửa sổ mở, với timeout 3600 giây.
- `--seed` mặc định dùng UUID của capture. Dùng `random` để sinh seed mới hoặc truyền
  một chuỗi cụ thể để dùng lại seed đó.
- `--profile <file.json>` áp tùy chỉnh lên trận mẫu. Xem [các trường profile](docs/PROFILE.md)
  và [JSON mẫu](profile.example.json).
- Khi trận kết thúc, kể cả bỏ trận, sandbox lưu vào
  `.tmp/battle_sim/played/played-<uuid>-<ts>.jsonl`. Có thể [replay file này](docs/REPLAY.md).
  Đóng màn kết quả để quay lại trang setup nếu chạy `--setup`, hoặc kết thúc phiên nếu chạy
  `--play`.

Xem đường đi của thao tác, tăng tốc, auto và xử lý kết quả trong
[cơ chế battle trong sandbox](docs/BATTLE_ENGINE.md).

### Setup GAT

```bash
uv run python battle_sim/sandbox --setup
```

Chọn **GAT** trong dropdown **Vùng** ở mục **Account gốc**. VN là mặc định cho
setup mới. Khi bấm **Chơi** với GAT, sandbox dùng port 8091 và cache riêng
`.tmp/battle_sim_gat/` (`versions.gat` trong `lib/versions.js`): capture `events-*.jsonl`,
`bundles/`, `maps/`, `config/<configVersion>/`, `mirror/<ClientVer>/`, `profiles/`, `played/`.
Bundle, config và map đi theo version trong `StartGameP` của capture. Catalog dùng chung các dict VN rồi ghép
`web/dict/gat-overrides.json` cho skin, pet, đồ cổ và asset theo vùng. Lần đầu chạy GAT cần mạng để tải config, pack `tw` và asset tĩnh còn thiếu
(mirror lấy theo deploy GAT đang live nếu chưa có). Xem [hero_gear.md](docs/planning/hero_gear.md) cho đối chiếu dữ liệu hero gear.

Chuẩn bị cache GAT (khi GAT cập nhật thì làm lại cả hai bước):

```bash
node battle_sim/scripts/snapshot.js --gat
```

```bash
uv run python .tmp/battle_research/launch_pmain.py .tmp/pcn .tmp/battle_sim_gat/events-pcn-<ngày>.jsonl https://hauntheroesweb.acenetgame.com/
```

Lệnh thứ hai mở GAT bằng profile `.tmp/pcn` với hook capture thụ động; chơi một trận
đến hết để có `StartGameP` + `QuitRoom` làm khung xương.

### Dùng đội hình pmain trong playtest GAT

```bash
node battle_sim/scripts/copy_pmain_to_gat.js
```

Script lấy capture hoàn chỉnh mới nhất theo tên file của pmain và GAT. Có thể
chỉ định file bằng `--vn` và `--gat`, hoặc chọn trận bằng `--vn-uuid` và
`--gat-uuid`. Script chép đội hình và hero hỗ trợ từ VN, gồm chỉ số, level,
đột phá và skill đã capture. Map, người chơi, máy và công trình lấy từ mẫu GAT.

Trong Setup, chọn vùng **GAT** rồi chọn trận theo **Capture ID** script in ra.
Để dùng lại seed gốc của trận mẫu, nhập **GAT template seed** vào ô seed.
Capture tạo ra dành cho chế độ **Chơi** offline và có danh sách thao tác rỗng.

### Tranh Bá liên server (battleType 42)

Trong **Màn chơi**, bật **Ghi đè**, chọn **Tranh Bá liên server** → **Boss** → **Bộ quái**.
Chỉ hỗ trợ vòng chiếm phòng; preset ghi rõ nhóm/ngày/phòng. Có thể dùng capture campaign, U Đô hoặc
Tranh Bá làm nguồn đội hình solo; engine kiểm tra boss/level với config của capture gốc.

Crawl lại catalog riêng (24 boss / 399 preset vòng chiếm phòng ở config này, bỏ sơ tuyển):

```bash
node battle_sim/scripts/gen_naval_dict.js sea_66328
```

`mirror.js fetch` có kèm bundle `guildPvpPromotion` để mở UI trận offline.
Xem [research và kiểm chứng](docs/planning/tranh_ba.md).

## Cấu trúc

- `replay.js` — replay + so sánh, 1 hoặc nhiều trận.
- `scripts/` — công cụ chạy riêng: `snapshot.js` (cache code bundle + map của deploy đang
  live), `mirror.js` (mirror asset battle), `gen_profile_dict.js` (sinh `hero-dict.json` + `support-dict.json`).
- `serve.js` — serve mirror local offline (`/sim.html`,
  `/__sim/*` = `web/`, `/__sim_config/*` = config cache, `/__sim/last-setup.json`).
- `sandbox/` + `web/boot.{html,js}` — boot engine và code game trong browser cách ly.
- `web/setup.html` + `web/setup/` — trang setup profile (`sandbox --setup`), UI bằng Preact +
  htm, ES module gốc của browser (không build; import map trong `setup.html` trỏ `preact`,
  `preact/hooks`, `htm` về `web/vendor/`): `index.js` (entry: state một nguồn qua `update()` →
  `normalize`, prefill từ capture, boot), `skin-rules.js` (rule skin của input, không DOM, import
  được trong Node), `profile-io.js` (state ↔ profile JSON; re-export `profile-state.js` = state shape +
  `normalize`, `profile-export.js` = `toProfile`, `profile-import.js` = `fromProfile`), `ui.js` (`html`, component nhỏ:
  Accordion, Section "Ghi đè", Select, NumberInput, Checkbox), `sections/` (mỗi khung form một file: `map`,
  `heroes`, `mounts`, `summoner`, `lists` cho trap/pet/spell, `buildings`, `golden`, `shared`), `side.js` (khung bên
  phải). Quy ước: handler đặt tên ở trên, template `html\`\`` không chứa hàm inline; `return html\``
  xuống dòng rồi mới viết nội dung, dấu backtick đóng nằm riêng một dòng (htm bỏ khoảng trắng có
  xuống dòng ở hai đầu nên DOM không đổi).
- `web/vendor/` — thư viện bên thứ ba vendor sẵn (sandbox chặn CDN): Preact 10.29.8 + hooks, htm
  3.1.1 (bản ES module). Nguồn, version, license: [web/vendor/README.md](web/vendor/README.md).
- `web/battle/` — mở trận đã capture trong trang cách ly, replay op log, so `QuitRoom`.
  `index.js` (entry, `runBattle`), `setup.js` (giống `Main`), `stubs.js` (lỗi,
  stub mạng, `QuitRoom`), `replay.js` (op log, tick, pause, so kết quả), `profile.js` +
  `hero/` (`selection.js`, `build.js`, `skin.js`) + `map-profile.js` + `build-skin-profile.js` (chỉ load khi `--profile`).
  Toàn bộ `web/` là ES module (`import`/`export`), kể cả `boot.js` (`boot.html` nạp bằng `type="module"`);
  chỉ engine và code của game (manifest, cocos2d, `jsList`) cùng `lib/proto_rebuild.js` vẫn nạp bằng
  `<script>` thường qua `loadScript` vì chúng sống bằng biến toàn cục (`cc`, `window.__require`, `makeRebuilder`).
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
