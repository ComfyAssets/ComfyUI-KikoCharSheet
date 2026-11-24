// Pure `state_json` helpers for the picker panels (no DOM, never mutate their inputs).
// Shapes: portrait {id}, costume {id, view}, pose {ids, flip, use_depth}.
import { MAX_POSES, move, remove, toggle, toggleFlip } from "./selection.js";

export const COSTUME_VIEWS = ["front", "diag", "side", "back"]; // the fork's view set, as in charsheet/nodes.py

export function defaultState(lib) {
  if (lib === "pose") return { ids: [], flip: [], use_depth: false };
  if (lib === "costume") return { id: "", view: "front" };
  return { id: "" };
}

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

const strings = (value) => (Array.isArray(value) ? value.filter((v) => typeof v === "string") : []);

/** Read a node's `state_json` (string or object) leniently; unusable fields fall back to defaults. */
export function parseState(lib, raw) {
  const data = readObject(raw);
  if (lib === "pose") {
    const ids = strings(data.ids);
    return { ids, flip: strings(data.flip).filter((id) => ids.includes(id)), use_depth: data.use_depth === true };
  }
  const id = typeof data.id === "string" ? data.id : "";
  if (lib === "costume") return { id, view: COSTUME_VIEWS.includes(data.view) ? data.view : "front" };
  return { id };
}

/** Canonical JSON for `state_json`, with a stable key order. */
export function serializeState(lib, state) {
  if (lib === "pose") return JSON.stringify({ ids: [...state.ids], flip: [...state.flip], use_depth: state.use_depth === true });
  if (lib === "costume") return JSON.stringify({ id: state.id, view: state.view });
  return JSON.stringify({ id: state.id });
}

/** Empty a portrait or costume pick (the node then uses its default item); a costume's view goes back to front. */
export function clearPick(lib, state) {
  return { ...state, ...defaultState(lib) };
}

/** Add or remove a pose; removing also clears its flip. A full selection refuses new ids. */
export function togglePose(state, id, max = MAX_POSES) {
  const { sel, refused } = toggle(state.ids, id, max);
  return { state: { ...state, ids: sel, flip: state.flip.filter((f) => sel.includes(f)) }, refused };
}

export function removePose(state, id) {
  return { ...state, ids: remove(state.ids, id), flip: remove(state.flip, id) };
}

/** Toggle the mirror flag of a selected pose (ids not in the selection are ignored). */
export function flipPose(state, id) {
  if (!state.ids.includes(id)) return { ...state, flip: [...state.flip] };
  return { ...state, flip: toggleFlip(state.flip, id) };
}

export function movePose(state, from, to) {
  return { ...state, ids: move(state.ids, from, to) };
}

/** Catalogue views that `state_json` may name, in catalogue order (unknown view ids are dropped). */
export function selectableViews(views) {
  return Array.isArray(views) ? views.filter((v) => COSTUME_VIEWS.includes(v)) : [];
}

/** The view to use for a costume with these views: the preferred one if offered, else front, else the first. */
export function costumeViewFor(views, preferred) {
  const usable = selectableViews(views);
  if (!usable.length) return "front";
  if (usable.includes(preferred)) return preferred;
  return usable.includes("front") ? "front" : usable[0];
}
