// Pose tray: numbered chips of the chosen poses; drag to reorder, × to remove, ⇋ to flip.
// At most 13 chips, so it is simply rebuilt on every change.
import { parseUploadId } from "./lib/gallery.js";
import { el, thumbBox, thumbImage } from "./dom.js";
import { thumbSrc } from "./cards.js";

const DRAG_TYPE = "application/x-charsheet-pose-index";

export function createTray({ ctx, itemById, onRemove, onFlip, onMove }) {
  const { t, d } = ctx;
  const list = el("ol", { class: "cs-tray-list" });
  const empty = el("div", { class: "cs-tray-empty", text: t("tray.empty") });
  const root = el("div", { class: "cs-tray" }, [
    el("div", { class: "cs-section-title", text: t("tray.title") }),
    empty,
    list,
  ]);
  let dragFrom = -1;

  function chip(id, index, flipped, style) {
    const item = itemById(id);
    const upload = parseUploadId(id);
    const label = upload ?? (item ? d(item.title) : id);
    const img = thumbImage(thumbSrc(ctx, id, item, { style }), { alt: label, missingText: t("uploads.notFound"), lazy: false });
    const box = thumbBox(img, flipped ? "cs-mirrored" : "");
    const flipBtn = el("button", {
      class: `cs-chip-btn cs-chip-flip${flipped ? " cs-active" : ""}`,
      type: "button",
      title: flipped ? t("tray.flipped") : t("tray.flip"),
      "aria-label": t("tray.flip"),
      "aria-pressed": flipped ? "true" : "false",
      text: "⇋",
      onclick: () => onFlip(id),
    });
    const removeBtn = el("button", {
      class: "cs-chip-btn cs-chip-remove",
      type: "button",
      title: t("tray.remove"),
      "aria-label": t("tray.remove"),
      text: "×",
      onclick: () => onRemove(id),
    });
    const li = el("li", { class: "cs-chip", draggable: "true", title: `${label} · ${t("tray.drag")}` }, [
      el("span", { class: "cs-chip-num", text: String(index + 1) }),
      box,
      el("span", { class: "cs-chip-label", text: label }),
      el("span", { class: "cs-chip-actions" }, [flipBtn, removeBtn]),
    ]);
    li.dataset.index = String(index);
    if (!item && upload === null) li.classList.add("cs-missing");
    return li;
  }

  list.addEventListener("dragstart", (e) => {
    const li = e.target.closest?.(".cs-chip");
    if (!li) return;
    dragFrom = Number(li.dataset.index);
    e.dataTransfer.effectAllowed = "move";
    e.dataTransfer.setData(DRAG_TYPE, String(dragFrom));
    e.dataTransfer.setData("text/plain", String(dragFrom));
    li.classList.add("cs-dragging");
  });
  list.addEventListener("dragover", (e) => {
    if (dragFrom < 0) return;
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
    const li = e.target.closest?.(".cs-chip");
    list.querySelectorAll(".cs-drop-target").forEach((n) => n !== li && n.classList.remove("cs-drop-target"));
    li?.classList.add("cs-drop-target");
  });
  list.addEventListener("drop", (e) => {
    if (dragFrom < 0) return;
    e.preventDefault();
    const li = e.target.closest?.(".cs-chip");
    const to = li ? Number(li.dataset.index) : list.children.length - 1;
    const from = dragFrom;
    dragFrom = -1;
    if (Number.isInteger(to) && to !== from) onMove(from, to);
  });
  list.addEventListener("dragend", () => {
    dragFrom = -1;
    list.querySelectorAll(".cs-dragging, .cs-drop-target").forEach((n) => n.classList.remove("cs-dragging", "cs-drop-target"));
  });

  function render(state) {
    const flips = new Set(state.flip);
    list.replaceChildren(...state.ids.map((id, i) => chip(id, i, flips.has(id), state.style)));
    empty.hidden = state.ids.length > 0;
  }

  return { root, render };
}
