import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';
import { capitalPreset, emptyState, normalize, fromProfile, toProfile } from '../web/setup/profile-io.js';
import { hasSummonedJoker, JOKER_SUMMON } from '../web/hero-lineup.js';
import { applyProfile } from '../web/battle/profile.js';

const dict = JSON.parse(readFileSync(new URL('../web/dict/profile-dict.json', import.meta.url)));
const maps = JSON.parse(readFileSync(new URL('../web/dict/map-dict.json', import.meta.url)));
const antiqueDict = JSON.parse(readFileSync(new URL('../web/dict/antique-dict.json', import.meta.url)));
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

test('battle applies owned mount skills independently of the single equipped mount', async (t) => {
  const player = { mounts: { 0: { code: 1, skillCode: 12345 }, _length: 1 }, mountCode: 1 };
  let profile = { mounts: { owned: ['azure_drone', 'ironclad_crab'], selected: null } };
  const realFetch = globalThis.fetch;
  globalThis.fetch = async (url) => ({ ok: true, json: async () => url.includes('active-profile') ? profile : dict });
  t.after(() => { globalThis.fetch = realFetch; });
  const rb = { listItems: (list) => Array.from({ length: list?._length || 0 }, (_, i) => list[i]) };
  const M = () => ({ get: () => ({}) });
  const start = { playerInfos: { 0: player, _length: 1 } };
  await applyProfile(start, rb, M, () => {});
  assert.equal(start.playerInfos[0].mountCode, 0);
  assert.equal(start.playerInfos[0].mounts._length, 2);
  assert.equal(start.playerInfos[0].mounts[0].skillCode, 12345);
  assert.equal(start.playerInfos[0].mounts[1].skillCode, dict.mounts.ironclad_crab.ranks[0].showSkill.code);
  profile.mounts.selected = 'ironclad_crab';
  await applyProfile(start, rb, M, () => {});
  assert.equal(start.playerInfos[0].mountCode, dict.mounts.ironclad_crab.code);
  profile.mounts.selected = 'missing';
  await assert.rejects(applyProfile(start, rb, M, () => {}), /must be owned/);
});

test('map: campaign stays as before; capital (U Do) boss + preset round trip', () => {
  assert.deepEqual(toProfile(fromProfile({ map: { mode: 'campaign', stage: 300 } }, base, dict, { maps }), dict).map, { mode: 'campaign', stage: 300 });
  // Old profiles have no mode: campaign.
  assert.deepEqual(toProfile(fromProfile({ map: { stage: 12 } }, base, dict, { maps }), dict).map, { mode: 'campaign', stage: 12 });
  const capital = { mode: 'capital', boss: 'nether_boggart', level: 11301 };
  assert.deepEqual(toProfile(fromProfile({ map: capital }, base, dict, { maps }), dict).map, capital);
  // A level that is not a preset of that boss drops the preset, an unknown boss is an error.
  assert.equal(fromProfile({ map: { ...capital, level: 10101 } }, base, dict, { maps }).map.level, null);
  assert.throws(() => fromProfile({ map: { ...capital, boss: 'missing' } }, base, dict, { maps }));
  assert.throws(() => fromProfile({ map: capital }, base, dict)); // map-dict required for a map
  // Any day/room of a preset (index ignored) maps back to that preset; the capture's 51701 is Nether Boggart.
  assert.deepEqual(capitalPreset(maps, 51701), { boss: 'nether_boggart', level: 51701 });
  assert.deepEqual(capitalPreset(maps, 41302), { boss: 'nether_boggart', level: 11301 });
  // Every boss has presets, and each preset has 3 creep types.
  for (const boss of Object.values(maps.capital.bosses)) {
    assert.ok(boss.presets.length > 0);
    for (const preset of boss.presets) assert.equal(preset.creeps.length, 3);
  }
});

test('antiques come from antique-dict.json: defaults, round trip, unknown name', () => {
  const name = Object.keys(antiqueDict.antiques)[0];
  assert.deepEqual(emptyState(dict).antiques, {});
  assert.ok(Object.keys(emptyState(dict, antiqueDict).antiques).length >= 0);
  const state = fromProfile({ antiques: { [name]: 1 } }, base, dict, { antiqueDict });
  assert.deepEqual(toProfile(state, dict).antiques, { [name]: 1 });
  assert.throws(() => fromProfile({ antiques: { [name]: 1 } }, base, dict)); // antique-dict required
  assert.throws(() => fromProfile({ antiques: { missing: 1 } }, base, dict, { antiqueDict }));
});

