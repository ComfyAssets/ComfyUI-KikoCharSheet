// One shared catalogue download per library, so every node on the canvas reuses it.

const cache = new Map();

/** Fetch `/charsheet/catalog/<lib>` once; concurrent and later callers share the promise. Failures are not cached. */
export function getCatalog(lib, fetchFn = (url) => fetch(url)) {
  if (cache.has(lib)) return cache.get(lib);
  const promise = (async () => {
    const resp = await fetchFn(`/charsheet/catalog/${lib}`);
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
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
