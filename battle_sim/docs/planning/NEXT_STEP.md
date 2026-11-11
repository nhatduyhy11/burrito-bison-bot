# NEXT STEP — Kiểm tra chơi tương tác trong simulator

Status 2026-11-11. Đọc file này đầu tiên khi bắt đầu session mới. Mục tiêu, nguyên tắc an
toàn và kiến thức nền: [research.md](research.md). Cách chạy: [battle_sim/README.md](../../README.md).

**An toàn (bắt buộc):** không gửi gói giả/đã sửa lên server thật, không chặn/giả socket hay
gọi hàm game trên trang live đang đăng nhập. Mọi thử nghiệm chạy trong `battle_sim/sandbox.py`.
Chi tiết: [research.md §Nguyên tắc an toàn](research.md#nguyên-tắc-an-toàn-vùng-xám-tránh-dính-ban).

## Đã có

| Mốc | Trạng thái | Code |
|---|---|---|
| A — logic sim headless | xong, replay khớp tuyệt đối mọi capture | `replay.js`, `lib/` |
| B1 — mirror asset | xong, 690MB | `scripts/mirror.js`, `serve.js` |
| B2 — boot cách ly | xong | `sandbox.py`, `web/boot.{html,js}` |
| B3 — trận có hình, replay op log | xong, `QuitRoom` khớp tuyệt đối | `web/battle/` |
| B4 — tự chơi trong simulator | `--play` + trang setup `--setup`, x2 và auto mở sẵn; trận chơi (auto) replay khớp tuyệt đối, **chưa chơi tay đến thắng** | `sandbox.py`, `web/battle/`, `web/setup/` |
| B5 — mở khoá, chỉnh số | chưa làm, chỉ trong bản cách ly | |

## Việc tiếp theo: chạy thử B4

Checkout mới thiếu mirror hoặc capture thì chép cache theo [CACHE.md](../../CACHE.md).

```bash
uv run python battle_sim/sandbox.py --setup
```

Dựng một profile trên trang setup (có pet, spell, skin building, skin 7 màu), thả pet, cast
spell, bấm các bảng chọn trong trận, chơi đến màn kết quả, rồi kiểm tra file `played-*.jsonl`
và log sandbox. Replay lại trận vừa chơi: xem
[README §Tự chơi](../../README.md#tự-chơi-trận-với-đội-hình-account-mốc-b-bước-4).
Playwright kết nối cửa sổ simulator qua CDP `127.0.0.1:9334`.

## Còn mở

- `remoteConfig` (`getRemoteAgent`) để rỗng: game dùng mặc định cho các `PerformType`. Nếu
  thấy hành vi lệch, cân nhắc lấy `checkConfig` từ capture thụ động.
- Headless chậm (~10 fps), một trận ~8 phút; cửa sổ thật nhanh hơn.
- Hero support vẫn lấy từ capture, profile chưa chọn được.
- Logic sim: director `onUnitCreated` (`updateBuildingEntityIds`, bind giường) không chạy
  trong Node. Chưa thấy ảnh hưởng; trận nào lệch thì kiểm chỗ này trước. Khi đó dùng thêm
  tier 3 (hash state theo tick, `getHashCode`/`dumpHash` của delegate) để tìm tick đầu tiên lệch.
  Chưa so vị trí boss theo tick (`boss.track`) và `UpdateDamage` mỗi 30s.
- Mở riêng theo chủ đề: [BUILD_SKINS.md](../../BUILD_SKINS.md), [PROFILE_SKINS.md](../../PROFILE_SKINS.md),
  các doc cơ chế trong [research.md](research.md#doc-cơ-chế).

## Gợi ý cách làm

Đi từng bước nhỏ, mỗi bước chạy `sandbox.py` để xem lỗi đầu tiên, sửa đúng chỗ đó rồi chạy
lại. Trước khi thêm init hay stub nào, đọc module tương ứng trong
`.tmp/bundle/main.1377a/modules/`. Lỗi bị game nuốt (`console.error` chỉ có message) thì dùng
`?trace=Module.method` để lấy stack.
