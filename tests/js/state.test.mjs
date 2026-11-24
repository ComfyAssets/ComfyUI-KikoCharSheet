import test from "node:test";
import assert from "node:assert/strict";
import {
  COSTUME_VIEWS,
  defaultState,
  parseState,
  serializeState,
  togglePose,
  removePose,
  flipPose,
  movePose,
  costumeViewFor,
  selectableViews,
} from "../../web/lib/state.js";

test("defaultState per library", () => {
  assert.deepEqual(defaultState("portrait"), { id: "" });
  assert.deepEqual(defaultState("costume"), { id: "", view: "front" });
  assert.deepEqual(defaultState("pose"), { ids: [], flip: [], use_depth: false });
  assert.deepEqual(COSTUME_VIEWS, ["front", "back", "side"]);
});

test("parseState falls back to defaults on empty or broken JSON", () => {
  assert.deepEqual(parseState("portrait", ""), { id: "" });
  assert.deepEqual(parseState("portrait", "{not json"), { id: "" });
  assert.deepEqual(parseState("pose", "[1,2]"), { ids: [], flip: [], use_depth: false });
  assert.deepEqual(parseState("costume", undefined), { id: "", view: "front" });
});

test("parseState keeps valid fields and drops bad ones", () => {
  assert.deepEqual(parseState("portrait", '{"id":"f71f980dde3","x":1}'), { id: "f71f980dde3" });
  assert.deepEqual(parseState("portrait", '{"id":5}'), { id: "" });
  assert.deepEqual(parseState("costume", '{"id":"SPR-1","view":"back"}'), { id: "SPR-1", view: "back" });
  assert.deepEqual(parseState("costume", '{"id":"SPR-1","view":"top"}'), { id: "SPR-1", view: "front" });
  assert.deepEqual(
    parseState("pose", '{"ids":["a",3,"b"],"flip":["b","zz"],"use_depth":true}'),
    { ids: ["a", "b"], flip: ["b"], use_depth: true }
  );
  assert.deepEqual(parseState("pose", '{"ids":"a","use_depth":"yes"}'), { ids: [], flip: [], use_depth: false });
});

test("serializeState writes the canonical shape in a stable key order", () => {
  assert.equal(serializeState("portrait", { id: "upload:me.png", junk: 1 }), '{"id":"upload:me.png"}');
  assert.equal(serializeState("costume", { view: "side", id: "c1" }), '{"id":"c1","view":"side"}');
  assert.equal(
    serializeState("pose", { use_depth: true, flip: ["b"], ids: ["a", "b"] }),
    '{"ids":["a","b"],"flip":["b"],"use_depth":true}'
  );
  const raw = '{"ids":["x"],"flip":[],"use_depth":false}';
  assert.equal(serializeState("pose", parseState("pose", raw)), raw);
});

test("togglePose adds, removes (also from flip) and refuses a 14th", () => {
  const s = { ids: ["a", "b"], flip: ["b"], use_depth: true };
  assert.deepEqual(togglePose(s, "c"), { state: { ids: ["a", "b", "c"], flip: ["b"], use_depth: true }, refused: false });
  assert.deepEqual(togglePose(s, "b"), { state: { ids: ["a"], flip: [], use_depth: true }, refused: false });
  assert.deepEqual(s, { ids: ["a", "b"], flip: ["b"], use_depth: true });
  const full = { ids: Array.from({ length: 13 }, (_, i) => `p${i}`), flip: [], use_depth: false };
  const out = togglePose(full, "extra");
  assert.equal(out.refused, true);
  assert.deepEqual(out.state.ids, full.ids);
});

test("removePose drops the id from ids and flip", () => {
  const s = { ids: ["a", "b", "c"], flip: ["a", "c"], use_depth: false };
  assert.deepEqual(removePose(s, "c"), { ids: ["a", "b"], flip: ["a"], use_depth: false });
  assert.deepEqual(s.ids, ["a", "b", "c"]);
});

test("flipPose toggles only selected ids; movePose reorders", () => {
  const s = { ids: ["a", "b"], flip: [], use_depth: false };
  assert.deepEqual(flipPose(s, "a").flip, ["a"]);
  assert.deepEqual(flipPose(flipPose(s, "a"), "a").flip, []);
  assert.deepEqual(flipPose(s, "zz").flip, []);
  assert.deepEqual(movePose(s, 1, 0).ids, ["b", "a"]);
  assert.deepEqual(s.ids, ["a", "b"]);
});

test("costumeViewFor picks a view the item has", () => {
  assert.equal(costumeViewFor([], "back"), "front");
  assert.equal(costumeViewFor(undefined, "back"), "front");
  assert.equal(costumeViewFor(["front"], "back"), "front");
  assert.equal(costumeViewFor(["front", "back", "side"], "side"), "side");
  assert.equal(costumeViewFor(["front", "back"], "side"), "front");
  assert.equal(costumeViewFor(["back", "side"], "front"), "back");
});

test("selectableViews keeps only the views state_json accepts, in catalogue order", () => {
  assert.deepEqual(selectableViews(["front", "diag", "side", "back"]), ["front", "side", "back"]);
  assert.deepEqual(selectableViews(undefined), []);
  assert.equal(costumeViewFor(["diag", "back"], "diag"), "back");
  assert.equal(costumeViewFor(["front", "diag"], "diag"), "front");
});
