# Resource bị ignore — mang sang máy khác

`battle_sim` cần một số file nằm trong `.tmp/` (gitignore). Clone repo thôi chưa chạy được.
Code chỉ đọc 2 thư mục `.tmp/battle_sim/` và `.tmp/battle_research/`. Đường dẫn tính từ gốc
repo, phải giữ nguyên.

## Bắt buộc copy (không tải lại được)

| Đường dẫn | Cỡ | Đọc bởi | Vì sao |
|---|---|---|---|
| `.tmp/battle_research/events-*.jsonl` | vài MB | `lib/capture.js` (`replay.js`, `serve.js`, `sandbox.py --battle/--play`) | Capture trận (`StartGameP` + `QuitRoom`). Mất thì phải chơi lại trên game thật. |
| `.tmp/battle_sim/bundles/index.<hash>.js` | 24MB | `lib/versions.js` | Code bundle đúng `battleVersion` của capture. Host chỉ giữ bản đang live. |
| `.tmp/battle_sim/maps/<mapVersion>/` | 2MB | `lib/versions.js` | Map Tiled đúng `mapVersion`. Cùng lý do như bundle. |
| `.tmp/battle_sim/played/*.jsonl` | nhỏ | `replay.js <file>` | Trận tự chơi bằng `--play` (nếu có). |

## Nên copy (tải lại được nhưng lâu hoặc có điều kiện)

| Đường dẫn | Cỡ | Ghi chú |
|---|---|---|
| `.tmp/battle_sim/mirror/<ClientVer>/` | ~680MB, ~14.1k file | Asset cho `serve.js` / `sandbox.py` (mốc B). `mirror.js fetch` tải lại được **chỉ khi** host vẫn ở cùng ClientVer. Game đã cập nhật thì mirror mới lệch với capture cũ. |
| `.tmp/battle_sim/config/<configVersion>/` | 4MB | Thiếu thì `lib/versions.js` tự tải từ CDN (CDN giữ bản cũ). |

## Không cần

- `.tmp/battle_sim/sandbox-*.log`, `simlog-*.json`: log chạy.
- Phần còn lại của `.tmp/battle_research/` (`q_*.js`, `driver.py`, ảnh, `data/`…): tool nghiên
  cứu. Chỉ cần nếu muốn capture trận mới bằng `run_runner_hooked.py` (cả thư mục ~80MB).
- `.tmp/bundle/`: bundle nghiên cứu cũ. `versions.js` có quét, nhưng `bundles/` đã đủ.
- `.tmp/pspo/`: profile Chrome **có đăng nhập**. Không mang sang máy khác.

## Đóng gói và giải nén

Ở máy cũ, tại gốc repo (nén giúp copy nhanh hơn nhiều so với 14k file lẻ). File nén ghi vào
`.tmp/` (đã gitignore) để không lỡ commit ~680MB vào repo:

```bash
tar -czf .tmp/battle_sim_cache.tgz --record-size=1M --checkpoint=50 --checkpoint-action='echo=%u MB' .tmp/battle_sim/bundles .tmp/battle_sim/maps .tmp/battle_sim/config .tmp/battle_sim/mirror .tmp/battle_research/events-*.jsonl
```

Cứ mỗi 50MB (tính theo dữ liệu gốc, trước khi nén) in một dòng `tar: 50 MB`, `tar: 100 MB`…;
tổng khoảng 720MB. Bỏ hai cờ `--checkpoint*` nếu không cần theo dõi. Giải nén cũng thêm được
cùng các cờ đó.

Có trận `--play` thì thêm `.tmp/battle_sim/played` vào lệnh trên.

Ở máy mới, chép file vào `.tmp/` của repo (sau khi checkout đúng nhánh), rồi tại gốc repo:

```bash
tar -xzf .tmp/battle_sim_cache.tgz
```

```bash
uv sync
```

## Kiểm tra sau khi chuyển

```bash
node battle_sim/replay.js
```

Phải khớp mọi trận (hiện 3/3), không có lỗi thiếu bundle hoặc map.

```bash
uv run python battle_sim/sandbox.py --headless
```

Phải ra `ready`, 0 request bị chặn, 0 file 404 (mirror đủ).

## Khi game cập nhật

Bundle và map mới chỉ lấy được lúc deploy đó còn live. Trước khi capture trận mới, chạy
`node battle_sim/snapshot.js`, rồi `node battle_sim/mirror.js fetch` nếu cần bản có hình.
Bộ cũ trong cache vẫn giữ để replay các capture cũ, nên cũng phải copy khi chuyển máy.
