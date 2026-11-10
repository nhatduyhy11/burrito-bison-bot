# Mốc A — Logic sim headless

Status 2026-11-10: **xong** — code ở [`battle_sim/`](../../../battle_sim/README.md).
Main doc: [README.md](README.md).

## Kết quả kiểm chứng

| Trận | Kết quả game | Tier 1 (`QuitRoom.extra` + end) | Tier 2 (wave / randomCode / boss kill) |
|---|---|---|---|
| Stage 51 `6af2ab8a…` | thắng, 4469 tick, 47 709 403 dmg | MATCH | MATCH (425 spawn, 29/29, 4/4) |
| Stage 97 `6af2b568…` | thắng, 4339 tick, 242 673 510 dmg | MATCH | MATCH (425 spawn, 29/29, 4/4) |
| Stage 51 `6af29854…` | thua `GroupAllDead_0`, 324s | MATCH | MATCH (425 spawn, 12/12) |

Trận thua đầu tiên không dùng được (thiếu `StartGameP` vì hook vào muộn).

## Mở

- Tier 3 (hash state theo tick, `getHashCode`/`dumpHash` của delegate) — chưa cần vì tier
  1+2 đã khớp tuyệt đối; dùng khi có trận lệch để tìm tick đầu tiên lệch.
- So thêm vị trí boss theo tick (`boss.track`, Stage 97) và `UpdateDamage` mỗi 30s.
- Director `onUnitCreated` (`updateBuildingEntityIds`, bind giường) không chạy trong sim —
  chưa thấy ảnh hưởng; nếu trận nào lệch thì kiểm chỗ này trước.
- Chưa chơi "live" (tự ra quyết định thay vì replay op log) — bước kế tiếp nếu cần
  simulator để thử chiến thuật.
