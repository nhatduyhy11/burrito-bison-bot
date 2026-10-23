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
| 0x13 | 0x0004 | **Replay broadcast feed lúc login** (chat + system + mine events), nhiều frame ~34KB |
| 0x13 | 0x0007 | **Kênh live push**: guild chat **và** event mỏ real-time (entry giống 0x0004: f7=150, f9=JSON args, f3=ts UTC) — mine_logger cần nghe kênh này |
| 0x1f | 0x0007 | **Leaderboard PvP mỏ** (push lúc login): entry = {f2: rank, f3: score, f1: profile đầy đủ nhúng (power, skins, avatar, blob config f17)} |
| 0x1f | 0x000a→0x000b | **Lịch sử đánh nhau ở mỏ** (trước nay nhầm "visit log"): entry = {f1: attacker, f2: defender, f3: ts, f5: battle id, f4: **bên thắng (1=attacker, 2=defender)**, f7/f6: JSON `{"rKey","pKey"}` rating attacker/defender, f9: profile defender nhúng}. Verify: HuAsura đánh OLNaji 2 lần đều f4=2 (thua) |
| 0x65 | 0x0009, 0x000c | Capture 2026-10-23: 0x9 = summary lượt đánh (nhóm 3 fighter {f1: id, f3: cờ thắng, f2: ?} + f3 = id winner); 0xc = list guild {f4: id chủ guild, f3 repeated: {f1: id thành viên, f2–f6: stat}} — chưa map đủ |
| 0x0d | 0x001f→0x0020 | **Player brief** — request `f1`=packed player ids; response: f1=id, f2=tên, f4=power?, f33=avatar id, f11=guild nhúng (tên + mô tả), f15=server. **Đây là nguồn id→tên** |
| 0x0d | 0x0019→0x001a | **Player full profile** (bấm vào 1 player/máy): heroes, items, power… popup "Mỏ Quặng LvX" |
| 0x24 | 0x0035→0x0036 | **Guild brief** — request f1=guild id (dạng f4 của tile: 5170010…); response f3={f2=tên, f11=server, f10/f3=số thành viên…}. Dùng khi mở minimap overview |
| 0x24 | 0x0033→0x0034 | **Guild detail**: f2=tên, f14=mô tả, f9/f8=id chủ guild, f13/f16=power, f26=log {thành viên, ts gia nhập}, f24=cửa sổ season guild, f1=id dạng f4 |
| 0x48 | 0x0001→0x0002 | **Full state khu mỏ** (summary + 65 tile, xem mục riêng) |
| 0x48 | 0x0006→0x0007 | **Chi tiết 4 điểm của 1 mỏ** (request packed tile id, bắn lúc click vào mỏ): tile như login + slot `f5` = chuỗi phiên đào 60 phút |
| 0x48 | 0x0008 | **Live push delta tile** (không có request) — tile cập nhật realtime khi có người vào/ra slot |
| 0x48 | 0x0013→0x0014 | Season Khai Thác Guild: start/end + packed list season tile id (513–544) |
| 0x48 | 0x0015→0x0016 | Request cùng ids với 0x0006 nhưng response **RỖNG (11B)** — no-op/legacy |
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
- **Click vào 1 mỏ (zoomin):** `0x48/0x0006→0x0007` (chi tiết 4 điểm, slot mang chuỗi phiên đào),
  `0x48/0x0015→0x0016` (rỗng), và brief `59 id` = toàn bộ người của mỏ — **tên không lazy theo điểm**
  (chi tiết: `docs/MINE_STRUCTURE.md` mục 5).
- **Sự kiện live chạy trên `0x13/0x0007`** — `0x0004` chỉ là replay lúc login; kèm theo đó server
  đẩy delta tile qua `0x48/0x0008`. ts trong event là UTC thật (đối chiếu wall-clock lệch <1s).
- Cross-check UI ↔ protocol: countdown "Mua giải tổng kết sau 60:04:31" trên màn mỏ khớp
  season end `2026-10-25 16:55Z` trong `0x48/0x0014` (capture lúc ~04:51Z).

**Season (`0x48/0x0014`):** f5=start, f4=end (unix s), f3=packed list season tile id
(513–544 = 32 giá trị liên tiếp; mã hóa chưa chốt, khả năng map*100+tile).

**Map state (`0x48/0x0002`, ~11.5KB):** top-level f1, f2=repeated tile, f3=summary.
Summary: f1=7057 (pos acc đang đứng), f2=10 (**số slot của acc** — khớp history type 1 `[7057, 10, ts]`),
f4=4500, f8=51520, f9={30000015, 3, 525}, f6/f7/f10 = timestamp (f6 ≈ thời điểm login).

