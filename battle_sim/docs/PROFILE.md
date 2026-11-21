# Profile JSON cho playtest

Profile ghi các tùy chỉnh áp lên trận mẫu trong simulator. Có thể tạo, xuất hoặc nhập JSON từ `--setup`, hoặc sửa [profile.example.json](../profile.example.json) và chạy từ gốc repo.

```bash
uv run python battle_sim/sandbox --battle "<uuid>" --play --profile battle_sim/profile.example.json
```

Bỏ trường muốn giữ từ capture. Với các danh sách như `traps`, `pets` và `spells`, mảng rỗng xóa danh sách. Các trường có thể dùng `null` được ghi riêng bên dưới. Hero hỗ trợ vẫn lấy từ capture.

## Map và đội hình

- `map` chọn màn chơi. Campaign dùng `{ "mode": "campaign", "stage": 66 }` và cần capture campaign để lấy đồng đội robot. U Đô dùng `{ "mode": "capital", "boss": "cursed_botchling", "level": 20701 }`, trong đó `level` phải là một preset thật của boss trong catalog. Tranh Bá liên server dùng `{ "mode": "naval", "boss": "hell_flytrap_70070401", "level": 2040401 }` (type 42), lấy boss và preset từ [naval-boss-dict.json](../web/dict/naval-boss-dict.json). Preset phân biệt sơ tuyển và nhóm/ngày/phòng của vòng chiếm phòng. Khi bỏ `map`, trận giữ màn gốc. Xem [map-dict.json](../web/dict/map-dict.json) và [boss-dict.json](../web/dict/boss-dict.json).
- `heroes` phải có đúng 5 hero khác nhau. Mỗi mục là slug hoặc object có `name` và phần tùy chỉnh. Hero đã có trong capture giữ tiến độ gốc. Hero mới lấy mẫu từ các hero cùng độ hiếm, hoặc từ toàn đội nếu thiếu mẫu cùng độ hiếm. Simulator lấy trung bình `attr` sau khi trừ `selfAttr` của skin, lấy level và `breakThrough` của hero trung vị, và chọn level skill theo đa số ở từng slot. Thánh Khí và Thần Khí của hero mẫu không được sao chép. Xem [catalog hero](../web/dict/hero-dict.json) và [cách cấu hình skin](../PROFILE_SKINS.md).
- `summonedJoker` có cùng định dạng với một hero. Khi Pháo Loli dùng skill skin `guns_n_roses` và Joker vắng mặt trong đội chính, setup mở Joker ở slot 6. Ví dụ `{ "name": "joker", "skin": "nocturnal_burglar", "star": 5 }` chỉ áp dụng cho Joker được triệu hồi.

### Gear và Dị Năng

- `avatar` trên hero đỏ là số node skill Dị Năng đã mở theo thứ tự chapter (0–5), ví dụ `{ "name": "lu_bu", "avatar": 2 }`. Mỗi node thay hoặc thêm một skill theo `avatarNodes` trong catalog. Simulator áp skill và giữ các chỉ số đã tính ở capture. Xem [hero gear](planning/hero_gear.md).
- `artifact` chọn Thần Khí cho hero đỏ bằng object có `quality` (4–7), `stage` theo phẩm và `entries` là danh sách object `{ code, value }`. Các dòng buff đội hoặc rainbow vào `battleEntryInfos`. Dùng `null` để tháo. Thay đổi này giữ nguyên `hero.attr`. Xem [Thần Khí](planning/artifact.md).
- `relic` chọn Thánh Khí bằng object có `name` (slug dòng Thánh Khí), `star` và `purification` (số lần thanh tẩy). Dùng `null` để tháo. Simulator cập nhật skill của Thánh Khí và giữ nguyên `hero.attr`. Xem [relic-dict.json](../web/dict/relic-dict.json) và [hero gear](planning/hero_gear.md).

## Mount và Summoner

