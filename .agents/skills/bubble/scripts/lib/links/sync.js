// Title sync: a fork and the bubble it came from keep the same title, whichever side is renamed.
import * as fs from 'node:fs';
import { loadTrack, saveTrack } from '../store.js';
import { linked, parentOf } from './follow.js';
/** Child retitled -> the parent bubble takes the new title. Returns a message, or ''. */
export function syncTitle(childFile, child) {
    const p = parentOf(childFile, child);
    if (!p || !child.parent || !child.title || p.bubble.title === child.title)
        return '';
    p.bubble.title = child.title;
    child.parent.title = child.title;
    saveTrack(p.file, p.track);
    saveTrack(childFile, child);
    return `parent bubble #${p.bubble.id} in ${child.parent.track} renamed too`;
}
/** Parent bubble renamed -> its fork's title (and the child's copy of it) follow. Returns a message, or ''. */
export function syncForkTitle(file, bubble) {
    if (!bubble.fork)
        return '';
    const childFile = linked(file, bubble.fork);
    if (!fs.existsSync(childFile))
        return '';
    const child = loadTrack(childFile);
    if (child.closed)
        return '';
    child.title = bubble.title;
    if (child.parent)
        child.parent.title = bubble.title;
    saveTrack(childFile, child);
    return `fork ${bubble.fork} renamed too`;
}
