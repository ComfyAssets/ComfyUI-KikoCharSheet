// Pure helpers for the picker's batched grid, thumbnails and uploads (no DOM, no ComfyUI imports).
// Ported from the ai-pose-gallery fork's web/gallery.js; upload rules mirror charsheet/uploads.py.

export const BATCH_SIZE = 60;

/** How many cards should be rendered after appending one more batch. */
export function nextRenderCount(rendered, total, batch = BATCH_SIZE) {
  return Math.min(total, rendered + batch);
}

/** Smallest whole number of batches (capped at total) that includes the item at `index`. */
export function renderCountToInclude(index, total, batch = BATCH_SIZE) {
  return Math.min(total, (Math.floor(index / batch) + 1) * batch);
}

// ---- Uploads ----

const MAX_UPLOAD_NAME_LENGTH = 200;
export const UPLOAD_PREFIX = "upload:";
export const UPLOAD_EXTENSIONS = [".png", ".jpg", ".jpeg", ".webp"];
export const UPLOAD_ACCEPT = UPLOAD_EXTENSIONS.join(",");
export const UPLOAD_SUBFOLDER = "charsheet";
export const MIN_UPLOAD_WIDTH = 1024;

/** File name of an `upload:<name>` id (split on the first `:` only), otherwise null. */
export function parseUploadId(id) {
  if (typeof id !== "string" || !id.startsWith(UPLOAD_PREFIX)) return null;
  return id.slice(UPLOAD_PREFIX.length);
}

export function formatUploadId(name) {
  return `${UPLOAD_PREFIX}${name}`;
}

/** ComfyUI /view URL for an upload (pass through api.apiURL before use). */
export function uploadThumbUrl(lib, name) {
  return `/view?type=input&subfolder=${encodeURIComponent(`${UPLOAD_SUBFOLDER}/${lib}`)}&filename=${encodeURIComponent(name)}`;
}

/** Mirror of uploads.py is_valid_upload_name; length is counted in code points. */
export function isValidUploadName(name) {
  if (typeof name !== "string" || !name || name.startsWith(".")) return false;
  if (name.includes("..") || name.includes("/") || name.includes("\\")) return false;
  for (const ch of name) {
    const code = ch.codePointAt(0);
    if (code < 32 || code === 127) return false;
  }
  const lower = name.toLowerCase();
  if (!UPLOAD_EXTENSIONS.some((ext) => lower.endsWith(ext))) return false;
  return [...name].length <= MAX_UPLOAD_NAME_LENGTH;
}

/** Same name rules as the Python side, applied to a File-like object. */
export function isValidUploadFile(file) {
  if (!file || typeof file.name !== "string") return false;
  return isValidUploadName(file.name);
}

/** True when the original image is narrower than recommended. */
export function sizeWarning(width) {
  return width < MIN_UPLOAD_WIDTH;
}

// ---- Portrait crop frame ----

export const CROP_ASPECT = 4 / 5;

const clamp01 = (v) => (Number.isFinite(v) ? Math.min(1, Math.max(0, v)) : 0.5);

/**
 * The 4:5 crop of a width x height image, in source pixels. `pos` is where the frame sits along
 * the axis it can move on: `x` and `y` run from 0 (left / top) to 1 (right / bottom), 0.5 = centred.
 */
export function cropRect(width, height, pos = {}) {
  const wide = width / height > CROP_ASPECT;
  const sw = wide ? Math.min(width, Math.round(height * CROP_ASPECT)) : width;
  const sh = wide ? height : Math.min(height, Math.round(width / CROP_ASPECT));
  return {
    sx: Math.round((width - sw) * clamp01(pos.x ?? 0.5)),
    sy: Math.round((height - sh) * clamp01(pos.y ?? 0.5)),
    sw,
    sh,
  };
}

/** CSS box (percent of the image) of the crop frame for the same arguments as `cropRect`. */
export function frameBox(width, height, pos = {}) {
  const { sx, sy, sw, sh } = cropRect(width, height, pos);
  const pct = (part, whole) => `${(part / whole) * 100}%`;
  return { left: pct(sx, width), top: pct(sy, height), width: pct(sw, width), height: pct(sh, height) };
}

/** Frame position after dragging it by (dx, dy) image-fractions of the preview; stays inside the image. */
export function dragFrame(width, height, pos, dx, dy) {
  const { sw, sh } = cropRect(width, height);
  const freeX = 1 - sw / width;
  const freeY = 1 - sh / height;
  return {
    x: freeX > 0 ? clamp01(clamp01(pos?.x ?? 0.5) + dx / freeX) : 0.5,
    y: freeY > 0 ? clamp01(clamp01(pos?.y ?? 0.5) + dy / freeY) : 0.5,
  };
}

/** True when the image is already 4:5, so there is nothing to crop. */
export function isFullFrame(width, height) {
  const { sw, sh } = cropRect(width, height);
  return sw === width && sh === height;
}

/** A cropped upload is stored as PNG: swap the extension, keep the rest of the name. */
export function croppedFileName(name) {
  const dot = name.lastIndexOf(".");
  return `${dot > 0 ? name.slice(0, dot) : name}.png`;
}

// ---- Thumbnails ----

/** Backend thumbnail route for a gallery item; `view` (costume) and `depth` (pose) are optional. */
export function thumbUrl(lib, id, { view, depth } = {}) {
  const params = [];
  if (view) params.push(`view=${encodeURIComponent(view)}`);
  if (depth) params.push("depth=1");
  const query = params.length ? `?${params.join("&")}` : "";
  return `/charsheet/thumb/${lib}/${encodeURIComponent(id)}${query}`;
}
