# NEXT STEP — Kiểm tra chơi tương tác trong simulator

Status 2026-11-11. Đọc file này đầu tiên khi bắt đầu session mới. Main doc: [README.md](README.md).

## Mục tiêu tổng

Mini game battle standalone, chạy local, có hình, dùng code và asset gốc của game. Mốc
đầu tiên: **dựng lại đúng y hệt** trận của account (không chỉnh số). Mở khoá hay sửa số chỉ
tính sau, và cũng chỉ trong bản cách ly.

## Nguyên tắc an toàn (bắt buộc, vì có nguy cơ dính ban)

Chi tiết trong [README.md §Nguyên tắc an toàn](README.md). Tóm tắt:

- **Không** gửi gói giả hay gói đã sửa lên server thật. **Không** chặn/giả socket hay gọi
  hàm game trên trang live đang đăng nhập (profile `.tmp/pspo`, CDP 9333). Trên trang live
  chỉ dùng hook đọc thụ động.
- Mọi thử nghiệm chạy trong `battle_sim/sandbox.py`: profile trống, chặn mọi request không
  phải `127.0.0.1:8090`. Giả socket hay stub mạng **chỉ** làm trong trang này.

## Đã có

| Mốc | Trạng thái | Code |
|---|---|---|
| A — logic sim headless | xong, replay khớp tuyệt đối 3/3 trận | `battle_sim/replay.js`, `lib/sim.js` |
| B1 — mirror asset | xong, 662MB | `mirror.js`, `serve.js` |
| B2 — boot cách ly | xong | `sandbox.py`, `web/boot.{html,js}` |
| B3 — trận có hình, replay op log | xong, `QuitRoom` khớp tuyệt đối (xem dưới) | `web/battle.js`, `lib/capture.js` |
| B4 — tự chơi trong simulator | đã có `--play`; cần chạy thử UI trên checkout này | `sandbox.py`, `web/battle.js` |

Cách chạy và cơ chế của B3 (stub, bỏ qua pause của director, đóng bảng vòng quay):
[battle_sim/README.md §Trận có hình](../../../battle_sim/README.md).

```bash
uv run python battle_sim/sandbox.py --battle 6af2ab8a2f05ea3f58336962 --page "/sim.html?speed=6" --keep --timeout 900
```

Kết quả B3: cả 3 trận đã capture (Stage 51 thắng/thua, Stage 97) đều khớp `QuitRoom` tuyệt
đối, 0 op lỗi, 0 request bị chặn, 0 file 404.

## Chạy thử B4

Nếu checkout mới thiếu mirror hoặc capture, chép và giải nén cache theo
[battle_sim/CACHE.md](../../../battle_sim/CACHE.md). Chỉ clone repo thì chưa có dữ liệu trận.

```bash
uv run python battle_sim/sandbox.py --battle 6af2ab8a2f05ea3f58336962 --play --seed random
```

`--play` mở cửa sổ Chromium cách ly, dùng đội hình từ `StartGameP` và để UI gửi op
qua `TDServerProxy` chế độ Local. Director tự điều khiển robot đồng đội và dừng trận
khi mở bảng chặn. `--seed random` tạo seed mới; có thể chơi tùy ý. Playwright có thể
kết nối cửa sổ simulator qua CDP `127.0.0.1:9334`.

Lần chạy thử tiếp theo: bấm map và các bảng chọn trong trận, chơi đến màn kết quả,
rồi kiểm tra file `played-*.jsonl` và log sandbox. Màn kết quả dùng phản hồi local
với `clientReward: null`. Xem [hướng dẫn tự chơi](../../../battle_sim/README.md#tự-chơi-trận-với-đội-hình-account-mốc-b-bước-4)
để biết cách replay lại trận vừa chơi.

## Còn mở từ B3

- Design resolution dùng 720×1280 (mặc định của `UIMgr.init`); `Main` lấy từ Canvas của launch
  scene, chưa đối chiếu.
- `remoteConfig` (`getRemoteAgent`) để rỗng: game dùng mặc định cho các `PerformType`. Nếu
  thấy hành vi lệch, cân nhắc lấy `checkConfig` từ capture thụ động.
- Headless chậm (~10 fps), một trận ~8 phút; cửa sổ thật nhanh hơn.

## Gợi ý cách làm

Đi từng bước nhỏ, mỗi bước chạy `sandbox.py` để xem lỗi đầu tiên, sửa đúng chỗ đó rồi chạy
lại. Trước khi thêm init hay stub nào, đọc module tương ứng trong
`.tmp/bundle/main.1377a/modules/`. Lỗi bị game nuốt (`console.error` chỉ có message) thì dùng
`?trace=Module.method` để lấy stack.
