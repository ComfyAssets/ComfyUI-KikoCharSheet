import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolveLang, createTranslator } from "../../web/lib/i18n.js";

const load = (l) => JSON.parse(readFileSync(new URL(`../../web/locales/${l}.json`, import.meta.url), "utf8"));
const leaves = (o, p = "") =>
  Object.entries(o).flatMap(([k, v]) => (v && typeof v === "object" ? leaves(v, `${p}${k}.`) : [`${p}${k}`]));

test("resolveLang", () => {
  assert.equal(resolveLang("zh-TW"), "zh");
  assert.equal(resolveLang("zh"), "zh");
  assert.equal(resolveLang("en"), "en");
  assert.equal(resolveLang("fr"), "en");
  assert.equal(resolveLang(undefined, ["de", "zh-CN"]), "zh");
  assert.equal(resolveLang(undefined, ["de"]), "en");
  assert.equal(resolveLang(undefined, undefined), "en");
});

test("translator interpolates, falls back to key, translates data", () => {
  const { t, d } = createTranslator({ a: { b: "{{count}} / {{max}} selected" } }, { 坐姿: "Sitting" });
  assert.equal(t("a.b", { count: 2, max: 13 }), "2 / 13 selected");
  assert.equal(t("a.b"), "{{count}} / {{max}} selected");
  assert.equal(t("missing.key"), "missing.key");
  assert.equal(d("坐姿"), "Sitting");
  assert.equal(d("其他"), "其他");
  assert.equal(d(5), 5);
});

test("zh and en have identical key sets", () => {
  const en = leaves(load("en")).sort();
  const zh = leaves(load("zh")).sort();
  assert.deepEqual(zh, en);
  assert.ok(en.length > 100);
});

test("every string is non-empty and placeholders match between languages", () => {
  const en = load("en"), zh = load("zh");
  const get = (o, k) => k.split(".").reduce((c, p) => c[p], o);
  for (const k of leaves(en)) {
    const a = get(en, k), b = get(zh, k);
    assert.ok(typeof a === "string" && a && typeof b === "string" && b, k);
    const vars = (s) => (s.match(/\{\{\w+\}\}/g) || []).sort().join();
    assert.equal(vars(a), vars(b), k);
  }
});

test("required keys exist", () => {
  const en = load("en");
  const t = createTranslator(en, {}).t;
  assert.equal(t("counter", { count: 1, max: 13 }), "1 / 13 selected");
  for (const k of ["panel.portrait", "panel.costume", "panel.pose", "search.pose", "sheet.pictureOrderHint",
    "uploads.prompt", "uploads.size", "sfw.confirm", "state.online", "tray.flip"]) {
    assert.notEqual(t(k), k, k);
  }
});
