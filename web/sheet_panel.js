// Pose Sheet Designer panel (CharSheetPoseSheet): settings row, live "W × H · MP" readout and a
// layout preview drawn by POST /charsheet/sheet/preview from the upstream Pose Picker's selection.
// All text goes through textContent (the `el` helper); there is no innerHTML.
import { el, errorText } from "./dom.js";
import {
  BACKGROUNDS,
  COLUMN_OPTIONS,
  MAX_SIDE,
  MIN_SIDE,
  PANEL_ASPECTS,
  STEP,
  createRequestGate,
  executedSelection,
  parseColumns,
  parseSheetState,
  previewRequest,
  readSelection,
  readoutVars,
  selectionSource,
  snapDimension,
} from "./lib/sheet.js";
import { watchCallback } from "./lib/widget.js";

const PREVIEW_ROUTE = "/charsheet/sheet/preview";
const DEBOUNCE_MS = 300;
const BACKGROUND_LABELS = { white: "sheet.white", lightgray: "sheet.lightGray" };

const stateWidgetOf = (node) => node?.widgets?.find((w) => w.name === "state_json") ?? null;

function field(label, control) {
  return el("label", { class: "cs-sheet-field" }, [el("span", { class: "cs-sheet-label", text: label }), control]);
}

function select(options, onChange) {
  const node = el("select", { class: "cs-select" });
  for (const { value, label } of options) node.appendChild(el("option", { value, text: label }));
  node.addEventListener("change", () => onChange(node.value));
  return node;
}

function sizeInput(label, onCommit) {
  const input = el("input", {
    class: "cs-input cs-sheet-size",
    type: "number",
    min: MIN_SIDE,
    max: MAX_SIDE,
    step: STEP,
    inputmode: "numeric",
    "aria-label": label,
  });
  // Commit on change (Enter or leaving a changed field) and on blur (re-snaps whatever is shown).
  input.addEventListener("change", () => onCommit(input));
  input.addEventListener("blur", () => onCommit(input));
  return input;
}

