// Move bubbles within the track, or to another one.
import { resolveRange, ensureId } from '../model.js';
/** Move a bubble (or N:M block) so it starts at position `to` in the resulting track. */
export function move(track, spec, to) {
    const [from, last] = resolveRange(track, spec);
    const block = track.bubbles.splice(from, last - from + 1);
    const pos = Number(to) - 1;
    if (!Number.isInteger(pos) || pos < 0 || pos > track.bubbles.length) {
        track.bubbles.splice(from, 0, ...block); // undo
        throw new Error(`bad position "${to}"`);
    }
    track.bubbles.splice(pos, 0, ...block);
    return `moved ${block.map((b) => `"${b.title}"`).join(', ')} to ${pos + 1}`;
}
/**
 * Move a bubble (or N:M block) to the end of another track, state, type and hint included. They get new ids
 * from `target`'s counter. Bubbles with a fork or side track are refused: those tracks link back here by id.
 */
export function moveTo(track, spec, target, targetName) {
    const [from, last] = resolveRange(track, spec);
    const linked = track.bubbles.slice(from, last + 1).filter((b) => b.fork || b.sides?.length);
    if (linked.length) {
        throw new Error(`${linked.map((b) => `"${b.title}"`).join(', ')} ${linked.length > 1 ? 'have' : 'has'} a fork or side track ` +
            'linked to this track — it stays here');
    }
    const block = track.bubbles.splice(from, last - from + 1);
    for (const { title, state, id: _old, ...rest } of block) {
        const b = { title, state }; // the new id goes right after state, as on every other bubble
        ensureId(target, b);
        target.bubbles.push(Object.assign(b, rest));
    }
    return `moved ${block.map((b) => `"${b.title}"`).join(', ')} to track "${targetName}"`;
}
