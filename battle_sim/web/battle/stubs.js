// Diagnostics and network stubs for the isolated battle page (this page only).
//   - console.error keeps stacks; ?trace=Module.method records the first throw with its stack
//   - SocketMgr / GameRoomSocket.send   -> logged, never sent (there is no socket anyway)
//   - PlayerModule.getMultiPlayerData   -> resolved at once (player data comes from StartGameP)
//   - PlayerModule.playerInfo           -> playerId + name, plus derma (worn Summoner skin): profile, else capture
//   - PlayerModule base-info cache      -> the other players (Đêm Đỏ guest) with their capture name + derma
//   - BuildProxy.QuitRoomRequest        -> recorded, answered locally with the client's own result
//   - BuildProxy.SetPauseRequest        -> answered locally (pause button / pause panel)

// Game code often catches and console.error()s; keep the stacks so the cause is visible.
export function captureErrors({ M, report, step }) {
  report.errors = [];
  const origError = console.error;
  console.error = function (...args) {
    const err = args.find((a) => a instanceof Error);
    if (report.errors.length < 20) {
      report.errors.push({
        msg: args.map((a) => (a instanceof Error ? String(a) : typeof a === "object" ? "[obj]" : String(a))).join(" ").slice(0, 300),
        stack: String((err || new Error()).stack).split("\n").slice(1, 8).map((l) => l.trim()).join(" | "),
        tick: report.tick,
      });
    }
    return origError.apply(this, args);
  };

  // Game code that catches and logs only String(err) loses the stack. ?trace=Module.method,...
  // wraps those methods so the first throw is recorded with its stack (diagnostics only).
  for (const spec of (new URLSearchParams(location.search).get("trace") || "").split(",").filter(Boolean)) {
    const [mod, meth] = spec.split(".");
    let proto;
    try { proto = M(mod).prototype; } catch (e) { step("trace: no such module", spec); continue; }
    const orig = proto[meth];
    if (typeof orig !== "function") { step("trace: no such method", spec); continue; }
    proto[meth] = function () {
      try { return orig.apply(this, arguments); } catch (e) {
        report.errors.push({ msg: `throw in ${spec}: ${e}`, stack: String(e && e.stack).split("\n").slice(1, 9).map((l) => l.trim()).join(" | "), tick: report.tick });
        throw e;
      }
    };
  }
}

export function stubNetwork({ M, report, step, myPid, summonerDerma, players = [] }) {
  const net = (what, extra) => {
    report.netCalls.push({ what, extra });
    if (report.netCalls.length <= 50) console.warn("[sim] stubbed net call", what, extra || "");
  };
  for (const name of ["SocketMgr", "GameRoomSocket"]) {
    const sock = M(name).Ins;
    sock.send = function (module, cmd, c2s) {
      let cmdName = cmd;
      try { cmdName = this.getCmdName(module, cmd); } catch (e) { /* keep number */ }
      net(`${name}.send`, { module, cmd: cmdName });
    };
  }
  const PlayerModule = M("PlayerModule");
  PlayerModule.Ins.getMultiPlayerData = async () => { net("PlayerModule.getMultiPlayerData (resolved locally)"); };
  // Shape of PlayerModule.updatePlayerInfo's holder; only playerId is known (from StartGameP).
  // derma: worn Summoner skin from the profile (summonerWorn); the battle reads it through
  // getSiglePlayerData -> SummonerUtils.getSummonerModel. Unset = default Summoner model.
  const me = players.find((p) => p.playerId === Number(myPid));
  // The profile's worn skin wins; without one, the capture's (Đêm Đỏ team info).
  const derma = summonerDerma ?? me?.derma ?? 0;
  const info = { playerId: myPid, name: me?.name, ...(derma ? { derma } : {}) };
  PlayerModule.Ins._playerInfo = { info, playerMoney: undefined, compressionFightCap: 0, speedCardEndDt: 0 };
  // Other players (Đêm Đỏ guest): the battle reads them through getSiglePlayerData, which serves the
  // base-info cache before asking the server. Seed it so the guest gets a name (not "undefined").
  // dt far ahead: the entry never expires (dt + CACHE_DURA >= server time).
  for (const p of players) {
    if (p === me) continue;
    PlayerModule.Ins._basePlayerCacheData.set(PlayerModule.Ins.getPlayerDataKey(p.playerId),
      { pInfo: { playerId: p.playerId, name: p.name, ...(p.derma ? { derma: p.derma } : {}) }, lastGetDataDt: 0, dt: 4e12 });
  }
  step("player", { playerId: PlayerModule.Ins.playerId, derma: info.derma || 0, players: players.map((p) => `${p.playerId}:${p.name}:${p.derma}`) });
}

