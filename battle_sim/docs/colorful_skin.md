# Săn skin rainbow (炫彩 / Skin Đa Sắc) và hero ẩn

Nhật ký research ngày 2026-11-09 (server VN `hauntedroomvnh5`). Ngoài flow chính
crawl → dump → UI; chỉ đọc khi cần đào lại skin/hero chưa ra mắt.

## Cách đào

1. Mở game bằng profile Chrome đã đăng nhập (playwright `launch_persistent_context`),
   đợi `window.aswallow.extAssetMgr._verUrlMap` có dữ liệu.
2. Config: lấy URL `preload_config` từ network, đổi thành `config`, giải nén
   `QuickLZ` → `BinaryReader` → `ConfigParser.writeBinaryDataWhenRead`, rồi
   dump mọi bảng `*LO` (tên lấy bằng regex `\b[A-Z]\w*LO\b` trên JS đã tải; ~450 bảng).
   Cách chung xem [BUNDLE_RESEARCH.md](BUNDLE_RESEARCH.md).
3. Asset ngoài bundle (`model/…`, `shuzhi/…`): danh sách key = `Object.keys(_verUrlMap)`
   (~13.8k key); URL tải = `extAssetMgr._transformUrl({ url: key })`.
4. Hiệu ứng skill nằm trong Cocos bundle `battleSkillRes` (`prefabs/Hero_XXX_pfN/...`),
   không nằm trong ext asset.
5. Render Spine bằng `spine-webgl` 3.8 trong headless Chrome để xem từng animation.

So sánh hai lần dump 2026-11-04 và 2026-11-09: main bundle `assets/main/index.1377a.js`
giống hệt (cùng md5), danh sách ext key giống hệt (13 807 key, không thêm/bớt).
Không có dữ liệu mới giữa hai lần.

## Nhận diện skin rainbow

- `DermaLO._color > 7` (= 8) là rainbow; client dùng đúng điều kiện này
  (`HeroUtils.isColorfulDerma`, `getDermaColorfulCfgByHeroSubType`). Mã skin
  `500HH04` (`HH` = hero), `_index = 4`, `_requirement` = đủ 3 skin thường.
- Item kích hoạt: `ItemLO._type = 29`, `_color = 8`, `_effect` = mã derma.
  Skin chưa ra mắt có `_name` dạng tiếng Trung `…炫彩皮` (chưa dịch).
- Skill rainbow: `SkillBaseLO` id `8004HH3s000` (`s` = sao 1..5), `_dermaIndex = 4`;
  nối qua `DermaStarLO._skill`.
- Skin chưa ra mắt = có `ItemLO` / `DermaStarLO` / `HandbookDermaNewLO` /
  `IndividualityHeadLO` nhưng **thiếu dòng `DermaLO`**. Client chỉ hiện skin khi
  `DermaLO` tồn tại và qua `openDay/openDate` + `bHideCond`, nên bật skin chỉ cần
  server đẩy config có dòng `DermaLO`.
- Asset kèm theo: `model/Hero_HHH_pf4` (thân), `_pf4_ez` (bản nhỏ), thường có
  `_pf4_01` (đơn vị/hiệu ứng phụ); khung avatar `shuzhi/AvatarFrame/common_txk_xcyxHH`;
  sảnh `shuzhi/xuancai/…` (`ui_xuancaidiangtang_HHH_zcj`, `ui_xuancai_ruko_HHH`,
  `xcdt_img_pfxqbanner_N`).
- Code battle gắn handler riêng theo tên viết tắt nội bộ của hero:
  `ColorSkin_<ABBR>_*` (preset buff/bullet/damage trong `SkillBuffLO`,
  `SkillBulletLO`, `SkillDamageLO`, `SkillBuffActionLO`).

## Trạng thái 2026-11-09

Đã ra mắt (có `DermaLO`, 6 skin): 001 Tôn Lôi Thần, 002 Huyết Ngục Thống Trị,
005 Cuồng Hoa Nghiệp Hải, 009 Thống Soái Thiên Không, 014 Giáp Đế Hoàng Long,
031 Đạo Chích Đêm Đen.

Chưa ra mắt (10 skin, đủ item + skill + sao, thiếu `DermaLO`):

