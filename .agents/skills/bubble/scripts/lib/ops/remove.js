// Delete bubbles.
import { resolveRange } from '../model.js';
export function remove(track, spec) {
    const [from, to] = resolveRange(track, spec);
    const gone = track.bubbles.splice(from, to - from + 1);
    return `removed ${gone.map((b) => `"${b.title}"`).join(', ')}`;
}
