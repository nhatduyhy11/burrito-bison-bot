# burrito-socket-capture

Nhánh nghiên cứu **websocket-only**: bắt và giải mã packet WS của game H5
(Haunted Room / Haunt Heroes). Toàn bộ logic bot vision cũ (automap, train,
night, hero select, runner…) đã bị xoá khỏi nhánh này — lịch sử vẫn còn trên
`master`.

## Tools (`tools/socket_log/`)

| File | Vai trò |
| --- | --- |
| `socket_capture.py` | POC bắt frame: hook mọi WebSocket, dump payload nguyên vẹn ra `frames/NNNNN-{S\|R}.bin` + `index.jsonl`, kèm step DSL (`click:X,Y`, `shot:NAME`, `sleep:S`, `mark:LABEL`) |
| `socket_decode.py` | Decoder wire-format generic (không cần schema `.proto`), annotate timestamp heuristic |
| `mine_logger.py` | Logger dài hạn: giữ session game mở, ghi JSONL (mine-events / mine-state / mine-tiles / player-briefs / guild-briefs), fetch tên người chơi qua injected request |
| `mine_report.py` | Aggregate các JSONL trên thành báo cáo |
| `process_guard.py` | Lock theo profile (chặn chạy 2 instance) + xử lý stop signals |
| `page_guards.py` | Chặn popup profile, ẩn iframe H5 SDK (inlined từ bot cũ) |
| `navigation.py` | `navigate_to_game` có retry qua transient hang (inlined từ bot cũ) |

## Usage

```bash
# Bắt frame thô (POC)
uv run python tools/socket_log/socket_capture.py --profile .tmp/m535 --settle 12 --step shot:home

# Logger dài hạn
uv run python tools/socket_log/mine_logger.py --profile .tmp/m535 --snapshot        # 1 pass state + tên, rồi thoát
uv run python tools/socket_log/mine_logger.py --profile .tmp/m535 --duration 300    # tự dừng sau 5 phút
```

Cần profile `.tmp/<name>` đã có session đăng nhập (persistent context của
Playwright). Raw streams ghi dưới `.tmp/mine-events/`.

## Docs

- [`SOCKET_PROTOCOL.md`](SOCKET_PROTOCOL.md) — reference protocol WS (framing, module/cmd, decode)
- [`MINE_STRUCTURE.md`](MINE_STRUCTURE.md) — cấu trúc world mỏ: map UI ↔ protocol
- `planning/` — research notes còn tồn động (socket research, leaderboard WS, conventions)
- `assets/` — ảnh in-game dùng đối chiếu protocol
