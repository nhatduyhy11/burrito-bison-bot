// Convert captured lobby hero objects into battle input without changing the capture.
export function rosterHero(hero, rb) {
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

