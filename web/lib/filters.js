// Pure catalogue filtering (safe mode, dropdown filters, search).

const identity = (value) => value;

function matchesQuery(item, needle, translate) {
  const fields = [item.id, item.title, item.search];
  const translated = translate(item.title);
  if (typeof translated === "string") fields.push(translated);
  return fields.some((f) => typeof f === "string" && f.toLowerCase().includes(needle));
}

/**
 * Filter catalogue items.
 * `filters` is {field: value}; an empty or missing value means "all".
 * `query` matches id, title, `search` and translate(title), case-insensitively.
 */
export function filterItems(items, { query = "", filters = {}, safeMode = false, translate = identity } = {}) {
  const needle = String(query || "").trim().toLowerCase();
  const active = Object.entries(filters || {}).filter(([, v]) => v !== "" && v != null);
  return items.filter((item) => {
    if (safeMode && item.nsfw) return false;
    if (active.some(([field, value]) => item[field] !== value)) return false;
    return !needle || matchesQuery(item, needle, translate);
  });
}

/** Sorted unique non-empty values of `field`. */
export function filterOptions(items, field) {
  const values = new Set();
  for (const item of items) {
    const v = item[field];
    if (v !== "" && v != null) values.add(v);
  }
  return [...values].sort((a, b) => (a < b ? -1 : a > b ? 1 : 0));
}
