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
