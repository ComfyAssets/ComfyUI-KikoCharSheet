// Which thumbnail URL a card, footer or tray chip shows (no DOM, no ComfyUI imports).
import { parseUploadId, thumbUrl, uploadThumbUrl } from "./gallery.js";

/**
 * Thumbnail for `id` (a gallery id or `upload:<name>`); `item` is its catalogue row, if any.
 * Returns {src, external}: external URLs are used as is, all others go through api.apiURL.
 */
export function thumbFor(lib, id, item, { view, depth } = {}) {
  const uploadName = parseUploadId(id);
  if (uploadName !== null) return { src: uploadThumbUrl(lib, uploadName), external: false };
  if (!item) return { src: thumbUrl(lib, id), external: false };
  if (item.online) return { src: item.thumb, external: true };
  if (lib === "costume" && view && Array.isArray(item.views) && item.views.length > 1) {
    return { src: thumbUrl(lib, id, { view }), external: false };
  }
  if (lib === "pose" && depth) return { src: thumbUrl(lib, id, { depth: true }), external: false };
  return { src: item.thumb, external: false };
}
