import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';
const catalog = JSON.parse(readFileSync(new URL('../web/dict/naval-boss-dict.json', import.meta.url)));
const bosses = Object.values(catalog.bosses);
const presets = bosses.flatMap((b) => b.presets);
test('naval catalog keeps all event pools and unique game level keys', () => {
  assert.equal(catalog.battleType, 42);
  assert.equal(bosses.length, 27);
  assert.equal(presets.length, 402);
  assert.equal(new Set(presets.map((p) => p.level)).size, 402);
  assert.equal(presets.filter((p) => p.phase === 'audition').length, 3);
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
