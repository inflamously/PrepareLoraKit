// What `show` and every mutation print: the track line, the listing, the handoff note or closed line, the fog warning.
import * as lib from '../index.js';
import * as links from '../links/index.js';
/** Print the track saved at `file`; returns 3 when the active bubble is fog (the human has to plan it), else 0. */
export function printTrack(file, track, opts) {
    console.log(lib.render(track, opts));
    const { fork, side } = lib.SYMBOLS.unicode;
    if (track.parent)
        console.log(`${fork} fork of ${links.linkLabel(file, track.parent)} in ${track.parent.track}`);
    if (track.origin)
        console.log(`${side} diverged from ${links.linkLabel(file, track.origin)} in ${track.origin.track}`);
    console.log('');
    console.log(lib.list(track, opts));
    if (track.closed) {
        console.log('');
        console.log(`${lib.SYMBOLS.unicode.lock} closed ${track.closed.at} — read-only; fork, diverge or switch to keep working`);
        return 0; // archived: nothing is active, so fog here never needs the human
    }
    if (track.handoff && track.handoff.note) {
        console.log('');
        console.log(`✎ handoff (${track.handoff.at}): ${track.handoff.note}`);
    }
    const active = lib.activeBubble(track);
    if (active && active.state === 'fog') {
        console.log('');
        console.log(`⚠ "${active.title}" is fog — the human plans it. Ask them to classify it (${lib.TYPES.join(', ')}) and fill it.`);
        return 3;
    }
    return 0;
}
