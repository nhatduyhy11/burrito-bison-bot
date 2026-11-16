# Battle X2 / AI (auto) button: client gate vs server

Passive capture on pmain (full cards), campaign battle (battleType 3, Local sync), 2026-11-16.
Probe: `.tmp/probe_battle_buttons.py` (log only). Log: `.tmp/battle_buttons/events-20261116-171226.jsonl` (contains login tokens; keep local).

## Findings

- **No request at click time.** Pressing X2 / AI sends no socket message. Every battle action is a
  local `TDServerProxy.commitClientRequest` op; the whole op list is uploaded once at the end in
  `QuitRoom(82/4)` `operations` (plus `extra` result JSON and `totalTime`).
- **X2** gate = client `UnlockMgr.checkPass(MODULE_Common_Enum.BattleSpeed = 9003)`
  (`BattleFrame._onButtonSpeed`, `_checkSpeedBtn`), or `_useSpeedCard` / speed-experience subscribe.
  Each toggle becomes op `SetSpeed(13) {setTime: 1.6|1}`; the saved speed is auto-applied at frame 100.
  → The server **sees** SetSpeed 1.6 in QuitRoom. Whether it validates it against the card is unknown.
- **AI / auto** gate = client `checkPass(BattleAI = 9007)` (`TDBattleFrame._onButtonAI` → `_checkAIBtn`
  → `HostingMgr.Ins.start/stop`), or `_useAICard` / trusteeship-experience item. Toggling emits
  **no op**; hosting then produces ordinary ops (Lottery 10, Select 8, Upgrade 6, ChangePos 5),
  indistinguishable from manual play in the upload.
- `checkPass` = `UnlockLO` conditions (VIP/card) + `_lockByServer` list sent at login; `skipAllCheckForDebug`
  short-circuits it to allow.

## Implication / open questions

- AI unlock via client gate leaves no AI-specific trace in the upload (only timing patterns).
- X2 unlock leaves explicit `SetSpeed 1.6` ops in QuitRoom from a no-card account — detectable if the
  server checks. Not verified; do not test on a live account (see battle_sim safety rule).
- Op type enum: `EClientOperationType_Build_Enum` in `BuildProto.js` (SetRoomId 2 … SetSpeed 13, ManualTick 18).
