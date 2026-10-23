# Mine claimer — Streak & Debuff tiers (decode reference + backlog)

> Key finding 2026-10-23. **Chưa implement** — backlog về sau. Doc này giữ cách decode để
> lát nữa bỏ vào `mine_logger.py` / `mine_report.py` mà không phải reverse lại.
> Capture tham chiếu: `.tmp/socket-capture/run-s7-lv8-v3` (战神), `run-s7-lv8-v2` (OLNaji),
> `run-check-streak` (streak 9→11 trong 5h). Probe: `.tmp/probe_tile_fields.py`,
> `.tmp/probe_olnaji_frames.py`.

## 1. UI → packet mapping (đã verify số thật)

Popup **"N|Lv Máy Đào Chính"** (click máy claimer giữa sàn) hiện 3 thứ trên mỗi hàng,
tất cả render thuần từ tile state + briefs — **không sinh request riêng**:

| Trên UI | Nguồn packet | Verify |
| --- | --- | --- |
| Ribbon đỏ "**N Chuỗi thắng**" | tile `f7` = repeated `{f1: slot_no, f2: streak}` | 战神 (7054, slot 9001) = **9**; OLNaji (7055) = **11**; slot thường đa số = 1 |
| Icon nắm đấm + **số tầng** | **`len(f5)` của slot** — số mốc ts trong packed string | 战神 = 4 mốc → 4 tầng; OLNaji = 1 → 1 tầng; HU.BON/HunCoCa = 0 mốc → không icon |
| Đồng hồ đếm ngược | `f5[0] − now` (mốc gần nhất) | 战神 16:40 ✓; OLNaji 23:21 ✓ (sai số < 5s giữa 2 shot) |

## 2. Chi tiết decode

Trong tile (có cả login `0x48/0x0002` lẫn detail `0x48/0x0007`, slot = submessage f5):

```python
# streak: f7 là repeated submessage {f1: slot_no, f2: streak}
for f, _w, v in decode_proto(tile_bytes):
    if f == 7 and isinstance(v, bytes):
        c = {cf: cv for cf, _cw, cv in decode_proto(v)}
        streak_by_slot[c[1]] = c[2]          # vd {9001: 9, 9002: 0, ...}

# debuff tiers: trong slot submessage, f5 = packed varints (ts hết hạn, TƯƠNG LAI)
slot = {sf: sv for sf, _sw, sv in decode_proto(slot_bytes)}
chain = list(read_packed_varints(slot[5])) if slot.get(5) else []
tiers = len(chain)                            # 4 = 4 tầng
next_expiry = min(chain)                      # countdown = next_expiry - now
# các mốc cách nhau đúng +3600s (cộng dồn theo tầng, không phải phiên đào quá khứ
# như decode nhầm ban đầu — đã sửa MINE_STRUCTURE.md mục 4)
```

Field kề bên cần biết: slot `f3` luôn = 0 (2 captures, chưa hiểu — không phải tầng);
tile `f6` = `{9001|9002: 0}` trên vài tile (chưa giải); `f8/f9` = cặp ts cách đúng 3600s
(thấy trên 1060/4044/6052 — chưa giải).

## 3. Nguồn chéo cho streak (đối chiếu, chưa cần parse)

- `0x1f/0x000b` (battle log, push lúc login): entry `{f1: attacker, f2: defender, f3: ts,
  f4: bên thắng (1=attacker, 2=defender), f7/f6: {"rKey","pKey"} rating}` — streak tăng khi
  defender thắng. Verify: HuAsura đánh OLNaji 2 lần, f4=2 cả 2 → OLNaji streak giữ/±.
- `0x1f/0x0007` leaderboard, `0x65/0x0009+0x000c` (round summary / list guild) — đã ghi
  trong `SOCKET_PROTOCOL.md` bảng module, chưa map đủ.

## 4. UI navigation để lấy data (socket_capture.py, cửa sổ 640x720)

Login → click(463,218) → click(470,690) → click(437,165) = view sector 7 →
click(345,285) = zoomin mỏ (sàn của mình) → click(163,63) = minimap → overview
(4 vòng tròn + 4 dòng "Sàn Máy Đào Chính"):

- **4 vòng tròn = 4 điểm theo đúng vị trí**: top_left/top_right/bot_left/bot_right =
  điểm 1/2/3/4 = thứ tự tile id (click TR đã nhảy đúng 7055; TL = 7054).
- **4 dòng list KHÔNG theo thứ tự tile** — nhóm guild mình lên trước (verify: rows
  [HUNTERS, HUNTERS, OLYMPUS, LxRVN] vs claims [7054 H, 7055 O, 7056 LxRVN, 7057 H]).
  Click dòng 2 (320,371) = HUNTERS lv8 = 7054 (đích của 战神/HU.BON).
- Click điểm trên overview → **nhảy thẳng vào sàn đó**, click máy giữa sàn (345,285) → popup.

## 5. Backlog (làm sau — chưa có trong code)

- [ ] `mine_logger.parse_tile`: giữ thêm `f7` (dict slot→streak) và `f5` (chain ts, hoặc
  đã suy ra `tiers` + `next_expiry`) — hiện chỉ giữ id/slot_no của slot, `f6`–`f9` bỏ hết.
- [ ] `mine_report`: thêm vào mỗi point `streak` (theo slot) + `debuff_tiers`/`debuff_expiry`
  (slot 9001 là chính), cân nhắc cảnh báo khi streak/tầng thay đổi giữa 2 lần snapshot.
- [ ] Giải nốt `f6`, `f8/f9`, `f3` (luôn 0) nếu bot cần.
