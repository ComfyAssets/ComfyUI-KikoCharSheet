// Mounts a panel as a DOM widget on the Portrait / Costume / Pose pickers and the Pose Sheet node, following H3
// Character Sheet Designer's integration: the hidden `state_json` STRING widget stays the only
// source of truth; the panel writes it on every change and re-reads it when it changes elsewhere
// (workflow load, undo, paste). Without addDOMWidget the plain text widget stays visible.
import { createTranslator, loadLocale, resolveLang } from "./lib/i18n.js";
import { MAX_POSES } from "./lib/selection.js";
import { serializeSheetState } from "./lib/sheet.js";
import { serializeState } from "./lib/state.js";
import { setValueOnce } from "./lib/widget.js";
import { createPickerPanel } from "./panel.js";
import { createSheetPanel } from "./sheet_panel.js";

export const PICKER_NODES = { CharSheetPortrait: "portrait", CharSheetCostume: "costume", CharSheetPose: "pose" };
export const SHEET_NODE = "CharSheetPoseSheet";
const LOG_PREFIX = "[CharSheet]";

const installed = new WeakMap();
let localePromise = null;
let warned = false;

/** One shared translator: the Comfy.Locale language, else English, else raw keys. */
export function getTranslator(app, api) {
  if (!localePromise) {
    localePromise = (async () => {
      const fetchFn = (url) => api.fetchApi(url);
      const lang = resolveLang(app.ui?.settings?.getSettingValue?.("Comfy.Locale"), globalThis.navigator?.languages);
      let locale = await loadLocale(lang, fetchFn);
      if (lang !== "en" && !Object.keys(locale.strings).length) locale = await loadLocale("en", fetchFn);
      return createTranslator(locale.strings, locale.data);
    })();
  }
  return localePromise;
}

function injectStylesheet() {
  if (document.querySelector("link[data-charsheet-style]")) return;
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = new URL("./style.css", import.meta.url).href;
  link.dataset.charsheetStyle = "";
  document.head.appendChild(link);
}

function warnFallback(reason) {
  if (warned) return;
  warned = true;
  console.warn(`${LOG_PREFIX} In-node panel unavailable (${reason}); edit the state_json text widget instead.`);
}

/** Record the change as one undo step, as native canvas operations do (H3's graphTransaction). */
function transaction(node, canvas, change) {
  const graph = node.graph;
  const canvasEvents = typeof canvas?.emitBeforeChange === "function" && typeof canvas?.emitAfterChange === "function";
  const graphEvents = typeof graph?.beforeChange === "function" && typeof graph?.afterChange === "function";
  if (canvasEvents) canvas.emitBeforeChange();
  try {
    if (graphEvents) {
      graph.beforeChange(node);
      try {
        change();
      } finally {
        graph.afterChange(node);
      }
    } else change();
  } finally {
    if (canvasEvents) canvas.emitAfterChange();
  }
  node.setDirtyCanvas?.(true, true);
}

/** Chain a node hook without changing the previous hook's return value. */
function chain(node, name, after) {
  const prior = node[name];
  node[name] = function (...args) {
    const result = prior?.apply(this, args);
    after.apply(this, args);
    return result;
  };
}

/** Hide the plain `state_json` widget; returns a function that puts it back exactly as it was. */
function hideStateWidget(widget) {
  const element = widget.element ?? widget.inputEl;
  const saved = {
    type: widget.type,
    hidden: widget.hidden,
    ownComputeSize: Object.prototype.hasOwnProperty.call(widget, "computeSize"),
    computeSize: widget.computeSize,
    elementHidden: element?.hidden,
  };
  widget.type = "hidden";
  widget.hidden = true;
  widget.computeSize = () => [0, -4];
  if (element) element.hidden = true;
  return () => {
    widget.type = saved.type;
    widget.hidden = saved.hidden;
    if (saved.ownComputeSize) widget.computeSize = saved.computeSize;
    else delete widget.computeSize;
    if (element) element.hidden = saved.elementHidden;
  };
}

/** Remove our presentation-only DOM widget (never the canonical state_json widget). */
function removeDomWidget(node, domWidget) {
  if (node.widgets?.includes(domWidget)) {
    if (typeof node.removeWidget === "function") node.removeWidget(domWidget);
    else {
      domWidget.onRemove?.();
      node.widgets.splice(node.widgets.indexOf(domWidget), 1);
    }
  } else domWidget.onRemove?.();
  domWidget.element?.remove?.();
}

