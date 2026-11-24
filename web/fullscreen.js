// ⤢ full-screen view: moves the panel's own root element into a fixed overlay and back, so
// selection and observers are kept (one instance, no state to sync). Moving an element can reset
// its scroll position and the grid's column count changes, so the caller snapshots and restores
// the scroll position around each move (`snapshot()` / `restore(snap)`).
import { el } from "./dom.js";

/** Insert `node` before `ref` in `parent`, keeping its state with Element.moveBefore where supported. */
function moveNode(parent, node, ref) {
  if (typeof parent.moveBefore === "function" && parent.isConnected && node.isConnected) {
    try {
      parent.moveBefore(node, ref);
      return;
    } catch {
      // Fall through to a plain DOM move (e.g. the browser refuses this particular move).
    }
  }
  parent.insertBefore(node, ref);
}

export function createFullscreen(root, { onChange = () => {}, snapshot = () => null, restore = () => {} } = {}) {
  let overlay = null;
  let placeholder = null;

  const onKey = (e) => {
    if (e.key !== "Escape" || !overlay) return;
    e.preventDefault();
    e.stopPropagation();
    close();
  };

  function open() {
    if (overlay || !root.parentNode) return;
    const snap = snapshot();
    placeholder = el("div", { class: "cs-fullscreen-placeholder" });
    root.parentNode.insertBefore(placeholder, root);
    overlay = el("div", { class: "cs-overlay", role: "dialog", "aria-modal": "true" });
    // Clicking the dimmed backdrop (not the panel) closes it.
    overlay.addEventListener("pointerdown", (e) => {
      if (e.target === overlay) close();
    });
    document.body.appendChild(overlay);
    root.classList.add("cs-is-fullscreen");
    moveNode(overlay, root, null);
    document.addEventListener("keydown", onKey, true);
    onChange(true);
    restore(snap);
  }

  function close() {
    if (!overlay) return;
    const snap = snapshot();
    document.removeEventListener("keydown", onKey, true);
    root.classList.remove("cs-is-fullscreen");
    if (placeholder?.parentNode) moveNode(placeholder.parentNode, root, placeholder);
    else root.remove();
    placeholder?.remove();
    overlay.remove();
    overlay = null;
    placeholder = null;
    onChange(false);
    restore(snap);
  }

  return {
    toggle: () => (overlay ? close() : open()),
    close,
    isOpen: () => Boolean(overlay),
  };
}
