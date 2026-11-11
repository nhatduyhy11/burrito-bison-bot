# Hero option (Summon, 3 lựa chọn)

**Client quyết hoàn toàn**, xác minh runtime 2026-11-10. Index: [research.md](research.md).

## Kết luận

Bấm Summon → `TDPlayerEntity.lottery()` → `randomCode()` sinh option **local**, không packet
nào. Replay `randomCode` từ cùng state RNG cho kết quả trùng 100% (6/6 summon, Stage 51).
RNG = `TDServer.randSeed` (`sfc32`, seed = chuỗi `uuid` trận) — dùng chung với spawn quái,
robot, spin.

## Flow

1. Client op `召唤 {type:1, lifeRatio}` (`operationType 10`). `lifeRatio` = máu cửa ×10000.
2. Config lượt hiện tại: `TDServer.lotteryConfigs[_refreshTimes]` (`BuildRefreshLO` lọc theo
   `battleType`). Free summon (`_freeLotteryCount`) bỏ qua cost.
3. Kiểm cost (`checkEnough`, giảm theo `querySummonCostReduceDiscount`); thiếu → tip, không random.
4. `randomCode(refreshType, lotteryNum=3, mode 0, …)`:
   - Lặp `lotteryNum` lần, mỗi lần duyệt `BuildSummonLO` lấy ứng viên: `type ∈ refreshType`,
     chưa bị chọn trong lượt, `getBuildLevel < num`, `appearNum` chưa đủ, `lifeRatio` thỏa,
     hero thuộc đội ra trận (`initHeros`), `RoomSpecialLevel`, `count`, `SpecialCondition`
     (`LotteryConditionType`: LotteryTimesLower, ActiveHeroFinal(Num), UnlockThreeSkin,
     AntiqueTypeLevel, ActiveAtrifactSkill).
   - Pick có trọng số `weight` bằng `randSeed.next(0, total)`.
   - Hết ứng viên → ra < 3 option (đã gặp 2 và 1 option).
5. Rỗng hoàn toàn → thử lại tối đa 3 lần với `pledgeType` (bảo đảm).
6. Chọn: `召唤选择 {indexs:[i], buildPos:[{x,y}], type}` → `selectLottery` → `_selectConfig`
   (PutonHero = tạo build hero; HeroUpStar = nâng sao; Treasure…; MagicCard/ActiveSkill…);
   `_refreshTimes++` (trừ free).

## Config (Stage 51, battleType 3)

`BuildRefreshLO` theo lượt: cost coin `30600001` 5, 10, 20, 40, 80, 160, 320, 400, 480, 560,
600, 640…; `refreshType` xen kẽ `[1]` (PutonHero) và `[2,3,4,9]` (HeroUpStar, PutonTreasure,
TreasureUpstar, MagicCard); `lotteryNum 3`, `selectNum 1`.

`ESummonType`: 1 PutonHero, 2 HeroUpStar, 3 PutonTreasure, 4 TreasureUpstar, 5 TreasureFinal,
6 ActiveSkill, 7 HeroFinal, 8 HeroSkin, 9 MagicCard. `BuildSummonLO`: 36/116/52/180/52/3/38/27
dòng theo type. Cột: code, heroCode, num, appearNum, color, buildType, type, effect, cost,
weight, turntableWeight, cardTurntableWeight, count, lifeRatio, RoomSpecialLevel, SpecialCondition.

Option vàng "Lucky Wheel" (MagicCard `900020001`, weight 1000, appearNum 1) → mở spin, xem
[spin.md](spin.md).

## UI (để bot/driver)

Game pause khi hiện option. Thẻ y≈560; x = 193/320/447 (3 thẻ), 252/387 (2), 320 (1).

## Mở

- `type=2` lottery (`lotteryInitialConfigs`, `BuildRefreshInitialLO`) dùng khi nào.
- Free lottery (`ActiveFreeLottery` mỗi 4 tick khi `_freeLotteryTimes > 0`).
