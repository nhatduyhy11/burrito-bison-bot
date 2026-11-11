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
| B1 — mirror asset | xong, 662MB | `scripts/mirror.js`, `serve.js` |
| B2 — boot cách ly | xong | `sandbox.py`, `web/boot.{html,js}` |
| B3 — trận có hình, replay op log | xong, `QuitRoom` khớp tuyệt đối (xem dưới) | `web/battle/`, `lib/capture.js` |
| B4 — tự chơi trong simulator | đã có `--play` và trang setup `--setup`; cần chơi thử bằng tay | `sandbox.py`, `web/battle/`, `web/setup.{html,js}` |

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
uv run python battle_sim/sandbox.py --setup
```

`--setup` mở trang setup: chọn capture gốc, seed, stage, hero (skin/sao/slot), trap, pet,
spell, skin building, rồi bấm "Chơi". Profile được lưu vào `.tmp/battle_sim/profiles/` và
trận mở với profile đó. Backend đọc đủ mọi phần (trừ hero support), khớp tuyệt đối với
capture. Chạy thẳng không qua trang:
`sandbox.py --battle <uuid> --play --seed random [--profile <file>]`.

`--play` mở cửa sổ Chromium cách ly, dùng đội hình từ `StartGameP` và để UI gửi op
qua `TDServerProxy` chế độ Local. Director tự điều khiển robot đồng đội và dừng trận
khi mở bảng chặn. `--seed random` tạo seed mới; có thể chơi tùy ý. Playwright có thể
kết nối cửa sổ simulator qua CDP `127.0.0.1:9334`.

Lần chạy thử tiếp theo: dựng một profile trên trang setup (có pet, spell, skin building,
skin 7 màu), thả pet, cast spell, bấm các bảng chọn trong trận, chơi đến màn kết quả,
rồi kiểm tra file `played-*.jsonl` và log sandbox. Màn kết quả dùng phản hồi local
với `clientReward: null`. Xem [hướng dẫn tự chơi](../../../battle_sim/README.md#tự-chơi-trận-với-đội-hình-account-mốc-b-bước-4)
để biết cách replay lại trận vừa chơi.

## Skin hero: rule đã xác nhận (capture pmain 2026-11-11)

Nguồn: `HeroDermaModule` trong bundle và trận `6af3d7da1d68f99b52631ef9` trong
`.tmp/battle_research/events-skin3-20261111.jsonl`.

- Mỗi hero có 3 skin thường: 1 đỏ (color 6) và 2 vàng (color 7). Skin 7 màu (color 8)
  yêu cầu cả 3 skin thường ở số sao ≥ sao của 7 màu.
- Skill skin đi theo **slot**, không theo skin đang mặc. Mỗi hero (theo `subType`) có
  3 slot thường (`HeroDermaSkill.skills`) và 1 slot 7 màu riêng (`colorSkills`).
- `StartGameP` gắn skill của **mọi skin trong slot**, mỗi skill ở mã của số sao hiện
  tại, theo thứ tự slot, sau các skill gốc. `index` là vị trí 1-based trong list. Ví dụ
  Dark Lubu mặc 5001301 vẫn có cả 3 skill 8004131x/8004132x/8004130x. `derma` chỉ là
  model đang mặc.
- `dermaIndex` của skill skin (2 = vàng 1, 3 = vàng 2, 4 = 7 màu) đi vào
  `reserved.dermaIndexsCond`. Perform BT kiểm tra các giá trị này bằng điều kiện
  `PF2/PF3/PF4` (`ToggleConditionBtNodeParser`), nên hiệu ứng hình phụ thuộc vào bộ skill
  skin. Không skill skin nào dùng `exclusionGroup`, nên phần logic không bị thay thế.
- `skin-profile.js` đã theo rule này (`slots`), xem
  [PROFILE_SKINS.md](../../../battle_sim/PROFILE_SKINS.md). Còn chưa xác nhận: skill 7 màu
  đứng sau 3 skill thường (chưa có account 7 màu).

## Trap, pet, spell (capture pmain `6af3dacb1d68f99b52632087`, replay khớp tuyệt đối)

Trận Stage 314 trong `.tmp/battle_research/events-trappet-20261111.jsonl`, 109 op, không
gặp boss (`bossNum` rỗng).

- Thả trap và pet đều dùng op Create (type 4) với `type` 7 (trap) hoặc 10 (pet) và
  `heroCode` là mã trap hoặc pet.
- Spell chủ động (thần trong `daoists`) dùng op type 19 `{skillCode}`. Mỗi lần cast tốn
  60 điện (item 30600002). Trận này chỉ có 1 lần cast (frame 3195). Các dòng "激活技能/神兵技能"
  trong log là thẻ chọn từ lượt quay (op 10 + 8), không phải spell.
- Chọn base: op type 2 `{roomId}`; người chơi ở room 1.

## Còn mở từ B3

- `remoteConfig` (`getRemoteAgent`) để rỗng: game dùng mặc định cho các `PerformType`. Nếu
  thấy hành vi lệch, cân nhắc lấy `checkConfig` từ capture thụ động.
- Headless chậm (~10 fps), một trận ~8 phút; cửa sổ thật nhanh hơn.

## Gợi ý cách làm

Đi từng bước nhỏ, mỗi bước chạy `sandbox.py` để xem lỗi đầu tiên, sửa đúng chỗ đó rồi chạy
lại. Trước khi thêm init hay stub nào, đọc module tương ứng trong
`.tmp/bundle/main.1377a/modules/`. Lỗi bị game nuốt (`console.error` chỉ có message) thì dùng
`?trace=Module.method` để lấy stack.
