import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';
import { emptyState, normalize, fromProfile } from '../web/setup/profile-io.js';
import { hasSummonedJoker, JOKER_SUMMON } from '../web/hero-lineup.js';

const dict = JSON.parse(readFileSync(new URL('../web/profile-dict.json', import.meta.url)));
const base = { battle: '', seed: '' };

test('all setup states retain five editable hero slots, including partial imports', () => {
  const state = emptyState();
  normalize(state, dict);
  assert.equal(state.heroes.length, 5);
  const imported = fromProfile({ heroes: ['hanuman'] }, base, dict);
  assert.equal(imported.heroes.length, 5);
  assert.equal(imported.heroes[0].name, 'hanuman');
  assert.equal(imported.heroes[4].name, '');
});

test('Joker support requires Loli summon skin in a slot and no regular Joker', () => {
  assert.equal(hasSummonedJoker([{ name: JOKER_SUMMON.hero }], true), true);
  assert.equal(hasSummonedJoker([{ name: JOKER_SUMMON.hero }], false), false);
  assert.equal(hasSummonedJoker([{ name: JOKER_SUMMON.summonedHero }], true), false);
});
