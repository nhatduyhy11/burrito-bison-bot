# Skin trong profile playtest

Level của hero và sao của skin là hai thông số riêng. Ví dụ, Venom ngoài capture dùng
chỉ số hero level 1. Có thể mặc Colorful 5 sao mà level của Venom vẫn là 1.

Trong `heroes`, dùng tên hero để giữ skin từ capture hoặc dùng object để chọn skin.
Tên skin tra trong `skins` của hero tương ứng trong [profile-dict.json](web/profile-dict.json).

```json
{
  "name": "venom",
  "skin": "colorful",
  "star": 3,
  "ownedSkins": { "pf1": 1, "pf2": 4 }
}
```

`star` là sao của skin đang mặc, mặc định 1. `ownedSkins` là các skin khác đã mở và số
sao tương ứng, có thể bỏ. Trong ví dụ, Colorful vẫn 3 sao, `pf1` được nâng từ 1 lên 3,
`pf2` giữ 4 và `pf3` được bổ sung ở 3 sao. Simulator áp quy tắc này theo yêu cầu ở đúng
mốc sao trong `DermaStarLO`. Với Colorful, mỗi skin yêu cầu được nâng tối thiểu bằng sao
của skin Colorful. Dòng `profile skin ranks` trong log sandbox ghi từng skin và rank cuối.
Trong config này, cả Venom và Hanuman đều cần `pf1` (mã bậc màu 6) cùng `pf2` và
`pf3` (mã bậc màu 7). Sao vượt quá rank có trong config báo lỗi.

Config `sea_65380` có 1–5 sao cho các skin Hanuman và Venom trong dict. Mỗi rank có
thể đổi mã skill và chỉ số. Simulator dùng model và skill ở rank của skin đang mặc,
và cộng chỉ số từ các skin đã mở vào hero. Phần này nằm trong
[skin-profile.js](web/skin-profile.js). Việc cộng dồn chỉ số chưa được đối chiếu với
capture từ account sở hữu Colorful.
