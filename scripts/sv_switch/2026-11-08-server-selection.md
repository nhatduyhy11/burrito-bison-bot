# Chọn server trước auto-login

Research ngày 2026-11-08: quan sát Playwright từ trước navigation, đọc HTTP
response và WebSocket frame, kiểm tra bundle đang phục vụ
`assets/main/index.1377a.js` và runtime. Sau bước quan sát, thử override response
login theo yêu cầu để kiểm chứng chuyển 571 → 829; không gọi `set_switchServer`.

## Kết luận

Đã kiểm chứng chuyển 571 → 829 bằng override `svrListT` trong HTTP response
login. Packet login thực gửi `serverId = 829`, `unitServerId = 829`; backend trả
`err = 0`, `newRole = false`. Dữ liệu nhân vật từ gameplay server xác nhận
`serverId = 829`, player ID khớp giữa login response và runtime; tên nhân vật
khớp `playerList` của server 829 trong danh sách đọc trước đó.
Lặp lại xác nhận `GameMgr.Ins.isInGame()` trả true; screenshot tại thời điểm
đó còn loading 70%, nên không dùng cờ này làm bằng chứng UI đã tải xong.

Thử nghiệm chỉ thay danh sách server trong response thành một object 829 đầy đủ
lấy từ `get_AllServerList`, giữ nguyên auth/token từ response thật. Không sửa
binary WS, không tạo nhân vật mới và không tích hợp tính năng vào crawler.
Chưa đo server mặc định ở lần mở tiếp theo không có override.

Auto-login hiện tại lấy lựa chọn từ backend PHP, không phải một key server trong
localStorage mà chỉ cần sửa. SDK xác thực account; sau đó game PHP trả server
mặc định. Cùng account có thể lấy được thông tin nhiều server.

## Luồng đã quan sát

1. SDK gọi `/service/user/h5_auto_login`.
2. Game GET `game_api.php?action=login`, có chữ ký `sign`.
   Response thành công chứa `game_uin`, `t_token`, `svrListT`.
   Phiên kiểm tra có đúng một phần tử trong `svrListT`, là server 571.
3. `AgentMgr.loginHandler` gán `_recentServerData = response.svrListT`, rồi
   `selectServer = _recentServerData[0]` và phát `LoginPhpSuccess`.
4. `LoginMgr.phpLoginSuccessHandler` phát `GetServerListSucceed` khi đã có
   `selectServer`. `LoginView._onGetServerListSucceed` đi qua kiểm tra điều khoản
   rồi `_onAgreeProtocol`; với `CloseAutoLogin = 0`, gọi `doConnectServer` ngay.
5. `AgentMgr._connectLoginServer` mở
   `wss://<selectServer.s_ip>:<selectServer.sPort>`.
   Phiên kiểm tra dùng `mg-sea-entry.bighost.games:19005`.
6. `AgentMgr.loginLoginServer` gửi `LoginProxy.LoginRequest`, module `0x01`,
   command `0x0002`. Decode packet thật xác nhận:

   | Protobuf field | Tên | Giá trị | Nguồn trong code |
   | --- | --- | --- | --- |
   | 8 | `serverId` | 571 | `Number(selectServer.area)` |
   | 13 | `unitServerId` | 571 | `selectServer.s_id` |

7. Response `0x01/0x0003` có `err = 0`, `newRole = false`, `role.sGameUrl`.
   Game mở socket gameplay theo URL backend trả, không tự suy ra từ server ID.

`svrListT` không phải toàn bộ danh sách server hay toàn bộ nhân vật của account.
Một GET đọc riêng `action=get_AllServerList` qua `GameHttp.get`, không gọi handler
chọn server, trả 877 server. Cả 571 và 829 đều có `playerList`; cả hai dùng cùng
login host/port ở phiên kiểm tra, nhưng có `area` và `s_id` khác nhau. Danh sách
đầy đủ đánh dấu cả hai `s_healthStatus = 2` (normal); metadata 571 trong response
login lại có status 3. Nên lấy object đích từ danh sách mới, không clone 571 rồi
chỉ thay một số.

## Flow đổi server có sẵn trong game

