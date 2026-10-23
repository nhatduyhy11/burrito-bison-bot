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
| 0x13 | 0x0007 | **Guild chat** (message: sender brief, text, ts, `{"type":2}`) — xuất hiện khi mở guild screen |
| 0x1f | 0x000a→0x000b | Capture 2026-10-23: response 0x000b là **visit log** (id, id, ts, JSON `{"rKey","pKey"}`, blob chứa `[6600,6000]`) — KHÔNG phải player brief như nghi ban đầu |
| 0x0d | 0x001f→0x0020 | **Player brief** — request `f1`=packed player ids; response: f1=id, f2=tên, f4=power?, f33=avatar id, f11=guild nhúng (tên + mô tả), f15=server. **Đây là nguồn id→tên** |
| 0x48 | 0x0001→0x0002 | **Full state khu mỏ** (summary + 65 tile, xem mục riêng) |
| 0x48 | 0x0013→0x0014 | Season Khai Thác Guild: start/end + packed list season tile id (513–544) |
| 0x48 | 0x001a→0x001b | Feed lịch sử mỏ: entry = {f2: JSON string, f1: type} — type 4 `[player_id, pos, action, ts]` (action 9001/9002/**9003**), type 1 `[7057, 10, ts]` |

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

## State khu mỏ (module 0x48 — ĐÃ PARSE ĐẦY ĐỦ 2026-10-23)

**Timing (chứng minh bằng 2 capture có mark — run-1 click rơi vào loading, run-2 click vào UI thật):**

- **Login:** client tự gửi cả 3 request `0x48/0x0001` (map state), `0x48/0x0013` (season),
  `0x48/0x001a` (history) ngay trong lúc load "Vào trò chơi" — trước khi home screen render.
  Full map state KHÔNG được request lại khi điều hướng.
- **Click icon Guild:** `0x13/0x0007` (guild chat feed).
- **Click "Khai Thác Guild":** `0x48/0x0013`→`0x0014` — chỉ refresh season info.
- **Click nút Log:** `0x0d/0x001f` (packed = đúng các player id trong history feed) → `0x0020`
  briefs để render tên. Lưu ý: kết luận cũ "bấm Log không sinh request nào" chỉ đúng khi
  popup Lịch Sử đang TRỐNG (POC 2026-10-22); khi có entry, popup fetch brief theo id.
- Cross-check UI ↔ protocol: countdown "Mua giải tổng kết sau 60:04:31" trên màn mỏ khớp
  season end `2026-10-25 16:55Z` trong `0x48/0x0014` (capture lúc ~04:51Z).

**Season (`0x48/0x0014`):** f5=start, f4=end (unix s), f3=packed list season tile id
(513–544 = 32 giá trị liên tiếp; mã hóa chưa chốt, khả năng map*100+tile).

**Map state (`0x48/0x0002`, ~11.5KB):** top-level f1, f2=repeated tile, f3=summary.
Summary: f1=7057 (pos đang focus / "Vị trí của tôi"?), f2=10, f4=4500, f8=51520,
f9={30000015, 3, 525}, f6/f7/f10 = timestamp (f6 ≈ thời điểm login).

Mỗi tile (65 tile, 7 map: 1×9, 2×20, 3×16, 4×8, 5×4, 6×4, 7×4; pos = map*1000+tile):

| Field | Ý nghĩa |
| --- | --- |
| f1 | pos = map*1000 + tile (vd 7057 = map 7, tile 57) |
| f2 | 1–7 (chưa map — nghi loại/tầng mỏ) |
| f3 | 1–9 (chưa map) |
| f4 | 0 hoặc dạng 513xxxx/5170010 (nghi liên quan season tile id) |
| f7 | repeated `{f1: action, f2: count}` — đếm event theo action trên tile trong season |
| f5 | repeated slot: f1=player id, f2=số slot (1–124 tùy tile, hoặc 9001/9002/9003), f5=packed ts |
| f5.f5 | timestamps chỉ xuất hiện khi slot **đang được đào**: [start] hoặc [start, end] (thấy cặp cách đúng 60 phút) |

Đối chiếu chéo đã xác minh: tile 6053 chứa đúng 3 player id như feed lịch sử `0x001b`;
player id trong slot đang đào của tile 7054 khớp visit log `0x1f/0x000b`.
Player id khoảng 517–519xxxxx chiếm phần lớn slot (id đều/đẹp — nghi "Máy Đào" NPC);
id 52x–53xxxxxx mới giống player thật.

Trích xuất JSON đầy đủ:

```bash
uv run python tools/socket_log/socket_decode.py <capture_dir> mine-state > mine-state.json
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
- [ ] Map `action` 1–12, `9001/9002/9003` và template 28000 (đối chiếu localization trong JS bundle nếu cần).
- [ ] Map tile f2 (1–7), f3 (1–9), f4 (513xxxx) và các slot 9001/9002/9003 trong map state 0x48.
- [ ] Giải nghĩa history entry type 1 `[7057, 10, ts]` (nghi event của bản thân/guild ở tile
  đang chiếm; số lượng không khớp 1:1 với popup Lịch Sử) và summary f9={30000015, 3, 525}.
- [x] id→tên player: request `0x0d/0x001f` với packed ids → `0x0020` trả tên (đã xác minh
  2026-10-23: 6 id trong history feed → HaHuu, UnVila, AESaa, AEDungg, AEBon, OLNiet).
- [ ] Kiểm tra server CN (`hauntheroesweb.acenetgame.com`) có cùng framing/module không.
- [ ] Xác định cách giữ session lâu dài (token login trong localStorage của profile có TTL
  `expires_in: 2419200` — 28 ngày, xem `env.json`); kiểm tra game có kick AFK/session idle
  lâu không (chưa gặp trong 4 phút test).
