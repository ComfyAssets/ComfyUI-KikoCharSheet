// Pure helpers for the Pose Sheet designer panel (no DOM, no ComfyUI imports; inputs are never mutated).
// The state rules mirror charsheet/sheet.py `parse_sheet_state`, but leniently: a bad field shows its
// default instead of raising, so a broken saved value still opens the panel.
import { parseState } from "./state.js";

export const POSE_NODE_CLASS = "CharSheetPose";
export const SELECTION_INPUT = "selection";
export const MIN_SIDE = 64;
export const MAX_SIDE = 8192;
export const STEP = 32;
export const MAX_COLUMNS = 7;
export const COLUMN_OPTIONS = ["auto", 1, 2, 3, 4, 5, 6, 7];
export const PANEL_ASPECTS = ["1:2", "2:3", "1:1"];
export const SIZE_MODES = ["auto", "manual"];
export const BACKGROUNDS = ["white", "lightgray"];
export const SHEET_DEFAULTS = Object.freeze({
  columns: "auto",
  panel_aspect: "1:2",
  size_mode: "auto",
  width: 2048,
  height: 2048,
  labels: false,
  background: "white",
});

function readObject(raw) {
  if (raw && typeof raw === "object" && !Array.isArray(raw)) return raw;
  if (typeof raw !== "string" || !raw.trim()) return {};
  try {
    const data = JSON.parse(raw);
    return data && typeof data === "object" && !Array.isArray(data) ? data : {};
  } catch {
    return {};
  }
}

const isColumns = (v) => v === "auto" || (Number.isInteger(v) && v >= 1 && v <= MAX_COLUMNS);
// Python accepts any whole number in range and plan_layout snaps it to 32; do the same here.
const isSide = (v) => Number.isInteger(v) && v >= MIN_SIDE && v <= MAX_SIDE;
const pick = (value, valid, fallback) => (valid(value) ? value : fallback);
const side = (value, fallback) => (isSide(value) ? snapDimension(value, fallback) : fallback);

/** Read the sheet `state_json` (string or object); unusable fields fall back to their defaults. */
export function parseSheetState(raw) {
  const data = readObject(raw);
  const d = SHEET_DEFAULTS;
  return {
    columns: pick(data.columns, isColumns, d.columns),
    panel_aspect: pick(data.panel_aspect, (v) => PANEL_ASPECTS.includes(v), d.panel_aspect),
    size_mode: pick(data.size_mode, (v) => SIZE_MODES.includes(v), d.size_mode),
    width: side(data.width, d.width),
    height: side(data.height, d.height),
    labels: pick(data.labels, (v) => typeof v === "boolean", d.labels),
    background: pick(data.background, (v) => BACKGROUNDS.includes(v), d.background),
  };
}

/** Canonical JSON for the sheet `state_json`, with a stable key order. */
export function serializeSheetState(state) {
  const s = parseSheetState(state);
  return JSON.stringify({
    columns: s.columns,
    panel_aspect: s.panel_aspect,
    size_mode: s.size_mode,
    width: s.width,
    height: s.height,
    labels: s.labels,
    background: s.background,
  });
}

/** The columns <select> value ("auto" or "1".."7") as a state value. */
export function parseColumns(value) {
  const n = Number(value);
  return Number.isInteger(n) && isColumns(n) ? n : "auto";
}

/** Python's round(): halves go to the even neighbour, so we snap exactly as charsheet/sheet.py does. */
function roundHalfEven(x) {
  const floor = Math.floor(x);
  const diff = x - floor;
  if (diff > 0.5) return floor + 1;
  if (diff < 0.5) return floor;
  return floor % 2 === 0 ? floor : floor + 1;
}

/** A width/height: nearest multiple of 32 (as sheet.py `_round_step`), clamped to MIN_SIDE..MAX_SIDE; unreadable → fallback. */
export function snapDimension(value, fallback) {
  const text = typeof value === "string" ? value.trim() : value;
  const n = typeof text === "number" ? text : text === "" ? NaN : Number(text);
  if (!Number.isFinite(n)) return fallback;
  const snapped = roundHalfEven(n / STEP) * STEP;
  return Math.min(MAX_SIDE, Math.max(MIN_SIDE, snapped));
}

/** Look up a link by id in `graph.links`, which is a Map in current frontends and a plain object or array in older ones. */
export function getLink(graph, id) {
  if (id === null || id === undefined) return null;
  const links = graph?.links;
  if (!links) return null;
  const link = typeof links.get === "function" ? links.get(id) : links[id];
  if (!link) return null;
  // Serialised (legacy) form: [id, origin_id, origin_slot, target_id, target_slot, type].
  if (Array.isArray(link)) return { id: link[0], origin_id: link[1], origin_slot: link[2] };
  return link;
}

function getNodeById(graph, id) {
  if (typeof graph?.getNodeById === "function") return graph.getNodeById(id) ?? null;
  const byId = graph?._nodes_by_id;
  if (byId) return (typeof byId.get === "function" ? byId.get(id) : byId[id]) ?? null;
  const list = graph?._nodes ?? graph?.nodes;
  return Array.isArray(list) ? (list.find((n) => n?.id === id) ?? null) : null;
}

const isPoseNode = (n) => !!n && (n.comfyClass === POSE_NODE_CLASS || n.type === POSE_NODE_CLASS);

/**
 * Where this node's `selection` input comes from: `none` (not connected), `pose` (a Pose Picker,
 * returned as `node`) or `other` (a reroute, a subgraph input or another node, unreadable here).
 */
export function selectionSource(graph, node) {
  const input = Array.isArray(node?.inputs) ? node.inputs.find((i) => i?.name === SELECTION_INPUT) : null;
  const link = getLink(graph, input?.link);
  if (!link) return { kind: "none", node: null };
  const origin = getNodeById(graph, link.origin_id);
  return isPoseNode(origin) ? { kind: "pose", node: origin } : { kind: "other", node: null };
}

/** The CharSheetPose node feeding `selection`, or null (no link, reroute, subgraph, other node type). */
export function findUpstreamPoseNode(graph, node) {
  return selectionSource(graph, node).node;
}

/** The selection a Pose node's `state_json` (string or object) describes. */
export const readSelection = (raw) => parseState("pose", raw);

/** The selection from the Pose Sheet node's `onExecuted` output (`ui.selection = [json]`), or null. */
export function executedSelection(output) {
  const raw = output?.selection;
  const first = Array.isArray(raw) ? raw[0] : raw;
  if (first === undefined || first === null) return null;
  if (typeof first === "string") {
    try {
      JSON.parse(first);
    } catch {
      return null;
    }
  }
  return readSelection(first);
}

/** Body for POST /charsheet/sheet/preview, or null when there is nothing to lay out. */
export function previewRequest(selection, state) {
  if (!selection || !Array.isArray(selection.ids) || !selection.ids.length) return null;
  return { ids: [...selection.ids], flip: [...(selection.flip ?? [])], use_depth: selection.use_depth === true, state };
}

/** Values for the "W × H · N.NN MP" readout. */
export function readoutVars({ width, height, megapixels }) {
  const mp = Number.isFinite(megapixels) ? megapixels : Math.round((width * height) / 10_000) / 100;
  return { width, height, megapixels: mp.toFixed(2) };
}

/** Request counter: only the newest token is current, so stale responses can be dropped. */
export function createRequestGate() {
  let latest = 0;
  return {
    next: () => ++latest,
    isCurrent: (token) => token === latest,
    cancel: () => {
      latest += 1;
    },
  };
}
