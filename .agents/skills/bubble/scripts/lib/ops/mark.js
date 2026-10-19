// Mark a bubble as the source of a fork or a side track (the links themselves are in ../links).
import { resolve, ensureId } from '../model.js';
/** Link a bubble to the child track forked from it; its state stays as is. Returns the bubble (with its id). */
export function markFork(track, addr, childRef) {
    const b = track.bubbles[resolve(track, addr)];
    if (b.state === 'done')
        throw new Error(`"${b.title}" is done — nothing left to fork`);
    if (b.fork)
        throw new Error(`"${b.title}" is already forked to ${b.fork}`);
    const id = ensureId(track, b);
    b.fork = childRef;
    return Object.assign(b, { id });
}
/** Link a bubble to a side track that went a different direction from it. Any state; the bubble doesn't wait for it. */
export function markDiverge(track, addr, childRef) {
    const b = track.bubbles[resolve(track, addr)];
    const id = ensureId(track, b);
    b.sides = [...(b.sides || []), childRef];
    return Object.assign(b, { id });
}
