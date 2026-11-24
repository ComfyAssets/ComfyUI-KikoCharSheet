// Mounts a picker panel as a DOM widget on Portrait / Costume / Pose nodes, following H3
// Character Sheet Designer's integration: the hidden `state_json` STRING widget stays the only
// source of truth; the panel writes it on every change and re-reads it when it changes elsewhere
// (workflow load, undo, paste). Without addDOMWidget the plain text widget stays visible.
import { createTranslator, loadLocale, resolveLang } from "./lib/i18n.js";
import { MAX_POSES } from "./lib/selection.js";
import { serializeState } from "./lib/state.js";
import { createPickerPanel } from "./panel.js";

export const PICKER_NODES = { CharSheetPortrait: "portrait", CharSheetCostume: "costume", CharSheetPose: "pose" };
const PANEL_MIN_HEIGHT = 720;
const PANEL_HEIGHT = 760;
const MIN_NODE_WIDTH = 720;
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
  console.warn(`${LOG_PREFIX} In-node picker unavailable (${reason}); edit the state_json text widget instead.`);
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

function hideStateWidget(widget) {
  widget.type = "hidden";
  widget.hidden = true;
  widget.computeSize = () => [0, -4];
  const element = widget.element ?? widget.inputEl;
  if (element) element.hidden = true;
}

export function installPanel(node, app, api) {
  if (installed.has(node)) return installed.get(node);
  const lib = PICKER_NODES[node.comfyClass] ?? PICKER_NODES[node.type];
  if (!lib) return null;
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
      getMinHeight: () => PANEL_MIN_HEIGHT,
      getHeight: () => PANEL_HEIGHT,
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
  hideStateWidget(widget);

  let panel = null;
  let frame = 0;
  let disposed = false;
  let lastValue = String(widget.value ?? "");

  const write = (state) => {
    const json = serializeState(lib, state);
    lastValue = json;
    if (json === widget.value) return;
    const previous = widget.value;
    transaction(node, app.canvas, () => {
      widget.value = json;
      widget.callback?.(json);
    });
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

  getTranslator(app, api).then((translate) => {
    if (disposed) return;
    panel = createPickerPanel({
      lib,
      multi: lib === "pose",
      max: MAX_POSES,
      state: widget.value,
      onChange: write,
      translate,
      api,
    });
    lastValue = String(widget.value ?? "");
    host.replaceChildren(panel.root);
    frame = requestAnimationFrame(loop);
    // Runs after nodeCreated/configure have settled the size (they reset it), so only grow.
    // node.size is a typed array in current frontends, so don't test with Array.isArray.
    if (typeof node.setSize === "function" && node.size?.length >= 2 && node.size[0] < MIN_NODE_WIDTH) {
      node.setSize([MIN_NODE_WIDTH, node.size[1]]);
      node.setDirtyCanvas?.(true, true);
    }
  });

  return record;
}

export function syncInstalled(node) {
  installed.get(node)?.sync();
}
