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

// ---- Thumbnails ----

/** Backend thumbnail route for a gallery item; `view` (costume) and `depth` (pose) are optional. */
export function thumbUrl(lib, id, { view, depth } = {}) {
  const params = [];
  if (view) params.push(`view=${encodeURIComponent(view)}`);
  if (depth) params.push("depth=1");
  const query = params.length ? `?${params.join("&")}` : "";
  return `/charsheet/thumb/${lib}/${encodeURIComponent(id)}${query}`;
}
