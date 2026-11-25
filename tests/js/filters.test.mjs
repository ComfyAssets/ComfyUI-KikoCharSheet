import test from "node:test";
import assert from "node:assert/strict";
import { filterItems, filterOptions } from "../../web/lib/filters.js";

const items = [
  { id: "SPR-1", title: "坐姿", nsfw: false, 体系: "全身单人", search: "坐 椅子" },
  { id: "SPR-2", title: "站姿", nsfw: true, 体系: "双人缠绵", search: "站" },
  { id: "C-3", title: "水手服", nsfw: false, 体系: "全身单人", search: "校服" },
];
const en = { 坐姿: "Sitting", 水手服: "Sailor uniform" };
const translate = (v) => en[v] || v;

test("safe mode hides nsfw items", () => {
  assert.deepEqual(filterItems(items, { safeMode: true }).map((i) => i.id), ["SPR-1", "C-3"]);
  assert.equal(filterItems(items, { safeMode: false }).length, 3);
});

test("query matches id, title, search field case-insensitively", () => {
  const ids = (q) => filterItems(items, { query: q }).map((i) => i.id);
  assert.deepEqual(ids("spr-2"), ["SPR-2"]);
  assert.deepEqual(ids("水手"), ["C-3"]);
  assert.deepEqual(ids("椅子"), ["SPR-1"]);
});

test("query matches the English translation of the title", () => {
  const out = filterItems(items, { query: "sailor", translate }).map((i) => i.id);
  assert.deepEqual(out, ["C-3"]);
  assert.deepEqual(filterItems(items, { query: "SITTING", translate }).map((i) => i.id), ["SPR-1"]);
  assert.deepEqual(filterItems(items, { query: "sailor" }), []);
});

test("filters: empty or missing value means all", () => {
  assert.equal(filterItems(items, { filters: { 体系: "" } }).length, 3);
  assert.equal(filterItems(items, { filters: {} }).length, 3);
  assert.deepEqual(filterItems(items, { filters: { 体系: "双人缠绵" } }).map((i) => i.id), ["SPR-2"]);
});

test("combined filters, query and safe mode", () => {
  const out = filterItems(items, { filters: { 体系: "全身单人" }, query: "sit", translate, safeMode: true });
  assert.deepEqual(out.map((i) => i.id), ["SPR-1"]);
});

test("filterOptions returns sorted unique non-empty values", () => {
  const list = [{ a: "b" }, { a: "a" }, { a: "b" }, { a: "" }, {}];
  assert.deepEqual(filterOptions(list, "a"), ["a", "b"]);
});

test("showOnline: false hides items loaded from their origin site", () => {
  const list = [{ id: "SPR-1" }, { id: "charadb-1", online: true }, { id: "shisei-1", online: false }];
  assert.deepEqual(filterItems(list, { showOnline: false }).map((i) => i.id), ["SPR-1", "shisei-1"]);
  assert.equal(filterItems(list, { showOnline: true }).length, 3);
  assert.equal(filterItems(list).length, 3);
});
