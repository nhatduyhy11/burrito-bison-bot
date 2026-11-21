import assert from 'node:assert/strict';
import { readFileSync, mkdtempSync, writeFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import vm from 'node:vm';
import { test } from 'node:test';
import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
const { loadCapture } = require('../lib/capture.js');
const list = (items) => ({ ...items, _length: items.length });
const event = (kind, msg, obj) => ({ kind, data: { msg, obj } });
const start = { battleType: 42, playerInfos: list([{ playerId: 123, heros: list([{ code: 1 }]) }]) };

test('capture attaches only this account roster before battle, and does not retroactively replace it', (t) => {
  const dir = mkdtempSync(join(tmpdir(), 'roster-capture-'));
  t.after(() => rmSync(dir, { recursive: true, force: true }));
  const path = join(dir, 'capture.jsonl');
  const roster = { playerId: 123, heros: list([{ code: 2, level: 90 }]), complete: false };
  writeFileSync(path, [event('roster', 'HeroRosterSnapshot', roster), event('room', 'StartGameP', start),
    event('roster', 'HeroRosterSnapshot', { ...roster, heros: list([{ code: 3 }]) }), event('sock', 'QuitRoom(', {})].map(JSON.stringify).join('\n'));
  assert.equal(loadCapture(path)[0].roster.heros[0].code, 2);
  roster.playerId = 999;
  writeFileSync(path, [event('roster', 'HeroRosterSnapshot', roster), event('room', 'StartGameP', start), event('sock', 'QuitRoom(', {})].map(JSON.stringify).join('\n'));
  assert.equal(loadCapture(path)[0].roster, undefined);
});

test('solo battle can use full hero roster from a naturally captured team lobby', (t) => {
  const dir = mkdtempSync(join(tmpdir(), 'roster-team-'));
  t.after(() => rmSync(dir, { recursive: true, force: true }));
  const path = join(dir, 'capture.jsonl');
  const heros = list([{ code: 2, relic: 10, artifact: { code: 42 } }]);
  writeFileSync(path, [event('sock', 'refreshMemberInfosR(3)', { members: list([{ baseInfo: { playerId: 123 }, moduleDatas: { heros } }]) }),
    event('room', 'StartGameP', start), event('sock', 'QuitRoom(', {})].map(JSON.stringify).join('\n'));
  const battle = loadCapture(path)[0];
  assert.equal(battle.team, undefined);
  assert.deepEqual(battle.roster, { playerId: 123, heros, source: 'team', complete: true });
});

test('passive hook records roster and nested lobby gear without changing calls or sending extra packets', () => {
  const events = [], calls = [];
  const td = { prototype: { onStartGamePPush(data) { calls.push(['start', data]); return 17; } } };
  const socket = { prototype: { send(...args) { calls.push(['send', ...args]); return 19; }, log(...args) { calls.push(['log', ...args]); } } };
  const artifact = { battleEntryInfos: list([{ code: 1, nested: { a: { b: { c: 42 } } } }]) };
  const modules = { TDModule: { TDModule: td }, SocketMgr: { SocketMgr: socket }, PlayerModule: { PlayerModule: { Ins: { playerId: 123 } } },
    HeroModule: { HeroModule: { Ins: { _uuid2HeroMap: { foreach(fn) { fn('a', { code: 1, artifact }); } } } } },
    SummonerModule: { SummonerModule: { Ins: { info: {} } } } };
  const window = { cc: { js: { getClassByName: (key) => modules[key]?.[key] } }, __require() { throw Error("Must not force game module loading"); }, __recordBattle: (data) => { events.push(JSON.parse(data)); return Promise.resolve(); } };
  const context = vm.createContext({ window, WebSocket: { OPEN: 1 } });
  const source = readFileSync(new URL('../../scripts/capture/battle-hook.js', import.meta.url), 'utf8');
  vm.runInContext(source, context);
  vm.runInContext(source, context); // idempotent
  assert.equal(td.prototype.onStartGamePPush(start), 17);
  const lobby = { members: list([{ artifact }]) };
  socket.prototype.log('refreshMemberInfosR(3)', lobby);
  assert.equal(socket.prototype.send.call({ _socket: { readyState: 1 } }, 82, 4, {}), 19);
  assert.deepEqual(calls.map(([name]) => name), ['start', 'log', 'send']);
  assert.deepEqual(events[0].data.obj.heros[0].artifact, artifact);
  assert.deepEqual(events.find((e) => e.data.msg === 'refreshMemberInfosR(3)').data.obj, lobby);
});
