// Retitle a bubble or the track itself.
import { resolve } from '../model.js';
export function rename(track, addr, title) {
    const b = track.bubbles[resolve(track, addr)];
    if (b.state === 'fog')
        throw new Error(`"${b.title}" is fog — plan it with fill`);
    if (!title)
        throw new Error('rename needs a title');
    const old = b.title;
    b.title = title;
    return `renamed "${old}" → "${title}"`;
}
/** Rename the track itself. */
export function setTitle(track, title) {
    if (!title)
        throw new Error('title needs text');
    const old = track.title;
    track.title = title;
    return `track "${old}" → "${title}"`;
}
