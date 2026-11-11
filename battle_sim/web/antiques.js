// Ownership and stars from the pmain StartGameP capture on 2026-11-11.
const PMAIN_STARS = {
  3001: 6, 3002: 6, 3003: 5, 3004: 6, 3005: 6, 3006: 6, 3008: 6, 3010: 6,
  4011: 5, 4012: 6, 4013: 5, 4017: 6, 4018: 5, 4019: 5, 4020: 6,
  5022: 3, 5023: 3, 5024: 5, 5025: 6, 5026: 5, 5027: 6, 5028: 6, 5029: 4,
  5030: 4, 5031: 5, 5032: 3, 5033: 4, 5034: 5, 5035: 5, 5036: 4,
  6039: 5, 6040: 1, 6041: 1, 6045: 1,
};

export function defaultAntiques(catalog) {
  return Object.fromEntries(Object.entries(catalog).flatMap(([name, { code, maxStar }]) =>
    PMAIN_STARS[code] ? [[name, Math.min(PMAIN_STARS[code], maxStar)]] : []));
}

export function starterAntiques(catalog) {
  const colors = new Set(["blue", "purple", "orange"]);
  return Object.fromEntries(Object.entries(catalog).flatMap(([name, { color }]) =>
    colors.has(color) ? [[name, 1]] : []));
}

export function antiqueSelections(owned, catalog) {
  if (!owned || typeof owned !== "object" || Array.isArray(owned)) {
    throw new Error("Đồ Cổ phải là danh sách tên và số sao");
  }
  return Object.entries(owned).map(([name, star]) => {
    const item = Object.hasOwn(catalog, name) && catalog[name];
    if (!item) throw new Error(`Không có Đồ Cổ "${name}"`);
    const rank = Number.isSafeInteger(star) && item.ranks.find((entry) => entry.star === star);
    if (!rank) throw new Error(`Số sao không hợp lệ cho Đồ Cổ "${name}": ${star}`);
    return { name, star, code: rank.code };
  });
}

export function battleAntiques(owned, catalog, haloTable) {
  return antiqueSelections(owned, catalog).map(({ code, star }) => {
    const rank = haloTable.get(code);
    if (!rank || rank.star !== star) throw new Error(`Thiếu rank Đồ Cổ ${code} trong config trận`);
    return { code, level: rank.haloLevelLimit };
  });
}
