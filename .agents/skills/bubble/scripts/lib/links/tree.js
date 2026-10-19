// Reading links for display and for close: a link's label, and every fork under a track.
import * as fs from 'node:fs';
import * as path from 'node:path';
import { loadTrack } from '../store.js';
import { linked } from './follow.js';
/** `#<position> "<title>"` of the bubble a link points to, as it is now; just the stored title once the track or bubble is gone. */
export function linkLabel(fromFile, link) {
    try {
        const track = loadTrack(linked(fromFile, link.track));
        const i = track.bubbles.findIndex((b) => b.id === link.bubble);
        if (i !== -1)
            return `#${i + 1} "${track.bubbles[i].title}"`;
    }
    catch {
        /* missing or unreadable: fall back to the title */
    }
    return `"${link.title}"`;
}
/** Every fork under `track`, forks of forks too, top down (a fork comes before its own forks). Side tracks aren't forks. */
export function forkTree(file, track, seen = new Set([path.resolve(file)])) {
    const out = [];
    for (const b of track.bubbles) {
        if (!b.fork)
            continue;
        const childFile = linked(file, b.fork);
        if (seen.has(childFile))
            continue;
        seen.add(childFile);
        if (!fs.existsSync(childFile)) {
            out.push({ file: childFile, track: null, problem: 'missing, skipped' });
            continue;
        }
        try {
            const child = loadTrack(childFile);
            out.push({ file: childFile, track: child });
            out.push(...forkTree(childFile, child, seen));
        }
        catch (err) {
            out.push({ file: childFile, track: null, problem: `unreadable, skipped (${err.message})` });
        }
    }
    return out;
}
