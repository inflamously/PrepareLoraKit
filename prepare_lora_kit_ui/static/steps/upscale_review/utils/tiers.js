/** Group review items into their min-side tiers, smallest first, unknown sizes last. */
export function groupByTier(items) {
  const tiers = new Map();
  items.forEach((item) => {
    const lo = item.tier_lo == null ? null : Number(item.tier_lo);
    const key = lo === null ? "unknown" : String(lo);
    if (!tiers.has(key)) {
      tiers.set(key, { key, lo, hi: lo === null ? null : Number(item.tier_hi), items: [] });
    }
    tiers.get(key).items.push(item);
  });
  return [...tiers.values()].sort((a, b) => {
    if (a.lo === null) return 1;
    if (b.lo === null) return -1;
    return a.lo - b.lo;
  });
}

export function formatTier(tier) {
  return tier.lo === null ? "Unknown size" : `${tier.lo}–${tier.hi}px`;
}
