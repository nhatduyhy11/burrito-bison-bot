# Hero phẩm đỏ — tên in-game & match skill GAT vs VN

Chuẩn: bản GAT (trunk_66196, tên TW). Tên VN/EN lấy từ bản VN (sea_65553, lang_vi / lang_en) cùng `HeroLO._code`. Cột TQ_vn là phiên âm Hán Việt thủ công của cột TQ (không có trong config).

Match = so sánh toàn bộ row config của 3 skill base (slot 1–3, family id `10<NN>0<slot>*000`) giữa GAT và VN trên 3 bảng `SkillBaseLO` + `SkillDamageLO` + `SkillTargetLO`: bộ id phải giống nhau và mọi field triển khai phải bằng nhau (đã loại trừ field hiển thị `_name/_desc/_detailedDesc/_icon`).

| Name VN | Name (EN) | Name TQ | TQ_vn (Hán Việt) | Match |
|---|---|---|---|---|
| Hanuman | Hanuman | 拳鬼 | Quyền Quỷ | 100% |
| Gai Độc | Spiker | 毒刺 | Độc Thứ | 100% |
| Pháp Sư Sương | Frosthealer | 霜愈法師 | Sương Dự Pháp Sư | 100% |
| Vua Pháp Sư | Archmage | 君王法師 | Quân Vương Pháp Sư | 100% |
| Pháo Loli | Cannon Girl | 蘿莉炮手 | La Lợi Pháo Thủ | 100% |
| Tôn Ngộ Không | Metaman | 孫悟空 | Tôn Ngộ Không | 100% |
| Hiệp Sĩ Sấm Sét | Laserman | 雷射俠 | Lôi Xạ Hiệp | 100% |
| Hắc Lữ Bố | Lu Bu | 鬼關羽 | Quỷ Quan Vũ | 100% |
| Rồng Máy | Pyrogon Mech | 炎龍機甲 | Viêm Long Cơ Giáp | 100% |
| Khổng Lồ Xanh | Blue Giant | 藍巨人 | Lam Cự Nhân | 100% |
| Alice | Mad Alice | 愛瘋絲 | Ái Phong Tư | 100% |
| Thuyền Trưởng U Ám | Ghost Captain | 幽冥船長 | U Minh Thuyền Trường | 100% |
| Thiên Sứ | Archangel | 聖天使 | Thánh Thiên Sứ | 100% |
| Cô Dâu Linh Dị | Bride Wraith | 鬼新娘 | Quỷ Tân Nương | 100% |
| JOKER | JOKER | JOKER | JOKER | 100% |
| Lôi Thần Kiếm Quang | Thundermaster | 光劍雷神 | Quang Kiếm Lôi Thần | 100% |

## Bản yg (weixin_129776, config21)

Cùng 36 hero / 16 hero đỏ / cùng code và set skill id, nhưng **định danh nhân vật khác hẳn** (theme thần thoại Trung, chữ giản thể): cùng một code là 3 nhân vật khác nhau ở 3 bản. Model gốc trùng nhau (`Hero_0NN`, art regional khác). HeroLO row chỉ khác `_dermaInterfacePic`/`_atkAction` (art/animation, không phải stat).

| Code | TQ (yg) | Hán Việt (yg) | TQ (GAT) | Name VN | Match yg↔GAT |
|---|---|---|---|---|---|
| 50000001 | 地藏王 | Địa Tạng Vương | 拳鬼 | Hanuman | 100% |
| 50000002 | 钟馗 | Chung Quỳ | 毒刺 | Gai Độc | 100% |
| 50000003 | 孟婆 | Mộng Bà | 霜愈法師 | Pháp Sư Sương | 100% |
| 50000004 | 东皇太一 | Đông Hoàng Thái Nhất | 君王法師 | Vua Pháp Sư | 100% |
| 50000005 | 罗刹女 | La Sát Nữ | 蘿莉炮手 | Pháo Loli | 100% |
| 50000008 | 斗战胜佛 | Đấu Chiến Thắng Phật | 孫悟空 | Tôn Ngộ Không | 100% |
| 50000009 | 二郎神 | Nhị Lang Thần | 雷射俠 | Hiệp Sĩ Sấm Sét | 100% |
| 50000013 | 阎罗王 | Diêm La Vương | 鬼關羽 | Hắc Lữ Bố | **67%** |
| 50000014 | 燃灯佛 | Nhiên Đăng Phật | 炎龍機甲 | Rồng Máy | 100% |
| 50000015 | 盘古 | Bàn Cổ | 藍巨人 | Khổng Lồ Xanh | 100% |
| 50000019 | 女娲 | Nữ Oa | 愛瘋絲 | Alice | 100% |
| 50000023 | 九灵元圣 | Cửu Linh Nguyên Thánh | 幽冥船長 | Thuyền Trưởng U Ám | 100% |
| 50000026 | 观音菩萨 | Quan Âm Bồ Tát | 聖天使 | Thiên Sứ | 100% |
| 50000030 | 九尾狐 | Cửu Vĩ Hồ | 鬼新娘 | Cô Dâu Linh Dị | 100% |
| 50000031 | 牛魔王 | Ngưu Ma Vương | JOKER | JOKER | 100% |
| 50000032 | 弥勒佛 | Di Lặc Phật | 光劍雷神 | Lôi Thần Kiếm Quang | 100% |

