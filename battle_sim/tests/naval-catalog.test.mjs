import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';
import generator from '../scripts/gen_naval_dict.js';
const catalog = JSON.parse(readFileSync(new URL('../web/dict/naval-boss-dict.json', import.meta.url)));
const bosses = Object.values(catalog.bosses);
const presets = bosses.flatMap((b) => b.presets);
test('naval catalog keeps all room pools and unique game level keys, excluding audition', () => {
  assert.equal(catalog.battleType, 42);
  assert.equal(bosses.length, 24);
  assert.equal(presets.length, 399);
  assert.equal(new Set(presets.map((p) => p.level)).size, 399);
  assert.ok(presets.every((p) => p.phase === 'rooms' && [1, 2, 3].includes(p.subType)));
  assert.ok(bosses.every((b) => ![70072501, 70072601, 70072701].includes(b.code)));
  for (const subType of [1, 2, 3]) {
    assert.equal(presets.filter((p) => p.subType === subType).length, 133);
    assert.equal(bosses.filter((b) => b.presets.some((p) => p.subType === subType)).length, 19);
  }
  for (const boss of bosses) {
    assert.ok(boss.name && boss.name_vn);
    for (const p of boss.presets) for (const code of p.creeps) assert.ok(catalog.creeps[code]);
  }
  const captured = bosses.find((b) => b.presets.some((p) => p.level === 2040401));
  assert.equal(captured.code, 70070401);
  assert.deepEqual(captured.presets.find((p) => p.level === 2040401).creeps, [70081501, 70081601, 70081901]);
});

test('naval generator excludes audition rows before reading their bosses or companions', () => {
  const room = { id: 2040400, subType: 2, day: 4, showCreep: '[70070401,70081501]', round: '[1]', battleGroundCode: 62061 };
  const tables = {
    GuildNavalMonthwarLO: { store: { foreach: (visit) => {
      // Audition data is deliberately unavailable: those rows must not enter the catalog pipeline.
      for (const id of [10000000, 20000000, 30000000]) visit(id, { id, subType: 0 });
      visit(room.id, room);
    } } },
    GuildNavalMonthwarRoundLO: { get: () => ({ roundType: 3, creep: '[70070401]' }) },
    BattleGroundLO: { get: () => ({}) },
    CreepLO: { get: (code) => ({ name: `creep ${code}`, simpleDesc: 'room creep' }) },
  };
  const generated = generator.navalCatalogs((name) => tables[name], (name) => tables[name]);
  assert.deepEqual(Object.values(generated.bosses).map((b) => b.code), [70070401]);
  assert.deepEqual(Object.values(generated.bosses)[0].presets, [
    { level: 2040401, phase: 'rooms', subType: 2, day: 4, position: 4, creeps: [70081501] },
  ]);
  assert.deepEqual(Object.keys(generated.creeps), ['70081501']);
});
