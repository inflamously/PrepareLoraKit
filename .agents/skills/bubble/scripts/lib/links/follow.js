// Following a link: where a relative link path points, and the parent bubble a fork came from.
import * as fs from 'node:fs';
import * as path from 'node:path';
import { loadTrack } from '../store.js';
/** The file a link path points to; link paths are relative to the linking track file. */
export const linked = (fromFile, rel) => path.resolve(path.dirname(fromFile), rel);
/** Load the parent track and the bubble a child was forked from, or null if the link is broken or the parent is closed. */
export function parentOf(childFile, child) {
    if (!child.parent)
        return null;
    const file = linked(childFile, child.parent.track);
    if (!fs.existsSync(file))
        return null;
    const track = loadTrack(file);
    if (track.closed)
        return null; // a closed parent is read-only: the child runs on, nothing flows back
    const bubble = track.bubbles.find((b) => b.id === child.parent.bubble);
    return bubble ? { file, track, bubble } : null;
}
