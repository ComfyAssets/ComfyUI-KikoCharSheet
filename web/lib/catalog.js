// One shared catalogue download per library, so every node on the canvas reuses it.

const cache = new Map();

/** Fetch `/charsheet/catalog/<lib>` once; concurrent and later callers share the promise. Failures are not cached. */
export function getCatalog(lib, fetchFn = (url) => fetch(url)) {
  if (cache.has(lib)) return cache.get(lib);
  const promise = (async () => {
    const resp = await fetchFn(`/charsheet/catalog/${lib}`);
    if (!resp.ok) throw await loadError(resp);
    return resp.json();
  })();
  cache.set(lib, promise);
  promise.catch(() => {
    if (cache.get(lib) === promise) cache.delete(lib);
  });
  return promise;
}

export function clearCatalogCache() {
  cache.clear();
}

/** A built-in costume with no picture: picking it sends its prompt text only. */
export function isTextOnly(item) {
  return item?.source === "builtin";
}

/** An Error for a failed catalogue request, with the server's own message when it sent one. */
async function loadError(resp) {
  let detail = "";
  try {
    const body = await resp.json();
    if (typeof body?.error === "string") detail = body.error;
  } catch {
    // not JSON: the status alone is the message
  }
  const error = new Error(detail ? `${detail} (HTTP ${resp.status})` : `HTTP ${resp.status}`);
  error.status = resp.status;
  return error;
}

/** The backend answers 503 while the gallery files have not been downloaded yet. */
export function needsSetup(err) {
  return err?.status === 503;
}

/** The command that downloads the gallery files, run in the pack's folder. */
export const SETUP_COMMAND = "python3 scripts/setup_assets.py --download";
