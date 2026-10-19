// Fork completion: a forked bubble waits for its child, and a finished child pops it, on up the chain.
import * as fs from 'node:fs';
import * as path from 'node:path';
import { loadTrack, saveTrack } from '../store.js';
import { linked, parentOf } from './follow.js';
/** A track is finished when it's closed, or has bubbles and all are done (an empty, unsketched track isn't). */
export const isFinished = (track) => !!track.closed || (track.bubbles.length > 0 && track.bubbles.every((b) => b.state === 'done'));
/** Throw if `bubble` has a fork that isn't finished yet; a missing child file needs `force`. */
export function checkForkFinished(file, bubble, { force = false } = {}) {
    if (!bubble.fork)
        return;
    const childFile = linked(file, bubble.fork);
    if (!fs.existsSync(childFile)) {
        if (force)
            return;
        throw new Error(`"${bubble.title}" waits for its fork ${bubble.fork}, which is missing — re-run with --force to pop it anyway`);
    }
    if (!isFinished(loadTrack(childFile))) {
        throw new Error(`"${bubble.title}" waits for its fork ${bubble.fork} — finish that track first (switch to it)`);
    }
}
/** Child finished (or closed) -> pop its parent bubble, and so on up the chain. Returns one message per popped parent. */
export function popFinishedParents(childFile, child) {
    const msgs = [];
    for (let file = childFile, track = child; isFinished(track);) {
        const p = parentOf(file, track);
        if (!p || p.bubble.state === 'done')
            break;
        p.bubble.state = 'done';
        saveTrack(p.file, p.track);
        msgs.push(`fork finished — popped "${p.bubble.title}" in ${path.relative(path.dirname(childFile), p.file).split(path.sep).join('/')}`);
        file = p.file;
        track = p.track;
    }
    return msgs;
}
