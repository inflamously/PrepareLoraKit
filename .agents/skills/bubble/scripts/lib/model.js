// The bubble model: fog types, which bubble is active, and how addresses resolve to bubbles.
export const TYPES = ['known-known', 'known-unknown', 'unknown-known', 'unknown-unknown'];
const TYPE_ALIASES = { kk: 'known-known', ku: 'known-unknown', uk: 'unknown-known', uu: 'unknown-unknown' };
/** Expand kk/ku/uk/uu shorthands; undefined stays undefined. */
export function normalizeType(type) {
    return type === undefined ? undefined : TYPE_ALIASES[type] || type;
}
export function checkType(type) {
    if (type !== undefined && !TYPES.includes(type)) {
        throw new Error(`unknown fog type "${type}" (use: ${TYPES.join(', ')} — or kk, ku, uk, uu)`);
    }
}
/** A bubble's stable id from the track's counter. Positions shift on move/insert/remove; ids don't. */
export function ensureId(track, b) {
    if (b.id === undefined) {
        b.id = track.nextId || 1;
        track.nextId = b.id + 1;
    }
    return b.id;
}
/** Index of the active bubble: the first one that isn't done. -1 = everything done. */
export function activeIndex(track) {
    return (track.bubbles || []).findIndex((b) => b.state !== 'done');
}
/** The active bubble, or null when all done. */
export function activeBubble(track) {
    const i = activeIndex(track);
    return i === -1 ? null : track.bubbles[i];
}
/** Resolve an address to a bubble index: "3" -> 3rd bubble; undefined -> the active bubble. */
export function resolve(track, addr) {
    if (addr === undefined || addr === null || addr === '') {
        const i = activeIndex(track);
        if (i === -1)
            throw new Error('all bubbles are done — nothing active');
        return i;
    }
    const n = Number(addr);
    if (!Number.isInteger(n) || n < 1)
        throw new Error(`bad bubble address "${addr}"`);
    if (!track.bubbles[n - 1])
        throw new Error(`no bubble at "${addr}"`);
    return n - 1;
}
/** Resolve "N" or "N:M" (inclusive, 1-based) to zero-based [from, to]. */
export function resolveRange(track, spec) {
    const m = /^(\d+)(?::(\d+))?$/.exec(String(spec || ''));
    if (!m)
        throw new Error(`bad bubble range "${spec}" (use N or N:M)`);
    const from = Number(m[1]);
    const to = m[2] === undefined ? from : Number(m[2]);
    if (from < 1 || to < from)
        throw new Error(`bad bubble range "${spec}"`);
    if (!track.bubbles[to - 1])
        throw new Error(`no bubble at "${to}"`);
    return [from - 1, to - 1];
}
