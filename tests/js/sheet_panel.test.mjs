// Exercises the Pose Sheet panel's refresh logic with a tiny fake DOM (no browser): triggers,
// debounce, stale-response dropping, empty selection, error handling and upstream callback cleanup.
import test, { mock } from "node:test";
import assert from "node:assert/strict";
import { createSheetPanel } from "../../web/sheet_panel.js";

class FakeElement {
  constructor(tag) {
    this.tagName = tag.toUpperCase();
    this.children = [];
    this.attrs = new Map();
    this.listeners = {};
    this.classes = new Set();
    this.hidden = false;
    this.textContent = "";
    this.value = "";
    this.readOnly = false;
    this.placeholder = "";
    const classes = this.classes;
    this.classList = {
      add: (c) => classes.add(c),
      remove: (c) => classes.delete(c),
      contains: (c) => classes.has(c),
      toggle: (c, on) => ((on ?? !classes.has(c)) ? classes.add(c) : classes.delete(c)),
    };
  }
  set className(v) {
    this.classes.clear();
    for (const c of String(v).split(/\s+/).filter(Boolean)) this.classes.add(c);
  }
  get className() {
    return [...this.classes].join(" ");
  }
  get src() {
    return this.attrs.get("src") ?? "";
  }
  set src(v) {
    this.attrs.set("src", String(v));
  }
  setAttribute(k, v) {
    if (k === "hidden") this.hidden = true;
    else this.attrs.set(k, String(v));
  }
  getAttribute(k) {
    return this.attrs.has(k) ? this.attrs.get(k) : null;
  }
  removeAttribute(k) {
    this.attrs.delete(k);
  }
  appendChild(child) {
    this.children.push(child);
    return child;
  }
  addEventListener(type, fn) {
    (this.listeners[type] ??= []).push(fn);
  }
  dispatch(type, extra = {}) {
    const event = { type, target: this, stopped: false, stopPropagation() { this.stopped = true; }, ...extra };
    for (const fn of this.listeners[type] ?? []) fn(event);
    return event;
  }
  find(pred) {
    if (pred(this)) return this;
    for (const c of this.children) {
      const hit = c instanceof FakeElement ? c.find(pred) : null;
      if (hit) return hit;
    }
    return null;
  }
  byClass(c) {
    return this.find((e) => e.classes.has(c));
  }
  all(pred, out = []) {
    if (pred(this)) out.push(this);
    for (const c of this.children) if (c instanceof FakeElement) c.all(pred, out);
    return out;
  }
}

globalThis.document = {
  activeElement: null,
  createElement: (tag) => new FakeElement(tag),
  createTextNode: (text) => ({ text }),
};

const translate = {
  t: (key, vars) => (vars ? `${key} ${JSON.stringify(vars)}` : key),
  d: (v) => v,
};
const flush = () => new Promise((r) => setImmediate(r));

function makeGraph({ ids = ["a", "b", "c"], linked = true, originType = "CharSheetPose" } = {}) {
  const poseWidget = { name: "state_json", value: JSON.stringify({ ids, flip: [], use_depth: false }) };
  const pickerCalls = [];
  poseWidget.callback = (v) => pickerCalls.push(v);
  const pickerCallback = poseWidget.callback;
  const pose = { id: 1, type: originType, comfyClass: originType, widgets: [poseWidget] };
  const graph = { links: new Map([[10, { id: 10, origin_id: 1, origin_slot: 5 }]]), getNodeById: (id) => (id === 1 ? pose : null) };
  const sheet = { id: 2, graph, inputs: [{ name: "selection", link: linked ? 10 : null }] };
  return { graph, sheet, pose, poseWidget, pickerCalls, pickerCallback };
}

function fakeApi(responder) {
  const calls = [];
  return {
    calls,
    fetchApi: (url, opts) => {
      const body = JSON.parse(opts.body);
      calls.push({ url, body });
      return responder(body, calls.length);
    },
  };
}

const okResponse = (body, extra = {}) =>
  Promise.resolve({
    ok: true,
    status: 200,
    json: async () => ({
      width: 2048,
      height: 2048,
      megapixels: 4.19,
      warnings: [],
      image: `data:image/png;base64,${body.ids.length}`,
      ...extra,
    }),
  });

function setup(opts = {}, responder = okResponse) {
  const g = makeGraph(opts);
  const api = fakeApi(responder);
  const changes = [];
  const panel = createSheetPanel({ node: g.sheet, state: opts.state ?? "", onChange: (s) => changes.push(s), translate, api });
  const img = panel.root.byClass("cs-sheet-image");
  const status = panel.root.byClass("cs-sheet-status");
  const readout = panel.root.byClass("cs-sheet-readout");
  return { ...g, api, changes, panel, img, status, readout };
}

