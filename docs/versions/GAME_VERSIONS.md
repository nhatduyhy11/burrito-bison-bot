# Game identity & version landscape

Ghi nhận: các "bản" ta đang thao tác là gì, quan hệ với nhau thế nào, bằng chứng kỹ thuật ở đâu. Ngày: 2026-11-16.

## Game là gì?

Một game H5 tower-defense (Cocos, cùng codebase 36 hero / bộ skill id `10<NN>0<slot>*000` ở mọi phiên bản), mỗi khu vực rebrand tên + art:

| Khu vực | Tên game | Host | Trạng thái với bot |
|---|---|---|---|
| Trung Quốc (official) | **妖怪金手指** (Yaoguai Jinshouzhi — "Golden Finger") | TapTap app [762818](https://www.taptap.cn/app/762818), package `com.dhmgygjsztt2.az`, publisher 霍尔果斯天翔, app ver 8.2 (update 2025-12-09) | chưa có access |
| GAT/TW (official) | Haunted Heroes | `hauntheroesweb.acenetgame.com` (mirror 65985, config `trunk_66196`) | dùng cho playtest port 8091 |
| VN (official) | Haunted Room | `hauntedroomvnh5.joynetgame.com` (config `sea_65553`) | bản chính của bot |
| Server riêng CN | "ygkksy" (tên page, pinyin viết tắt — chưa xác thực) | `sy.betainc.store/ygkksy/index.php` (config21 ≈ `weixin_129776`) | bot vào bằng `env.ygkksy` |

Trang portal H5 `https://www.wanyiwan.top/game/ygjsz` (React SPA, không có text tĩnh) được bundle yg nhúng vào flow gift "add to desktop" — `ygjsz` = 妖怪金手指 (pinyin initials), khẳng định cùng game.

Mô tả chính thức trên TapTap khớp y theme hero của bản yg: "您将化身驱鬼小道士…召唤上古神将" (đạo sĩ trừ tà, triệu hồi thượng cổ thần tướng = 地藏王/钟馗/女娲/二郎神…). Xem bảng hero ở [docs/hero-red-name-skill-match.md](../hero-red-name-skill-match.md).

## "yg" là private server — đã xác nhận

Bằng chứng từ chính trang wrapper trả về sau login (`sy.betainc.store/ygkksy/index.php`, fetch 2026-11-16, lưu `.tmp/ygkksy-research/wrapper.html`):

```json
localConfig = {"AgentCode": "wechat", "ServerName": "大蓝微信专服", "DataBinPath": "config_all/weixin",
  "__SDKGameUrl": "https://zeus.aidalan.com/v1/H5Game?game_id=191&channel_id=282&game_channel_id=7109",
  "HttpSerever": "game.ygkksy.com:6162/sy_api/game_api.php",
  "ClientVer": "129091", "ConfigVer": "128977", "DistTime": "20260615 …"}
```

- **专服** = dedicated server: `ServerName` tự khai là "大蓝微信专服" (kênh WeChat của platform 大蓝 / aidalan.com), không phải line chính thức.
- API riêng `game.ygkksy.com:6162`, không host nào của nhà phát hành chính (`acenetgame.com` / `joynetgame.com`).
- Config `128977` **lệch version counter** với cả GAT (66196) lẫn VN (65553) — không so sánh số tuyệt đối (mỗi line một counter), nhưng build `20260615` mới hơn cả config cache GAT/VN của ta.
- Không có lang pack (`lang_*.bin`): tên giản thể nằm thẳng trong config — hành vi bản build nội địa; bundle `index.0f8ab.js` còn só log dev `localhost:7456` (Cocos Creator dev preview).
- Wrapper chủ động **patch config runtime**: chèn `isAdvertise:1` vào `checkConfig` ("临时开启广告开关") — hành vi server riêng, không phải client chính thức.

Kết luận: bản "yg" ta đang dùng = client build CN gốc chạy trên một **kênh server riêng (大蓝微信专服)**, wrapper bởi operator `betainc.store`. Theme nhân vật (thần thoại Trung) gần với bản CN official hơn; GAT/VN là rebrand hải ngoại (đổi tên + art, cùng số liệu skill).

## "Golden finger" = tên CN chính thức, không phải server riêng

Nghe "có một server là golden finger" — đó chính là **妖怪金手指**, tên Trung official của game (bản TapTap 官服). Không phải một server lạ: các bản hải ngoại (Haunted Heroes / Haunted Room) là rebrand của cùng game này.

## CN official đi trước GAT/VN/yg bao xa? (check 2026-11-16)

**APK TapTap = route chết.** APK game (apk_id 976264, 17MB, `com.dhmgygjsztt2.az`) là WebView shell — vào app phải login, chọn game rồi mới load H5 từ server; download web bị chặn sau QR/TapTap client. Trong APK không có bundle game nào đểExtract.

Nhưng độ mới của CN không phụ thuộc APK — game hot-update từ server, chứng cứ từ chính config + forum TapTap:

| Bằng chứng | CN official | yg (2026-06-15) | GAT 66196 |
|---|---|---|---|
| Main campaign max stage | **440** (công báo 2026-10-15: 新增主线关卡421-440关) | 400 | 400 |
| Skin 炫彩 (colorful) | nhiều wave, có 女娲/观音炫彩 (2026-10~11 炫彩殿堂) | không có mechanic | 6 released + 10 staged chưa mở |
| Mechanic mới nhất CN | 擎天石尊 (女娲炫彩: 补天石×20 triệu hồi 10s, ăn đá +1s tối đa +20s,普攻 20000% ATK, 30%×2 hit / 20%×3 hit); 玉净瓶 (观音炫彩: tích năng, 20道甘露 = 怒气+40 & 暴伤+15%/20s) | **0 hit** trong config | **0 hit** trong config |

Timeline công bố trên forum TapTap (account official 抓鬼助手小金):

- **2026-02-15** (春节版本): 罗刹女炫彩「金阙玄后」(沙瀑葬域), 牛魔王炫彩「混天魔尊」(焚天圣魔), 皮肤套装系统, 新召唤兽/坐骑/道法 — wave 炫彩 này GAT/VN có mặt trong config (đợt 6 skin released).
- **2026-10-15**: 主线 421-440, 装备上限 33阶, 万鬼之巅噩梦难度3, 无限列车 841-880, 封魔宝箱五连开.
- **2026-10~11**: 炫彩殿堂 quay lại với 女娲炫彩 (擎天石尊) + 观音炫彩 (玉净瓶) — mechanic chưa tồn tại trong config của GAT lẫn yg (grep `擎天石|补天石|玉净瓶` = 0 hit ở cả hai).

Kết luận: **GAT/VN đi sau CN official ít nhất 2 wave nội dung** (stage +40, 1 wave 炫彩 mới + cơ chế hàng đầu chưa có trong config); bản yg private (build 2026-06) cũng thiếu wave 10/2026. Ngày "update 2025-12-09" trên TapTap chỉ là ngày update APK shell — content CN vẫn chạy đều qua server maintenance.

Nguồn: [bài đăng cập nhật 10/2026](https://www.taptap.cn/moment/859502425801754164), [công bố Tết 2026](https://www.taptap.cn/moment/772155355420428664), screenshot Douyin @零氪王 (do user cung cấp, 2026-11).

## Vì sao nhiều bản đến vậy?

Game H5 phổ biến mô hình phân phối **nhiều kênh song song**, mỗi kênh một server + một client build:

1. **Official regional**: nhà phát hành tự chạy line CN (TapTap/app), TW/GAT, SEA/VN — domain riêng, config version counter riêng, rebrand tên + art theo thị trường.
2. **渠道服 (channel servers)**: platform bên thứ ba (đại 蓝 aidalan, wanyiwan…) mua/được cấp build, chạy server riêng cho user của kênh họ (微信专服 = server dành cho user WeChat của kênh đó) — thường có gift/quà riêng, đôi khi nội dung bật/tắt theo kênh.
3. **Server riêng/reseller**: operator như `betainc.store` wrapper lại một channel server, bán access (token/timestamp trong `env.ygkksy`) — client vẫn là build gốc, chỉ điểm vào + config agent là của operator.

Cùng một engine + bảng config nghĩa là so sánh skill/hero giữa các bản là hợp lệ (đã làm trong [docs/hero-red-name-skill-match.md](../hero-red-name-skill-match.md)); khác biệt gameplay thật nằm ở data từng line (vd. addon +100% ATK của yg ở hero 50000013 slot 2) và các build patch sau khi fork.

## Về tên "ygkksy"

Chưa xác thực được nghĩa. Biết chắc: `ygjsz` = 妖怪金手指 (portal wanyiwan dùng, trùng game). `ygkksy` là viết tắt pinyin do operator page đặt — khả năng 妖怪氪金手游 (妖怪 kējīn shǒuyóu) hoặc 妖怪客栈…, chỉ ghi nhận, không kết luận.
