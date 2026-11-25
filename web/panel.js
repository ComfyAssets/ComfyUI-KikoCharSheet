// The shared in-node picker panel (Portrait, Costume, Pose). Builds its DOM once; selection and
// thumbnail changes update cards in place, and only filter changes rebuild the batched grid.
import { getCatalog } from "./lib/catalog.js";
import { filterItems, filterOptions } from "./lib/filters.js";
import { BATCH_SIZE, nextRenderCount, parseUploadId, renderCountToInclude } from "./lib/gallery.js";
import { MAX_POSES } from "./lib/selection.js";
import { firstVisibleId, restoredScrollTop } from "./lib/scroll.js";
import {
  clearPick,
  costumeViewFor,
  flipPose,
  movePose,
  parseState,
  hasWideRenders,
  isWideLens,
  removePose,
  selectableViews,
  setWideLens,
  togglePose,
} from "./lib/state.js";
import { LIBRARIES, buildCard, optionLabel, setCardSelected, thumbSrc, updateCardThumb } from "./cards.js";
import { el, errorText, setThumbSrc, thumbBox, thumbImage } from "./dom.js";
import { createFullscreen } from "./fullscreen.js";
import { createTray } from "./tray.js";
import { UploadSection } from "./uploads.js";

const SHAKE_MS = 400;
const SEARCH_DEBOUNCE_MS = 150;
const SENTINEL_MARGIN = "600px";

/**
 * @param {{lib: "portrait"|"costume"|"pose", multi?: boolean, max?: number, state: object|string,
 *   onChange: (state: object) => void, translate: {t: Function, d: Function}, api: any}} options
 * @returns {{root: HTMLElement, setState: (state: object|string) => void, destroy: () => void}}
 */