test.beforeEach(() => mock.timers.enable({ apis: ["setTimeout"] }));
test.afterEach(() => mock.timers.reset());

test("a connected Pose node's selection is previewed once after the 300 ms debounce", async () => {
  const s = setup();
  s.panel.tick();
  s.panel.onConnectionsChange();
  mock.timers.tick(299);
  assert.equal(s.api.calls.length, 0);
  mock.timers.tick(1);
  await flush();
  assert.equal(s.api.calls.length, 1);
  assert.equal(s.api.calls[0].url, "/charsheet/sheet/preview");
  assert.deepEqual(s.api.calls[0].body.ids, ["a", "b", "c"]);
  assert.equal(s.api.calls[0].body.state.columns, "auto");
  assert.equal(s.img.hidden, false);
  assert.equal(s.img.src, "data:image/png;base64,3");
  assert.match(s.readout.textContent, /sheet\.readout .*"megapixels":"4\.19"/);
  // Same body again: no refetch.
  s.panel.onConnectionsChange();
  mock.timers.tick(300);
  await flush();
  assert.equal(s.api.calls.length, 1);
  s.panel.destroy();
});

test("changing a setting writes state and refetches with it", async () => {
  const s = setup();
  mock.timers.tick(300);
  await flush();
  const columns = s.panel.root.find((e) => e.tagName === "SELECT");
  columns.value = "2";
  columns.dispatch("change");
  assert.equal(s.changes.at(-1).columns, 2);
  mock.timers.tick(300);
  await flush();
  assert.equal(s.api.calls.length, 2);
  assert.equal(s.api.calls[1].body.state.columns, 2);
  s.panel.destroy();
});

test("manual size snaps to 32 and clamps on change and blur; the readout follows at once", async () => {
  const s = setup();
  mock.timers.tick(300);
  await flush();
  const manual = s.panel.root.find((e) => e.tagName === "BUTTON" && e.textContent === "sheet.sizeManual");
  manual.dispatch("click");
  assert.equal(s.changes.at(-1).size_mode, "manual");
  assert.equal(s.changes.at(-1).width, 2048); // seeded from the Auto size
  const [width, height] = s.panel.root.all((e) => e.classes.has("cs-sheet-size"));
  assert.equal(width.readOnly, false);
  width.value = "1000";
  width.dispatch("change");
  assert.equal(width.value, "992");
  assert.equal(s.changes.at(-1).width, 992);
  assert.match(s.readout.textContent, /"width":992,"height":2048,"megapixels":"2\.03"/);
  height.value = "99999";
  height.dispatch("blur");
  assert.equal(height.value, "8192");
  assert.equal(s.changes.at(-1).height, 8192);
  mock.timers.tick(300);
  await flush();
  assert.deepEqual([s.api.calls.at(-1).body.state.width, s.api.calls.at(-1).body.state.height], [992, 8192]);
  s.panel.destroy();
});

test("in Auto mode the size fields are read-only and ignore edits", async () => {
  const s = setup();
  mock.timers.tick(300);
  await flush();
  const width = s.panel.root.byClass("cs-sheet-size");
  assert.equal(width.readOnly, true);
  assert.equal(width.value, "2048"); // computed size from the preview
  width.value = "512";
  width.dispatch("change");
  assert.equal(s.changes.length, 0);
  s.panel.destroy();
});

test("an empty selection shows 'no poses' and calls no route", async () => {
  const s = setup({ ids: [] });
  mock.timers.tick(300);
  await flush();
  assert.equal(s.api.calls.length, 0);
  assert.equal(s.status.textContent, "sheet.noPoses");
  assert.equal(s.img.hidden, true);
  s.panel.destroy();
});

test("disconnecting drops the preview and shows 'no poses'", async () => {
  const s = setup();
  mock.timers.tick(300);
  await flush();
  s.sheet.inputs[0].link = null;
  s.panel.onConnectionsChange();
  mock.timers.tick(300);
  await flush();
  assert.equal(s.status.textContent, "sheet.noPoses");
  assert.equal(s.img.hidden, true);
  s.panel.destroy();
});

