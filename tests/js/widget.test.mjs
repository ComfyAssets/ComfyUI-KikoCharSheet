import test from "node:test";
import assert from "node:assert/strict";
import { setValueOnce, watchCallback } from "../../web/lib/widget.js";

/** Like the current frontend's DOM widget: the value setter itself calls `callback`. */
class SetterWidget {
  #v = "";
  calls = [];
  callback = (v) => this.calls.push(v);
  get value() {
    return this.#v;
  }
  set value(v) {
    this.#v = v;
    this.callback?.(this.value);
  }
}

test("a setter that already calls the callback fires it exactly once", () => {
  const w = new SetterWidget();
  const original = w.callback;
  setValueOnce(w, "a");
  assert.deepEqual(w.calls, ["a"]);
  assert.equal(w.value, "a");
  assert.equal(w.callback, original);
});

test("a plain widget gets its callback called once with the widget as this", () => {
  const seen = [];
  const w = {
    value: "",
    callback(v) {
      seen.push([this, v]);
    },
  };
  setValueOnce(w, "b");
  assert.equal(w.value, "b");
  assert.deepEqual(seen, [[w, "b"]]);
});

test("a prototype callback is not shadowed afterwards; no callback is fine", () => {
  const proto = { callback() {} };
  const w = Object.create(proto);
  w.value = "";
  setValueOnce(w, "c");
  assert.equal(Object.prototype.hasOwnProperty.call(w, "callback"), false);
  const bare = { value: "" };
  setValueOnce(bare, "d");
  assert.equal(bare.value, "d");
  assert.equal("callback" in bare, false);
});

test("watchCallback runs the original callback first, then the watcher, with the same this", () => {
  const order = [];
  const w = {
    value: "",
    callback(v) {
      order.push(["orig", this, v]);
      return "kept";
    },
  };
  const unwatch = watchCallback(w, (v) => order.push(["watch", v]));
  assert.equal(w.callback("x"), "kept");
  assert.deepEqual(order, [["orig", w, "x"], ["watch", "x"]]);
  unwatch();
  w.callback("y");
  assert.equal(order.length, 3);
});

test("unwatch restores an own callback, or removes the shadow of a prototype one", () => {
  const own = { callback() {} };
  const original = own.callback;
  const unwatchOwn = watchCallback(own, () => {});
  assert.notEqual(own.callback, original);
  unwatchOwn();
  assert.equal(own.callback, original);

  const proto = { callback() {} };
  const inherited = Object.create(proto);
  const unwatchInherited = watchCallback(inherited, () => {});
  assert.equal(Object.prototype.hasOwnProperty.call(inherited, "callback"), true);
  unwatchInherited();
  assert.equal(Object.prototype.hasOwnProperty.call(inherited, "callback"), false);

  const bare = {};
  const unwatchBare = watchCallback(bare, () => {});
  bare.callback("z");
  unwatchBare();
  assert.equal("callback" in bare, false);
});

test("a watcher wrapped by someone else goes quiet on unwatch and keeps their wrapper", () => {
  const seen = [];
  const w = { callback: (v) => seen.push(["orig", v]) };
  const unwatch = watchCallback(w, (v) => seen.push(["watch", v]));
  const ours = w.callback;
  const theirs = (v) => {
    seen.push(["theirs", v]);
    ours(v);
  };
  w.callback = theirs;
  unwatch();
  assert.equal(w.callback, theirs);
  w.callback("q");
  assert.deepEqual(seen, [["theirs", "q"], ["orig", "q"]]);
  unwatch(); // idempotent
});

test("watchCallback works with setValueOnce on a setter widget", () => {
  const w = new SetterWidget();
  const seen = [];
  const unwatch = watchCallback(w, (v) => seen.push(v));
  setValueOnce(w, "a");
  assert.deepEqual(w.calls, ["a"]);
  assert.deepEqual(seen, ["a"]);
  unwatch();
  setValueOnce(w, "b");
  assert.deepEqual(seen, ["a"]);
  assert.deepEqual(w.calls, ["a", "b"]);
});

test("a throwing watcher does not break the original callback", () => {
  const seen = [];
  const w = { callback: (v) => seen.push(v) };
  watchCallback(w, () => {
    throw new Error("boom");
  });
  const warnings = [];
  const realWarn = console.warn;
  console.warn = (...args) => warnings.push(args);
  try {
    assert.doesNotThrow(() => w.callback("k"));
  } finally {
    console.warn = realWarn;
  }
  assert.deepEqual(seen, ["k"]);
  assert.equal(warnings.length, 1);
  assert.match(String(warnings[0][1]), /boom/);
});
