import test from "node:test";
import assert from "node:assert/strict";
import {
  BATCH_SIZE, nextRenderCount, renderCountToInclude, parseUploadId, formatUploadId,
  uploadThumbUrl, isValidUploadName, isValidUploadFile, thumbUrl,
} from "../../web/lib/gallery.js";

test("batching", () => {
  assert.equal(BATCH_SIZE, 60);
  assert.equal(nextRenderCount(0, 200), 60);
  assert.equal(nextRenderCount(180, 200), 200);
  assert.equal(renderCountToInclude(0, 200), 60);
  assert.equal(renderCountToInclude(60, 200), 120);
  assert.equal(renderCountToInclude(199, 200), 200);
});

test("upload ids split on the first colon only", () => {
  assert.equal(parseUploadId("upload:我的 头像 (1).JPG"), "我的 头像 (1).JPG");
  assert.equal(parseUploadId("upload:a:b.png"), "a:b.png");
  assert.equal(parseUploadId("f71f980dde3"), null);
  assert.equal(parseUploadId(null), null);
  assert.equal(formatUploadId("me.png"), "upload:me.png");
});

test("valid names match the Python vectors", () => {
  for (const n of ["me.png", "我的 头像 (1).JPG", "x.webp", "a".repeat(195) + ".jpeg"]) {
    assert.equal(isValidUploadName(n), true, n);
  }
});

test("invalid names match the Python vectors", () => {
  const bad = ["../a.png", "a/b.png", "a\\b.png", ".hidden.png", "a.gif", "a\x00.png", "a\nb.png",
    "a\tb.png", "a\x7f.png", "a".repeat(201) + ".png", "a".repeat(196) + ".jpeg", "", null, 5];
  for (const n of bad) assert.equal(isValidUploadName(n), false, JSON.stringify(n));
});

test("isValidUploadFile checks the file name", () => {
  assert.equal(isValidUploadFile({ name: "ok.PNG" }), true);
  assert.equal(isValidUploadFile({ name: "ok.gif" }), false);
  assert.equal(isValidUploadFile({ name: ".png" }), false);
  assert.equal(isValidUploadFile(null), false);
});

test("uploadThumbUrl encodes CJK, spaces and parentheses", () => {
  assert.equal(
    uploadThumbUrl("portrait", "我的 头像 (1).JPG"),
    "/view?type=input&subfolder=charsheet%2Fportrait&filename=" + encodeURIComponent("我的 头像 (1).JPG"),
  );
  assert.match(uploadThumbUrl("pose", "a b.png"), /filename=a%20b\.png$/);
});

test("thumbUrl builds the route with optional query", () => {
  assert.equal(thumbUrl("pose", "SPR-0001"), "/charsheet/thumb/pose/SPR-0001");
  assert.equal(thumbUrl("costume", "a/b 中"), "/charsheet/thumb/costume/" + encodeURIComponent("a/b 中"));
  assert.equal(thumbUrl("costume", "X", { view: "back" }), "/charsheet/thumb/costume/X?view=back");
  assert.equal(thumbUrl("pose", "X", { depth: true }), "/charsheet/thumb/pose/X?depth=1");
  assert.equal(thumbUrl("pose", "X", { view: "front", depth: true }), "/charsheet/thumb/pose/X?view=front&depth=1");
});
