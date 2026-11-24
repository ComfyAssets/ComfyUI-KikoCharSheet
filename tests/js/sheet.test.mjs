import test from "node:test";
import assert from "node:assert/strict";
import {
  COLUMN_OPTIONS,
  MAX_SIDE,
  MIN_SIDE,
  SHEET_DEFAULTS,
  createRequestGate,
  executedSelection,
  findUpstreamPoseNode,
  getLink,
  parseColumns,
  parseSheetState,
  previewRequest,
  readoutVars,
  selectionSource,
  serializeSheetState,
  snapDimension,
} from "../../web/lib/sheet.js";

// ---- state ----

test("defaults mirror charsheet/sheet.py parse_sheet_state", () => {
  assert.deepEqual(SHEET_DEFAULTS, {
    columns: "auto",
    panel_aspect: "1:2",
    size_mode: "auto",
    width: 2048,
    height: 2048,
    labels: false,
    background: "white",
  });
  assert.equal(MIN_SIDE, 64);
  assert.equal(MAX_SIDE, 8192);
  assert.deepEqual(COLUMN_OPTIONS, ["auto", 1, 2, 3, 4, 5, 6, 7]);
});

test("empty, broken or non-object state gives the defaults", () => {
  for (const raw of ["", "  ", "{nope", "[1,2]", "42", null, undefined]) {
    assert.deepEqual(parseSheetState(raw), SHEET_DEFAULTS, String(raw));
  }
});

test("valid fields are kept, from a string or an object", () => {
  const state = {
    columns: 3,
    panel_aspect: "2:3",
    size_mode: "manual",
    width: 1536,
    height: 2560,
    labels: true,
    background: "lightgray",
  };
  assert.deepEqual(parseSheetState(JSON.stringify(state)), state);
  assert.deepEqual(parseSheetState(state), state);
});

test("invalid fields fall back to their defaults one by one", () => {
  const parsed = parseSheetState({
    columns: 8,
    panel_aspect: "3:4",
    size_mode: "fixed",
    width: 100, // not a multiple of 32
    height: 9000,
    labels: "yes",
    background: "black",
    extra: 1,
  });
  assert.deepEqual(parsed, SHEET_DEFAULTS);
  assert.equal(parseSheetState({ columns: 0 }).columns, "auto");
  assert.equal(parseSheetState({ columns: true }).columns, "auto");
  assert.equal(parseSheetState({ columns: 2.5 }).columns, "auto");
  assert.equal(parseSheetState({ width: true }).width, 2048);
  assert.equal(parseSheetState({ width: 64, height: 8192 }).width, 64);
  assert.equal(parseSheetState({ width: 64, height: 8192 }).height, 8192);
});

test("parsing does not mutate its input", () => {
  const input = { columns: 9, width: 1 };
  parseSheetState(input);
  assert.deepEqual(input, { columns: 9, width: 1 });
});

test("serialize writes the canonical key order", () => {
  const json = serializeSheetState({ ...SHEET_DEFAULTS, background: "lightgray", columns: 2 });
  assert.equal(
    json,
    '{"columns":2,"panel_aspect":"1:2","size_mode":"auto","width":2048,"height":2048,"labels":false,"background":"lightgray"}',
  );
  assert.deepEqual(parseSheetState(json), { ...SHEET_DEFAULTS, background: "lightgray", columns: 2 });
});

test("parseColumns reads the select value", () => {
  assert.equal(parseColumns("auto"), "auto");
  assert.equal(parseColumns("4"), 4);
  assert.equal(parseColumns("0"), "auto");
  assert.equal(parseColumns("8"), "auto");
  assert.equal(parseColumns("x"), "auto");
});

test("snapDimension rounds to 32 and clamps to the allowed range", () => {
  assert.equal(snapDimension("1000", 2048), 992);
  assert.equal(snapDimension(1008, 2048), 1024); // halfway rounds up
  assert.equal(snapDimension("1024", 2048), 1024);
  assert.equal(snapDimension("10", 2048), 64);
  assert.equal(snapDimension("-500", 2048), 64);
  assert.equal(snapDimension("99999", 2048), 8192);
  assert.equal(snapDimension("", 1536), 1536);
  assert.equal(snapDimension("abc", 1536), 1536);
  assert.equal(snapDimension(" 2050 ", 1536), 2048);
});

// ---- upstream lookup ----

const poseNode = { id: 7, type: "CharSheetPose", comfyClass: "CharSheetPose" };
const rerouteNode = { id: 9, type: "Reroute" };
const sheetWith = (link) => ({ id: 3, inputs: [{ name: "character_image", link: 99 }, { name: "selection", link }] });

function mapGraph(links, nodes) {
  return {
    links: new Map(Object.entries(links).map(([k, v]) => [Number(k), v])),
    getNodeById: (id) => nodes.find((n) => n.id === id) ?? null,
  };
}

test("getLink reads Map-like, plain-object, array and legacy array links", () => {
  const link = { id: 5, origin_id: 7, origin_slot: 5 };
  assert.deepEqual(getLink({ links: new Map([[5, link]]) }, 5), link);
  assert.deepEqual(getLink({ links: { 5: link } }, 5), link);
  const sparse = [];
  sparse[5] = link;
  assert.deepEqual(getLink({ links: sparse }, 5), link);
  assert.deepEqual(getLink({ links: { 5: [5, 7, 5, 3, 1, "CHARSHEET_POSES"] } }, 5), { id: 5, origin_id: 7, origin_slot: 5 });
  assert.equal(getLink({ links: new Map() }, 5), null);
  assert.equal(getLink({}, 5), null);
  assert.equal(getLink(null, 5), null);
  assert.equal(getLink({ links: { 5: link } }, null), null);
});

