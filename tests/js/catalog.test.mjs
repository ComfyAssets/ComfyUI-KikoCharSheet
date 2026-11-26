import test, { beforeEach } from "node:test";
import assert from "node:assert/strict";
import { getCatalog, clearCatalogCache } from "../../web/lib/catalog.js";

beforeEach(() => clearCatalogCache());

const okFetch = (calls) => async (url) => {
  calls.push(url);
  return { ok: true, status: 200, json: async () => [{ id: "x" }] };
};

test("getCatalog called twice fetches once", async () => {
  const calls = [];
  const [a, b] = await Promise.all([getCatalog("pose", okFetch(calls)), getCatalog("pose", okFetch(calls))]);
  await getCatalog("pose", okFetch(calls));
  assert.deepEqual(calls, ["/charsheet/catalog/pose"]);
  assert.deepEqual(a, [{ id: "x" }]);
  assert.equal(a, b);
});

test("separate libs fetch separately", async () => {
  const calls = [];
  await getCatalog("pose", okFetch(calls));
  await getCatalog("costume", okFetch(calls));
  assert.equal(calls.length, 2);
});

test("a failed load is not cached so retry works", async () => {
  const bad = async () => ({ ok: false, status: 503, json: async () => ({}) });
  await assert.rejects(getCatalog("pose", bad), /503/);
  const calls = [];
  assert.deepEqual(await getCatalog("pose", okFetch(calls)), [{ id: "x" }]);
});

test("isTextOnly is true for the pack's built-in costumes only", async () => {
  const { isTextOnly } = await import("../../web/lib/catalog.js");
  assert.equal(isTextOnly({ id: "nude", source: "builtin" }), true);
  assert.equal(isTextOnly({ id: "SPR-0001", source: "gia" }), false);
  assert.equal(isTextOnly(undefined), false);
});

test("a failed load keeps the server's message and status", async () => {
  const missing = async () => ({ ok: false, status: 503, json: async () => ({ error: "Gallery data not found" }) });
  await assert.rejects(getCatalog("costume", missing), (err) => {
    assert.equal(err.status, 503);
    assert.equal(err.message, "Gallery data not found (HTTP 503)");
    return true;
  });
  const broken = async () => ({ ok: false, status: 500, json: async () => { throw new Error("not json"); } });
  await assert.rejects(getCatalog("pose", broken), (err) => err.status === 500 && err.message === "HTTP 500");
});

test("needsSetup is true only when the gallery files are missing", async () => {
  const { needsSetup } = await import("../../web/lib/catalog.js");
  assert.equal(needsSetup(Object.assign(new Error("x"), { status: 503 })), true);
  assert.equal(needsSetup(Object.assign(new Error("x"), { status: 500 })), false);
  assert.equal(needsSetup(new Error("offline")), false);
});