| Hero | Mã derma | Item | Skill rainbow | Asset đã lên CDN |
| --- | --- | --- | --- | --- |
| 003 Pháp Sư Sương | 5000304 | 30290051 | Linh Hồn Hồi Sinh | chỉ banner `pfxqbanner_3` |
| 004 Vua Pháp Sư | 5000404 | 30290052 | Sân Khấu Ảo Mộng | khung avatar `xcyx04`, banner |
| 008 Tôn Ngộ Không | 5000804 | 30290054 | Hầu Tử Hầu Tôn | không |
| 013 Hắc Lữ Bố | 5001304 | 30290056 | Truy Nã Tử Thần | không |
| 015 Khổng Lồ Xanh | 5001504 | 30290058 | Bão Táp Kim Loại | **model đủ** (`pf4`, `pf4_ez`, `pf4_01`, `pf4_01_gongji_2`), khung `xcyx15` |
| 019 Alice | 5001904 | 30290059 | Thánh Ca Trời Ban | không |
| 023 Thuyền Trưởng U Ám | 5002304 | 30290060 | Cấm Khu Xanh | không |
| 026 Thiên Sứ | 5002604 | 30290061 | Cú Đêm Bí Thuật | không |
| 030 Cô Dâu Linh Dị | 5003004 | 30290062 | Thiên Sứ Huyết Lệ | **model đủ**, ảnh handbook/half/head, khung `xcyx30` |
| 032 Lôi Thần Kiếm Quang | 5003204 | 30290064 | Đại Từ Bi Chưởng | không |

Ứng viên ra mắt sớm nhất: 015 và 030 (đã có model trên CDN). Phụ đề trong
`ItemLO._desc` của item chưa ra mắt (vd `…皮肤-未来战警`, `…皮肤-埃及艳后`) là
placeholder copy-paste, không phải tên skin thật (`埃及艳后` gắn cho cả 003 dù là
chủ đề skin 030).

Viết tắt `ColorSkin_*` đã map được qua id skill: `ZK` → 002, `LCN` → 005,
`YJ` → 009, `RDF` → 014, `PG` → 015, `JWH` → 030. `GYN`, `DZ` có trong code nhưng
chưa có dòng config nào dùng — handler cho skin tương lai (GYN có `Jade_Bottle`,
`Rain` → suy đoán hợp với 032 "Đại Từ Bi Chưởng", chưa xác nhận).

## Kiểm chứng skin rainbow 015 (Khổng Lồ Xanh)

Kết luận: asset `Hero_015_pf4*` đúng là skin rainbow của hero 015. Tên nội bộ
của hero 015 là **盘古 (Bàn Cổ)** (`BuildLO` heroCode 50000015: `提升盘古的必杀技`),
nên skin mang chủ đề chiến thần lửa có sừng, không giống Hulk xanh của bản gốc.

Bằng chứng độc lập:

- Config: `ItemLO 30290058 蓝巨人炫彩皮` → `5001504`; `DermaStarLO 5001504`
  → skill `8004153s000`; `SkillActionLO._log = 盘古皮肤`; buff perform
  `Hero_015_pf4_bc_tar`; bullet `Hero_015_pf4_skill_01`; handbook `jy_img_pf4_015`.
- Code: preset `ColorSkin_PG_Record` + công thức `dynamicsFactor`
  = `clamp(p_blood_lost // step * step, 0, max)` (mục tiêu mất máu càng nhiều thì
  hệ số diệt càng cao), popup `p_pangu_pf4`. Skill rainbow dùng hệ **Mất HP
  (Blood)** — cùng cơ chế với cả 3 skill gốc của hero 015.
- Metadata Spine (`skeleton.audio`, đường dẫn PSD của artist):
  `Hero_015` = `…/Hero_000_绿巨人/…`, `Hero_015_pf4` = `…/炫彩皮肤场景/绿巨人`,
  `Hero_015_pf4_01` = `…/技能特效/spine/015_pf4_盘古`.
- `ModelDisplayLO`: `Hero_015_pf4` có mốc ra đòn `_gongji [0.7, 0.4]`,
  `_bisha [1.3, 0.5]` trùng y hệt `Hero_015` gốc và skin pf1/pf3.

Đối chiếu kỹ năng gốc (hero 015 không skin):

