// Pure scroll-position rules for keeping the grid in place across the ⤢ full-screen move.

/**
 * Id of the first card still visible at `scrollTop`. `cards` are {id, top, bottom} in grid order,
 * measured in the scroll box's own coordinates. Null above the grid (uploads), past the end or empty.
 */
export function firstVisibleId(cards, scrollTop) {
  if (!cards.length || scrollTop < cards[0].top) return null;
  return cards.find((card) => card.bottom > scrollTop)?.id ?? null;
}

/**
 * Scroll top to use after the move: the old value when the column count is unchanged, otherwise the
 * anchor card's new top (so it sits at the top of the scroll box), else the old value.
 */
export function restoredScrollTop(before, after) {
  if (before.columns === after.columns || !before.anchorId || after.anchorTop == null) return before.top;
  return after.anchorTop;
}
