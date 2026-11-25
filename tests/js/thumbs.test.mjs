import test from "node:test";
import assert from "node:assert/strict";
import { thumbFor } from "../../web/lib/thumbs.js";

const pose = { id: "full_P001", thumb: "/charsheet/thumb/pose/full_P001?style=grey", online: false };
const shisei = { id: "shisei-01", thumb: "/charsheet/thumb/costume/shisei-01", online: false, views: ["front", "back"] };
const single = { id: "SPR-0001", thumb: "/charsheet/thumb/costume/SPR-0001", online: false, views: [] };
const online = { id: "charadb-O001", thumb: "https://charadb.example/thumb/001.webp", online: true, views: [] };

test("gallery items use the catalogue thumb", () => {
  assert.deepEqual(thumbFor("pose", pose.id, pose), { src: pose.thumb, external: false });
  assert.deepEqual(thumbFor("costume", single.id, single, { view: "back" }), { src: single.thumb, external: false });
});

test("online-only items use their own URL and are marked external", () => {
  assert.deepEqual(thumbFor("costume", online.id, online, { view: "front" }), { src: online.thumb, external: true });
});

test("multi-view costumes and wide-lens poses use the thumb route variants", () => {
  assert.deepEqual(thumbFor("costume", shisei.id, shisei, { view: "back" }), {
    src: "/charsheet/thumb/costume/shisei-01?view=back",
    external: false,
  });
  assert.deepEqual(thumbFor("pose", pose.id, pose, { style: "grey_wide" }), {
    src: "/charsheet/thumb/pose/full_P001?style=grey_wide",
    external: false,
  });
});

test("uploads use ComfyUI /view and ignore the pose style", () => {
  assert.deepEqual(thumbFor("pose", "upload:my pose.png", null, { style: "grey_wide" }), {
    src: "/view?type=input&subfolder=charsheet%2Fpose&filename=my%20pose.png",
    external: false,
  });
});

test("an id missing from the catalogue still gets a route (it 404s and shows not found)", () => {
  assert.deepEqual(thumbFor("portrait", "gone id", undefined), {
    src: "/charsheet/thumb/portrait/gone%20id",
    external: false,
  });
});

test("a pose thumbnail always names its render set, so the address never matches an old cached drawing", () => {
  assert.deepEqual(thumbFor("pose", pose.id, pose, { style: "grey" }), {
    src: "/charsheet/thumb/pose/full_P001?style=grey",
    external: false,
  });
  assert.equal(thumbFor("pose", pose.id, pose).src, "/charsheet/thumb/pose/full_P001?style=grey");
  assert.equal(thumbFor("pose", "gone", null).src, "/charsheet/thumb/pose/gone?style=grey");
});