export function createPickerPanel({ lib, multi = lib === "pose", max = MAX_POSES, state, onChange, translate, api }) {
  const { t, d } = translate;
  const spec = LIBRARIES[lib];
  let current = parseState(lib, state);
  let items = [];
  let itemById = new Map();
  let filtered = [];
  let rendered = 0;
  const cards = new Map(); // id -> rendered card element
  let marked = new Set(); // ids whose cards currently show as selected
  let observer = null;
  let safeMode = true;
  let query = "";
  const filters = {};
  let shakeTimer = null;
  let searchTimer = null;
  let loadGeneration = 0;
  let destroyed = false;

  const selectedIds = () => (multi ? current.ids : current.id ? [current.id] : []);
  const thumbOpts = (id) => {
    if (lib === "pose") return { style: current.style };
    if (lib === "costume" && id === current.id) return { view: current.view };
    return {};
  };
  const ctx = { lib, api, t, d, thumbOpts };

  // ---- Header ----
  const counter = el("span", { class: "cs-counter", "aria-live": "polite" });
  const currentLabel = el("span", { class: "cs-current" });
  const countLabel = el("span", { class: "cs-item-count" });
  const expandBtn = el("button", { class: "cs-icon-btn cs-expand", type: "button", text: "⤢" });
  const header = el("div", { class: "cs-header" }, [
    el("span", { class: "cs-title", text: t(`panel.${lib}`) }),
    multi ? counter : currentLabel,
    el("span", { class: "cs-spacer" }),
    countLabel,
    expandBtn,
  ]);

  // ---- Filter row ----
  const search = el("input", { class: "cs-input cs-search", type: "search", placeholder: t(`search.${lib}`), "aria-label": t(`search.${lib}`) });
  const selects = spec.filters.map((f) => {
    const select = el("select", { class: "cs-select", "aria-label": t(f.label), title: t(f.label) });
    select.addEventListener("change", () => {
      filters[f.field] = select.value;
      renderGrid();
    });
    return { spec: f, select };
  });
  const lensBtn = lib === "pose" ? el("button", { class: "cs-btn cs-toggle cs-lens", type: "button", title: t("lens.hint") }) : null;
  const sfwBtn = el("button", { class: "cs-btn cs-toggle cs-sfw", type: "button" });
  const randomBtn = el("button", { class: "cs-btn", type: "button", text: t("random") });
  const resetBtn = el("button", { class: "cs-btn cs-btn-quiet", type: "button", text: t("reset") });
  const filterRow = el("div", { class: "cs-filters" }, [search, ...selects.map((s) => s.select), lensBtn, sfwBtn, randomBtn, resetBtn]);

  const confirmYes = el("button", { class: "cs-btn cs-btn-danger", type: "button", text: t("sfw.confirmYes") });
  const confirmNo = el("button", { class: "cs-btn cs-btn-primary", type: "button", text: t("sfw.confirmNo") });
  const sfwConfirm = el("div", { class: "cs-confirm", role: "alertdialog", hidden: true }, [
    el("div", { text: t("sfw.confirm") }),
    el("div", { class: "cs-actions" }, [confirmYes, confirmNo]),
  ]);

  // ---- Scroll area ----
  const uploadsBox = el("section", { class: "cs-uploads" });
  const status = el("div", { class: "cs-status", hidden: true });
  const grid = el("div", { class: "cs-grid cs-gallery", role: "list" });
  const sentinel = el("div", { class: "cs-sentinel", "aria-hidden": "true" });
  const scroll = el("div", { class: "cs-scroll" }, [uploadsBox, status, grid, sentinel]);

  // ---- Footer ----
  const footer = el("div", { class: "cs-footer" });
  const tray = multi
    ? createTray({
        ctx,
        itemById: (id) => itemById.get(id),
        onRemove: (id) => commit(removePose(current, id)),
        onFlip: (id) => commit(flipPose(current, id)),
        onMove: (from, to) => commit(movePose(current, from, to)),
      })
    : null;
  const pickThumb = thumbImage("", { className: "cs-thumb", missingText: t("uploads.notFound"), lazy: false });
  const pickTitle = el("div", { class: "cs-pick-title" });
  const pickId = el("div", { class: "cs-pick-id" });
  const pickNote = el("div", { class: "cs-pick-note" });
  const viewSelect = el("select", { class: "cs-select cs-view-select", "aria-label": t("view.label"), title: t("view.label") });
  const viewField = el("label", { class: "cs-view-field", hidden: true }, [el("span", { text: t("view.label") }), viewSelect]);
  const pickRemove = el("button", {
    class: "cs-chip-btn cs-chip-remove cs-pick-remove",
    type: "button",
    title: t("tray.remove"),
    "aria-label": t("tray.remove"),
    text: "×",
    hidden: true,
    onclick: () => commit(clearPick(lib, current)),
  });
  const pickBox = el("div", { class: "cs-pick" }, [
    thumbBox(pickThumb, "cs-pick-thumb"),
    el("div", { class: "cs-pick-text" }, [el("div", { class: "cs-section-title", text: t("state.current") }), pickTitle, pickId, pickNote]),
    lib === "costume" ? viewField : null,
    pickRemove,
  ]);
  footer.appendChild(multi ? tray.root : pickBox);

  const root = el("div", { class: `cs-panel cs-lib-${lib}`, "data-lib": lib }, [header, filterRow, sfwConfirm, scroll, footer]);
  const fullscreen = createFullscreen(root, { onChange: updateExpandButton, snapshot: snapshotScroll, restore: restoreScroll });

  // Keys pressed inside the panel stay in the panel: ComfyUI's window-level keybindings only skip
  // text fields, so Delete on a focused card would delete the node. Ctrl/Meta combos (undo, copy)
  // and Escape outside full screen still reach ComfyUI.
  root.addEventListener("keydown", (e) => {
    if (e.ctrlKey || e.metaKey) return;
    if (e.key === "Escape" && !fullscreen.isOpen()) return;
    e.stopPropagation();
  });

  const uploads = new UploadSection({
    api,
    lib,
    t,
    container: uploadsBox,
    getSelectedIds: selectedIds,
    onPick: (id, opts) => pick(id, opts),
    onDeleted: (id) => {
      if (multi) commit(removePose(current, id));
      else if (current.id === id) commit(clearPick(lib, current));
    },
  });

  // ---- Catalogue and grid ----
  function setStatus(text, { error = false, retry = false } = {}) {
    status.replaceChildren();
    status.hidden = !text;
    status.classList.toggle("cs-error-text", error);
    if (!text) return;
    status.appendChild(el("span", { text }));
    if (retry) status.appendChild(el("button", { class: "cs-btn", type: "button", text: t("state.retry"), onclick: loadItems }));
  }

  async function loadItems() {
    const generation = ++loadGeneration;
    setStatus(t("state.loading", { label: t(`panel.${lib}`) }));
    try {
      const data = await getCatalog(lib, (url) => api.fetchApi(url));
      if (destroyed || generation !== loadGeneration) return;
      items = Array.isArray(data) ? data : [];
      itemById = new Map(items.map((item) => [item.id, item]));
      setStatus("");
      populateFilters();
      renderGrid();
      refreshSelectionUI(null);
    } catch (err) {
      if (destroyed || generation !== loadGeneration) return;
      setStatus(t("state.loadError", { lib: t(`panel.${lib}`), error: errorText(err) }), { error: true, retry: true });
    }
  }

  function populateFilters() {
    const visible = safeMode ? items.filter((item) => !item.nsfw) : items;
    for (const { spec: f, select } of selects) {
      const values = filterOptions(visible, f.field);
      if (filters[f.field] && !values.includes(filters[f.field])) filters[f.field] = "";
      select.replaceChildren(
        el("option", { value: "", text: t(f.all) }),
        ...values.map((v) => el("option", { value: v, text: optionLabel(f, v, translate) }))
      );
      select.value = filters[f.field] || "";
    }
  }

  function disconnectObserver() {
    observer?.disconnect();
    observer = null;
  }

  function observeSentinel() {
    disconnectObserver();
    if (destroyed || rendered >= filtered.length || typeof IntersectionObserver !== "function") return;
    observer = new IntersectionObserver(
      (entries) => {
        if (!entries.some((entry) => entry.isIntersecting)) return;
        renderUpTo(nextRenderCount(rendered, filtered.length, BATCH_SIZE));
        observeSentinel(); // a sentinel still in view triggers another batch
      },
      { root: scroll, rootMargin: SENTINEL_MARGIN }
    );
    observer.observe(sentinel);
  }

  function renderUpTo(count) {
    if (count <= rendered) return;
    const fragment = document.createDocumentFragment();
    for (const item of filtered.slice(rendered, count)) {
      const card = buildCard(item, ctx);
      cards.set(item.id, card);
      fragment.appendChild(card);
    }
    grid.appendChild(fragment);
    rendered = count;
    markSelected(true);
  }

  function renderGrid() {
    disconnectObserver();
    filtered = filterItems(items, { query, filters, safeMode, translate: d });
    rendered = 0;
    cards.clear();
    marked = new Set();
    grid.replaceChildren();
    scroll.scrollTop = 0;
    countLabel.textContent = t("state.itemCount", { count: filtered.length });
    if (items.length && !filtered.length) setStatus(t("state.empty"));
    else if (items.length) setStatus("");
    renderUpTo(nextRenderCount(0, filtered.length, BATCH_SIZE));
    observeSentinel();
  }

  /** Move selection marks to the current picks; `full` re-checks every rendered card (after a batch). */
  function markSelected(full = false) {
    const ids = selectedIds();
    const position = new Map(ids.map((id, i) => [id, i + 1]));
    const touch = full ? cards.keys() : new Set([...marked, ...ids]);
    for (const id of touch) {
      const card = cards.get(id);
      if (card) setCardSelected(card, position.has(id), multi ? position.get(id) : 0);
    }
    marked = new Set(ids);
    uploads.markSelected(ids);
  }

  // ---- Selection ----
  function pick(id, { ensure = false } = {}) {
    if (multi) {
      if (ensure && current.ids.includes(id)) return;
      const { state: next, refused } = togglePose(current, id, max);
      if (refused) return shakeCounter();
      return commit(next);
    }
    if (current.id === id) return;
    const next = { ...current, id };
    if (lib === "costume") next.view = costumeViewFor(itemById.get(id)?.views, current.view);
    commit(next);
  }

  function commit(next) {
    const previous = current;
    current = next;
    refreshSelectionUI(previous);
    onChange({ ...current });
  }

  function refreshSelectionUI(previous) {
    markSelected();
    if (previous && lib === "pose" && previous.style !== current.style) {
      for (const [id, card] of cards) updateCardThumb(card, thumbSrc(ctx, id, itemById.get(id), thumbOpts(id)));
    }
    if (previous && lib === "costume") {
      for (const id of new Set([previous.id, current.id])) {
        const card = cards.get(id);
        if (card) updateCardThumb(card, thumbSrc(ctx, id, itemById.get(id), thumbOpts(id)));
      }
    }
    renderHeader();
    renderFooter();
    renderLensButton();
  }

  /** Normal / wide-lens switch; shown when the catalogue has wide renders or wide is already on. */
  function renderLensButton() {
    if (!lensBtn) return;
    const wide = isWideLens(current);
    lensBtn.textContent = wide ? t("lens.wide") : t("lens.normal");
    lensBtn.setAttribute("aria-pressed", wide ? "true" : "false");
    lensBtn.hidden = !wide && !hasWideRenders(items);
  }

  function itemLabel(id) {
    const upload = parseUploadId(id);
    if (upload !== null) return upload;
    const item = itemById.get(id);
    return item ? d(item.title) : id;
  }

  function renderHeader() {
    if (multi) {
      counter.textContent = t("counter", { count: current.ids.length, max });
      counter.classList.toggle("cs-full", current.ids.length >= max);
      counter.title = current.ids.length >= max ? t("state.limit", { max }) : "";
    } else {
      currentLabel.textContent = current.id ? itemLabel(current.id) : t("state.noneSelected");
    }
  }

  function renderFooter() {
    if (multi) {
      tray.render(current);
      return;
    }
    const id = current.id;
    const item = itemById.get(id);
    const missing = Boolean(id) && items.length > 0 && !item && parseUploadId(id) === null;
    pickBox.classList.toggle("cs-empty", !id);
    pickBox.classList.toggle("cs-missing", missing);
    pickThumb.hidden = !id;
    pickRemove.hidden = !id;
    if (id) setThumbSrc(pickThumb, thumbSrc(ctx, id, item, thumbOpts(id)));
    pickTitle.textContent = id ? itemLabel(id) : t("state.noneSelected");
    pickId.textContent = id ? `#${id}` : "";
    pickNote.textContent = missing ? t("uploads.notFound") : id ? "" : t("state.defaultHint");
    if (lib === "costume") renderViewSelect(item);
  }

  function renderViewSelect(item) {
    const views = selectableViews(item?.views);
    viewField.hidden = views.length <= 1;
    if (views.length <= 1) return;
    const label = (v) => {
      const text = t(`view.${v}`);
      return text === `view.${v}` ? v : text;
    };
    viewSelect.replaceChildren(...views.map((v) => el("option", { value: v, text: label(v) })));
    viewSelect.value = costumeViewFor(views, current.view);
  }

  viewSelect.addEventListener("change", () => {
    if (viewSelect.value !== current.view) commit({ ...current, view: viewSelect.value });
  });

  function shakeCounter() {
    clearTimeout(shakeTimer);
    counter.classList.remove("cs-shake");
    void counter.offsetWidth; // restart the animation
    counter.classList.add("cs-shake");
    shakeTimer = setTimeout(() => counter.classList.remove("cs-shake"), SHAKE_MS);
  }

  // ---- Controls ----
  function renderSfwButton() {
    sfwBtn.textContent = safeMode ? t("sfw.on") : t("sfw.off");
    sfwBtn.setAttribute("aria-pressed", safeMode ? "true" : "false");
    sfwBtn.classList.toggle("cs-danger-on", !safeMode);
  }

  function setSafeMode(on) {
    safeMode = on;
    sfwConfirm.hidden = true;
    renderSfwButton();
    populateFilters();
    renderGrid();
  }

  sfwBtn.addEventListener("click", () => {
    if (safeMode) sfwConfirm.hidden = !sfwConfirm.hidden;
    else setSafeMode(true);
  });
  confirmYes.addEventListener("click", () => setSafeMode(false));
  confirmNo.addEventListener("click", () => {
    sfwConfirm.hidden = true;
  });
  lensBtn?.addEventListener("click", () => commit(setWideLens(current, !isWideLens(current))));

  search.addEventListener("input", () => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => {
      query = search.value;
      renderGrid();
    }, SEARCH_DEBOUNCE_MS);
  });

  resetBtn.addEventListener("click", () => {
    clearTimeout(searchTimer);
    query = "";
    search.value = "";
    for (const { spec: f, select } of selects) {
      filters[f.field] = "";
      select.value = "";
    }
    renderGrid();
  });

  randomBtn.addEventListener("click", () => {
    const taken = new Set(selectedIds());
    const pool = filtered.filter((item) => !taken.has(item.id));
    if (!pool.length) return;
    if (multi && current.ids.length >= max) return shakeCounter();
    const choice = pool[Math.floor(Math.random() * pool.length)];
    const index = filtered.indexOf(choice);
    renderUpTo(renderCountToInclude(index, filtered.length, BATCH_SIZE));
    observeSentinel();
    pick(choice.id);
    scrollToCard(cards.get(choice.id));
  });

  /** Centre a card in the panel's own scroll area (never scrolls the page or canvas). */
  function scrollToCard(card) {
    if (!card) return;
    // Layout offsets (relative to the positioned scroll box) are unaffected by canvas zoom.
    scroll.scrollTop = Math.max(0, card.offsetTop - (scroll.clientHeight - card.offsetHeight) / 2);
  }

  function gridColumns() {
    const template = getComputedStyle(grid).gridTemplateColumns;
    return template && template !== "none" ? template.split(" ").length : 0;
  }

  /** Scroll state before the ⤢ move: scrollTop, column count and the first visible card. */
  function snapshotScroll() {
    const boxes = [];
    for (const card of grid.children) boxes.push({ id: card.dataset.id, top: card.offsetTop, bottom: card.offsetTop + card.offsetHeight });
    return { top: scroll.scrollTop, columns: gridColumns(), anchorId: firstVisibleId(boxes, scroll.scrollTop) };
  }

  function restoreScroll(snap) {
    if (!snap) return;
    const anchor = snap.anchorId ? cards.get(snap.anchorId) : null;
    const target = restoredScrollTop(snap, { columns: gridColumns(), anchorTop: anchor ? anchor.offsetTop : null });
    // A wider grid is shorter: render more batches until the target is reachable, or it gets clamped.
    while (scroll.scrollHeight - scroll.clientHeight < target && rendered < filtered.length) {
      renderUpTo(nextRenderCount(rendered, filtered.length, BATCH_SIZE));
    }
    scroll.scrollTop = target;
    observeSentinel();
  }

  grid.addEventListener("click", (e) => {
    const card = e.target.closest?.(".cs-card[data-id]");
    if (card && grid.contains(card)) pick(card.dataset.id);
  });
  grid.addEventListener("keydown", (e) => {
    if (e.key !== "Enter" && e.key !== " ") return;
    const card = e.target.closest?.(".cs-card[data-id]");
    if (!card) return;
    e.preventDefault();
    pick(card.dataset.id);
  });

  function updateExpandButton(open) {
    const label = open ? t("panel.collapse") : t("panel.expand");
    expandBtn.title = label;
    expandBtn.setAttribute("aria-label", label);
    expandBtn.setAttribute("aria-pressed", open ? "true" : "false");
  }
  expandBtn.addEventListener("click", () => fullscreen.toggle());

  // ---- Init ----
  renderSfwButton();
  updateExpandButton(false);
  refreshSelectionUI(null);
  loadItems();

  return {
    root,
    /** Replace the panel's state from outside (workflow load, undo, hand edit of state_json). */
    setState(next) {
      const previous = current;
      current = parseState(lib, next);
      refreshSelectionUI(previous);
    },
    getState: () => ({ ...current }),
    destroy() {
      destroyed = true;
      disconnectObserver();
      clearTimeout(shakeTimer);
      clearTimeout(searchTimer);
      fullscreen.close();
      uploads.destroy();
    },
  };
}
