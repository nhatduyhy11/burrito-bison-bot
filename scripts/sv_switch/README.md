# sv_switch POC

CLI Playwright độc lập để chọn server **trong phiên login** bằng override HTTP
response `action=login`. Không import hay sửa code crawler/socket_log; không crawl,
không gọi `set_switchServer` để lưu lựa chọn mặc định. Dùng dependencies Python /
Playwright có sẵn của repo.

Chạy từ root repo:

```bash
uv run python tools/sv_switch/switch.py --profile .tmp/m571 --server 829

uv run python tools/sv_switch/switch.py \
  --auth-json /path/to/auth.json --acc 'account@example.com' --server 829
```

- Bắt buộc chọn `--profile` **hoặc** `--auth-json` + `--acc`. Không mở cùng profile
  trong hai browser process; Chrome sẽ từ chối profile đang được dùng.
- JSON cùng format với crawler: object các key localStorage SDK, một key
  `*_allLoginList` chứa `value[email]`, và wrapper `*_userLoginData`. Chỉ đọc file,
  chọn account rồi restore vào context fresh; không ghi token/account vào kết quả.
- `--server N` (alias `--sv N`): `s_id` server đích, lấy object đầy đủ từ danh sách
  backend mới mỗi lần chạy; không dùng metadata hardcode hay cache research.
- `--headless`: chạy ẩn. `--browser chrome|chromium` (mặc định chrome).
- `--keep-open`: giữ browser sau khi xác minh, Ctrl+C để đóng. Mặc định đóng browser
  sau khi nhận được dữ liệu nhân vật, có thể trước khi UI tải asset xong.
- `--timeout 120`: thời hạn login/xác minh, tính bằng giây.
- `--out path`: thư mục output mới. Mặc định tạo thư mục riêng dưới `.tmp/sv-switch`.
  `result.json` chứa server đích, lựa chọn cũ, có nhân vật sẵn hay không, server/ID
  nhân vật backend trả, `newRole`, trạng thái thành công hoặc lỗi. Không ghi traffic
  thô, token hay auth JSON. Exit 0 khi xác minh thành công, 1 khi thất bại.

## Cách hoạt động

Gắn route trước navigation → lấy response login thật → giữ response trong khi GET
`get_AllServerList` bằng signer của game với `game_uin` vừa xác thực → tìm `s_id`
đích → thay riêng `svrListT` thành object đích → trả response cho game.
Auth/token được giữ nguyên. Game tự mở login/gameplay socket và tự điền `serverId`
từ `area`, `unitServerId` từ `s_id`; hai giá trị không bị giả định luôn bằng nhau.

Xác minh bằng `PlayerModule.playerInfo.info.serverId` từ gameplay server, không
chỉ dựa vào `selectServer` phía client. Fresh-auth còn đối chiếu account trong
SDK frame. Nếu không tìm được server hoặc override lỗi, abort response login,
không âm thầm thả response cũ để vào nhầm server.

## Có cần tạo nhân vật sẵn không?

POC cho chọn server trong danh sách dù chưa có `playerList`, với trạng thái
normal/new. Server maintenance bị từ chối; server full chỉ cho qua khi có nhân vật
sẵn, theo điều kiện trong UI game. Không hỗ trợ ID tùy ý ngoài danh sách backend.

Khi chưa có nhân vật, login có thể tạo nhân vật mới hoặc đi qua onboarding;
chưa kiểm chứng flow đó. `newRole` được ghi trong kết quả. Có nhân vật mới không
đảm bảo đủ level/điều kiện mở tính năng. Đã kiểm chứng account có nhân vật ở 829:
PHP mặc định trả 571, override sang 829 thành công, backend xác nhận server 829
và `newRole=false`, ở cả mode profile và fresh-auth JSON. Chưa kiểm chứng server
gộp hay việc ghi nhớ server ở lần mở sau.

## Kiểm tra local

```bash
uv run python -m unittest discover -s tools/sv_switch -p 'test_*.py' -v
uv run ruff check tools/sv_switch
```
