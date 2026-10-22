# Haunted Room — Giao Thức WebSocket (Nghiên Cứu POC)

> Kết quả reverse-engineer phiên POC 2026-10-22, server VN, profile `.tmp/m535`.
> Công cụ: `tools/socket_log/socket_capture.py` (bắt frame) + `tools/socket_log/socket_decode.py` (decode).
> Capture mẫu: `.tmp/socket-capture/run-mine1`, `.tmp/socket-capture/probe1`.

## Tổng quan

- Game H5 chạy hoàn toàn trong browser, **chỉ dùng WebSocket** (không WASM, không REST gameplay).
- Endpoint: `wss://mg-sea-entry.bighost.games/ws?nodeName=wgamed&threadId=5&platform=singapore_online`
  (kèm socket phụ `wss://mg-sea-entry.bighost.games:19005/` cho handshake/redirect).
- **Toàn bộ state game (kể cả lịch sử khu mỏ) được server push ngay sau login** (5.3–8.4s,
  ~200KB tổng). Việc mở popup Lịch Sử trong khu mỏ KHÔNG sinh request nào — UI render từ state client.

## Framing

```
request  = [len:2 BE][module:1][cmd:2 BE][seq:1][protobuf body]
response = [len:2 BE][seq:1][01][01][module:1][cmd:2 BE][status:1=00][protobuf body]
```

- `response.cmd = request.cmd + 1`; `response.seq` = `request.seq` của request tương ứng.
- Body là protobuf wire format chuẩn, không có schema `.proto` (client decode bằng code sinh sẵn).
- Heartbeat: mỗi ~5s, `module 0x02 cmd 0x0008` ↔ response `0x0009` (chứa server time varint).
- Login: client đăng ký kênh broadcast bằng `module 0x10 cmd 0x0008` (packed list kênh),
  sau đó server đẩy lịch sử broadcast theo nhiều frame.

## Các module đã map (một phần)

| Module | Cmd | Ý nghĩa |
| --- | --- | --- |
| 0x02 | 0x0008 | Heartbeat / time sync |
| 0x13 | 0x0004 | **Push broadcast feed** (chat + system events), nhiều frame ~34KB lúc login |
| 0x1f | 0x000a→0x000b | Danh sách player brief (id, tên, avatar, level, last-login) |
| 0x48 | 0x0001→0x0002 | Full state bản đồ khu mỏ (66 ô + vị trí người chơi) |
| 0x48 | 0x0013→0x0014 | Thông tin season Khai Thác Guild (start/end, danh sách tile) |

## Lịch sử khu mỏ (mục tiêu POC — ĐÃ XÁC MINH)

Nằm trong broadcast feed (module `0x13` cmd `0x0004`), mỗi entry là repeated `f2`:

| Field | Ý nghĩa |
| --- | --- |
| f1 | msg id (tăng dần) |
| f2 | kênh: 1 = world chat, 2 = system broadcast |
| f3 | unix timestamp (giây) |
| f7 | loại broadcast: **150 = sự kiện khu mỏ**, 151/152/153 = loại khác |
| f9 | template args, JSON string: `[["PLAYER"],[28000],[pos],[action]]` |

- `28000` = template "đồng quê tại…" trên client.
- `pos` = `map*1000 + tile` (vd `5047` = map 5 / Mỏ Đá Cháy, tile 47; `6053` = map 6).
- `action`: `9001` = vào khu/khai thác; các giá trị 1–12 chưa map rõ (mở vấn đề).
- Popup Lịch Sử trong game lọc sự kiện theo **map đang mở**: phiên test chỉ hiện 1 entry
  (AEMìn @5047, 15:35:38Z = "19 phút trước" so với login 15:55:17Z) — khớp UI chính xác.

Trích xuất JSON:

```bash
uv run python tools/socket_log/socket_decode.py .tmp/socket-capture/run-mine1 mine-events
```

## Listener chạy dài hạn (ĐÃ LÀM — 2026-10-22)

`tools/socket_log/mine_logger.py`: giữ session mở vô hạn, decode live broadcast push, ghi event mới
vào `.tmp/mine-events/mine-events.jsonl` (dedupe theo id qua restart), `--webhook` để đẩy
alert, tự reload page khi game socket đứt (socket handshake `:19005/` đóng thường xuyên là
hành vi bình thường — không được tính là mất kết nối).

```bash
uv run python tools/socket_log/mine_logger.py --profile .tmp/m535
uv run python tools/socket_log/mine_logger.py --profile .tmp/m535 --duration 300   # tự dừng sau 5 phút
uv run python tools/socket_log/mine_logger.py --profile .tmp/m535 --webhook http://localhost:8000/mine-alerts
```

## Đang mở (open items)

- [ ] Chạy listener dài (~1 giờ+) để bắt event phát sinh real-time và xác nhận mọi loại
  thay đổi của mỏ đều đi qua broadcast type 150 (đã thấy action `9002` trong login push,
  chưa thấy live).
- [ ] Map `action` 1–12, `9001/9002` và template 28000 (đối chiếu localization trong JS bundle nếu cần).
- [ ] Kiểm tra server CN (`hauntheroesweb.acenetgame.com`) có cùng framing/module không.
- [ ] Xác định cách giữ session lâu dài (token login trong localStorage của profile có TTL
  `expires_in: 2419200` — 28 ngày, xem `env.json`); kiểm tra game có kick AFK/session idle
  lâu không (chưa gặp trong 4 phút test).
