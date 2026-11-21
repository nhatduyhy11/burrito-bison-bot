// Passive observation only: call the original methods once, never send packets or alter RNG.
(() => {
  if (window.__battleCaptureReady) return;
  // Reflection sees only classes the game has already loaded. Never force __require/init at login.
  const cls = (name) => window.cc?.js?.getClassByName(name);
  const TD = cls("TDModule"), Socket = cls("SocketMgr");
  if (!TD || !Socket) return;
  const td = TD.prototype, socket = Socket.prototype;
  const start = td.onStartGamePPush, send = socket.send, log = socket.log;
  const record = (kind, msg, obj) => {
    try { window.__recordBattle(JSON.stringify({ kind, data: { msg, obj } })).catch(() => {}); } catch {}
  };
  const snapshot = () => {
    try {
      // Read an already logged-in game's cache, without asking the server for anything.
      const heroes = [];
      cls("HeroModule").Ins._uuid2HeroMap.foreach((_k, hero) => heroes.push(hero));
      if (!heroes.length) return;
      record("roster", "HeroRosterSnapshot", {
        playerId: cls("PlayerModule").Ins.playerId,
        heros: { ...heroes, _length: heroes.length }, source: "hero-module", complete: false,
      });
    } catch {}
  };
  td.onStartGamePPush = function (data) {
    snapshot();
    record("room", "StartGameP(12)", data);
    try {
      const info = cls("SummonerModule").Ins.info;
      record("context", "Equipped summoner skin", { derma: info.derma || 0, heroId: info.heroId });
    } catch {}
    return start.apply(this, arguments);
  };
  socket.send = function (module, command, data) {
    const result = send.apply(this, arguments);
    if (module === 82 && command === 4 && this._socket?.readyState === WebSocket.OPEN) record("sock", "QuitRoom(4)", data);
    return result;
  };
  socket.log = function (msg, obj) {
    // Serialize the actual decoded object directly, so nested gear entries are not cut to <deep>.
    if (typeof msg === "string" && /(?:HeroInfoP|GetHeroInfoR|refreshMemberInfosR)\(/.test(msg)) record("sock", msg, obj);
    return log.apply(this, arguments);
  };
  window.__battleCaptureReady = true;
})();