// Play mode, this page only: act as if both privilege month cards are bought, in every battle type.
// UnlockLO gates two battle features on condition PrivilgeMonthCard (type 11), checked through
// MallModule.checkActVipCardIsBuy(NewMonthCard, card): 9003 BattleSpeed needs card 7 (x1.6 speed,
// BATTLE_SPEED_TIME_SCALE [1, 1.6]) and 9007 BattleAI card 8 (auto, HostingMgr). The buttons also
// need ActivityModule.isOpen(MonthCardDict) (speed) and TDModule.isHasAiButton (auto: battle type in
// ConstLO NeedAIBtnBattleType and 9008 BattleAIEntrance = player level >= 3, unknown here).
export function unlockMonthCards({ M, R, step }) {
  const { EActivityType_Activity_Enum: Act } = R("ActivityProto");
  const { MODULE_Common_Enum: Mod } = R("CommonProto");
  const mall = M("MallModule").Ins;
  const isBuy = mall.checkActVipCardIsBuy;
  mall.checkActVipCardIsBuy = function (type, card) {
    return type === Act.NewMonthCard || isBuy.apply(this, arguments);
  };
  const activity = M("ActivityModule").Ins;
  const isOpen = activity.isOpen;
  activity.isOpen = function (code) {
    return code === Act.MonthCardDict || isOpen.apply(this, arguments);
  };
  const unlock = M("UnlockMgr").Ins;
  const checkPass = unlock.checkPass;
  unlock.checkPass = function (id) {
    const result = checkPass.apply(this, arguments);
    return Number(id) === Mod.BattleAIEntrance ? { ...result, allow: true } : result;
  };
  const td = M("TDModule").Ins;
  td.isHasAiButton = function () {
    return !this.myPlayerEntity?.isSpectating && unlock.checkPass(Mod.BattleAIEntrance, false).allow;
  };
  // Auto play runs in HostingMgr.update, which only ticks while in a room with both sockets
  // connected (there are none here; robots are driven by the director instead). Report that
  // state to the game code only for the duration of that update.
  const hosting = M("HostingMgr").Ins;
  const roomMgr = M("GameRoomMgr").Ins;
  const sockets = [M("GameRoomSocket").Ins, M("SocketMgr").Ins];
  const update = hosting.update;
  let inUpdate = false;
  const inRoom = Object.getOwnPropertyDescriptor(Object.getPrototypeOf(roomMgr), "isInRoom");
  Object.defineProperty(roomMgr, "isInRoom", { configurable: true, get() { return inUpdate || inRoom.get.call(this); } });
  for (const sock of sockets) {
    const isConnecting = sock.isConnecting;
    sock.isConnecting = function () { return inUpdate || isConnecting.apply(this, arguments); };
  }
  hosting.update = function () {
    inUpdate = true;
    try { return update.apply(this, arguments); } finally { inUpdate = false; }
  };

  // Diagnostics: keep the battle frame (speed / auto buttons) reachable over CDP.
  const Frame = M("BattleFrame").prototype;
  const initUI = Frame.initUI;
  Frame.initUI = function () {
    window.__simBattleFrame = this;
    return initUI.apply(this, arguments);
  };
  step("month cards (local)", {
    speed: unlock.checkPass(Mod.BattleSpeed, false).allow, auto: unlock.checkPass(Mod.BattleAI, false).allow,
  });
}