So sánh skill cùng phương pháp (SkillBaseLO + SkillDamageLO + SkillTargetLO, family `10<NN>0<slot>*`, bỏ field hiển thị): 15/16 hero match 100% yg↔GAT↔VN. Skill id set trùng khớp hoàn toàn, schema row không drift.

## Issue

Không có issue skill: 16/16 hero đỏ match 100%. Cụ thể trên 144 tổ hợp (16 hero × 3 slot × 3 bảng): 88 tổ hợp có row ở cả hai bản — bộ id trùng khớp và 0 khác biệt field; 56 tổ hợp không có row ở **cả hai** bản (43 `SkillTargetLO`, 13 `SkillDamageLO` — cơ chế chạy qua row dùng chung) → vẫn là match. `_phases` của mọi slot đều trỏ trong nội bộ family, không có tham chiếu ra ngoài. Màu hero (`_color=6`) trùng nhau ở cả hai bản.

### Khác biệt ngoài phạm vi skill (không ảnh hưởng match)

- **50000001** và **50000013** bị đổi định danh theo khu vực: model GAT `Hero_001`/`Hero_013` vs VN `Hero_001_sea`/`Hero_013_sea` (asset regional có chủ đích). TW 拳鬼 ↔ VN Hanuman; TW 鬼關羽 (Quan Vũ) ↔ VN Hắc Lữ Bố (Lữ Bố) — khác cả nhân vật, không chỉ tên. Skill vẫn match 100%.
- Tên EN là bản localization riêng (Metaman, Spiker…), JOKER giữ nguyên cả 3 ngôn ngữ.

### Issue skill: 50000013 slot 2 — khác biệt thật giữa yg vs GAT/VN

`SkillDamageLO[10130201000]`: yg có `_addonType="Normal_Trigger"` + `_addon=-100`, GAT/VN để `""`/`0`. Mọi field khác của row và của cả family đều bằng nhau; mô tả skill 2 bên cũng như nhau (3 đợt × 3 đạn, 30% ATK, xuyên 3 lần).

Engine (đọc từ src bundle, cả yg lẫn GAT cùng cơ chế): khi `addonType` khác rỗng, mỗi hit được gắn thêm 1 addon damage với `factor = _addon`; `Normal_Trigger` không nằm trong case nào của switch (`Blood_Less_Check*`, `Damage_According_To_Blood`) nên rơi xuống nhánh gắn addon generic. Theo quy ước dấu của row gốc (`-30` = 30% ATK), `-100` = **mỗi hit của skill 2 Diêm La Vương (yg) cộng thêm 100% ATK** — bản GAT/VN (鬼關羽) đã bỏ addon này. Skill yg ăn mạnh hơn hẳn GAT/VN ở slot 2, và phần mô tả không nhắc gì đến nó.

---

Script: `.tmp-scratch/hero-red-compare.js` → `.tmp-scratch/hero-red-compare.json` (GAT vs VN); `.tmp-scratch/hero-red-yg-compare.js` → `.tmp-scratch/hero-red-yg-compare.json` (yg vs GAT). Nguồn config: GAT `config.66196.bin` + `lang_tw` (lúc đó ở `.tmp/skin-research-cn/`, nay cache GAT là `.tmp/battle_sim_gat/config/<configVersion>/`); VN `.tmp/battle_sim/config/sea_65553/config.bin` + `lang_vi`/`lang_en`; yg `.tmp/ygkksy-research/config21.bin` (không có lang pack, tên giản thể gốc trong config).

Nguồn gốc các bản (yg = private server, 妖怪金手指 = tên CN official…): [docs/versions/GAME_VERSIONS.md](versions/GAME_VERSIONS.md).