test('Dị Năng: only red heroes have skill nodes; picker value round trips and is validated', async () => {
  for (const hero of Object.values(dict.heroes)) assert.equal(!!hero.avatarNodes, hero.color === 'red', hero.name);
  assert.equal(dict.heroes.lu_bu.avatarNodes.length, 5);
  const state = fromProfile({ heroes: [{ name: 'lu_bu', avatar: 2 }, 'redhood'] }, base, dict);
  assert.equal(state.heroes[0].custom, true);
  assert.equal(state.heroes[0].avatar, 2);
  assert.deepEqual(toProfile(state, dict).heroes[0], { name: 'lu_bu', avatar: 2, slots: [] });
  // "Tùy chỉnh" customizes everything: a red hero's Dị Năng starts at 0; not custom = as captured.
  const skinsOnly = fromProfile({ heroes: [{ name: 'lu_bu', slots: [] }] }, base, dict);
  assert.equal(toProfile(skinsOnly, dict).heroes[0].avatar, 0);
  skinsOnly.heroes[0].custom = false;
  normalize(skinsOnly, dict);
  assert.equal(skinsOnly.heroes[0].avatar, null);
  assert.equal(toProfile(skinsOnly, dict).heroes[0], 'lu_bu');
  assert.throws(() => fromProfile({ heroes: [{ name: 'lu_bu', avatar: 6 }] }, base, dict));
  assert.throws(() => fromProfile({ heroes: [{ name: 'lu_bu', avatar: 1.5 }] }, base, dict));
});

test('Dị Năng: battle rebuilds hero.skills from the node chain, whatever nodes the hero came with', async () => {
  const { applyAvatar } = await import('../web/battle/hero/avatar.js');
  const rb = { listItems: (o) => (Array.isArray(o) ? o : Object.keys(o).filter((k) => !k.startsWith('_')).map((k) => o[k])) };
  const nodes = dict.heroes.lu_bu.avatarNodes;
  const skill = (code, index) => ({ code, index, isShow: false });
  // pmain Lữ Bố: nodes 1-2 open (10130602000) plus relic and skin skills.
  const hero = { code: 50000013, skills: [skill(10130202000, 2), skill(10130302000, 3), skill(52060201400, 0), skill(10130602000, 1), skill(80041311000, 7)] };
  const codes = (n) => applyAvatar(hero, nodes, n, rb, () => {}).skills.map((s) => s.code);
  assert.deepEqual(codes(0), [10130202000, 10130302000, 52060201400, 10130101000, 80041311000]);
  assert.deepEqual(codes(1), [10130202000, 10130302000, 52060201400, 10130601000, 80041311000]);
  assert.deepEqual(codes(2), hero.skills.map((s) => s.code));
  // Node 5 replaces node 3's skill.
  assert.deepEqual(codes(5), [10130605000, 10130604000, 52060201400, 10130602000, 80041311000]);
  assert.throws(() => applyAvatar(hero, nodes, 6, rb, () => {}));
  // Alice: nodes add skills (replaces null); closing them removes the skills again.
  const alice = Object.values(dict.heroes).find((h) => h.code === 50000019).avatarNodes;
  const a = { code: 50000019, skills: [skill(10190201000, 2), skill(10190601000, 0)] };
  assert.deepEqual(applyAvatar(a, alice, 0, rb, () => {}).skills.map((s) => s.code), [10190201000]);
  assert.deepEqual(applyAvatar(a, alice, 3, rb, () => {}).skills.map((s) => s.code), [10190201000, 10190601000, 10190602000, 10190603000]);
});

test('Dị Năng: a replacing node whose skill the hero lacks is skipped alone, never added', async () => {
  const { applyAvatar } = await import('../web/battle/hero/avatar.js');
  const rb = { listItems: (o) => o };
  const skill = (code, index) => ({ code, index, isShow: false });
  const run = (hero, name) => {
    let log;
    const out = applyAvatar(hero, dict.heroes[name].avatarNodes, 5, rb, (_, data) => (log = data));
    return { codes: out.skills.map((s) => s.code), skipped: log.skipped };
  };
  // Lữ Bố below the breakthrough of 10130202000: node 3 skipped, node 5 (replaces node 3's skill) too.
  const lb = { code: 50000013, skills: [skill(10130101000, 1), skill(10130201000, 2), skill(10130302000, 3)] };
  assert.deepEqual(run(lb, 'lu_bu'), { codes: [10130602000, 10130201000, 10130604000], skipped: [3, 5] });
  // Archmage without 10040303000: node 2 skipped, node 4 (base skill) and node 5 (adds) still apply.
  const am = { code: 50000004, skills: [skill(10040101000, 1), skill(10040201000, 2), skill(10040301000, 3)] };
  assert.deepEqual(run(am, 'archmage'), { codes: [10040601000, 10040604000, 10040301000, 10040603000, 10040605000], skipped: [2] });
});
