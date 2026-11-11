# Hero spin (大转盘 / Lucky Wheel)

Trụ cột 2 của simulator. Status 2026-11-10: **client quyết hoàn toàn** — đã xác minh runtime
(1 spin, Stage 51). Main doc: [README.md](README.md). Cùng cơ chế random với
[hero_option.md](hero_option.md).

## Trigger (3 nguồn, đã verify trong code + config)

| Nguồn | Code | entityId gửi lên |
|---|---|---|
| Giết unit có `CreepLO.killedTrigger` chứa `OpenWheel` | `BattleTDBaseDirector.onUnitDead` → `_openWheelEntityIds.push(entityID)`; mở 1 wheel / 10 tick ở `onLogicTick` | entityID của unit chết (vd `3100031`) |
| Option vàng MagicCard "Lucky Wheel" (`900020001`, effect `10001305000`) | skill action preset `MagicCardOpenWheel` | `2` (`ECustomOpenWheelEntityID.MagicCard`) |
| Trap (organ) đặc biệt "Lucky Drop" (airdrop, đặt bằng nút Build Trap — user xác nhận 2026-11-10; icon `skill_jiguan_007`), chỉ khi đã nâng tới mốc "Low-probability bonus: gains one Spin chance" (`40100707000`) | action `40100701400` (bậc cd 45s) / `40100704400` (bậc cd 30s), preset `OrganSkillOpenWheel`, điều kiện theo số lớp buff | `1` (`OrganSkill`) |

- `CreepLO`: 758 creep có `OpenWheel` — các biến thể code `…02` (`type 2`, mini boss) của mọi
  loại zombie + boss (`type 3`). Mini boss và final boss đi cùng 1 đường → khớp quan sát
  "mini/final như nhau". Một số có thêm `|Block`.
- Không mở nếu trận đã kết thúc (`checkBattleEnd`) hoặc GM `BLOCK_ALL_LOTTERY`.

## Flow

1. Client op `大转盘召唤 {lifeRatio, entityId}` (`LotteryElite`) → `TDPlayerEntity.lotteryElite`.
2. Config: `lotteryEliteConfigs[_refreshEliteIndex]` (`BuildRefreshEliteLO`): `lotteryNum 8`,
   `refreshType [1,2,3,4,6,7]`. Loại trừ code đang có trong `_lotteryCodes` / `_giftCodes`.
3. `randomCode(…, mode 1, elite=true)` → 8 ô, pick theo **`turntableWeight`**.
4. Số ô trúng `_selectEliteNum`: random theo `BuildTurntableLO` — num 1/2/3/4 với weight
   8000/1600/320/80 (≈80% / 16% / 3.2% / 0.8%).
   - Lucky Wheel (MagicCard): tối thiểu `ConstLO TDLotteryEliteGuaranteedNum` = **2**.
   - Kẹp ≤ số ô có.
5. Chọn ô trúng: rút không hoàn lại trong 8 ô theo `turntableWeight` → `_giftCodes`.
   **Kết quả có trước animation** (log `大转盘选中奖励：[…]`).
6. UI `TDRouletteWheel` chỉ diễn animation dừng ở ô đã định. Tap blank/skip vẫn gửi
   `大转盘选择 {buildPos[], entityId}` (`SelectElite`, op 9) → `selectElite` áp từng gift
   (MagicCard/ActiveSkill → ActiveSkill op; HeroFinal → HeroFinalSkill; còn lại `_selectConfig`),
   `_refreshEliteIndex++`.
7. Nút Refresh (1/1) = **xem quảng cáo** (`HangUpRouletteWheel`) → random lại 8 ô, giữ số ô trúng
   = số gift cũ.

## Quan sát runtime

2 spin, đều do mini boss chết, không packet nào ngoài `UpdateDamage` định kỳ:

| frame | entityId | lifeRatio | 8 ô | trúng |
|---|---|---|---|---|
| 1180 | 3100031 | 10000 | 300001004, 300001001, 250010001, 250010026, 250020004, 250010003, 400011013, 300001003 | 250010026, 250010003 |
| 2310 | 3100112 | 6921 | 250020003, 400011004, 250020026, 250010001, 250020013, 300001026, 300001003, 250020004 | 250020013, 250020026 |

Skip → `大转盘选择` 3 frame sau, áp ngay ("升级" ×2).

Kiểm chứng ngoài game: port `sfc32` sang Python, lấy state RNG sau `randomCode` → draw kế tiếp
×10000 = 9493.7 và 8314.6 → rơi vào bucket num 2 (8000–9600) đúng như game. RNG port được.

## Mở

- `cardTurntableWeight` (cột riêng cho MagicCard) dùng ở đâu — chưa thấy trong `randomCode`
  base, có thể override ở `TDAdvGuidePlayerEntity`/`TDTeamHighPlayerEntity`.
- `HostingMgr.triggerOtherLotteryElite` (auto/hosting cho người chơi khác) — chưa đọc.