Mỗi tile — **65 tile = 64 điểm mỏ + 1 mỏ phẳng sector 1; 1084 slot = 64×15 + 124**
(cấu trúc world chi tiết xem `docs/MINE_STRUCTURE.md`):

| Field | Ý nghĩa |
| --- | --- |
| f1 | pos = **id tĩnh của tile trong bảng server** (KHÔNG phải map*1000+tile — dãy id 1058–1065 thuộc sector 4/5); sector đọc từ f2 |
| f2 | **sector 1–7** [x đã chốt 2026-10-23] |
| f3 | **level điểm mỏ 1–9** [x đã chốt] — điểm 4 của mỗi mỏ = level trên của title sector |
| f4 | 0 hoặc `5XX00YY` (5XX ∈ 513–544 trùng season id, YY ∈ 4–12) — nghi node Mỏ Quặng + lượng còn lại |
| f7 | repeated `{f1: action, f2: count}` — đếm event theo action trên tile trong season |
| f5 | repeated slot: f1=player id (0 = trống), f2=số slot (điểm thường: 1–12 + 9001/9002/9003; sector 1: 1–124), f5=packed ts |
| f5.f5 | timestamps chỉ xuất hiện khi slot **đang được đào**: [start] hoặc [start, end] (thấy cặp cách đúng 60 phút) |
| f6 | `{1: 9001, 2: 0 hoặc ts}` trên 1 số điểm — nghi event chiếm điểm gần nhất |
| f8/f9 | hiếm; khi có f8 − f9 = đúng 3600s — cặp cửa sổ 1 giờ, chưa chốt |

State **không chứa tên player/guild** — chỉ có id; tên lấy qua `0x0d/0x001f→0x0020`.

Slot 9001–9003 **[x chốt 2026-10-23] = bộ claimer của guild chủ điểm**: 3 acc **cùng 1 guild**
(rule game) và guild đó = guild claim `f4` của tile — nhận diện người claim ngay từ state mà không
cần `0x24/0x0035`. `mine_report.py` đối chiếu cả 2 phía, lệch thì đưa vào `errors` (chi tiết
`docs/MINE_STRUCTURE.md` mục 2).

Đối chiếu chéo đã xác minh: tile 6053 chứa đúng 3 player id như feed lịch sử `0x001b`;
acc chính (HuAsura, id 51921435, guild HUNTERS) nằm ở tile 7057 slot 10 — khớp UI
"sector 7, mỏ Mỏ Huyền Quang, điểm 4 (lv9)".

Trích xuất JSON đầy đủ:

```bash
uv run python tools/socket_log/socket_decode.py <capture_dir> mine-state > mine-state.json
```

## Listener chạy dài hạn (ĐÃ LÀM — 2026-10-22; nâng cấp live push 2026-10-23)

`tools/socket_log/mine_logger.py`: giữ session mở vô hạn, tự reload page khi game socket đứt
(socket handshake `:19005/` đóng thường xuyên là hành vi bình thường — không được tính là mất
kết nối), `--webhook` đẩy alert. Ghi **5 stream raw** dưới `.tmp/mine-events/`:

| File | Nội dung |
| --- | --- |
| `mine-events.jsonl` | broadcast type 150 từ `0x13/0x0004` (replay) + `0x13/0x0007` (live), dedupe id qua restart |
| `mine-state.jsonl` | snapshot map lúc login `0x48/0x0002` — **server cũng đẩy 0x0002 một phần giữa session**, 1 dòng/tile |
| `mine-tiles.jsonl` | delta tile `0x48/0x0008` (`--no-tiles` để tắt) |
| `player-briefs.jsonl` | mọi `0x0d/0x0020` client nhận: id, tên, power, server, **f11 = {id guild, tên guild}** |
| `guild-briefs.jsonl` | `0x24/0x0036` — response không echo id, map qua **seq** của request `0x24/0x0035` |

**Fetch tên chủ động (mặc định bật, `--no-fetch-names` để tắt):** loggerinject frame
`0x0d/0x001f` (packed 60 id/lần) thẳng vào game socket qua JS (`WebSocket.prototype.send`
hook bắt instance, `page.add_init_script` **bậc page** — script bậc context KHÔNG chạy trên
page có sẵn của persistent profile), rồi đọc response `0x0020` như bình thường. Client không
bị ảnh hưởng (đã chạy 180s sạch). Đã verify 2026-10-23: 195/195 người trong mỏ có tên,
không ai chiếm >1 slot (live + offline đều xác nhận quy tắc 1 user = 1 slot).

