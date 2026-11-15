# Cache, snapshot và mirror

Chạy các lệnh từ gốc repo. Cache và capture VN nằm dưới `.tmp/battle_sim/` và
`.tmp/battle_research/` (gitignore). Replay headless cần capture, bundle, config và map
đúng version. Sandbox browser cần thêm mirror asset.

## Snapshot và version

Mỗi trận chạy đúng bộ file khớp version trong `StartGameP` (`lib/versions.js`), cache ở
`.tmp/battle_sim/` (không commit):

| `StartGameP` | Ý nghĩa | Cache | Nguồn |
|---|---|---|---|
| `battleVersion` | `BATTLE_ENGINE_VERSION` + `ENGINE_BRIDGE_VERSION` in trong code bundle | `bundles/index.<hash>.js` (quét cả `.tmp/bundle/main.*/`) | `snapshot.js` |
| `configVersion` | `ConfigParser.branch_version` | `config/<ver>/{config,preload_config}.bin` | tự tải từ CDN khi thiếu (CDN giữ bản cũ) |
| `mapVersion` | `resources/tiledBgVersion.json` | `maps/<ver>/*.json` | `snapshot.js` |

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

## Mirror asset cho browser

Tạo mirror khi `ClientVer` cần dùng còn live. `plan` liệt kê những gì cần tải, còn
`fetch` tải file vào cache.

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
  - bundle view trận theo mode: `guildPVP` (+ `worldBoss`, `climbTower` mà prefab tham chiếu chéo)
    cho U Đô `battleType 21`, `worldBossMatch` cho Ác Mộng/World Boss tháng `battleType 43`
    (`BattleTDWorldBossMatchView`). Thiếu bundle view thì trận đứng sau `StartGameP pushed`
    (log 404 `assets/<bundle>/config.*.json`, "View加载失败"). Mode mới: thêm bundle vào `BUNDLES`;
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

### Model hero trong trận

- Hero (và creep, boss, build) trong trận là spine ở ext-res
  `model/<tên>/<tên>_<hash>.{json,skel,atlas,png}`, kèm bản `_h`/`_l` (atlas độ phân giải
  cao/thấp). Không nằm trong bundle Cocos nào.
- Tên model gốc lấy từ `HeroLO.model`. Khi hero mặc skin, tên lấy từ `DermaLO.deco` (vd `Hero_001_pf2`).
  Game load khi unit xuất hiện, qua `aswallow.extAssetMgr`, vào `GameSpine` ở node
  `$_DISPLAY_NODE` của unit.
- Mirror lấy model theo bộ lọc vùng cho mọi account. Đổi account hoặc chơi hero/skin khác
  trong cùng vùng bằng `--play` dùng lại được mirror.
- Bộ lọc vùng dựa vào hậu tố tên thư mục, nên tên như `Hero_001_kr_pf1` vẫn có thể được mirror.

## Chuyển cache sang máy khác

### Bắt buộc copy (không tải lại được)

| Đường dẫn | Đọc bởi | Vì sao |
|---|---|---|
| `.tmp/battle_research/events-*.jsonl` | `lib/capture.js` (`replay.js`, `serve.js`, `sandbox --battle/--play`) | Capture trận (`StartGameP` + `QuitRoom`). Mất thì phải chơi lại trên game thật. |
| `.tmp/battle_sim/bundles/index.<hash>.js` | `lib/versions.js` | Code bundle đúng `battleVersion` của capture. Host chỉ giữ bản đang live. |
| `.tmp/battle_sim/maps/<mapVersion>/` | `lib/versions.js` | Map Tiled đúng `mapVersion`. Cùng lý do như bundle. |
| `.tmp/battle_sim/played/*.jsonl` | `replay.js <file>` | Trận tự chơi bằng `--play` (nếu có). |

### Nên copy (tải lại được nhưng lâu hoặc có điều kiện)

| Đường dẫn | Ghi chú |
|---|---|
| `.tmp/battle_sim/mirror/<ClientVer>/` | Asset cho `serve.js` / `sandbox`. `mirror.js fetch` tải lại được **chỉ khi** host vẫn ở cùng ClientVer. Game đã cập nhật thì mirror mới lệch với capture cũ. |
| `.tmp/battle_sim/config/<configVersion>/` | Thiếu thì tự tải từ CDN (CDN giữ bản cũ): `replay.js` qua `lib/versions.js`, sandbox/trang sim qua `serve.js` khi trang xin `/__sim_config/...`. Xoá bản cũ sau khi game update vẫn an toàn. |

### Không cần

- `.tmp/battle_sim/sandbox-*.log`, `simlog-*.json`: log chạy.
- Phần còn lại của `.tmp/battle_research/` (`q_*.js`, `driver.py`, ảnh, `data/`…): tool nghiên
  cứu. Chỉ cần nếu muốn capture trận mới bằng `run_runner_hooked.py`.
- `.tmp/bundle/`: bundle nghiên cứu cũ. `versions.js` có quét, nhưng `bundles/` đã đủ.
- `.tmp/pspo/`: profile Chrome **có đăng nhập**. Không mang sang máy khác.

### Đóng gói và giải nén

Ở máy cũ, tại gốc repo (nén giúp copy mirror nhanh hơn). File nén ghi vào
`.tmp/` (đã gitignore) để tránh đưa cache vào Git:

```bash
tar -czf .tmp/battle_sim_cache.tgz .tmp/battle_sim/bundles .tmp/battle_sim/maps .tmp/battle_sim/config .tmp/battle_sim/mirror .tmp/battle_research/events-*.jsonl
```

Có trận `--play` thì thêm `.tmp/battle_sim/played` vào lệnh trên.

Ở máy mới, chép file vào `.tmp/` của repo (sau khi checkout đúng nhánh), rồi tại gốc repo:

```bash
tar -xzf .tmp/battle_sim_cache.tgz
```

```bash
uv sync
```

### Kiểm tra sau khi chuyển

```bash
node battle_sim/replay.js
```

Replay phải khớp mọi capture hoàn chỉnh và tìm được bundle, map đúng version.

```bash
uv run python battle_sim/sandbox --headless
```

Phải ra `ready`, 0 request bị chặn, 0 file 404 (mirror đủ).
