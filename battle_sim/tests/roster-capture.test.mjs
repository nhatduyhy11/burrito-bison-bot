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

test('roster snapshot marks lobby-cache gaps and reports failures instead of staying silent', () => {
  const read = (hook) => {
    const events = [];
    const socket = { prototype: { send() { return 19; }, log() {} } };
    const td = { prototype: { onStartGamePPush() {} } };
    const map = { foreach(fn) { fn('a', { code: 1 }); } };
    const modules = { TDModule: { TDModule: td }, SocketMgr: { SocketMgr: socket }, PlayerModule: { PlayerModule: { Ins: { playerId: 123 } } },
      HeroModule: { HeroModule: { Ins: { _uuid2HeroMap: map } } }, SummonerModule: { SummonerModule: { Ins: { info: {} } } } };
    const window = { cc: { js: { getClassByName: (key) => modules[key]?.[key] } }, __recordBattle: (data) => { events.push(JSON.parse(data)); return Promise.resolve(); } };
    vm.runInContext(hook, vm.createContext({ window, WebSocket: { OPEN: 1 } }));
    td.prototype.onStartGamePPush({});
    return { events, map };
  };
  const source = readFileSync(new URL('../../scripts/capture/battle-hook.js', import.meta.url), 'utf8');
  const ok = read(source);
  assert.equal(ok.events[0].data.msg, 'HeroRosterSnapshot');
  assert.deepEqual(ok.events[0].data.obj.incompleteFields, ['artifact', 'relic']);
  assert.equal(ok.events[0].data.obj.complete, false);
  // Empty lobby cache: an explicit error event, not a silent gap in the capture.
  const empty = read(source.replace("cls(\"HeroModule\").Ins._uuid2HeroMap.foreach((_k, hero) => heroes.push(hero));", ""));
  assert.equal(empty.events[0].data.msg, 'HeroRosterSnapshotError');
  assert.equal(empty.events[0].data.obj.reason, 'hero cache empty');
  // A throwing cache surfaces the reason too.
  const boom = read(source.replace("=> heroes.push(hero));", "=> { throw Error('boom'); });"));
  assert.equal(boom.events[0].data.msg, 'HeroRosterSnapshotError');
  assert.equal(boom.events[0].data.obj.reason, 'boom');
});

test('hook keeps every lobby message except keep-alive and chat noise', () => {
  const events = [];
  const socket = { prototype: { send() { return 19; }, log() {} } };
  const td = { prototype: { onStartGamePPush() {} } };
  const modules = { TDModule: { TDModule: td }, SocketMgr: { SocketMgr: socket }, PlayerModule: { PlayerModule: { Ins: { playerId: 123 } } },
    HeroModule: { HeroModule: { Ins: { _uuid2HeroMap: { foreach() {} } } } }, SummonerModule: { SummonerModule: { Ins: { info: {} } } } };
  const window = { cc: { js: { getClassByName: (key) => modules[key]?.[key] } }, __recordBattle: (data) => { events.push(JSON.parse(data)); return Promise.resolve(); } };
  vm.runInContext(readFileSync(new URL('../../scripts/capture/battle-hook.js', import.meta.url), 'utf8'), vm.createContext({ window, WebSocket: { OPEN: 1 } }));
  for (const msg of ['收到 Ping', '收到 PingR', '发送 GetChatList', '收到 GetChatListR', '收到 HeroInfoP(1)', '发送 EnterRoom(2)', '收到 refreshMemberInfosR(3)']) {
    socket.prototype.log(msg, { msg });
  }
  assert.deepEqual(events.map((e) => e.data.msg), ['收到 HeroInfoP(1)', '发送 EnterRoom(2)', '收到 refreshMemberInfosR(3)']);
});

