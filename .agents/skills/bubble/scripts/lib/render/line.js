// The one-line track: the status line and `tracks`.
import { activeIndex } from '../model.js';
import { paint, shorten, symbolFor, symbolsFor, useColor } from './symbols.js';
/** One-line render: `Title   S ●──●──◐──❓ F   prev ‹ ◐ active › next`, or `… F   🔒 closed` (nothing active). */
export function render(track, opts) {
    const sym = symbolsFor(opts);
    const bubbles = track.bubbles || [];
    const index = track.closed ? -1 : activeIndex(track);
    const color = useColor(opts);
    const line = bubbles.map((b, i) => symbolFor(b, i === index, sym)).join(sym.sep);
    const head = `${paint(color, 'title', track.title || 'Plan')}   ${paint(color, 'track', `S ${line}${line ? ' ' : ''}F`)}   `;
    if (track.closed)
        return head + paint(color, 'context', `${sym.lock} closed`);
    const active = bubbles[index];
    if (!active)
        return head + paint(color, 'context', 'all done');
    const prev = bubbles[index - 1];
    const next = bubbles[index + 1];
    const here = active.state === 'fog' ? `${sym.fog} needs you` : `${sym.active} ${shorten(active.title, sym)}`;
    const context = (prev ? shorten(prev.title, sym) + sym.prev : '') + here + (next ? sym.next + shorten(next.title, sym) : '');
    return head + paint(color, 'context', context);
}
