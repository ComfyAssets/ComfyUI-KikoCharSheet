import test from "node:test";
import assert from "node:assert/strict";
import { MAX_POSES, toggle, move, remove, toggleFlip } from "../../web/lib/selection.js";

test("MAX_POSES is 13", () => assert.equal(MAX_POSES, 13));

test("toggle adds and removes without mutating", () => {
  const sel = ["a", "b"];
  const added = toggle(sel, "c", 13);
  assert.deepEqual(added, { sel: ["a", "b", "c"], refused: false });
  assert.deepEqual(sel, ["a", "b"]);
  assert.deepEqual(toggle(sel, "a", 13), { sel: ["b"], refused: false });
});

test("toggle refuses a 14th item and leaves the input unchanged", () => {
  const sel = Array.from({ length: 13 }, (_, i) => `p${i}`);
  const copy = [...sel];
  const out = toggle(sel, "extra", MAX_POSES);
  assert.equal(out.refused, true);
  assert.deepEqual(out.sel, copy);
  assert.deepEqual(sel, copy);
});

test("toggle still removes when the selection is full", () => {
  const sel = Array.from({ length: 13 }, (_, i) => `p${i}`);
  const out = toggle(sel, "p3", 13);
  assert.equal(out.refused, false);
  assert.equal(out.sel.length, 12);
});

test("move reorders and preserves the other items", () => {
  const sel = ["a", "b", "c", "d"];
  assert.deepEqual(move(sel, 0, 2), ["b", "c", "a", "d"]);
  assert.deepEqual(move(sel, 3, 0), ["d", "a", "b", "c"]);
  assert.deepEqual(sel, ["a", "b", "c", "d"]);
  assert.deepEqual(move(sel, 9, 0), sel);
});

test("remove drops one id and keeps the rest", () => {
  const sel = ["a", "b", "c"];
  assert.deepEqual(remove(sel, "b"), ["a", "c"]);
  assert.deepEqual(sel, ["a", "b", "c"]);
  assert.deepEqual(remove(sel, "zz"), sel);
});

test("toggleFlip adds then removes an id", () => {
  const flips = ["a"];
  assert.deepEqual(toggleFlip(flips, "b"), ["a", "b"]);
  assert.deepEqual(toggleFlip(flips, "a"), []);
  assert.deepEqual(flips, ["a"]);
});
