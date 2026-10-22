# Socket Step Learn — Quy Trình Reverse-Engineer Binary WS Của Game H5 (POC 2026-10-22)

> Bài học rút ra từ phiên POC lấy lịch sử khu mỏ (xem `docs/SOCKET_PROTOCOL.md`).
> Ghi lại từng bước CÁCH LÀM để tái sử dụng cho feature/dashboard tiếp theo.
> Toàn bộ step chạy trên server VN, profile `.tmp/m535`, không cần mitmproxy hay sửa payload.

## Bước 0: Dựng lại bối cảnh từ code có sẵn (5 phút)

Đọc `tools/hauntedroom_runner.py` + `hauntedroom/core/cli.py` để biết:
- Browser launch thế nào: `launch_persistent_context(user_data_dir=.tmp/<profile>)`,
  viewport 640x720, channel `chrome`, `service_workers: block`, URL VN/CN mặc định.
- Profile `.tmp/m535` đã có session đăng nhập → không cần xử lý auth thủ công.

**Bài học:** tái dùng đúng cách runner launch browser thay vì viết riêng — giữ nguyên
hành vi (popup guard, retry navigation) và session cũ vẫn còn hiệu lực.

## Bước 1: Viết tool bắt frame TRƯỚC khi phân tích gì cả

`tools/socket_log/socket_capture.py` — 3 phần:
1. Hook mọi WebSocket của mọi page: `page.on("websocket")` → `ws.on("framesent" / "framereceived")`.
2. Dump từng payload **nguyên vẹn (binary giữ nguyên)** ra `frames/NNNNN-{S|R}.bin`
   + `index.jsonl` ghi `{seq, t(ms), dir, size, file}` — đây là "xương sống" để correlate sau này.
3. Step DSL để lái game: `click:X,Y`, `shot:NAME`, `sleep:S`, `mark:LABEL`.

**Bài học:**
- Playwright/CDP trả payload ĐÃ giải mã TLS và ĐÃ inflate (permessage-deflate) — không cần wireshark.
- `mark` trước mỗi click là thứ cho phép truy vết "event này sinh ra do thao tác nào".
- Cần hook cả `context.on("page")` phòng game mở tab/frame mới.

## Bước 2: Probe mù — chỉ login, chưa bấm gì

Chạy:

```bash
uv run python tools/socket_log/socket_capture.py --profile .tmp/m535 --settle 12 --step shot:... --step sleep:...
```

→ Xem screenshot các mốc để biết trạng thái sau login (có popup AFK không, đã vào home chưa).

Kết quả ngay lập tức:
- Thấy endpoint thật: `wss://mg-sea-entry.bighost.games/ws?nodeName=wgamed...`
- Thấy volume: ~280 frame ngay khi login → game push state, không phải request-response thuần.

## Bước 3: Chạy đúng luồng thao tác thật, có mark + screenshot từng bước

Dùng tọa độ đọc từ screenshot mẫu (view 640x720 → click trùng 1:1):
đóng AFK popup → home → icon Guild (470,690) → Khai Thác Guild (437,165) → Log (253,695),
mỗi bước chèn `mark:tên-bước` + `shot`.

**Bài học:** nếu chưa biết tọa độ thì tách nhỏ — chạy 1 click + shot rồi xem ảnh, sửa, chạy lại.
Toàn bộ flow trúng ngay lần đầu vì tọa độ lấy từ ảnh người dùng cung cấp.

## Bước 4: Tìm framing từ chính dữ liệu (không đoán mò)

Thủ tục chuẩn trên `index.jsonl` + file frame:
1. **Tìm length prefix:** so `size` với 2 byte đầu. Thấy `00f1` = 241 = 243−2 trên MỌI frame
   → prefix 2 byte big-endian. Xác nhận lại trên frame khác (56−2=54, 17−2=15).
