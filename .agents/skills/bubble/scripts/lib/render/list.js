// The numbered listing that `show` prints.
import { activeIndex } from '../model.js';
import { symbolFor, symbolsFor } from './symbols.js';
/** Multi-line listing of the track, with addressable indexes. */
export function list(track, opts) {
    const sym = symbolsFor(opts);
    const index = track.closed ? -1 : activeIndex(track);
    return (track.bubbles || [])
        .map((b, i) => {
        const mark = i === index ? '→' : ' ';
        const type = b.type ? ` [${b.type}]` : '';
        const fork = (b.fork ? ` ${sym.fork} ${b.fork}` : '') + (b.sides || []).map((s) => ` ${sym.side} ${s}`).join('');
        const hint = b.hint ? `\n        ↳ ${b.hint}` : '';
        return `${mark} ${String(i + 1).padEnd(3)} ${symbolFor(b, i === index, sym)} ${b.state.padEnd(6)} ${b.title}${type}${fork}${hint}`;
    })
        .join('\n');
}