test('loadCapture keeps lobby events between battles as each battle pre-window', (t) => {
  const dir = mkdtempSync(join(tmpdir(), 'roster-pre-'));
  t.after(() => rmSync(dir, { recursive: true, force: true }));
  const path = join(dir, 'capture.jsonl');
  const start2 = { ...start, battleType: 3 };
  writeFileSync(path, [
    event('sock', 'EnterRoom(2)', { battleType: 42 }), // before the first battle
    event('room', 'StartGameP', start), event('sock', 'QuitRoom(', {}),
    event('sock', 'QuitRoomR(4)', { result: 1 }), // reward response lands after the battle
    event('sock', 'refreshMemberInfosR(3)', { members: list([]) }),
    event('room', 'StartGameP', start2), event('sock', 'QuitRoom(', {}),
    event('sock', 'QuitRoomR(4)', { result: 2 }),
  ].map(JSON.stringify).join('\n'));
  const battles = loadCapture(path);
  assert.equal(battles.length, 2);
  assert.deepEqual(battles[0].pre.map((e) => e.data.msg), ['EnterRoom(2)']);
  assert.deepEqual(battles[0].events.map((e) => e.data.msg), ['QuitRoom(']);
  assert.equal(battles[0].start.battleType, 42);
  assert.deepEqual(battles[1].pre.map((e) => e.data.msg), ['QuitRoomR(4)', 'refreshMemberInfosR(3)']);
  assert.deepEqual(battles[1].events.map((e) => e.data.msg), ['QuitRoom(']);
  assert.equal(battles[1].start.battleType, 3);
});

test('solo roster gets relic/artifact from login wearList responses, in the battle lineup shape', (t) => {
  const dir = mkdtempSync(join(tmpdir(), 'roster-gear-'));
  t.after(() => rmSync(dir, { recursive: true, force: true }));
  const path = join(dir, 'capture.jsonl');
  const roster = { playerId: 123, heros: list([{ code: 2, uuid: 'h2' }, { code: 3, uuid: 'h3' }, { code: 4, uuid: 'h4' }]),
    complete: false, incompleteFields: ['artifact', 'relic'] };
  const entries = list([{ code: 40002907, value: 2483 }]);
  const relics = { err: 0, relicList: list([{ code: 82060401, uuid: 'r1', star: 3 }, { code: 82050201, uuid: 'r2' }]),
    wearList: list([{ heroUuid: 'h2', uuid: 'r1' }]) };
  const artifacts = { err: 0, artifactList: list([{ code: 10406001, uuid: 'a1', entryInfos: list([{ code: 1, value: 2 }]), battleEntryInfos: entries },
    { code: 11304001, uuid: 'a2', lockEntryCodes: list([]) }]), wearList: list([{ heroUuid: 'h2', uuid: 'a1' }, { heroUuid: 'h3', uuid: 'a2' }]) };
  const write = (lines) => writeFileSync(path, lines.map(JSON.stringify).join('\n'));
  const tail = [event('roster', 'HeroRosterSnapshot', roster), event('room', 'StartGameP', start), event('sock', 'QuitRoom(', {})];
  write([event('sock', ' 收到 GetRelicInfoR(5) 来自 RelicProxy(33)', relics), event('sock', ' 收到 GetArtifactInfoR(3) 来自 ArtifactProxy(32)', artifacts), ...tail]);
  const enriched = loadCapture(path)[0].roster;
  const [h2, h3, h4] = [0, 1, 2].map((i) => enriched.heros[i]);
  assert.equal(h2.relic, 82060401);
  assert.deepEqual(h2.artifact, { uuid: 'a1', code: 10406001, battleEntryInfos: entries });
  assert.equal(h3.relic, undefined); // wears no relic
  assert.deepEqual(h3.artifact, { uuid: 'a2', code: 11304001 });
  assert.equal(h4.relic, undefined);
  assert.equal(h4.artifact, undefined);
  assert.deepEqual(enriched.incompleteFields, []);
  assert.equal(enriched.complete, true);
  assert.deepEqual(enriched.gearFrom, ['relic:wearList', 'artifact:wearList']);
  // Only the relic response: artifact stays a known gap, nothing invented.
  write([event('sock', ' 收到 GetRelicInfoR(5) 来自 RelicProxy(33)', relics), ...tail]);
  const partial = loadCapture(path)[0].roster;
  assert.equal(partial.heros[0].relic, 82060401);
  assert.equal(partial.heros[0].artifact, undefined);
  assert.deepEqual(partial.incompleteFields, ['artifact']);
  assert.equal(partial.complete, false);
  // No response: roster unchanged.
  write(tail);
  assert.deepEqual(loadCapture(path)[0].roster, roster);
});
