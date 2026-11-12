import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';
import { capitalPreset, emptyState, normalize, fromProfile, toProfile } from '../web/setup/profile-io.js';
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

test('mount ownership and optional selection round trip; unowning clears selection', () => {
  const state = fromProfile({ mounts: { owned: ['azure_drone', 'ironclad_crab'], selected: 'azure_drone' } }, base, dict);
  assert.deepEqual(toProfile(state, dict).mounts, { owned: ['azure_drone', 'ironclad_crab'], selected: 'azure_drone' });
  state.mounts.owned = ['ironclad_crab'];
  normalize(state, dict);
  assert.deepEqual(toProfile(state, dict).mounts, { owned: ['ironclad_crab'], selected: null });
  assert.throws(() => fromProfile({ mounts: { owned: [], selected: 'azure_drone' } }, base, dict));
  assert.throws(() => fromProfile({ mounts: { owned: ['missing'] } }, base, dict));
});

test('Summoner: event skin takes no skill slot, worn skin round trips and must be ticked', () => {
  const skins = [
    { name: 'skeletian', star: 5 }, { name: 'night_wander', star: 4 }, { name: 'castle_count', star: 4 },
    { name: 'sanguin_dragoon', star: 1 },
  ];
  const state = fromProfile({ summonerSkins: skins, summonerWorn: 'sanguin_dragoon' }, base, dict);
  const profile = toProfile(state, dict);
  assert.deepEqual(profile.summonerSkins, skins);
  assert.equal(profile.summonerWorn, 'sanguin_dragoon');
  state.summonerSkins = state.summonerSkins.filter(({ name }) => name !== 'sanguin_dragoon');
  normalize(state, dict);
  assert.equal(toProfile(state, dict).summonerWorn, null);
  assert.throws(() => fromProfile({ summonerSkins: [...skins, { name: 'azure_valkyrie' }] }, base, dict));
  assert.throws(() => fromProfile({ summonerSkins: ['skeletian'], summonerWorn: 'azure_valkyrie' }, base, dict));
});

test('Joker support requires Loli summon skin in a slot and no regular Joker', () => {
  assert.equal(hasSummonedJoker([{ name: JOKER_SUMMON.hero }], true), true);
  assert.equal(hasSummonedJoker([{ name: JOKER_SUMMON.hero }], false), false);
  assert.equal(hasSummonedJoker([{ name: JOKER_SUMMON.summonedHero }], true), false);
});

test('battle applies owned mount skills independently of the single equipped mount', async () => {
  const { runInNewContext } = await import('node:vm');
  const player = { mounts: { 0: { code: 1, skillCode: 12345 }, _length: 1 }, mountCode: 1 };
  let profile = { mounts: { owned: ['azure_drone', 'ironclad_crab'], selected: null } };
  const window = {};
  runInNewContext(readFileSync(new URL('../web/battle/profile.js', import.meta.url), 'utf8'), {
    window,
    fetch: async (url) => ({ ok: true, json: async () => url.includes('active-profile') ? profile : dict }),
  });
  const rb = { listItems: (list) => Array.from({ length: list?._length || 0 }, (_, i) => list[i]) };
  const M = () => ({ get: () => ({}) });
  const start = { playerInfos: { 0: player, _length: 1 } };
  await window.SimBattle.applyProfile(start, rb, M, () => {});
  assert.equal(start.playerInfos[0].mountCode, 0);
  assert.equal(start.playerInfos[0].mounts._length, 2);
  assert.equal(start.playerInfos[0].mounts[0].skillCode, 12345);
  assert.equal(start.playerInfos[0].mounts[1].skillCode, dict.mounts.ironclad_crab.ranks[0].showSkill.code);
  profile.mounts.selected = 'ironclad_crab';
  await window.SimBattle.applyProfile(start, rb, M, () => {});
  assert.equal(start.playerInfos[0].mountCode, dict.mounts.ironclad_crab.code);
  profile.mounts.selected = 'missing';
  await assert.rejects(window.SimBattle.applyProfile(start, rb, M, () => {}), /must be owned/);
});

test('map: campaign stays as before; capital (U Do) boss + preset round trip', () => {
  assert.deepEqual(toProfile(fromProfile({ map: { mode: 'campaign', stage: 300 } }, base, dict), dict).map, { mode: 'campaign', stage: 300 });
  // Old profiles have no mode: campaign.
  assert.deepEqual(toProfile(fromProfile({ map: { stage: 12 } }, base, dict), dict).map, { mode: 'campaign', stage: 12 });
  const capital = { mode: 'capital', boss: 'nether_boggart', level: 11301 };
  assert.deepEqual(toProfile(fromProfile({ map: capital }, base, dict), dict).map, capital);
  // A level that is not a preset of that boss drops the preset, an unknown boss is an error.
  assert.equal(fromProfile({ map: { ...capital, level: 10101 } }, base, dict).map.level, null);
  assert.throws(() => fromProfile({ map: { ...capital, boss: 'missing' } }, base, dict));
  // Any day/room of a preset (index ignored) maps back to that preset; the capture's 51701 is Nether Boggart.
  assert.deepEqual(capitalPreset(dict, 51701), { boss: 'nether_boggart', level: 51701 });
  assert.deepEqual(capitalPreset(dict, 41302), { boss: 'nether_boggart', level: 11301 });
  // Every boss has presets, and each preset has 3 creep types.
  for (const boss of Object.values(dict.maps.capital.bosses)) {
    assert.ok(boss.presets.length > 0);
    for (const preset of boss.presets) assert.equal(preset.creeps.length, 3);
  }
});