- `LoginServersPanel` mở danh sách bằng `AgentMgr.getServerList` →
  `get_AllServerList`.
- `LoginServerItem.staticeSwitchServer` gán `AgentMgr.Ins.selectServer` bằng
  object server được chọn, rồi gọi `AgentMgr.swicthServer` (tên trong bundle
  viết đúng như vậy).
- `swicthServer` đóng socket hiện tại và GET `action=set_switchServer`, với
  `username`, `unitServer = selectServer.s_id`, `platform`; `GameHttp.get` thêm
  metadata, thời gian và chữ ký.
- Callback chờ chuỗi `success`, sau đó restart game hoặc phát lại
  `LoginPhpSuccess`, tùy login stage.

Đây là thao tác thay đổi trạng thái dù dùng HTTP GET. Thử nghiệm không gọi endpoint
này. Code gợi ý nó lưu lựa chọn phía backend; phạm vi và độ bền của lựa chọn chưa
được đo bằng thử nghiệm đổi server.

## Các phương án cho bước thử sau

| Phương án | Điểm can thiệp | Nhận định |
| --- | --- | --- |
| Dùng flow game | Chọn object đích rồi `swicthServer` | Có luồng sẵn và callback xác nhận; có thể thay mặc định phía backend. |
| Override response login | Thay `svrListT[0]` trước `loginHandler` | Đã kiểm chứng 571 → 829 thành công với auth/token giữ nguyên, dùng đầy đủ object đích lấy từ list. |
| Override runtime | Đặt `selectServer` trước `_connectLoginServer` | Tránh sửa binary nhưng phải hook trước auto-login, không chỉ evaluate sau khi trang tải xong. |
| Rewrite packet WS | Đổi field 8 và 13 của `Login_Login_C2S` | Có thể thiết kế, nhưng phải encode lại protobuf/length, giữ metadata client nhất quán và dùng đúng login endpoint. Chưa cần ưu tiên. |

Setter `selectServer` còn có nhánh ưu tiên `window.urlKV.serverData` nếu có object
này. Phiên kiểm tra không có `serverData`; chưa xác minh cách truyền object qua
URL, nên chưa thể kết luận chỉ thêm `?serverId=829` là hoạt động.

## Có cần tạo nhân vật sẵn không?

Không phải điều kiện chung để hiện/chọn server trong UI: `LoginServerItem`
cho chọn server normal/new ngay cả khi không có `playerList`. Có ngoại lệ:
server full (`s_healthStatus = 1`) chỉ cho qua khi có nhân vật; maintenance
(`s_healthStatus = 4`) bị chặn. Protocol login cũng có cờ response `newRole`,
và `loginServerSuccessHandler` xử lý cờ này.

Chưa thử account trên server chưa có nhân vật, nên chưa chốt khi nào backend
tạo role và còn bước onboarding nào. Với mục tiêu crawl, có role cùng level hoặc
điều kiện mở tính năng vẫn có thể cần thiết. Server 829 đã có `playerList`;
thử nghiệm vào đúng nhân vật có sẵn và backend trả `newRole = false`.

## Liên hệ với tooling repo

- [browser/session.py](../../tools/socket_log/browser/session.py):
  `open_game_session` gọi `on_page` trước navigation, phù hợp gắn listener từ đầu;
  hook gửi WS hiện tại không triển khai lựa chọn server.
- [browser/auth.py](../../tools/socket_log/browser/auth.py): fresh-auth khôi phục
  danh tính SDK, chưa có tham số chọn server game.
- [capture/frames.py](../../tools/socket_log/capture/frames.py): chỉ ghi WS;
  cần listener request/response riêng để thấy PHP login và danh sách server.

Khi tích hợp: lấy object đích từ list, đặt lựa chọn trước socket login, kiểm
tra cả hai field login, response `err/newRole` và server nhân vật do gameplay
server trả như trong thử nghiệm. Chỉ sửa state hiển thị ở client không đủ để
xác nhận. Mới kiểm chứng một account và một cặp server, chưa bao phủ server gộp,
server full/maintenance hay account chưa có nhân vật ở server đích.