2. **Histogram size + timeline:** frame 6B lặp đều ~5s = heartbeat; frame nhỏ khác = request ADSL.
3. **Pair request/response qua byte cuối request (`seq`):** response mang `seq` đó ở byte đầu
   → ghép cặp chính xác hàng trăm frame chỉ bằng script.
4. Đối chiếu nhiều cặp để thấy bất biến: `response.cmd = request.cmd + 1`,
   `[01][01]` = flag OK, response body luôn protobuf (thấy varint timestamp ~1.79e9, string UTF-8).

## Bước 5: Decoder protobuf KHÔNG CẦN schema

`tools/socket_log/socket_decode.py` — walker wire-format generic (~40 dòng):
- Đọc key varint → `field`, `wire type`; wire 0 = varint, 2 = length-delimited, 1/5 = fixed.
- Bytes con: thử decode tiếp như protobuf (in cây), fail thì in hex, được thì in UTF-8.
- Heuristic nhận dạng: giá trị 1.7e9–2.0e9 → annotate ngày giờ UTC (giúp nhận ra timestamp ngay).

**Bài học:** không cần tìm file `.proto` trong JS bundle cho bước POC — decode mù vẫn đọc được
cấu trúc; chỉ cần schema thật khi muốn tên field "chính xác".

## Bước 6: Định vị dữ liệu mục tiêu bằng CORRELATION, không phải đoán

Trình tự đã dùng khi tìm "lịch sử khu mỏ":
1. **Timeline quanh mark `clicked-log`:** chỉ thấy heartbeat → popup KHÔNG request gì
   → suy ra data đã nằm trong client từ lúc login → đổi hướng tìm trong login burst.
2. **Grep nhị phân bằng chuỗi đã biết từ UI:** tên "AEMìn" hiện trên popup → `bytes.find`
   trong mọi frame → frame `#099`, `#209`... chứa tên này.
3. **Lọc theo cửa sổ timestamp:** popup ghi "19 phút trước", login lúc 15:55:17Z
   → scan cây decode mọi frame, chỉ giữ giá trị 15:2x–15:3xZ → còn vài ứng viên.
4. **Đối chiếu chặt UI ↔ decoded:** event `AEMìn @ pos 5047, 15:35:38` là event DUY NHẤT
   thuộc map đang mở (map 5) và popup cũng hiển thị ĐÚNG 1 entry → khớp = xác nhận.
5. Phân loại phần còn lại: histogram `f7` theo loại (150 = mine event, 151/152/153 khác,
   `f2=1` chat thuần) → hiểuShape dữ liệu từng loại.

**Bài học lớn nhất:** dữ liệu game H5 thường được PUSH SỚM (lúc login), UI chỉ render lại.
Luôn kiểm tra "thao tác có sinh request không" trước khi giả định nó gọi server.

## Bước 7: Extractor + xác minh tái lập

Thêm lệnh `mine-events` vào decoder → JSON `{id, time, player, pos, action}`.
Chạy trên 2 capture khác nhau (run-mine1, probe1) → cùng 32 events → dữ liệu ổn định,
không phụ thuộc phiên bắt.

## Bước 8: Ghi doc

Kết quả → `docs/SOCKET_PROTOCOL.md` (reference), open items → mục "Đang mở".

## Checklist tái sử dụng cho game H5 khác

- [ ] Tái dùng runner/profile để có session thật
- [ ] Capture mọi WS frame + index.jsonl + mark theo thao tác
- [ ] Tìm length prefix bằng so khớp `size` vs byte đầu
- [ ] Pair req/resp bằng seq; tìm heartbeat (frame nhỏ lặp đều)
- [ ] Decode protobuf generic + annotate timestamp
- [ ] Timeline quanh mark → biết cái gì push lúc login, cái gì theo thao tác
- [ ] Grep needle từ chuỗi UI nhìn thấy; lọc cửa sổ timestamp; đối chiếu số entry UI
- [ ] Extractor JSON + chạy chéo ≥2 phiên
- [ ] Doc reference + open items