- `mounts` gồm `owned` là danh sách slug sở hữu và `selected` là một slug trong danh sách. Ví dụ `{ "owned": ["azure_drone"], "selected": "azure_drone" }`. Dùng `selected: null` hoặc bỏ `selected` để không cưỡi. Mount mới dùng skill rank đầu tiên. Mount có trong capture giữ skill cũ. Các chỉ số account do server tính vẫn lấy từ capture.
- `summonerSkins` là danh sách object có `name` và `star`, tối đa 3 skin có skill. Skin sự kiện chỉ cộng chỉ số, như `sanguin_dragoon`, có thể mặc và không chiếm slot skill trong `summonerInfos`.
- `summonerWorn` chọn slug trong `summonerSkins`, hoặc `null` để dùng model mặc định. Trường này chỉ được đọc khi có `summonerSkins`. Simulator đặt `derma` trên player info để đổi model.

## Đồ Cổ

`antiques` là object ánh xạ slug sang số sao. Dùng `{}` để xóa danh sách. [Catalog Đồ Cổ](../web/dict/antique-dict.json) cung cấp màu, số sao tối đa và mã rank. `ranks[star - 1]` là mã theo sao trong capture. Khi ghi đè, simulator dùng `haloLevelLimit` của rank làm `level`, rồi engine tra hiệu ứng từ config game.

## Trap, pet, spell và công trình

| Trường | Giá trị |
|---|---|
| `traps` | Tối đa 3 trap khác nhau. Mỗi mục là slug hoặc object có `name`, `level` và `star`. Level và sao mặc định đều là 1. Skill lấy theo sao. |
| `pets` | Cùng dạng với `traps`, tối đa 3 pet khác nhau. Với mỗi loại skill trong `SummonCreatureLO.skill`, simulator chọn level cao nhất có `starRequire` không vượt số sao. |
| `spells` | Tối đa 2 spell khác nhau theo `DaoistFormationLO`. Mỗi mục là slug hoặc object có `name` và `star` (mặc định 1). Skill lấy từ `DaoistStarLO`. |
| `buildings` | Skin cửa, giường, chuột và mèo qua các key `door`, `bed`, `generator`, `cat`. Xem [cấu hình skin công trình](../BUILD_SKINS.md#trong-profile-playtest). |
| `goldenSkinsCount` | Số nguyên không âm: tổng sao skin vàng hero (`DermaLO.color` 7) account sở hữu. Pet được cộng `FinalHurtAdd` = giá trị × 150 ở battle type có trong `ConstLO.SummonCreatureLevelUpBattleType`. GAT bật cho U Đô, World Boss, Guild Co-Boss và Ác Mộng (21/37/38/42/43). Config SEA không có key này nên trên VN giá trị không ảnh hưởng trận. Xem [BUILD_SKINS.md](../BUILD_SKINS.md#dữ-liệu-trong-startgamep). |

## Catalog

Dùng slug trong [web/dict](../web/dict/) khi điền tên. Key thường lấy từ tên tiếng Anh. Các mục thiếu tên dùng `id_<mã>`. `name` lấy từ gói tiếng Anh và `name_vn` từ gói tiếng Việt. `color` của hero, trap và pet thể hiện độ hiếm (`purple` 4, `orange` 5, `red` 6, `gold` 7).

- `hero-dict.json` chứa hero + skin + node Dị Năng; `support-dict.json` chứa mount, Summoner, trap, pet, spell và building. Các giới hạn level và số sao nằm ở `maxLevel` và `maxStar` của mục tương ứng.
- `map-dict.json` chứa khoảng stage campaign và danh sách boss U Đô. `boss-dict.json` chứa preset của boss và tham chiếu quái trong `creeps-dict.json`.
- `antique-dict.json`, `relic-dict.json` và `artifact-dict.json` chứa metadata Đồ Cổ, Thánh Khí và Thần Khí. Catalog Thánh Khí gồm các dòng đỏ, vàng và 7 màu có skill, cùng dữ liệu thanh tẩy. Các chỉ số do server đã gộp vào `hero.attr`.

Tạo lại các catalog sinh từ config khi đổi version. Thay hai giá trị trong lệnh bằng version tương ứng của trận mẫu.

```bash
node battle_sim/scripts/gen_profile_dict.js "<configVersion>" "<battleVersion>"
```
