// Pure selection helpers for the pose picker (never mutate their inputs).

export const MAX_POSES = 13;

/** Add `id` unless full (then `refused`), or remove it when already selected. */
export function toggle(sel, id, max = MAX_POSES) {
  if (sel.includes(id)) return { sel: sel.filter((x) => x !== id), refused: false };
  if (sel.length >= max) return { sel: [...sel], refused: true };
  return { sel: [...sel, id], refused: false };
}

/** Move the item at `from` to position `to`; out-of-range indexes return a copy unchanged. */
export function move(sel, from, to) {
  const out = [...sel];
  if (!Number.isInteger(from) || !Number.isInteger(to)) return out;
  if (from < 0 || from >= out.length || to < 0 || to >= out.length) return out;
  const [item] = out.splice(from, 1);
  out.splice(to, 0, item);
  return out;
}

export function remove(sel, id) {
  return sel.filter((x) => x !== id);
}

export function toggleFlip(flips, id) {
  return flips.includes(id) ? flips.filter((x) => x !== id) : [...flips, id];
}
