// Where tracks live: find, name, load and save them.
// Layout: .bubble-tracks/<name>.json per track, .bubble-tracks/current names the active one.
// No `current` file = the default track, .bubble-tracks/track.json (name "track").
import * as fs from 'node:fs';
import * as path from 'node:path';
export const TRACK_DIR = '.bubble-tracks';
const CURRENT_FILE = 'current';
export const DEFAULT_NAME = 'track';
const NAME_RE = /^[A-Za-z0-9_-]+$/;
// Names and paths.
export function checkName(name) {
    if (!name || !NAME_RE.test(name))
        throw new Error(`bad track name "${name || ''}" (letters, digits, - and _ only)`);
    return name;
}
export const trackPath = (bubblesDir, name) => path.join(bubblesDir, `${name}.json`);
// Finding tracks.
/** Walk up from `dir` looking for a .bubble-tracks directory. */
export function findBubblesDir(dir) {
    let current = path.resolve(dir || '.');
    for (;;) {
        const candidate = path.join(current, TRACK_DIR);
        try {
            if (fs.statSync(candidate).isDirectory())
                return candidate;
        }
        catch {
            /* keep walking */
        }
        const parent = path.dirname(current);
        if (parent === current)
            return null;
        current = parent;
    }
}
/** Track names in a .bubble-tracks dir, sorted. */
export function listTracks(bubblesDir) {
    try {
        return fs
            .readdirSync(bubblesDir)
            .filter((f) => f.endsWith('.json') && NAME_RE.test(f.slice(0, -5)))
            .map((f) => f.slice(0, -5))
            .sort();
    }
    catch {
        return [];
    }
}
// The current pointer: .bubble-tracks/current names the current track.
export function currentName(bubblesDir) {
    try {
        const name = fs.readFileSync(path.join(bubblesDir, CURRENT_FILE), 'utf8').trim();
        if (NAME_RE.test(name))
            return name;
    }
    catch {
        /* no pointer: the default track */
    }
    return DEFAULT_NAME;
}
export function setCurrent(bubblesDir, name) {
    fs.mkdirSync(bubblesDir, { recursive: true });
    fs.writeFileSync(path.join(bubblesDir, CURRENT_FILE), checkName(name) + '\n', 'utf8');
}
// Reading and writing one track file.
export function loadTrack(file) {
    const track = JSON.parse(fs.readFileSync(file, 'utf8'));
    if (!track || !Array.isArray(track.bubbles))
        throw new Error('missing "bubbles" array');
    return track;
}
/** Atomic write: temp file + rename. */
export function saveTrack(file, track) {
    fs.mkdirSync(path.dirname(file), { recursive: true });
    const tmp = `${file}.${process.pid}.tmp`;
    fs.writeFileSync(tmp, JSON.stringify(track, null, 2) + '\n', 'utf8');
    fs.renameSync(tmp, file);
}
// All of it together: the current track, loaded.
/** Current track: null (none), { file, name, bubblesDir, error } (unreadable), or { file, name, bubblesDir, track }. */
export function findTrack(dir) {
    const bubblesDir = findBubblesDir(dir);
    if (!bubblesDir)
        return null;
    const name = currentName(bubblesDir);
    const file = trackPath(bubblesDir, name);
    if (!fs.existsSync(file))
        return null;
    try {
        return { file, name, bubblesDir, track: loadTrack(file) };
    }
    catch (err) {
        return { file, name, bubblesDir, error: err.message };
    }
}
