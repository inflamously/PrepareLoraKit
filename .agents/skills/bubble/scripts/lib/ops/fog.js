// The fog lifecycle: turn bubbles into fog, classify them, fill them with the human's content.
import { normalizeType, checkType, resolve, resolveRange } from '../model.js';
/** Turn a bubble (or N:M range) into fog. Done bubbles need `force`. */
export function fog(track, spec, type, { force = false } = {}) {
    type = normalizeType(type);
    checkType(type);
    const [from, to] = spec === undefined ? [resolve(track), resolve(track)] : resolveRange(track, spec);
    const picked = track.bubbles.slice(from, to + 1);
    const finished = picked.filter((b) => b.state === 'done');
    if (finished.length && !force) {
        throw new Error(`${finished.map((b) => `"${b.title}"`).join(', ')} ${finished.length > 1 ? 'are' : 'is'} done — ` +
            'confirm with the human, then re-run with --force');
    }
    for (const b of picked) {
        b.state = 'fog';
        if (type)
            b.type = type;
    }
    return picked.length === 1 ? `"${picked[0].title}" is now fog` : `bubbles ${from + 1}–${to + 1} are now fog`;
}
export function setType(track, addr, type) {
    if (!type)
        throw new Error('type needs a value');
    type = normalizeType(type);
    checkType(type);
    const b = track.bubbles[resolve(track, addr)];
    b.type = type;
    return `"${b.title}" classified as ${type}`;
}
/** Human-planned content for a fog bubble: fog -> todo. */
export function fill(track, addr, title) {
    const b = track.bubbles[resolve(track, addr)];
    if (b.state !== 'fog')
        throw new Error(`"${b.title}" isn't fog — use rename to change its title`);
    if (!title)
        throw new Error('fill needs a title');
    b.title = title;
    b.state = 'todo';
    return `filled "${b.title}"`;
}