**Bước tổng hợp (parse lần 2, tách riêng):** `tools/socket_log/mine_report.py` đọc 5 stream raw →
rebuild world mới nhất (snapshot + delta theo `logged_at`, snapshot ≥32 tile mới reset map) →
nhóm tile: trong sector sort theo pos, **cắt chunk 4 = 1 mỏ phụ (`sub` 1..n, điểm 1–4)** — sector là
dãy id liên tiếp nên KHÔNG tách mỏ bằng gap id; **id cao nhất của mỏ phụ = level trên**, 3 điểm còn
lại level dưới — khớp 16/16 mỏ. Xuất `mine-report.json` + cây sector → mỏ phụ → điểm (**dict key
`Lv{level}_{vị trí}`** — layout 2x2: top_left_1/top_right_2/bot_left_3 = 3 điểm level dưới,
bot_right = điểm level trên; point giữ tile id tĩnh ở field `id`) → occupant
tách `claimer` (slot 9001–9003, bộ claimer của guild chủ điểm) + `users` (slot 1–12), kèm `warnings`
(trùng slot, thiếu tên, mỏ thiếu điểm, f3 lệch level suy ra) và `errors` (3 claimer lệch guild nhau hoặc
lệch guild claim `f4`). Tên sector = nhãn level ("Lv2-Lv3"), không phải tên in-game. Sector 1 bỏ qua.

```bash
uv run python tools/socket_log/mine_logger.py --profile .tmp/m535 --snapshot   # 1 vòng snapshot + tên (~20-25s), tự thoát
uv run python tools/socket_log/mine_logger.py --profile .tmp/m535
uv run python tools/socket_log/mine_logger.py --profile .tmp/m535 --duration 300   # tự dừng sau 5 phút
uv run python tools/socket_log/mine_logger.py --profile .tmp/m535 --snapshot --dir .tmp/mine-events-$(date +%Y%m%d-%H%M%S)  # một-off vào folder timestamp
uv run python tools/socket_log/mine_logger.py --profile .tmp/m535 --webhook http://localhost:8000/mine-alerts
uv run python tools/socket_log/mine_report.py --dir .tmp/mine-events   # tổng hợp 1 folder -> mine-report.json
```

```bash
uv run python tools/socket_log/mine_logger.py --profile .tmp/m535
uv run python tools/socket_log/mine_logger.py --profile .tmp/m535 --duration 300   # tự dừng sau 5 phút
uv run python tools/socket_log/mine_logger.py --profile .tmp/m535 --webhook http://localhost:8000/mine-alerts
```

## Đang mở (open items)

- [ ] Chạy listener dài (~1 giờ+, logger đã nghe `0x13/0x0007`) để xác nhận mọi loại thay đổi
  của mỏ đều đi qua broadcast type 150 (live đã thấy: action `9001` rồi `12` cách 6s trên
  `0x13/0x0007`).
- [ ] Map `action` 1–12, `9001/9002/9003` và template 28000 (đối chiếu localization trong JS bundle nếu cần).
- [ ] Giải f6, f8/f9 — xem open items cuối `docs/MINE_STRUCTURE.md`
  (nghi vấn "lazy name" + owner guild + slot 9001–9003 đã giải xong 2026-10-23: tên fetch nguyên mỏ
  lúc zoomin; **f4 = id guild chủ điểm**, tra tên qua `0x24/0x0035→0x0036`;
  **slot 9001–9003 = bộ claimer của guild chủ điểm** — 3 acc cùng guild, trùng guild claim `f4`).
- [ ] Giải nghĩa history entry type 1 `[7057, 10, ts]` (nghi event về slot của chính mình —
  pos + slot khớp summary f1/f2; số lượng không khớp 1:1 với popup Lịch Sử) và summary f9={30000015, 3, 525}.
- [x] id→tên player: request `0x0d/0x001f` với packed ids → `0x0020` trả tên (đã xác minh
  2026-10-23: 6 id trong history feed → HaHuu, UnVila, AESaa, AEDungg, AEBon, OLNiet).
- [ ] Kiểm tra server CN (`hauntheroesweb.acenetgame.com`) có cùng framing/module không.
- [ ] Xác định cách giữ session lâu dài (token login trong localStorage của profile có TTL
  `expires_in: 2419200` — 28 ngày, xem `env.json`); kiểm tra game có kick AFK/session idle
  lâu không (chưa gặp trong 4 phút test).
