import test from "node:test";
import assert from "node:assert/strict";
import { firstVisibleId, restoredScrollTop } from "../../web/lib/scroll.js";

const rows = [
  { id: "a", top: 300, bottom: 500 },
  { id: "b", top: 300, bottom: 500 },
  { id: "c", top: 510, bottom: 710 },
  { id: "d", top: 720, bottom: 920 },
];

test("firstVisibleId returns the first card whose bottom is below the scroll top", () => {
  assert.equal(firstVisibleId(rows, 300), "a");
  assert.equal(firstVisibleId(rows, 499), "a");
  assert.equal(firstVisibleId(rows, 500), "c");
  assert.equal(firstVisibleId(rows, 715), "d");
});

test("firstVisibleId is null above the grid, past the end, or with no cards", () => {
  assert.equal(firstVisibleId(rows, 120), null); // the uploads section is at the top
  assert.equal(firstVisibleId(rows, 5000), null);
  assert.equal(firstVisibleId([], 0), null);
});

test("restoredScrollTop keeps scrollTop when the column count is unchanged", () => {
  assert.equal(restoredScrollTop({ top: 640, columns: 5, anchorId: "c" }, { columns: 5, anchorTop: 900 }), 640);
});

test("restoredScrollTop puts the anchor card at the top when columns change", () => {
  assert.equal(restoredScrollTop({ top: 640, columns: 5, anchorId: "c" }, { columns: 9, anchorTop: 410 }), 410);
});

test("restoredScrollTop falls back to scrollTop without an anchor", () => {
  assert.equal(restoredScrollTop({ top: 80, columns: 5, anchorId: null }, { columns: 9, anchorTop: null }), 80);
  assert.equal(restoredScrollTop({ top: 80, columns: 5, anchorId: "x" }, { columns: 9, anchorTop: null }), 80);
});