/** How to build and size the panel for this node's class, or null when the node gets none. */
function panelSpec(node, api) {
  const lib = PICKER_NODES[node.comfyClass] ?? PICKER_NODES[node.type];
  if (lib) {
    return {
      minHeight: 720,
      height: 760,
      minWidth: 720,
      serialize: (state) => serializeState(lib, state),
      create: ({ state, onChange, translate }) =>
        createPickerPanel({ lib, multi: lib === "pose", max: MAX_POSES, state, onChange, translate, api }),
    };
  }
  if (node.comfyClass === SHEET_NODE || node.type === SHEET_NODE) {
    return {
      minHeight: 560,
      height: 600,
      minWidth: 600,
      serialize: serializeSheetState,
      create: ({ state, onChange, translate }) => createSheetPanel({ node, state, onChange, translate, api }),
      // Preview refresh triggers on top of the panel's own (its state, the upstream state_json callback, tick()).
      hooks: ["onConnectionsChange", "onExecuted"],
    };
  }
  return null;
}

export function installPanel(node, app, api) {
  if (installed.has(node)) return installed.get(node);
  const spec = panelSpec(node, api);
  if (!spec) return null;
  const widget = node.widgets?.find((w) => w.name === "state_json");
  if (!widget) return null;
  if (typeof node.addDOMWidget !== "function" || typeof document === "undefined") {
    warnFallback("addDOMWidget is not available");
    return null;
  }

  injectStylesheet();
  const host = document.createElement("div");
  host.className = "cs-host";
  let domWidget;
  try {
    domWidget = node.addDOMWidget("charsheet_panel", "CHARSHEET_PANEL", host, {
      getMinHeight: () => spec.minHeight,
      getHeight: () => spec.height,
      hideOnZoom: false,
      serialize: false,
    });
  } catch (err) {
    warnFallback(err instanceof Error ? err.message : String(err));
    return null;
  }
  if (!domWidget) {
    warnFallback("addDOMWidget returned nothing");
    return null;
  }
  domWidget.serialize = false;
  const unhide = hideStateWidget(widget);

  let panel = null;
  let frame = 0;
  let disposed = false;
  let lastValue = String(widget.value ?? "");

  const write = (state) => {
    const json = spec.serialize(state);
    lastValue = json;
    if (json === widget.value) return;
    const previous = widget.value;
    transaction(node, app.canvas, () => setValueOnce(widget, json));
    node.onWidgetChanged?.("state_json", json, previous, widget);
  };

  // Pick up edits made elsewhere (configure, undo, paste); at most one cheap string compare per frame.
  const sync = () => {
    const value = String(widget.value ?? "");
    if (value === lastValue) return;
    lastValue = value;
    panel?.setState(value);
  };
  const loop = () => {
    if (disposed) return;
    sync();
    panel?.tick?.();
    frame = requestAnimationFrame(loop);
  };

  const record = {
    sync,
    dispose() {
      if (disposed) return;
      disposed = true;
      cancelAnimationFrame(frame);
      panel?.destroy();
      installed.delete(node);
    },
  };
  installed.set(node, record);
  chain(node, "onConfigure", () => sync());
  chain(node, "onRemoved", () => record.dispose());
  for (const hook of spec.hooks ?? []) {
    chain(node, hook, (...args) => {
      if (!disposed) panel?.[hook]?.(...args);
    });
  }

  getTranslator(app, api).then((translate) => {
    if (disposed) return;
    try {
      panel = spec.create({ state: widget.value, onChange: write, translate });
    } catch (err) {
      // Leave the node editable: drop the panel and show the plain text widget again.
      record.dispose();
      removeDomWidget(node, domWidget);
      unhide();
      node.setDirtyCanvas?.(true, true);
      warnFallback(`the panel could not be built: ${err instanceof Error ? err.message : String(err)}`);
      return;
    }
    lastValue = String(widget.value ?? "");
    host.replaceChildren(panel.root);
    frame = requestAnimationFrame(loop);
    // Runs after nodeCreated/configure have settled the size (they reset it), so only grow.
    // node.size is a typed array in current frontends, so don't test with Array.isArray.
    if (typeof node.setSize === "function" && node.size?.length >= 2 && node.size[0] < spec.minWidth) {
      node.setSize([spec.minWidth, node.size[1]]);
      node.setDirtyCanvas?.(true, true);
    }
  });

  return record;
}

export function syncInstalled(node) {
  installed.get(node)?.sync();
}
