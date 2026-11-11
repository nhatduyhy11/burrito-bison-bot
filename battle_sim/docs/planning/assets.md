# Assets cho battle

Kiểm kê 2026-11-10 từ runtime (bundle config + manifest ext-res) và config LO. Bundle nào
được mirror và vì sao: [battle_sim/README.md §Mirror asset](../../README.md#mirror-asset-mốc-b-bước-1).
Index: [research.md](research.md). Dump: `.tmp/battle_research/assets/` (`ext-res-version_64467.json`, `campaign_assets.json`),
`.tmp/battle_research/bundles.json`.

## Nguồn asset

Host `https://hauntedroomvnh5.joynetgame.com/`. Hai loại:

1. **Cocos bundle** `assets/<bundle>/` — `config.<hash>.json` (path → uuid) + `import/<2 ký tự>/<uuid>.<hash>.json`
   + `native/<2 ký tự>/<uuid>.<hash>.<ext>`. Đọc runtime: `cc.assetManager.getBundle(n)._config.paths._map`.
2. **ext-res** `ext-res/<path có hash>` — manifest `ext-res/version_<ver>.json` (13807 entry,
   logical path → path có hash, vd `model/Boss_014/Boss_014.json` → `model/Boss_014/Boss_014_6d286.json`).
   Prefix ext-res do `ResourceManager._extResPathPrefixList`: `model/`, `model_frame/`,
   `ext_ui/`, `shuzhi/`, `heroBust/`, `userProto`, `battleLog`, `data/`.

Version (`64467`) và hash đổi theo đợt deploy → luôn lấy từ page vừa boot.

## Bundle liên quan battle

| Bundle | paths / assets | Nội dung |
|---|---|---|
| `battle` | 276 / 1595 | `prefabs/tiledBg` (map Tiled + brush/tileset, 49), widget HUD (26), attachments (21), view (18), rollerBg, spine UI kết quả trận |
| `battleSkillRes` | 820 / 3061 | FX skill theo model: `prefabs/Hero_0xx*`, `Boss_0xx`, `XG_0xx`, `build`, `buff`, `machine_*` (trap), `shenshou_*` (beast), `daoist` |
| `towerDefense` | 208 / 535 | UI TD: thẻ summon, vòng quay, cảnh báo, HUD |
| `organ` | 81 / 180 | UI trap/organ |
| `resources` | 843 / 1735 | `ui/common`, shader (`shaders/battle`…), audio, `prefabs/model` |
| `internal`, `login` | 17 / 170 | builtin material/effect, font — dependency của `battle` |

Khác (hangup, hero, summon, activity…) là lobby/UI ngoài trận — không cần.

## ext-res cho battle

- `model/<Name>/<Name>.{json,atlas,png}` (spine; `GameSpine` dùng `.json` cho `model/`):
  594 thư mục, gồm biến thể vùng `_sea/_jp/_kr/_tw/_us`.
  - Creep/boss campaign: **69 model** (`XG_0xx`, `Boss_0xx`) từ 133 creep code
    (`AdventuretdRoundLO.creep` → `CreepLO.model`).
  - Hero: **36 model** (`HeroLO.model`, `Hero_0xx`, có `_sea`); skin qua `DermaLO.deco`.
    Mirror lấy đủ mọi hero và skin, xem README §Model hero trong trận.
  - Build: `build_*` (vd `build_cdz_001`, `build_zcm_001` — giường/cửa/công trình).
- `shuzhi/icon`, `shuzhi/head` — icon tài nguyên, avatar (HUD).
- Kích thước tham khảo: `Boss_014` json 70KB + atlas 5KB + png 52KB.

## Map

- Map = prefab `battle/prefabs/tiledBg/map/<tiledBg>` chứa `mapJson` (Tiled JSON: layer
  `tiled/map/brush/grids/build/bed/gate/born/bornPlayer/organ…`) + `commonJson` +
  `brushJson` (tileset `prefabs/tiledBg/brush/<theme>/…`). Engine: `TiledMapData.initData`
  qua `BattleEngineDelegate.initMapData`.
- `BattleGroundLO.tiledBg` theo `battleGroundCode` của level. **Campaign 400 level chỉ dùng 5
  map**: `td_bgs_002`, `td_jd_001`, `td_xx_001`, `td_yy_001`, `td_bwg_001` (80 level mỗi map).
  `houseNum 6`, `duration 1800`.

## APK Android

Bản `com.ygjszsea.google 1.10000.51` (`_mod`, ký TESTKEY, nguồn không chính thức — chỉ đọc,
không cài/chạy) chỉ là bản "vỏ" (resource 62127, không có `battleSkillRes` và phần lớn model),
còn lại hot-update. `assets/src/project_62127.manifest` liệt kê 52662 file kèm size + md5,
`packageUrl` `https://mg-sea-cdnres.bighost.games/sea/android/`. Không dùng cho simulator.

## Mở

- Danh sách file thật sự tải trong 1 trận (để cắt bớt mirror): đọc `misses.log` / resource
  timing của trang sandbox.