| Kỹ năng gốc | Loại | Animation / đạn gốc | Ở skin pf4 |
| --- | --- | --- | --- |
| Bão Biển Chỉ Dẫn (ném biển STOP) | PRIMARY | `gongji` + đạn `Hero_015_gongji_01` | `gongji` có, cùng mốc ra đòn |
| Lốp Xe Huyết Đao (ném lốp xe) | MANUAL | `bisha` + đạn `Hero_015_bisha_01` | `bisha` có, cùng mốc ra đòn |
| Định Luật Hulk | PASSIVE | không animation riêng | không đổi |
| Thần Binh / Thần Khí | PASSIVE | không animation riêng | không đổi |

Skin pf4 có đủ bộ animation như gốc (`daiji, gongji, bisha, paobu, siwang,
zhanshi, kongzhi, shouji`) + `chuchang` (xuất hiện; rainbow 001 cũng có, gốc thì không).
Không skill derma nào có `_effect` đổi `Bullet_Model`, nên đạn của 2 skill gốc
vẫn là đạn gốc; skin thay **toàn bộ thân** (rig 152 bone, gốc 72 bone) và **thêm
1 skill** (Bão Táp Kim Loại: mỗi 10 s gây Mất HP 6 s diện rộng, giảm 50% trị liệu,
"Diệt Sạch" quái theo % máu mất).

Lưu ý: skin rainbow đã ra mắt **có** thể đổi hiệu ứng đòn đánh/tuyệt kỹ — 014 có
`prefabs/Hero_014_pf4/Hero_014_pf04_gongji_01`, `…_bisha_01/02` trong
`battleSkillRes` và mốc `_bisha` khác gốc. 015 hiện chưa có thư mục
`prefabs/Hero_015_pf4` trong `battleSkillRes` (cả `Hero_015_pf4_skill_01` cũng chưa).

Hiệu ứng lạ (`Hero_015_pf4_01`, linh thể lửa cầm kiếm: `chuxian, gongji1-3,
paobu, siwang`) là model của creep **仙剑** `CreepLO 30061000..30061400`
(subType 915), đặt cạnh 火莲花 `30058xxx` (subType 914, model `Hero_014_pf4_01`)
của skin 014. Khác 014 (skill `80041431000` triệu hồi 火莲花 qua `SkillSummonLO`),
hiện **không** `SkillSummonLO` nào gọi `30061xxx`, và skill của creep
(`10004601000`, `10004701000`) chưa có trong `SkillBaseLO` → phần triệu hồi của
skin 015 chưa nối config (đang làm hoặc bỏ).

Bẫy dễ nhầm: trong thư mục `model/Hero_001_pf4/` có file lạc tên
`Hero_015_pf4.json`; cấu trúc của nó trùng rig Hanuman rainbow (173 bone, 92 slot,
cùng đường dẫn PSD `Hero_015_pf4_盘古` mà `Hero_001_pf4` cũng mang) — không phải
skin 015. Skin 015 thật là `model/Hero_015_pf4/`.

## Hero ẩn

Không có hero chưa ra mắt trên server VN:

- `HeroLO` có 36 hero (`50000001..50000036`), tất cả `_isShow = 1`; model
  `Hero_001..Hero_036` đều có, không có `Hero_037+`.
- `ChipItemLO 40001037..40001074` (鲁肃, 孙策, 吕布, 魔吕布魔晶…, icon placeholder
  `icon_sp_001`) và ảnh `CircleHead/touxiang_yuan_037..074` (cùng dải số, cùng
  khoảng trống 050/051/061) là dữ liệu sót từ game Tam Quốc dùng chung engine.
- `head/touxiang_img_037.png` (yêu tinh đội mũ sắt) không được config/code nào
  tham chiếu.
- Model không được tham chiếu: biến thể vùng (`kr_`, `jp_`, `tw_`, `sea_`), thú cưỡi
  `zuoqi_06/09`, `machine_ui_018`, `role_zhaohuan_001y` — không phải hero.

## Kiểm tra lại lần sau

- Hash `assets/main/index.*.js` hoặc số ext key đổi → dump lại.
- Có dòng `DermaLO` mới với `_color = 8` → skin vừa mở.
- Có thư mục `prefabs/Hero_015_pf4` / `Hero_030_pf4` trong `battleSkillRes`,
  hoặc `SkillSummonLO` trỏ tới `30061xxx` → 015 sắp ra.
- `ColorSkin_GYN_*` / `ColorSkin_DZ_*` xuất hiện trong config → skin của hero
  tương ứng đã được nối.
