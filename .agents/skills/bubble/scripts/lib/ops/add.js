// Add a todo or fog bubble, at the end or at a position (insert).
import { ensureId } from '../model.js';
export function add(track, title, { fog = false, at } = {}) {
    const bubbles = track.bubbles;
    const bubble = fog ? { title: title || '???', state: 'fog' } : { title: title || '', state: 'todo' };
    if (!bubble.title)
        throw new Error('add needs a title');
    if (at !== undefined) {
        const pos = Number(at) - 1;
        if (!Number.isInteger(pos) || pos < 0 || pos > bubbles.length)
            throw new Error(`bad position "${at}"`);
        bubbles.splice(pos, 0, bubble);
    }
    else {
        bubbles.push(bubble);
    }
    ensureId(track, bubble);
    return `added ${fog ? 'fog' : 'bubble'} "${bubble.title}"`;
}