test("findUpstreamPoseNode follows the selection link to a Pose node", () => {
  const graph = mapGraph({ 5: { id: 5, origin_id: 7, origin_slot: 5 } }, [poseNode]);
  assert.equal(findUpstreamPoseNode(graph, sheetWith(5)), poseNode);
});

test("findUpstreamPoseNode works with plain-object links and node lists", () => {
  const byId = { links: { 5: { origin_id: 7 } }, _nodes_by_id: { 7: poseNode } };
  assert.equal(findUpstreamPoseNode(byId, sheetWith(5)), poseNode);
  const list = { links: { 5: { origin_id: 7 } }, _nodes: [rerouteNode, poseNode] };
  assert.equal(findUpstreamPoseNode(list, sheetWith(5)), poseNode);
});

test("findUpstreamPoseNode accepts a node known only by comfyClass or type", () => {
  const byClass = { id: 7, type: "Pose Picker (Char Sheet)", comfyClass: "CharSheetPose" };
  assert.equal(findUpstreamPoseNode(mapGraph({ 5: { origin_id: 7 } }, [byClass]), sheetWith(5)), byClass);
  const byType = { id: 7, type: "CharSheetPose" };
  assert.equal(findUpstreamPoseNode(mapGraph({ 5: { origin_id: 7 } }, [byType]), sheetWith(5)), byType);
});

test("findUpstreamPoseNode returns null for reroutes, subgraph inputs, other nodes and no link", () => {
  const graph = mapGraph(
    { 5: { origin_id: 9 }, 6: { origin_id: -10 }, 8: { origin_id: 42 } },
    [poseNode, rerouteNode, { id: 42, type: "CharSheetPortrait", comfyClass: "CharSheetPortrait" }],
  );
  assert.equal(findUpstreamPoseNode(graph, sheetWith(5)), null); // reroute
  assert.equal(findUpstreamPoseNode(graph, sheetWith(6)), null); // subgraph input
  assert.equal(findUpstreamPoseNode(graph, sheetWith(8)), null); // other node type
  assert.equal(findUpstreamPoseNode(graph, sheetWith(null)), null);
  assert.equal(findUpstreamPoseNode(graph, sheetWith(77)), null); // dangling link id
  assert.equal(findUpstreamPoseNode(graph, { id: 3 }), null); // no inputs
  assert.equal(findUpstreamPoseNode(null, sheetWith(5)), null);
});

test("selectionSource tells disconnected, pose and other sources apart", () => {
  const graph = mapGraph({ 5: { origin_id: 7 }, 6: { origin_id: 9 } }, [poseNode, rerouteNode]);
  assert.deepEqual(selectionSource(graph, sheetWith(null)), { kind: "none", node: null });
  assert.deepEqual(selectionSource(graph, sheetWith(5)), { kind: "pose", node: poseNode });
  assert.deepEqual(selectionSource(graph, sheetWith(6)), { kind: "other", node: null });
  assert.deepEqual(selectionSource(graph, sheetWith(77)), { kind: "none", node: null });
});

// ---- preview request ----

test("previewRequest builds the route body, or null when nothing is selected", () => {
  const state = { ...SHEET_DEFAULTS, columns: 2 };
  assert.deepEqual(previewRequest({ ids: ["a", "b"], flip: ["b"], use_depth: true }, state), {
    ids: ["a", "b"],
    flip: ["b"],
    use_depth: true,
    state,
  });
  assert.equal(previewRequest({ ids: [], flip: [], use_depth: false }, state), null);
  assert.equal(previewRequest(null, state), null);
});

test("executedSelection reads the node's ui.selection payload", () => {
  const sel = { ids: ["a"], flip: [], use_depth: false };
  assert.deepEqual(executedSelection({ selection: [JSON.stringify(sel)] }), sel);
  assert.deepEqual(executedSelection({ selection: JSON.stringify(sel) }), sel);
  assert.deepEqual(executedSelection({ selection: [{ ids: ["x", 3], flip: ["x", "y"] }] }), {
    ids: ["x"],
    flip: ["x"],
    use_depth: false,
  });
  assert.equal(executedSelection({}), null);
  assert.equal(executedSelection(null), null);
  assert.equal(executedSelection({ selection: ["{bad"] }), null);
});

test("readoutVars formats megapixels with two decimals", () => {
  assert.deepEqual(readoutVars({ width: 2048, height: 2048, megapixels: 4.19 }), {
    width: 2048,
    height: 2048,
    megapixels: "4.19",
  });
  assert.deepEqual(readoutVars({ width: 1024, height: 1024 }), { width: 1024, height: 1024, megapixels: "1.05" });
  assert.deepEqual(readoutVars({ width: 3232, height: 1280, megapixels: 4.1 }).megapixels, "4.10");
});

test("the request gate only accepts the latest token", () => {
  const gate = createRequestGate();
  const a = gate.next();
  const b = gate.next();
  assert.equal(gate.isCurrent(a), false);
  assert.equal(gate.isCurrent(b), true);
  gate.cancel();
  assert.equal(gate.isCurrent(b), false);
});