test("a non-Pose origin waits for a run, then previews ui.selection", async () => {
  const s = setup({ originType: "Reroute" });
  mock.timers.tick(300);
  await flush();
  assert.equal(s.api.calls.length, 0);
  assert.equal(s.status.textContent, "sheet.previewAfterRun");
  s.panel.onExecuted({ selection: [JSON.stringify({ ids: ["x", "y"], flip: ["y"], use_depth: true })], warnings: [] });
  mock.timers.tick(300);
  await flush();
  assert.equal(s.api.calls.length, 1);
  assert.deepEqual(s.api.calls[0].body, { ids: ["x", "y"], flip: ["y"], use_depth: true, state: s.api.calls[0].body.state });
  assert.equal(s.panel.root.byClass("cs-sheet-note").hidden, false);
  s.panel.destroy();
});

test("upstream state_json edits refresh through the wrapped callback, which is removed on destroy", async () => {
  const s = setup();
  mock.timers.tick(300);
  await flush(); // first refresh installs the watcher
  assert.notEqual(s.poseWidget.callback, s.pickerCallback);
  s.poseWidget.value = JSON.stringify({ ids: ["a"], flip: [], use_depth: false });
  s.poseWidget.callback(s.poseWidget.value);
  assert.deepEqual(s.pickerCalls, [s.poseWidget.value]); // the picker's own callback still runs
  mock.timers.tick(300);
  await flush();
  assert.equal(s.api.calls.length, 2);
  assert.deepEqual(s.api.calls[1].body.ids, ["a"]);
  s.panel.destroy();
  assert.equal(s.poseWidget.callback, s.pickerCallback);
});

test("tick() notices upstream edits that bypass callbacks (undo, load)", async () => {
  const s = setup();
  s.panel.tick();
  mock.timers.tick(300);
  await flush();
  s.poseWidget.value = JSON.stringify({ ids: ["c", "b"], flip: [], use_depth: false });
  s.panel.tick();
  mock.timers.tick(300);
  await flush();
  assert.deepEqual(s.api.calls.at(-1).body.ids, ["c", "b"]);
  s.panel.destroy();
});

test("a stale response is dropped when a newer request was sent", async () => {
  const pending = [];
  const s = setup({}, (body) => new Promise((resolve) => pending.push({ body, resolve })));
  mock.timers.tick(300);
  await flush();
  s.poseWidget.value = JSON.stringify({ ids: ["a"], flip: [], use_depth: false });
  s.panel.tick();
  mock.timers.tick(300);
  await flush();
  assert.equal(pending.length, 2);
  // Newer answers first, then the stale one arrives.
  pending[1].resolve(await okResponse(pending[1].body));
  await flush();
  pending[0].resolve(await okResponse(pending[0].body));
  await flush();
  assert.equal(s.img.src, "data:image/png;base64,1");
  s.panel.destroy();
});

test("a route error is shown inline and the last good preview stays", async () => {
  let fail = false;
  const s = setup({}, (body) =>
    fail
      ? Promise.resolve({ ok: false, status: 400, json: async () => ({ error: "unknown pose id: zz" }) })
      : okResponse(body),
  );
  mock.timers.tick(300);
  await flush();
  fail = true;
  s.poseWidget.value = JSON.stringify({ ids: ["zz"], flip: [], use_depth: false });
  s.panel.tick();
  mock.timers.tick(300);
  await flush();
  assert.equal(s.img.hidden, false);
  assert.equal(s.img.src, "data:image/png;base64,3");
  assert.match(s.status.textContent, /sheet\.previewError .*unknown pose id: zz/);
  assert.equal(s.status.classes.has("cs-error-text"), true);
  s.panel.destroy();
});

test("setState re-renders the controls without writing back", async () => {
  const s = setup();
  s.panel.setState(JSON.stringify({ columns: 4, panel_aspect: "1:1", size_mode: "manual", width: 1024, height: 1536 }));
  assert.equal(s.changes.length, 0);
  const selects = s.panel.root.all((e) => e.tagName === "SELECT");
  assert.deepEqual(selects.map((e) => e.value), ["4", "1:1", "white"]);
  assert.match(s.readout.textContent, /"width":1024,"height":1536/);
  s.panel.destroy();
});

test("keys pressed in the panel stay in it, except Ctrl/Meta combos and Escape", () => {
  const s = setup();
  assert.equal(s.panel.root.dispatch("keydown", { key: "Delete" }).stopped, true);
  assert.equal(s.panel.root.dispatch("keydown", { key: "z", ctrlKey: true }).stopped, false);
  assert.equal(s.panel.root.dispatch("keydown", { key: "Escape" }).stopped, false);
  s.panel.destroy();
});

test("nothing runs after destroy", async () => {
  const s = setup();
  s.panel.destroy();
  s.panel.onConnectionsChange();
  s.panel.tick();
  mock.timers.tick(1000);
  await flush();
  assert.equal(s.api.calls.length, 0);
});
