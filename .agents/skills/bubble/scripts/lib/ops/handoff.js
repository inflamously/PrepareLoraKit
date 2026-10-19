// The note a fresh chat reads to resume the track.
/** Save (or clear with "-") the note a fresh chat reads to pick this track back up. */
export function setHandoff(track, note, now = new Date()) {
    if (!note)
        throw new Error('handoff needs a note (or - to clear it)');
    if (note === '-') {
        delete track.handoff;
        return 'cleared the handoff note';
    }
    track.handoff = { note, at: now.toISOString().slice(0, 16).replace('T', ' ') + ' UTC' };
    return 'saved the handoff note';
}
