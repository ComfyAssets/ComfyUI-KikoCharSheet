import test from "node:test";
import assert from "node:assert/strict";
import { setValueOnce } from "../../web/lib/widget.js";

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
