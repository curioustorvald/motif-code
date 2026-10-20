/**
 * Lookahead scroll: given a cursor position, the current scroll
 * offset, the number of visible cells and the max scroll, return the new scroll
 * so the cursor stays inside the central 64% of the viewport — the view scrolls
 * only when the cursor enters the 18% edge band, and just enough to return it to
 * that band's boundary. Within the band the scroll is unchanged (keeps any
 * fractional wheel offset). Used by every grid view's cursor-follow.
 */
export function lookahead(pos, scroll, vis, maxScroll) {
  const clamp = (v) => Math.min(Math.max(v, 0), Math.max(0, maxScroll));
  if (vis <= 0) return clamp(scroll);
  const edge = Math.max(1, Math.floor(vis * 0.18));
  const top = Math.floor(scroll);
  if (pos < top + edge) return clamp(pos - edge);
  if (pos > top + vis - 1 - edge) return clamp(pos - (vis - 1 - edge));
  return clamp(scroll); // cursor already inside the central 64%
}

/** Wheel-scroll step quantized to a multiple of `quantum`, carrying the
 *  remainder forward so no distance is lost. */
export function wheelStep(remainder, rawDelta, quantum = 4) {
  const total = remainder + rawDelta;
  const step = Math.trunc(total / quantum) * quantum;
  return { step, remainder: total - step };
}
