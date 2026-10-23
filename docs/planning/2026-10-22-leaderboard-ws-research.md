# Research: Lấy Leaderboard qua WebSocket — browser-only

> Ngày: 2026-10-22. Mục tiêu: fetch leaderboard game Haunt Heroes web (CN:
> `hauntheroesweb.acenetgame.com`) theo interval ~5s, không phụ tầng mạng.
> Liên quan: `socket_research.md` (vision protocol-bot dài hạn) — doc này là
> bước khảo sát đầu tiên, scope thu hẹp vào leaderboard và giữ bot chạy bằng browser.

## Quyết định đã chốt

- **Browser-only** (2026-10-22): game chạy trong Chromium do Playwright điều
  khiển (persistent context, hiện nằm trong `tools/socket_log/mine_logger.py`)
  nên mọi traffic đều thấy được từ trong page — chỉ dùng browser + WebSocket
  hook, không can thiệp tầng mạng.

## Findings

1. **Leaderboard không phải REST API**: khi mở màn leaderboard trong game,
   Network tab (filter Fetch/XHR) không thấy request nào tương ứng → dữ liệu
   gần như chắc chắn đi qua **WebSocket** (game web không mở được raw TCP;
   H5 joynetgame kiểu này mặc định là WS push).
2. **WS trong DevTools dễ bị bỏ sót**: phải filter **WS** (không phải
   Fetch/XHR), tìm connection status `101` → tab **Messages** mới thấy frame.
   Frame mũi tên lên = client gửi ("lệnh xin data"), mũi tên xuống = server push.
3. **Hai hướng poll 5s từ trong page**:
   - *Passive*: nghe frame, mỗi khi server push leaderboard thì lưu bản mới nhất.
   - *Active*: bắt frame **out** phát ra lúc mở màn leaderboard (= request xin
     data), rồi `ws.send()` lại đúng frame đó mỗi 5s — tương đương replay REST
     nhưng trên WS.
4. **Cầu nối Playwright ↔ page** (không cần nghe console.log):
   `context.expose_binding()` trước khi navigate + `context.add_init_script()`
   để monkey-patch `window.WebSocket`; frame (text hoặc binary → base64) đẩy
   thẳng về handler Python kèm cờ is_text. Hook phải giữ `instanceof` hoạt động
   (gán `prototype` từ WebSocket gốc) nếu không game có thể crash lúc init.
5. **Nếu frame là binary** (protobuf/custom bytes): tìm schema trong JS bundle
   qua Sources (Ctrl+Shift+F) với từ khóa `protobuf`, `.proto`, `decode`,
   `msgpack`, `rank` — game Laya/Cocos thường đóng gói sẵn codec, gọi lại được
   từ console. Chưa xác nhận game thuộc case nào.

## Rủi ro / lưu ý

- Token/sign trong frame hoặc handshake có thể hết hạn → ưu tiên tái dùng frame
  thật của game thay vì tự đóng gói packet.
- Server game ngắt connection nếu thiếu heartbeat — trong browser thì game tự
  lo; chỉ cần nhớ điều này khi sau này port sang protocol-bot thật
  (`socket_research.md` mục heartbeat).
- Poll 5s khác nhịp chơi thật → thêm jitter (`5 + random(0..1)s`) để hạn chế
  rate-limit/flag.

## Next steps (open items)

- [ ] Xác nhận WS: F12 → Network → filter WS → mở màn leaderboard → tìm frame
      tương ứng, copy message.
- [ ] Xác định định dạng frame: JSON text hay binary.
- [ ] Nếu binary: trích schema/codec từ JS bundle.
- [ ] Viết `ws_hook` init script + cắm `expose_binding` vào runner.
- [ ] Module poller 5s (passive trước, active nếu cần), lưu JSON ra file cho
      phần khác của bot đọc.