export function createSheetPanel({ node, state, onChange, translate, api }) {
  const { t } = translate;
  let current = parseSheetState(state);
  let executed = null; // selection from the last run (ui.selection), for unreadable upstreams
  let plan = null; // last good preview response: {width, height, megapixels, warnings, image}
  let lastKey = null; // body of the last request sent, so repeated triggers don't refetch
  let sourceKey = null; // what tick() last saw upstream
  let timer = 0;
  let destroyed = false;
  const gate = createRequestGate();
  const upstream = { node: null, unwatch: null };

  // ---- DOM ----
  const readout = el("span", { class: "cs-counter cs-sheet-readout", "aria-live": "polite" });
  const header = el("div", { class: "cs-header" }, [
    el("span", { class: "cs-title", text: t("panel.sheet") }),
    el("span", { class: "cs-spacer" }),
    readout,
  ]);

  const columnsSelect = select(
    COLUMN_OPTIONS.map((c) => ({ value: String(c), label: c === "auto" ? t("sheet.auto") : String(c) })),
    (value) => commit({ ...current, columns: parseColumns(value) }),
  );
  const aspectSelect = select(
    PANEL_ASPECTS.map((a) => ({ value: a, label: a })),
    (value) => commit({ ...current, panel_aspect: value }),
  );
  const backgroundSelect = select(
    BACKGROUNDS.map((b) => ({ value: b, label: t(BACKGROUND_LABELS[b]) })),
    (value) => commit({ ...current, background: value }),
  );
  const autoBtn = el("button", { type: "button", class: "cs-btn cs-toggle", text: t("sheet.sizeAuto") });
  const manualBtn = el("button", { type: "button", class: "cs-btn cs-toggle", text: t("sheet.sizeManual") });
  autoBtn.addEventListener("click", () => commit({ ...current, size_mode: "auto" }));
  manualBtn.addEventListener("click", () => {
    if (current.size_mode === "manual") return;
    // Start Manual from the size Auto produced, so switching alone changes nothing.
    const seed = plan ? { width: plan.width, height: plan.height } : {};
    commit({ ...current, ...seed, size_mode: "manual" });
  });
  const sizeToggle = el("div", { class: "cs-sheet-segment", role: "group" }, [autoBtn, manualBtn]);

  const commitSize = (key) => (input) => {
    if (current.size_mode !== "manual") return;
    const value = snapDimension(input.value, current[key]);
    input.value = String(value);
    if (value !== current[key]) commit({ ...current, [key]: value });
  };
  const widthInput = sizeInput(t("sheet.width"), commitSize("width"));
  const heightInput = sizeInput(t("sheet.height"), commitSize("height"));
  const labelsBtn = el("button", { type: "button", class: "cs-btn cs-toggle", text: t("sheet.labels") });
  labelsBtn.addEventListener("click", () => commit({ ...current, labels: !current.labels }));

  const settings = el("div", { class: "cs-filters cs-sheet-settings" }, [
    field(t("sheet.columns"), columnsSelect),
    field(t("sheet.panelAspect"), aspectSelect),
    field(t("sheet.outputSize"), sizeToggle),
    field(t("sheet.width"), widthInput),
    field(t("sheet.height"), heightInput),
    field(t("sheet.background"), backgroundSelect),
    field(" ", labelsBtn),
  ]);

  const warnings = el("div", { class: "cs-warning-text cs-sheet-warnings", hidden: true });
  const image = el("img", { class: "cs-sheet-image", alt: t("sheet.previewTitle"), draggable: "false", hidden: true });
  const status = el("p", { class: "cs-sheet-status" });
  const note = el("p", { class: "cs-sheet-note", hidden: true });
  const preview = el("div", { class: "cs-sheet-preview" }, [image, status]);
  const hint = el("p", { class: "cs-sheet-hint", text: t("sheet.pictureOrderHint") });

  const root = el("div", { class: "cs-panel cs-sheet-panel" }, [header, settings, warnings, preview, note, hint]);
  // Keys stay in the panel (ComfyUI's keybindings only skip text fields); Ctrl/Meta combos and
  // Escape still reach ComfyUI.
  root.addEventListener("keydown", (e) => {
    if (e.ctrlKey || e.metaKey || e.key === "Escape") return;
    e.stopPropagation();
  });

  // ---- rendering ----
  function renderControls() {
    columnsSelect.value = String(current.columns);
    aspectSelect.value = current.panel_aspect;
    backgroundSelect.value = current.background;
    const manual = current.size_mode === "manual";
    autoBtn.setAttribute("aria-pressed", manual ? "false" : "true");
    manualBtn.setAttribute("aria-pressed", manual ? "true" : "false");
    labelsBtn.setAttribute("aria-pressed", current.labels ? "true" : "false");
    for (const input of [widthInput, heightInput]) {
      input.readOnly = !manual;
      input.classList.toggle("cs-readonly", !manual);
    }
    renderSize();
  }

  function renderSize() {
    const manual = current.size_mode === "manual";
    const size = manual ? current : plan;
    // Don't overwrite a field the user is typing in.
    if (document.activeElement !== widthInput) widthInput.value = size ? String(size.width) : "";
    if (document.activeElement !== heightInput) heightInput.value = size ? String(size.height) : "";
    widthInput.placeholder = manual ? "" : t("sheet.auto");
    heightInput.placeholder = manual ? "" : t("sheet.auto");
    readout.textContent = size ? t("sheet.readout", readoutVars(size)) : t("sheet.readoutAuto");
    const list = plan?.warnings ?? [];
    warnings.hidden = !list.length;
    warnings.textContent = list.join(" ");
  }

  function showStatus(text, { error = false, keepImage = false } = {}) {
    status.textContent = text;
    status.hidden = !text;
    status.classList.toggle("cs-error-text", error);
    if (!keepImage) {
      image.hidden = true;
      image.removeAttribute("src");
    }
    preview.classList.toggle("cs-sheet-empty", image.hidden);
  }

  // ---- upstream ----
  function watchUpstream(poseNode) {
    if (poseNode === upstream.node) return;
    upstream.unwatch?.();
    upstream.node = poseNode;
    upstream.unwatch = null;
    const widget = stateWidgetOf(poseNode);
    // Keep the picker's own callback (it runs first); only add a preview refresh after it.
    if (widget) upstream.unwatch = watchCallback(widget, () => schedule());
  }

  function resolveSelection() {
    const source = selectionSource(node.graph, node);
    watchUpstream(source.node);
    if (source.kind === "pose") return { kind: "pose", selection: readSelection(stateWidgetOf(source.node)?.value) };
    if (source.kind === "other") return { kind: "other", selection: executed };
    return { kind: "none", selection: null };
  }

  // ---- preview ----
  function schedule() {
    if (destroyed) return;
    clearTimeout(timer);
    timer = setTimeout(() => refreshPreview(), DEBOUNCE_MS);
  }

  async function refreshPreview({ force = false } = {}) {
    if (destroyed) return;
    clearTimeout(timer);
    const { kind, selection } = resolveSelection();
    const body = previewRequest(selection, current);
    note.hidden = !(kind === "other" && body);
    note.textContent = note.hidden ? "" : t("sheet.lastRunPreview");
    if (!body) {
      gate.cancel(); // drop any response still in flight
      lastKey = null;
      plan = null;
      renderSize();
      showStatus(kind === "other" ? t("sheet.previewAfterRun") : t("sheet.noPoses"));
      return;
    }
    const key = JSON.stringify(body);
    if (key === lastKey && !force) return;
    lastKey = key;
    const token = gate.next();
    preview.classList.add("cs-loading");
    if (image.hidden) showStatus(t("sheet.previewLoading"));
    try {
      const resp = await api.fetchApi(PREVIEW_ROUTE, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: key,
      });
      const data = await resp.json().catch(() => ({}));
      if (destroyed || !gate.isCurrent(token)) return;
      if (!resp.ok) throw new Error(data?.error || `HTTP ${resp.status}`);
      if (typeof data?.image !== "string" || !data.image.startsWith("data:image/")) throw new Error("no preview image");
      plan = {
        width: data.width,
        height: data.height,
        megapixels: data.megapixels,
        warnings: Array.isArray(data.warnings) ? data.warnings.map(String) : [],
      };
      image.src = data.image;
      image.hidden = false;
      showStatus("", { keepImage: true });
      renderSize();
    } catch (err) {
      if (destroyed || !gate.isCurrent(token)) return;
      lastKey = null; // the same settings may be retried on the next change
      // Keep the last good picture; say what went wrong under it.
      showStatus(t("sheet.previewError", { message: errorText(err) }), { error: true, keepImage: true });
    } finally {
      if (gate.isCurrent(token)) preview.classList.remove("cs-loading");
    }
  }

  function commit(next) {
    const parsed = parseSheetState(next);
    const changed = JSON.stringify(parsed) !== JSON.stringify(current);
    current = parsed;
    renderControls();
    if (!changed) return;
    onChange(current);
    schedule();
  }

  renderControls();
  showStatus("");
  schedule();

  return {
    root,
    /** Node → panel: a new `state_json` value (load, undo, paste). */
    setState(raw) {
      current = parseSheetState(raw);
      renderControls();
      schedule();
    },
    refreshPreview,
    /** Called every frame by the mount loop: catches upstream edits that bypass widget callbacks (undo, load). */
    tick() {
      if (destroyed) return;
      const source = selectionSource(node.graph, node);
      const value = source.node ? String(stateWidgetOf(source.node)?.value ?? "") : "";
      const key = `${source.kind}|${source.node?.id ?? ""}|${value}`;
      if (key === sourceKey) return;
      sourceKey = key;
      schedule();
    },
    onConnectionsChange() {
      schedule();
    },
    onExecuted(output) {
      const selection = executedSelection(output);
      if (selection) executed = selection;
      schedule();
    },
    destroy() {
      if (destroyed) return;
      destroyed = true;
      clearTimeout(timer);
      gate.cancel();
      upstream.unwatch?.();
      upstream.unwatch = null;
      upstream.node = null;
    },
  };
}
