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
  assert.equal(thumbUrl("pose", "X", { style: "grey_wide" }), "/charsheet/thumb/pose/X?style=grey_wide");
  assert.equal(thumbUrl("pose", "X", { style: "grey" }), "/charsheet/thumb/pose/X?style=grey");
  assert.equal(thumbUrl("pose", "X", { view: "front", style: "grey_wide" }), "/charsheet/thumb/pose/X?view=front&style=grey_wide");
});

test("cropRect gives a centred 4:5 crop and follows the frame position", async () => {
  const { cropRect } = await import("../../web/lib/gallery.js");
  assert.deepEqual(cropRect(941, 1672), { sx: 0, sy: 248, sw: 941, sh: 1176 }); // tall: full width
  assert.deepEqual(cropRect(941, 1672, { y: 0 }), { sx: 0, sy: 0, sw: 941, sh: 1176 });
  assert.deepEqual(cropRect(941, 1672, { y: 1 }), { sx: 0, sy: 496, sw: 941, sh: 1176 });
  assert.deepEqual(cropRect(2000, 1000, { x: 1 }), { sx: 1200, sy: 0, sw: 800, sh: 1000 }); // wide: full height
  assert.deepEqual(cropRect(2000, 1000, { x: 7, y: NaN }), { sx: 1200, sy: 0, sw: 800, sh: 1000 });
  assert.deepEqual(cropRect(1024, 1280, { x: 0, y: 1 }), { sx: 0, sy: 0, sw: 1024, sh: 1280 });
});

test("frameBox matches cropRect as percentages", async () => {
  const { frameBox } = await import("../../web/lib/gallery.js");
  assert.deepEqual(frameBox(2000, 1000, { x: 0 }), { left: "0%", top: "0%", width: "40%", height: "100%" });
  assert.deepEqual(frameBox(1000, 2500, { y: 1 }), { left: "0%", top: "50%", width: "100%", height: "50%" });
});

test("dragFrame moves along the free axis only and stops at the edges", async () => {
  const { dragFrame } = await import("../../web/lib/gallery.js");
  // 1000x2500: the frame is half the height, so dragging by a quarter of the image moves it half its travel.
  assert.deepEqual(dragFrame(1000, 2500, { x: 0.5, y: 0.5 }, 0.3, -0.25), { x: 0.5, y: 0 });
  assert.deepEqual(dragFrame(1000, 2500, { x: 0.5, y: 0.5 }, 0, 0.125), { x: 0.5, y: 0.75 });
  assert.deepEqual(dragFrame(1000, 2500, { x: 0.5, y: 0.5 }, 0, 9), { x: 0.5, y: 1 });
  assert.deepEqual(dragFrame(2000, 1000, { x: 0, y: 0.5 }, 0.3, 0.4), { x: 0.5, y: 0.5 });
  assert.deepEqual(dragFrame(1024, 1280, { x: 0.5, y: 0.5 }, 0.2, 0.2), { x: 0.5, y: 0.5 });
});

test("isFullFrame and croppedFileName", async () => {
  const { isFullFrame, croppedFileName, isValidUploadName } = await import("../../web/lib/gallery.js");
  assert.equal(isFullFrame(1024, 1280), true);
  assert.equal(isFullFrame(1600, 2000), true);
  assert.equal(isFullFrame(941, 1672), false);
  assert.equal(croppedFileName("me.JPG"), "me.png");
  assert.equal(croppedFileName("我的 头像 (1).webp"), "我的 头像 (1).png");
  assert.equal(croppedFileName("a.b.jpeg"), "a.b.png");
  assert.equal(isValidUploadName(croppedFileName("ok.jpeg")), true);
});
