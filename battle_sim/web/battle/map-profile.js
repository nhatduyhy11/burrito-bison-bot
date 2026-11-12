// Local playtest profile, map part (?play&profile): profile.map -> StartGameP battleType / level,
// checked against /__sim/dict/map-dict.json (scripts/gen_profile_dict.js) and the game config.
//   campaign: { stage }
//   capital (U Đô, GuildNavalWar): { boss, level } of a preset in map-dict capital. The game plays it
//   solo (no robot teammates) and puts the 5 heroes on the field itself
//   (GuildPVPBattleRoom.createInitHeroBuild). See docs/planning/capital.md.
const CAMPAIGN_BATTLE_TYPE = 3; // EBattleTypeHangUpSystem

export async function applyMapProfile(start, map, rb, M, step) {
  const response = await fetch("/__sim/dict/map-dict.json");
  if (!response.ok) throw new Error(`Could not load map-dict: HTTP ${response.status}`);
  const maps = await response.json();
  if (map.mode === "campaign") return applyCampaign(start, map, M);
  if (map.mode === "capital") return applyCapital(start, map, maps.capital, rb, M, step);
  throw new Error(`Unsupported map mode: ${map.mode}`);
}

function applyCampaign(start, { stage }, M) {
  const level = Number.isSafeInteger(stage) && stage > 0 && M("AdventuretdLevelLO").get(stage * 10);
  if (!level || !M("BattleGroundLO").get(level.battleGroundCode)) {
    throw new Error(`Unknown campaign stage: ${stage}`);
  }
  // Campaign StartGameP carries the robot teammates; a capital capture has none to borrow.
  if (start.battleType !== CAMPAIGN_BATTLE_TYPE) {
    throw new Error(`Campaign needs a campaign capture as base battle (this one is battleType ${start.battleType})`);
  }
  start.level = stage;
}

function applyCapital(start, map, capital, rb, M, step) {
  const boss = capital.bosses[map.boss];
  if (!boss) throw new Error(`Unknown capital boss: ${map.boss}`);
  if (!boss.presets.some((preset) => preset.level === map.level)) {
    throw new Error(`Capital level ${map.level} is not a preset of ${map.boss}`);
  }
  const row = M("GuildNavalWarLO").get(map.level - (map.level % 100));
  if (!row || JSON.parse(row.showCreep)[0] !== boss.code || !M("BattleGroundLO").get(row.battleGroundCode)) {
    throw new Error(`Capital level ${map.level} does not match the game config`);
  }
  start.battleType = capital.battleType;
  start.level = map.level;
  start.playerInfos = { 0: rb.listItems(start.playerInfos)[0], _length: 1 };
  step("capital map", { boss: boss.name, level: map.level, creeps: JSON.parse(row.showCreep).slice(1) });
}
