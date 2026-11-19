# Đêm Đỏ trong setup UI (bbb-47c)

Thiết kế option chọn mode Đêm Đỏ (battleType 47) trên trang setup. Cơ chế của mode: [blood_night.md](blood_night.md).

## Nguyên tắc

- Server không có hệ số đội. Mỗi hero trong đội hình mang `attr` đã gộp sẵn của **acc sở hữu**.
  Nên setup chỉ cần biết mỗi slot hero thuộc acc nào, rồi lấy attr theo acc đó.
- Chỉ đội trưởng (Master, `leaderId`) chơi. Acc còn lại là Guest.
- Phần không phải hero (bẫy, pet, phép, support, công trình, thú cưỡi, đồ cổ…) đã được server ghép
  sẵn vào `playerInfos[0]` của capture. Tab Support / Summoner giữ nguyên, ghi đè thẳng vào đó.

## Nguồn dữ liệu

- Trận gốc **phải là capture Đêm Đỏ**: chỉ ở đó mới có Guest.
- Roster: gói sảnh `refreshMemberInfosR` (TeamExpedition16Proxy) trong cùng file log, gần nhất
  trước `StartGameP`. Có đủ hero của từng acc (`members[].moduleDatas.heros`) và lực chiến acc
  (`baseInfo.fightCap`). Gói này không vào trận; chỉ setup/engine dùng để tra.
- Chủ của một hero ra trận = acc có hero cùng `uuid` trong roster.
- Hero lấy từ roster cần chỉnh cho giống bản ra trận: `attr[6]` = 0, thêm `attr[10162]` = 0.
  Log cắt mất các dòng Thần Khí (`<deep>`) trong roster, nên Thần Khí của hero chỉ có trong
  roster bị bỏ dòng (giữ mã). Attr đã gộp sẵn nên chỉ thiếu buff đội / rainbow.

## Giao diện

- "Màn chơi" thêm mode **Đêm Đỏ**: chọn Ải 1–80. Hover hiện 3 loại quái của ải (blood-dict.json).
  Mode chỉ có khi trận gốc là capture Đêm Đỏ. Bật Màn chơi trên capture Đêm Đỏ sẽ điền sẵn Đêm Đỏ.
- Tab Teams khi mode Đêm Đỏ: 3 slot trên = **Master**, 3 slot dưới = **Guest**, 6 hero khác nhau.
  Tiêu đề mỗi phe hiện tên acc và lực chiến **lúc capture** (tổng 3 hero ra trận + lực acc). Không
  tính lại khi swap.
- Joker: bên có Pháo Loli mặc skin Guns N' Roses mà cả 6 slot không có Joker thì Joker hiện ở
  slot 4 của bên đó, lấy attr theo acc của bên đó.

## Lấy hero cho một slot

1. Hero đang ra trận của đúng acc đó: giữ nguyên object trong `StartGameP`.
2. Hero có trong roster acc đó: object roster (đã chỉnh như trên).
3. Không có: mượn chỉ số trung bình như hiện tại (`hero/build.js`), nhưng donor là roster của acc đó.

Thứ tự `heros` trong trận theo vị trí chủ ở capture (capture: Guest, Master xen kẽ).

## Profile

`map: { mode: "blood", level: <TeamExpandLO id 1001–1080> }`, `heroes` = 3 hero Master,
`guestHeroes` = 3 hero Guest. `summonedJoker` như cũ.