// Play mode, this page only: spin re-roll (TDRouletteWheel "Refresh 1/1"). The button is a
// CommonAdsButtonComponent for HangUpRouletteWheel: shown only with that module's advertise info
// (leftTimes > 0, sent by the lobby, absent here) and checkAdsUnLock. Pressing it plays an ad; here
// the ad is skipped as FREE, then the wheel resends LotteryElite. The game allows it once per battle
// (TDServer.wheelWatchAds), so a fixed leftTimes 1 is enough.
export function unlockWheelRefresh({ M, R, step }) {
  const id = R("CommonProto").MODULE_Common_Enum.HangUpRouletteWheel;
  const { FREE } = R("ISDKInterface").ADS_STATUS;
  const common = M("CommonModule").Ins;
  const info = { id, leftTimes: 1, lastTime: 0 };
  const getInfo = common.getAdvertiseInfo;
  common.getAdvertiseInfo = function (m) { return m === id ? info : getInfo.apply(this, arguments); };
  const unlocked = common.checkAdsUnLock;
  common.checkAdsUnLock = function (m) { return m === id || unlocked.apply(this, arguments); };
  const show = common.showAdvertise;
  common.showAdvertise = function (key, scene, cb) {
    if (key !== M("AdsLO").get(id)?.key) return show.apply(this, arguments);
    step("wheel refresh: ad skipped (local)");
    cb(FREE);
  };
  step("wheel refresh (local)", { module: id });
}

// Pause button (TDBattleFrame._onClickClose): TDServerProxy.pauseBattle sends SetPause and opens
// TDBattlePausePanel only from SetPauseR. Answer locally (no reward preview). The open panel is a
// blocking view, so the director pauses the battle; Continue sends SetPause 0 and the director
// resumes when the panel closes. Quit dispatches AbandonBattle -> battle ends -> QuitRoom.
export function stubPause({ M, step }) {
  M("BuildProxy").Ins.SetPauseRequest = function (req, cbs) {
    step("SetPause (local)", { isPause: req.isPause, frame: req.frame });
    const cb = cbs && cbs[0];
    if (cb) setTimeout(() => cb({ err: 0, showRewards: null }), 0);
  };
}

// Speed button in team battles (TDBattleTeamFrame / TDBattleTeamHighFrame = Blood Night /
// TDBattleWerewolfFrame): _setTimeSpeed calls TDModule.setBattleSpeed, which sends
// BuildRoomProxy.SetSpeedRequest({speed: 10 * timeScale}) to the room server and commits the
// SetSpeed op only from its callback. There is no room server here: answer locally so the op
// goes through the Local path like campaign's.
export function stubRoomSpeed({ M, step }) {
  M("BuildRoomProxy").Ins.SetSpeedRequest = function (req, cbs) {
    step("SetSpeedRequest (local)", { speed: req.speed });
    const cb = cbs && cbs[0];
    if (cb) setTimeout(() => cb({ err: 0 }), 0);
  };
}

// Play mode: closing the result view would leave the battle for the lobby, which this page does
// not have (it hangs). Flag it instead; sandbox goes back to the setup page (or ends the run).
export function leaveOnResultClose({ M, step }) {
  const View = M("BattleBaseResultView").prototype;
  const onClose = View.onClose;
  View.onClose = function () {
    step("result view closed");
    window.__simLeave = "result closed";
    try { return onClose.apply(this, arguments); } catch (e) { /* lobby flow, not available here */ }
  };
}

export function stubQuitRoom({ M, report, step, rb, play, onQuit }) {
  M("BuildProxy").Ins.QuitRoomRequest = function (req, cbs) {
    report.quit = { type: req.type, extra: req.extra, endFrame: req.endFrame, totalTime: req.totalTime, battleType: req.battleType };
    // Play mode: keep the op log the game would upload, so a played battle can be replayed.
    if (play) report.quit.operations = rb.listItems(req.operations).map((o) => ({ operationType: o.operationType, playerId: o.playerId, operFrame: o.operFrame, index: o.index, args: o.args }));
    step("QuitRoom (local)", { type: req.type, endFrame: req.endFrame, totalTime: req.totalTime });
    const cb = cbs && cbs[0];
    if (cb) setTimeout(() => cb({ err: 0, result: req.type, clientReward: null, otherReward: null, extra: req.extra }), 0);
    onQuit();
  };
}
