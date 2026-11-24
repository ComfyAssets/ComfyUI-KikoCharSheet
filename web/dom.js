// Small DOM helpers shared by the panel modules. Text always goes through textContent or
// setAttribute, never innerHTML, so file names and ids can't inject markup.

export function el(tag, props = {}, children = []) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(props)) {
    if (value === undefined || value === null || value === false) continue;
    if (key === "class") node.className = value;
    else if (key === "text") node.textContent = value;
    else if (key.startsWith("on") && typeof value === "function") node.addEventListener(key.slice(2), value);
    else node.setAttribute(key, value === true ? "" : String(value));
  }
  for (const child of [].concat(children)) {
    if (child) node.appendChild(typeof child === "string" ? document.createTextNode(child) : child);
  }
  return node;
}

export const errorText = (err) => (err instanceof Error ? err.message : String(err));

/** Resolve a {src, external} thumb (see lib/thumbs.js) to a URL the browser can load. */
export function resolveSrc(api, thumb) {
  return thumb.external ? thumb.src : api.apiURL(thumb.src);
}

/** Thumbnail <img> that swaps to a "not found" box when it fails to load. */
export function thumbImage(src, { alt = "", className = "cs-thumb", missingText = "", lazy = true } = {}) {
  // `loading` must be set before `src`: a detached <img> starts fetching as soon as it has a src.
  const img = el("img", { class: className, loading: lazy ? "lazy" : undefined, decoding: "async", alt, draggable: "false" });
  if (src) img.setAttribute("src", src);
  img.addEventListener("error", () => img.classList.add("cs-thumb-broken"));
  img.addEventListener("load", () => img.classList.remove("cs-thumb-broken"));
  img.dataset.missing = missingText;
  return img;
}

/** Wrap a thumbnail so a broken image shows its `data-missing` text via CSS. */
export function thumbBox(img, extraClass = "") {
  const box = el("div", { class: `cs-thumb-box ${extraClass}`.trim() }, [img]);
  box.appendChild(el("span", { class: "cs-thumb-missing", text: img.dataset.missing || "" }));
  return box;
}

export function setThumbSrc(img, src) {
  if (img.getAttribute("src") === src) return;
  img.classList.remove("cs-thumb-broken");
  img.setAttribute("src", src);
}
