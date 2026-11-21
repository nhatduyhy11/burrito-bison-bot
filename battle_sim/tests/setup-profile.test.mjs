import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';
import { emptyState, normalize, fromProfile, toProfile } from '../web/setup/profile-io.js';
import { hasSummonedJoker, JOKER_SUMMON } from '../web/hero-lineup.js';
import { applyProfile } from '../web/battle/profile.js';

// One lookup table for both sides: hero-dict (heroes) + support-dict (the non-hero groups).
const dict = {
  ...JSON.parse(readFileSync(new URL('../web/dict/hero-dict.json', import.meta.url))),
  ...JSON.parse(readFileSync(new URL('../web/dict/support-dict.json', import.meta.url))),
};
const maps = JSON.parse(readFileSync(new URL('../web/dict/map-dict.json', import.meta.url)));
const bossDict = JSON.parse(readFileSync(new URL('../web/dict/boss-dict.json', import.meta.url)));
const creepsDict = JSON.parse(readFileSync(new URL('../web/dict/creeps-dict.json', import.meta.url)));
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

test('Summoner gear: partial toggle map round trips and drives the bed build skills', async (t) => {
  assert.equal(emptyState(dict).summonerGear, null);
  const gear = { cash_boost: true, rage_gain_upon_defeat: false };
  assert.deepEqual(toProfile(fromProfile({ summonerGear: gear }, base, dict), dict).summonerGear, gear);
  assert.throws(() => fromProfile({ summonerGear: { missing: true } }, base, dict));

  const list = (items) => ({ ...Object.fromEntries(items.map((item, i) => [i, item])), _length: items.length });
  const start = () => ({
    playerInfos: {
      0: {
        builds: list([{
          type: dict.buildings.bed.buildType,
          skills: list([
            { code: 123, index: 1, level: 1, isShow: false }, // a server-added non-gear skill
            { code: dict.summonerGear.rage_gain_upon_defeat.code, index: 1, level: 1, isShow: false }, // captured gear skill
          ]),
        }]),
      },
      _length: 1,
    },
  });
  const skills = (s) => Array.from({ length: s.playerInfos[0].builds[0].skills._length },
    (_, i) => s.playerInfos[0].builds[0].skills[i].code);
  const realFetch = globalThis.fetch;
  let profile, s;
  globalThis.fetch = async (url) => ({ ok: true, json: async () => url.includes('active-profile') ? profile : dict });
  t.after(() => { globalThis.fetch = realFetch; });
  const rb = { listItems: (list_) => Array.from({ length: list_?._length || 0 }, (_, i) => list_[i]) };
  const M = () => ({ get: () => ({}) });
  const run = async (p) => { profile = p; s = start(); await applyProfile(s, rb, M, () => {}); };
  // A key absent from the map keeps the captured gear skill; true/false add/remove their code.
  await run({ summonerGear: { cash_boost: true } });
  assert.deepEqual(skills(s), [dict.summonerGear.cash_boost.code, 123, dict.summonerGear.rage_gain_upon_defeat.code]);
  await run({ summonerGear: { cash_boost: true, rage_gain_upon_defeat: false } });
  assert.deepEqual(skills(s), [dict.summonerGear.cash_boost.code, 123]);
  await run({ summonerGear: { cash_boost: false, rage_gain_upon_defeat: true } });
  assert.deepEqual(skills(s), [dict.summonerGear.rage_gain_upon_defeat.code, 123]);
  await run({ summonerGear: null });
  assert.deepEqual(skills(s), [123, dict.summonerGear.rage_gain_upon_defeat.code]); // untouched
  await assert.rejects(run({ summonerGear: { missing_name: true } }), /Unknown summonerGear/);
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
  const catalogs = { maps, bossDict };
  assert.deepEqual(toProfile(fromProfile({ map: { mode: 'campaign', stage: 300 } }, base, dict, catalogs), dict).map, { mode: 'campaign', stage: 300 });
  // Old profiles have no mode: campaign.
  assert.deepEqual(toProfile(fromProfile({ map: { stage: 12 } }, base, dict, catalogs), dict).map, { mode: 'campaign', stage: 12 });
  const capital = { mode: 'capital', boss: 'nether_boggart', level: 11301 };
  assert.deepEqual(toProfile(fromProfile({ map: capital }, base, dict, catalogs), dict).map, capital);
  // A level that is not a preset of that boss drops the preset, an unknown boss is an error.
  assert.equal(fromProfile({ map: { ...capital, level: 10101 } }, base, dict, catalogs).map.level, null);
  assert.throws(() => fromProfile({ map: { ...capital, boss: 'missing' } }, base, dict, catalogs));
  assert.throws(() => fromProfile({ map: capital }, base, dict)); // map-dict required for a map
  assert.throws(() => fromProfile({ map: capital }, base, dict, { maps })); // boss-dict required for capital
  // map-dict only lists the boss ids, boss-dict has the data; every preset has 3 creeps known to creeps-dict.
  assert.deepEqual(maps.capital.bosses, Object.keys(bossDict.bosses));
  for (const boss of Object.values(bossDict.bosses)) {
    assert.ok(boss.presets.length > 0);
    for (const preset of boss.presets) {
      assert.equal(preset.creeps.length, 3);
      for (const id of preset.creeps) assert.ok(creepsDict.creeps[id], id);
    }
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

test('Dị Năng: a node below its breakthrough (skillUnlock) is skipped, adding nodes included', async () => {
  const { applyAvatar } = await import('../web/battle/hero/avatar.js');
  const rb = { listItems: (o) => o };
  const skill = (code, index) => ({ code, index, isShow: false });
  const alice = Object.values(dict.heroes).find((h) => h.code === 50000019).avatarNodes;
  assert.equal(alice[1].minBreakThrough, 6);
  assert.equal(dict.heroes.lu_bu.avatarNodes[2].minBreakThrough, 6);
  assert.equal(dict.heroes.lu_bu.avatarNodes[3].minBreakThrough, 9);
  const run = (breakThrough) => {
    let log;
    const hero = { code: 50000019, breakThrough, skills: [skill(10190201000, 2), skill(10190301000, 3)] };
    const out = applyAvatar(hero, alice, 5, rb, (_, data) => (log = data));
    return { codes: out.skills.map((s) => s.code), skipped: log.skipped };
  };
  // Node 2 (adds Sát Thương Choáng) needs breakthrough 6; the other adding nodes are not gated.
  assert.deepEqual(run(5), { codes: [10190201000, 10190301000, 10190601000, 10190603000, 10190604000, 10190605000], skipped: [2] });
  assert.deepEqual(run(6).skipped, []);
  assert.ok(run(6).codes.includes(10190602000));
});

test('Thần Khí: battle builds hero.artifact from quality/stage/entries; null removes it', async () => {
  const A = await import('../web/artifacts.js');
  const { applyArtifact } = await import('../web/battle/hero/artifact.js');
  const ad = JSON.parse(readFileSync(new URL('../web/dict/artifact-dict.json', import.meta.url)));
  // Fake config rebuilt from artifact-dict.json rules (same formulas gen_profile_dict.js checks).
  const items = {}, entries = {};
  for (const [heroCode, { pool }] of Object.entries(ad.heroes)) {
    for (const [q, max] of Object.entries(A.MAX_STAGE)) {
      for (let s = 1; s <= max; s++) items[A.artifactCode(pool, +q, s)] = { hero: +heroCode };
    }
    for (const [family, { skillCode, ranges }] of Object.entries(ad.buffs)) {
      for (const [q, [minValue, maxValue]] of Object.entries(ranges)) {
        entries[A.entryCode(pool, +family, +q)] = { entryType: 2, skillCode, minValue, maxValue };
      }
    }
    for (const family of [1, 2, 3]) {
      entries[A.entryCode(pool, family, 8)] = { entryType: 2, skillCode: A.rareSkill(+heroCode, family), minValue: 0, maxValue: 0 };
    }
  }
  entries[80001905] = { entryType: 1, minValue: 0, maxValue: 9999 };
  const tables = { ArtifactLO: items, ArtifactEntryLO: entries };
  const Mx = (name) => (tables[name] ? { store: tables[name], get: (k) => tables[name][k] } : { get: () => ({}) });
  const lb = { code: 50000013, artifact: { code: 10806003, uuid: 'cap', battleEntryInfos: { 0: { value: 704, code: 80003005 }, _length: 1 } } };
  const run = (sel) => applyArtifact(lb, sel, Mx, () => {});

  // Rebuilding the captured item gives the same snapshot (uuid kept).
  assert.deepEqual(run({ quality: 6, stage: 3, entries: [{ code: 80003005, value: 704 }] }).artifact, lb.artifact);
  // Rainbow value defaults to 0; no entries -> no battleEntryInfos.
  assert.deepEqual(run({ quality: 4, stage: 1, entries: [] }).artifact, { code: 10804001, uuid: 'cap' });
  assert.equal(run({ quality: 7, stage: 5, entries: [{ code: 80000208 }] }).artifact.battleEntryInfos[0].value, 0);
  assert.equal('artifact' in run(null), false);
  // A hero without an artifact gets a generated uuid.
  assert.equal(applyArtifact({ code: 50000013 }, { quality: 6, stage: 1 }, Mx, () => {}).artifact.uuid.length, 24);

  for (const bad of [
    { quality: 8, stage: 1 }, { quality: 4, stage: 4 }, { quality: 6, stage: 0 },
    { quality: 4, stage: 1, entries: [{ code: 80003005, value: 200 }] }, // 0 slots at purple stage 1
    { quality: 6, stage: 3, entries: [{ code: 80003005, value: 801 }] }, // out of range
    { quality: 6, stage: 3, entries: [{ code: 10003005, value: 704 }] }, // other hero's pool
    { quality: 6, stage: 3, entries: [{ code: 80001905, value: 586 }] }, // stat line (entryType 1)
    { quality: 6, stage: 3, entries: [{ code: 80000208, value: 1 }] }, // rainbow must be 0
  ]) assert.throws(() => run(bad), undefined, JSON.stringify(bad));
  assert.throws(() => applyArtifact({ code: 50000099 }, { quality: 6, stage: 1 }, Mx, () => {}));
});

test('Thần Khí: setup import/export passes artifact through unchanged', () => {
  const artifact = { quality: 6, stage: 3, entries: [{ code: 80003005, value: 704 }] };
  const state = fromProfile({ heroes: [{ name: 'lu_bu', artifact }, { name: 'hanuman', artifact: null }] }, base, dict);
  const out = toProfile(state, dict).heroes;
  assert.deepEqual(out[0], { name: 'lu_bu', artifact });
  assert.deepEqual(out[1], { name: 'hanuman', artifact: null });
});

test('Thần Khí: slots follow quality/stage; empty slots are left out of the profile', () => {
  const artifact = { quality: 7, stage: 5, entries: [{ code: 80003007, value: 2500 }, { code: 80000208, value: 0 }] };
  const state = fromProfile({ heroes: [{ name: 'lu_bu', artifact }] }, base, dict);
  normalize(state, dict);
  assert.equal(state.heroes[0].artifact.slots.length, 7);
  state.heroes[0].artifact.slots[0] = null;
  assert.deepEqual(toProfile(state, dict).heroes[0].artifact.entries, [{ code: 80000208, value: 0 }]);
  // Gold stage 5 -> red keeps stage 4 at most; purple stage 1 has no slot left.
  state.heroes[0].artifact.quality = 6;
  normalize(state, dict);
  assert.deepEqual([state.heroes[0].artifact.stage, state.heroes[0].artifact.slots.length], [4, 5]);
  Object.assign(state.heroes[0].artifact, { quality: 4, stage: 1 });
  normalize(state, dict);
  assert.deepEqual(toProfile(state, dict).heroes[0].artifact, { quality: 4, stage: 1, entries: [] });
});

test('campaign stage map: full stage range, boss + minions all resolvable in the creeps dict', () => {
  const campaignDict = JSON.parse(readFileSync(new URL('../web/dict/campaign-dict.json', import.meta.url)));
  const stages = campaignDict.stages;
  const codes = Object.keys(stages).map(Number).sort((a, b) => a - b);
  assert.deepEqual([codes[0], codes[codes.length - 1], codes.length], [maps.campaign.minStage, maps.campaign.maxStage, maps.campaign.stages]);
  for (const [stage, entry] of Object.entries(stages)) {
    if (entry.boss) assert.ok(creepsDict.campaign[entry.boss], `stage ${stage} boss ${entry.boss} missing from creeps dict`);
    for (const code of entry.minions) assert.ok(creepsDict.campaign[code], `stage ${stage} minion ${code} missing from creeps dict`);
    assert.ok(!entry.minions.includes(entry.boss), `stage ${stage} lists its own boss as a minion`);
  }
});

test('Trap / Pet / Spell: reserved slots stay null in state, compact in the profile', () => {
  const state = fromProfile(
    { pets: [{ name: 'colossal_ape', star: 2 }, 'alien_critter'], spells: ['sword_radiance'], traps: ['demon_spike'] },
    base, dict,
  );
  assert.deepEqual([state.traps.length, state.pets.length, state.spells.length], [3, 3, 2]);
  assert.deepEqual([state.traps[0].name, state.pets[0].star, state.pets[1].level], ['demon_spike', 2, 1]);
  assert.deepEqual([state.traps[1], state.pets[2], state.spells[1]], [null, null, null]);
  // The emit drops empty slots: the engine reads every entry head-on, so it must not see nulls.
  const profile = toProfile(state, dict);
  assert.deepEqual(profile.traps, [{ name: 'demon_spike', level: 1, star: 1 }]);
  assert.deepEqual(profile.pets, [
    { name: 'colossal_ape', level: 1, star: 2 },
    { name: 'alien_critter', level: 1, star: 1 },
  ]);
  assert.deepEqual(profile.spells, [{ name: 'sword_radiance', star: 1 }]);
  // Filling and clearing slots: state normalize keeps the null placeholders, emit compacts again.
  state.traps[1] = { name: 'molten_furnace', level: 2, star: 3 };
  state.pets[2] = { name: 'dreamweaver_spider', level: 3, star: 4 };
  state.spells[1] = { name: 'hellish_flame', star: 2 };
  state.traps[0] = null;
  state.pets[0] = null;
  normalize(state, dict);
  const next = toProfile(state, dict);
  assert.deepEqual(next.traps, [{ name: 'molten_furnace', level: 2, star: 3 }]);
  assert.deepEqual(next.pets, [
    { name: 'alien_critter', level: 1, star: 1 },
    { name: 'dreamweaver_spider', level: 3, star: 4 },
  ]);
  assert.deepEqual(next.spells, [
    { name: 'sword_radiance', star: 1 },
    { name: 'hellish_flame', star: 2 },
  ]);
  // Override on with every slot cleared still replaces the capture list (with nothing).
  state.pets = state.pets.map(() => null);
  normalize(state, dict);
  assert.deepEqual(toProfile(state, dict).pets, []);
});

test('Dị Vật: battle swaps suit/gold skills on index 0; gold follows min(gold, suit star); null clears', async () => {
  const { applyBeautyBag } = await import('../web/battle/hero/beauty-bag.js');
  const { types } = JSON.parse(readFileSync(new URL('../web/dict/beautybag-dict.json', import.meta.url)));
  const rb = { listItems: (list) => list };
  const M = () => ({ get: () => ({}) });
  // Captured Hanuman: Tê Liệt suit N2 + gold N1 (events-pmain-20261119), plus an unrelated skill.
  const hero = { code: 1, skills: [{ code: 111, index: 0 }, { code: 60000500200, index: 0 }, { code: 60000510100, index: 0 }, { code: 222, index: 1 }] };
  const codes = (sel) => applyBeautyBag(hero, sel, types, rb, M, () => {}).skills.map((s) => s.code);
  assert.deepEqual(codes({ type: 'magic', star: 10, gold: 10 }), [111, 60000200300, 60000210300, 222]);
  assert.deepEqual(codes({ type: 'magic', star: 4, gold: 10 }), [111, 60000200100, 60000210100, 222]);
  assert.deepEqual(codes({ type: 'paralyze', star: 5, gold: 0 }), [111, 60000500200, 222]);
  assert.deepEqual(codes(null), [111, 222]);
  assert.throws(() => codes({ type: 'magic', star: 16 }));
  assert.throws(() => codes({ type: 'nope', star: 1 }));
});

test('Dị Vật: setup import/export keeps capture (omitted), none (null) and a pick', () => {
  const { types } = JSON.parse(readFileSync(new URL('../web/dict/beautybag-dict.json', import.meta.url)));
  const beautyBag = { type: 'paralyze', star: 7, gold: 3 };
  const state = fromProfile({ heroes: [{ name: 'hanuman', beautyBag }, { name: 'lu_bu', beautyBag: null }, 'joker'] }, base, dict, { beautyBagTypes: types });
  const out = toProfile(state, dict).heroes;
  assert.deepEqual(out[0], { name: 'hanuman', beautyBag });
  assert.deepEqual(out[1], { name: 'lu_bu', beautyBag: null });
  assert.equal(out[2], 'joker');
});

test('naval: boss/preset round trip, rejecting another boss or unknown level', () => {
  const navalDict = JSON.parse(readFileSync(new URL('../web/dict/naval-boss-dict.json', import.meta.url)));
  const catalogs = { maps, navalDict };
  for (const [boss, entry] of Object.entries(navalDict.bosses)) {
    for (const preset of entry.presets) {
      const map = { mode: 'naval', boss, level: preset.level };
      assert.deepEqual(toProfile(fromProfile({ map }, base, dict, catalogs), dict).map, map);
    }
  }
  const boss = Object.keys(navalDict.bosses)[0];
  const profile = { map: { mode: 'naval', boss, level: 2040401 } };
  assert.equal(fromProfile(profile, base, dict, catalogs).map.level, null);
  assert.throws(() => fromProfile({ map: { mode: 'naval', boss: 'missing' } }, base, dict, catalogs));
  assert.throws(() => fromProfile(profile, base, dict, { maps }), /naval-boss-dict/);
});

test('naval: map override validates game config and removes old encounter HP and teammates', async (t) => {
  const { applyMapProfile } = await import('../web/battle/map-profile.js');
  const navalDict = JSON.parse(readFileSync(new URL('../web/dict/naval-boss-dict.json', import.meta.url)));
  const boss = Object.keys(navalDict.bosses).find((key) => navalDict.bosses[key].code === 70070401);
  const realFetch = globalThis.fetch;
  globalThis.fetch = async () => ({ ok: true, json: async () => navalDict });
  t.after(() => { globalThis.fetch = realFetch; });
  let code = 70070401;
  const M = (name) => ({ get: () => name === 'GuildNavalMonthwarLO' ? { showCreep: JSON.stringify([code, 70081501]), battleGroundCode: 62061 } : {} });
  const rb = { listItems: (list) => Array.from({ length: list._length }, (_, i) => list[i]) };
  const start = { battleType: 3, level: 1, curLife: { _length: 1 }, playerInfos: { 0: { playerId: 1 }, 1: { playerId: 2 }, _length: 2 } };
  const map = { mode: 'naval', boss, level: 2040401 };
  await applyMapProfile(start, map, rb, M, () => {});
  assert.equal(start.battleType, 42);
  assert.equal(start.level, 2040401);
  assert.equal(start.playerInfos._length, 1);
  assert.equal(start.curLife, undefined);
  code = 70070101;
  await assert.rejects(applyMapProfile(start, map, rb, M, () => {}), /does not match/);
  await assert.rejects(applyMapProfile(start, { ...map, level: 999 }, rb, M, () => {}), /not a preset/);
});

test('naval capture prefill finds the captured boss/preset, normalizing its bed index', async (t) => {
  const { prefill } = await import('../web/setup/capture.js');
  const navalDict = JSON.parse(readFileSync(new URL('../web/dict/naval-boss-dict.json', import.meta.url)));
  const realFetch = globalThis.fetch;
  globalThis.fetch = async () => ({ ok: true, json: async () => ({ start: { battleType: 42, level: 2040403 } }) });
  t.after(() => { globalThis.fetch = realFetch; });
  const map = await prefill(dict, maps, 'vn', 'naval-prefill-check', 'map', navalDict);
  assert.equal(map.mode, 'naval');
  assert.equal(map.level, 2040401);
  assert.equal(navalDict.bosses[map.boss].code, 70070401);
});
