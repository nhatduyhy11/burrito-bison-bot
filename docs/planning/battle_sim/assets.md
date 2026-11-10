# Assets cho battle

Status 2026-11-10: kiểm kê từ runtime (bundle config + manifest ext-res) và config LO.
**Đã mirror** bằng `battle_sim/mirror.js`: 587MB, lớn hơn ước tính từ APK vì gồm toàn bộ
`model/` hero và skin; xem `battle_sim/README.md`. Main doc: [README.md](README.md).
Dump: `.tmp/battle_research/assets/` (`ext-res-version_64467.json`, `campaign_assets.json`),
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

## Đủ để dựng "battle y hệt" (đề xuất)

Offline mirror cho bản có hình (xem README §Simulator): tải toàn bộ bundle `internal`,
`resources`, `login`, `battle`, `battleSkillRes`, `towerDefense`, `organ` theo config +
`ext-res` lọc prefix `model/` (chỉ model trong danh sách campaign + hero + build) và
`shuzhi/`, cùng manifest; serve local cùng cấu trúc URL. Logic sim headless chỉ cần map
JSON (5 file) + config `.bin`.

## APK Android (kiểm 2026-11-10)

File `com.ygjszsea.google 1.10000.51` (bản `_mod`, ký TESTKEY — nguồn không chính thức, chỉ
đọc, không cài/chạy). 200MB, Cocos native, resource version **62127** (web đang 64467 →
cũ hơn, config/asset có thể lệch).

- Trong APK: bundle `battle`, `towerDefense`, `resources`, `login`, `internal`, `main`
  (`index.jsc` 4.5MB — JS mã hóa, key trong `libcocos2djs.so`) + ext-res một phần (116 file).
  **Không có `battleSkillRes`** và phần lớn model → APK là bản "vỏ", còn lại hot-update.
- Giá trị chính: `assets/src/project_62127.manifest` (hot-update) liệt kê **52662 file kèm
  size + md5** (tổng 1.43GB), `packageUrl` `https://mg-sea-cdnres.bighost.games/sea/android/`.
- Dung lượng bộ asset battle tính từ manifest này:

| Phần | MB | file |
|---|---|---|
| bundle `battleSkillRes` | 65.6 | 4756 |
| ext-res model campaign (69 creep/boss) + hero (36) | 48.8 | 888 |
| ext-res model `build_*` | 15.9 | 449 |
| bundle `battle` | 14.5 | 1702 |
| bundle `resources` | 14.5 | 2416 |
| bundle `towerDefense` | 6.1 | 706 |
| bundle `organ` | 2.3 | 266 |
| bundle `login` (chủ yếu UI/video login, chỉ cần font) | 94.9 | 498 |
| **Tổng** (bỏ `login` ≈ 168MB) | 262.6 | |

## Mở

- Danh sách file thật sự tải trong 1 trận (để lọc tối thiểu): đã bật
  `performance.setResourceTimingBufferSize(100000)` + clear trên page runner hiện tại — chạy 1
  map rồi đọc `performance.getEntriesByType('resource')`.
- Dung lượng: đã ước lượng qua manifest APK (version 62127, xem trên); chốt lại theo bản web
  khi mirror thật.
