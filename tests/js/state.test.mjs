import test from "node:test";
import assert from "node:assert/strict";
import {
  COSTUME_VIEWS,
  clearPick,
  defaultState,
  hasWideRenders,
  isWideLens,
  setWideLens,
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
  assert.deepEqual(defaultState("pose"), { ids: [], flip: [], style: "grey" });
  assert.deepEqual(COSTUME_VIEWS, ["front", "diag", "side", "back"]);
});

test("parseState falls back to defaults on empty or broken JSON", () => {
  assert.deepEqual(parseState("portrait", ""), { id: "" });
  assert.deepEqual(parseState("portrait", "{not json"), { id: "" });
  assert.deepEqual(parseState("pose", "[1,2]"), { ids: [], flip: [], style: "grey" });
  assert.deepEqual(parseState("costume", undefined), { id: "", view: "front" });
});

test("parseState keeps valid fields and drops bad ones", () => {
  assert.deepEqual(parseState("portrait", '{"id":"f71f980dde3","x":1}'), { id: "f71f980dde3" });
  assert.deepEqual(parseState("portrait", '{"id":5}'), { id: "" });
  assert.deepEqual(parseState("costume", '{"id":"SPR-1","view":"back"}'), { id: "SPR-1", view: "back" });
  assert.deepEqual(parseState("costume", '{"id":"SPR-1","view":"top"}'), { id: "SPR-1", view: "front" });
  assert.deepEqual(parseState("costume", '{"id":"SPR-1","view":"diag"}'), { id: "SPR-1", view: "diag" });
  assert.deepEqual(
    parseState("pose", '{"ids":["a",3,"b"],"flip":["b","zz"],"style":"grey_wide"}'),
    { ids: ["a", "b"], flip: ["b"], style: "grey_wide" }
  );
  assert.deepEqual(parseState("pose", '{"ids":"a","use_depth":"yes"}'), { ids: [], flip: [], style: "grey" });
});

test("serializeState writes the canonical shape in a stable key order", () => {
  assert.equal(serializeState("portrait", { id: "upload:me.png", junk: 1 }), '{"id":"upload:me.png"}');
  assert.equal(serializeState("costume", { view: "side", id: "c1" }), '{"id":"c1","view":"side"}');
  assert.equal(
    serializeState("pose", { style: "grey_wide", flip: ["b"], ids: ["a", "b"] }),
    '{"ids":["a","b"],"flip":["b"],"style":"grey_wide"}'
  );
  const raw = '{"ids":["x"],"flip":[],"style":"grey"}';
  assert.equal(serializeState("pose", parseState("pose", raw)), raw);
});

test("togglePose adds, removes (also from flip) and refuses a 14th", () => {
  const s = { ids: ["a", "b"], flip: ["b"], style: "grey_wide" };
  assert.deepEqual(togglePose(s, "c"), { state: { ids: ["a", "b", "c"], flip: ["b"], style: "grey_wide" }, refused: false });
  assert.deepEqual(togglePose(s, "b"), { state: { ids: ["a"], flip: [], style: "grey_wide" }, refused: false });
  assert.deepEqual(s, { ids: ["a", "b"], flip: ["b"], style: "grey_wide" });
  const full = { ids: Array.from({ length: 13 }, (_, i) => `p${i}`), flip: [], style: "grey" };
  const out = togglePose(full, "extra");
  assert.equal(out.refused, true);
  assert.deepEqual(out.state.ids, full.ids);
});

test("removePose drops the id from ids and flip", () => {
  const s = { ids: ["a", "b", "c"], flip: ["a", "c"], style: "grey" };
  assert.deepEqual(removePose(s, "c"), { ids: ["a", "b"], flip: ["a"], style: "grey" });
  assert.deepEqual(s.ids, ["a", "b", "c"]);
});

test("flipPose toggles only selected ids; movePose reorders", () => {
  const s = { ids: ["a", "b"], flip: [], style: "grey" };
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

test("selectableViews keeps the four known views in catalogue order", () => {
  assert.deepEqual(selectableViews(["front", "diag", "side", "back", "top"]), ["front", "diag", "side", "back"]);
  assert.deepEqual(selectableViews(undefined), []);
  assert.equal(costumeViewFor(["front", "diag", "back"], "diag"), "diag");
  assert.equal(costumeViewFor(["top", "back"], "top"), "back");
});

test("clearPick empties a single pick and resets the costume view without mutating", () => {
  const costume = { id: "SUM-0237", view: "back" };
  assert.deepEqual(clearPick("costume", costume), { id: "", view: "front" });
  assert.deepEqual(costume, { id: "SUM-0237", view: "back" });
  assert.deepEqual(clearPick("portrait", { id: "por-a" }), { id: "" });
});

test("pose style: grey unless the state names a known render set", () => {
  assert.equal(parseState("pose", '{"ids":[],"style":"grey_wide"}').style, "grey_wide");
  for (const old of ['{"ids":[]}', '{"ids":[],"use_depth":true}', '{"ids":[],"style":"line"}', '{"ids":[],"style":"depth"}', '{"ids":[],"style":"clay"}']) {
    assert.deepEqual(parseState("pose", old), { ids: [], flip: [], style: "grey" }, old);
  }
});

test("the lens switch sets the wide render set and does not mutate", () => {
  const s = { ids: ["a"], flip: [], style: "grey" };
  assert.deepEqual(setWideLens(s, true), { ids: ["a"], flip: [], style: "grey_wide" });
  assert.deepEqual(setWideLens({ ...s, style: "grey_wide" }, false), s);
  assert.deepEqual(s, { ids: ["a"], flip: [], style: "grey" });
  assert.equal(isWideLens(s), false);
  assert.equal(isWideLens({ style: "grey_wide" }), true);
  assert.equal(isWideLens({ use_depth: true }), false);
});

test("hasWideRenders: true when any catalogue item has a wide render", () => {
  assert.equal(hasWideRenders([{ wide: false }, {}]), false);
  assert.equal(hasWideRenders([{ wide: false }, { wide: true }]), true);
  assert.equal(hasWideRenders([]), false);
});
