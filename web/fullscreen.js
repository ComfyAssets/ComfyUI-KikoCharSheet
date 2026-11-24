// ⤢ full-screen view: moves the panel's own root element into a fixed overlay and back, so
// scroll position, selection and observers are kept (one instance, no state to sync).
import { el } from "./dom.js";

export function createFullscreen(root, { onChange = () => {} } = {}) {
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
    placeholder = el("div", { class: "cs-fullscreen-placeholder" });
    root.parentNode.replaceChild(placeholder, root);
    overlay = el("div", { class: "cs-overlay", role: "dialog", "aria-modal": "true" });
    // Clicking the dimmed backdrop (not the panel) closes it.
    overlay.addEventListener("pointerdown", (e) => {
      if (e.target === overlay) close();
    });
    overlay.appendChild(root);
    root.classList.add("cs-is-fullscreen");
    document.body.appendChild(overlay);
    document.addEventListener("keydown", onKey, true);
    onChange(true);
  }

  function close() {
    if (!overlay) return;
    document.removeEventListener("keydown", onKey, true);
    root.classList.remove("cs-is-fullscreen");
    if (placeholder?.parentNode) placeholder.parentNode.replaceChild(root, placeholder);
    else root.remove();
    overlay.remove();
    overlay = null;
    placeholder = null;
    onChange(false);
  }

  return {
    toggle: () => (overlay ? close() : open()),
    close,
    isOpen: () => Boolean(overlay),
  };
}
