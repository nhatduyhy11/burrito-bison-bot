// Đêm Đỏ (battleType 47) hero lineup: 3 Master heroes (profile.heroes, the team leader = the player)
// + 3 Guest heroes (profile.guestHeroes). Each hero fights with its owner's attr, so every slot is
// built from its own account: the captured lineup hero of that account, else its roster entry
// (lobby refreshMemberInfosR, capture.team), else stats borrowed from that roster.
// See docs/planning/blood_night_setup.md.
import { hasSummonedJoker, JOKER_SUMMON } from "../../hero-lineup.js";
import { heroBuilder, jokerPick } from "./selection.js";

const PER_SIDE = 3;
const SIDES = ["master", "guest"];

// A roster hero as the battle gets it: attr[6] 100 -> 0 and attr[10162] = 0 added (compared on
// capture 6afeadd7); `_TempSort` the log cut to "<deep>" goes back to []. The log also cut the
// Thần Khí entry rows, so those are dropped (code kept; its stats are in attr already).
function rosterHero(hero, rb) {
  const clean = JSON.parse(JSON.stringify(hero), (key, value) => (key === "_TempSort" && value === "<deep>" ? [] : value));
  const attrs = new Map(rb.listItems(clean.attr._keyList).map((key, i) => [Number(key), clean.attr._valueList[String(i)]]));
  attrs.set(6, 0);
  if (!attrs.has(10162)) attrs.set(10162, 0);
  clean.attr = { _keyList: [...attrs.keys()], _valueList: [...attrs.values()] };
  const cut = (list) => rb.listItems(list).some((entry) => typeof entry !== "object");
  if (clean.artifact && (cut(clean.artifact.entryInfos) || cut(clean.artifact.battleEntryInfos))) {
    clean.artifact = { ...clean.artifact, entryInfos: { _length: 0 }, battleEntryInfos: { _length: 0 } };
  }
  return clean;
}

function picks(profile, key, catalog) {
  const list = profile[key];
  if (!Array.isArray(list) || list.length !== PER_SIDE) throw new Error(`Đêm Đỏ: profile ${key} needs exactly ${PER_SIDE} heroes`);
  return list.map((entry) => {
    const selection = typeof entry === "string" ? { name: entry } : entry;
    const option = catalog.heroes[selection?.name];
    if (!option) throw new Error(`Unknown heroes option: ${selection?.name}`);
    return { option, selection };
  });
}

export function applyBloodTeam({ profile, player, catalog, relicLines, asList, rb, M, step, start, team }) {
  if (!team) throw new Error("Đêm Đỏ needs a capture with the team roster (refreshMemberInfosR)");
  const leaderId = Number(start.leaderId);
  const member = { master: team.find((m) => m.playerId === leaderId), guest: team.find((m) => m.playerId !== leaderId) };
  if (!member.master || !member.guest) throw new Error("Đêm Đỏ capture roster has no leader / guest");
  const lineup = rb.listItems(player.heros);
  const source = {};
  const ownerOf = new Map();
  for (const side of SIDES) {
    const roster = rb.listItems(member[side].heros);
    const uuids = new Set(roster.map((h) => h.uuid));
    const inLineup = lineup.filter((h) => uuids.has(h.uuid));
    inLineup.forEach((h) => ownerOf.set(h.uuid, side));
    const fixed = roster.map((h) => rosterHero(h, rb));
    source[side] = { owned: [...inLineup, ...fixed.filter((h) => !inLineup.some((x) => x.code === h.code))], donors: fixed };
  }

  const selected = { master: picks(profile, "heroes", catalog), guest: picks(profile, "guestHeroes", catalog) };
  const all = [...selected.master, ...selected.guest];
  if (new Set(all.map(({ option }) => option.code)).size !== all.length) throw new Error("Đêm Đỏ: the 6 heroes must differ");
  const { build, state } = heroBuilder({ relicLines, rb, M, step });
  const built = Object.fromEntries(SIDES.map((side) => [side, selected[side].map((pick) => build(pick, source[side]))]));

  // Slot order follows the captured owners (capture: guest, master, guest, ...); a lineup that does
  // not split 3 + 3 falls back to that alternation.
  let order = lineup.map((h) => ownerOf.get(h.uuid));
  if (SIDES.some((side) => order.filter((s) => s === side).length !== PER_SIDE)) order = ["guest", "master", "guest", "master", "guest", "master"];
  const next = { master: 0, guest: 0 };
  player.heros = asList(order.map((side) => built[side][next[side]++]));
  step("blood team", Object.fromEntries(SIDES.map((side) => [side, { player: member[side].playerId, heroes: built[side].map((h) => h.code) }])));

  const loliSide = SIDES.find((side) => selected[side].some(({ selection }) => selection.name === JOKER_SUMMON.hero));
  if (loliSide && hasSummonedJoker(all.map(({ selection }) => selection), state.jokerSkillSlotted)) {
    // Joker fights with the stats of Loli's account.
    player.support = build(jokerPick(profile, catalog), source[loliSide]);
    step("blood joker", { side: loliSide });
  }
}
