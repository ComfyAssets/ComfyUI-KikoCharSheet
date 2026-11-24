// Per-library panel configuration and gallery card construction.
import { thumbFor } from "./lib/thumbs.js";
import { el, resolveSrc, setThumbSrc, thumbBox, thumbImage } from "./dom.js";

const SOURCE_LABELS = { gia: "source.gia", "gia-anime": "source.giaAnime", charadb: "source.charadb", shisei: "source.shisei" };

/** Filter selects (field, label key, "all" key) and card subtitle fields per library. */
export const LIBRARIES = {
  portrait: {
    filters: [
      { field: "发长", label: "filters.portrait.hair", all: "filters.portrait.hairAll" },
      { field: "分区", label: "filters.portrait.section", all: "filters.portrait.sectionAll" },
    ],
    sub: ["发长", "分区"],
  },
  costume: {
    filters: [
      { field: "一级分类", label: "filters.costume.group", all: "filters.costume.groupAll" },
      { field: "分类", label: "filters.costume.category", all: "filters.costume.categoryAll" },
      { field: "source", label: "filters.costume.source", all: "filters.costume.sourceAll", labels: SOURCE_LABELS },
    ],
    sub: ["分类"],
  },
  pose: {
    filters: [
      { field: "体系", label: "filters.pose.system", all: "filters.pose.systemAll" },
      { field: "角度", label: "filters.pose.angle", all: "filters.pose.angleAll" },
    ],
    sub: ["分类", "角度"],
  },
};

/** Display text of a filter option value. */
export function optionLabel(spec, value, { t, d }) {
  const key = spec.labels?.[value];
  return key ? t(key) : d(value);
}

export function subtitle(lib, item, d) {
  return LIBRARIES[lib].sub
    .map((field) => item[field])
    .filter((v) => typeof v === "string" && v)
    .map(d)
    .join(" · ");
}

/** Resolved thumbnail URL of `id` for the given view/depth. */
export function thumbSrc(ctx, id, item, opts) {
  return resolveSrc(ctx.api, thumbFor(ctx.lib, id, item, opts));
}

/**
 * Build one gallery card. `ctx` is {lib, api, t, d, thumbOpts(id) -> {view, depth}}.
 * Clicks are handled by the grid (event delegation), not per card.
 */
export function buildCard(item, ctx) {
  const { t, d } = ctx;
  const title = d(item.title);
  const img = thumbImage(thumbSrc(ctx, item.id, item, ctx.thumbOpts(item.id)), {
    alt: title,
    missingText: t("uploads.notFound"),
  });
  const box = thumbBox(img);
  if (item.online) {
    box.appendChild(el("span", { class: "cs-badge cs-badge-online", title: t("state.onlineHint"), text: t("state.online") }));
  }
  box.appendChild(el("span", { class: "cs-order", "aria-hidden": "true" }));
  box.appendChild(el("span", { class: "cs-check", "aria-hidden": "true", text: "✓" }));
  const card = el(
    "div",
    { class: "cs-card", role: "button", tabindex: "0", "aria-pressed": "false", title: `${title} · ${item.id}` },
    [box, el("div", { class: "cs-card-title", text: title }), el("div", { class: "cs-card-sub", text: subtitle(ctx.lib, item, d) })]
  );
  card.dataset.id = item.id;
  return card;
}

/** Mark a card selected or not, with its 1-based position for multi pickers (0 = no number). */
export function setCardSelected(card, selected, position = 0) {
  card.classList.toggle("cs-selected", selected);
  card.setAttribute("aria-pressed", selected ? "true" : "false");
  const order = card.querySelector(".cs-order");
  if (order) order.textContent = selected && position ? String(position) : "";
}

export function updateCardThumb(card, src) {
  const img = card.querySelector("img.cs-thumb");
  if (img) setThumbSrc(img, src);
}
