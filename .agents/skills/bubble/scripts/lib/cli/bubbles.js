// Bubble-level commands: act on the current track (show, add, insert, remove, move, fog, fill, done, ...),
// or with --to on another one (add, insert, hint write into it; move sends bubbles to it).
import * as fs from 'node:fs';
import * as lib from '../index.js';
import * as links from '../links/index.js';
import { isAddr, isRange, needAddr } from './args.js';
import { printTrack } from './print.js';
const STOP = '⏸ stop — show this track to the human and wait. They may move, insert, remove, rename, hint or fog ' +
    'bubbles before the next one starts.';
/** Commands that take --to <track>: add, insert and hint write into it; move sends bubbles to it. */
const TO_COMMANDS = ['add', 'insert', 'hint', 'move', 'mv'];
/** The current track, loaded; throws when there is none or it can't be read. */
function currentTrack(dir) {
    const found = lib.findTrack(dir);
    if (!found) {
        const bubblesDir = lib.findBubblesDir(dir);
        const names = bubblesDir ? lib.listTracks(bubblesDir) : [];
        if (!bubblesDir || !names.length)
            throw new Error(`no bubble track found from ${dir} — start one with: switch <name>`);
        throw new Error(`current track "${lib.currentName(bubblesDir)}" not found — use: switch <name> (tracks: ${names.join(', ')})`);
    }
    if (!found.track)
        throw new Error(`invalid ${found.file}: ${found.error}`);
    return found;
}
/** The --to track, loaded; it must already exist. Whether it is current doesn't change. */
function namedTrack(dir, name) {
    lib.checkName(name);
    const bubblesDir = lib.findBubblesDir(dir);
    const file = bubblesDir && lib.trackPath(bubblesDir, name);
    if (!bubblesDir || !file || !fs.existsSync(file))
        throw new Error(`no track "${name}" — create it first: create ${name}`);
    try {
        return { file, name, bubblesDir, track: lib.loadTrack(file) };
    }
    catch (err) {
        throw new Error(`invalid ${file}: ${err.message}`);
    }
}
const closedError = (name) => new Error(`track "${name}" is closed (read-only) — fork, diverge or switch to keep working`);
/** Run a bubble-level command on the current track (or the --to track); returns an exit code. */
export function runBubbleCommand(cmd, args, { dir, opts, renderOpts }) {
    if (opts.to !== undefined && !TO_COMMANDS.includes(cmd))
        throw new Error(`--to works only with add, insert, hint and move`);
    // add, insert and hint --to change the --to track; move --to takes from the current one.
    const into = opts.to !== undefined && cmd !== 'move' && cmd !== 'mv';
    const found = into ? namedTrack(dir, opts.to) : currentTrack(dir);
    const { file, track } = found;
    let msg;
    let before; // another track's save, run once nothing can be refused any more
    let after; // cross-track follow-up (fork links), run once this track is saved
    let stop = false;
    switch (cmd) {
        case 'show':
        case 'status':
            return printTrack(file, track, renderOpts);
        case 'add': {
            const fog = opts.fog || (args.length === 1 && args[0] === '?');
            msg = lib.add(track, fog && args[0] === '?' ? undefined : args.join(' '), { fog, at: opts.at });
            break;
        }
        case 'insert': {
            if (args[0] === 'at')
                args.shift();
            const at = needAddr(args, 'insert at N <title> | insert at N ?');
            const fog = opts.fog || (args.length === 1 && args[0] === '?');
            msg = lib.add(track, fog && args[0] === '?' ? undefined : args.join(' '), { fog, at });
            break;
        }
        case 'remove':
        case 'rm':
            if (!isRange(args[0]))
                throw new Error('usage: remove N | remove N:M');
            msg = lib.remove(track, args[0]);
            break;
        case 'move':
        case 'mv': {
            const usage = 'usage: move N to M | move N:M to M | move N:M --to <track>';
            if (!isRange(args[0]))
                throw new Error(usage);
            const spec = args.shift();
            if (opts.to !== undefined) {
                if (args.length)
                    throw new Error(usage);
                const target = namedTrack(dir, opts.to);
                if (target.file === file)
                    throw new Error(`"${target.name}" is the current track — use: move N to M`);
                if (target.track.closed)
                    throw closedError(target.name);
                msg = lib.moveTo(track, spec, target.track, target.name);
                msg += `\n${lib.render(target.track, renderOpts)}`;
                before = () => lib.saveTrack(target.file, target.track); // first: a crash in between duplicates, never loses
                break;
            }
            if (args[0] === 'to')
                args.shift();
            if (!isAddr(args[0]))
                throw new Error(usage);
            msg = lib.move(track, spec, args[0]);
            break;
        }
        case 'rename': {
            const addr = needAddr(args, 'rename N <title>');
            msg = lib.rename(track, addr, args.join(' '));
            after = () => links.syncForkTitle(file, track.bubbles[lib.resolve(track, addr)]);
            break;
        }
        case 'handoff':
            msg = lib.setHandoff(track, args.join(' '));
            if (track.handoff)
                msg += ` — in a fresh chat run: /bubble switch ${found.name}`;
            break;
        case 'title':
            msg = lib.setTitle(track, args.join(' '));
            after = () => links.syncTitle(file, track);
            break;
        case 'hint': {
            const addr = needAddr(args, 'hint N <text> | hint N -');
            msg = lib.hint(track, addr, args.join(' '));
            break;
        }
        case 'fog': {
            const spec = isRange(args[0]) ? args.shift() : undefined;
            msg = lib.fog(track, spec, args[0], { force: opts.force });
            break;
        }
        case 'type': {
            const addr = isAddr(args[0]) ? args.shift() : undefined;
            msg = lib.setType(track, addr, args[0]);
            break;
        }
        case 'fill': {
            const addr = isAddr(args[0]) ? args.shift() : undefined;
            msg = lib.fill(track, addr, args.join(' '));
            break;
        }
        case 'done': {
            const active = lib.activeBubble(track);
            if (active)
                links.checkForkFinished(file, active, { force: opts.force });
            msg = lib.done(track);
            after = () => links.popFinishedParents(file, track).join('\n');
            stop = true;
            break;
        }
        default:
            throw new Error(`unknown command "${cmd}" — try: help`);
    }
    // A closed track is archived: every change above is refused before anything is written.
    if (track.closed)
        throw closedError(found.name);
    if (into)
        msg += ` — on track "${found.name}"; the current track stays "${lib.currentName(found.bubblesDir)}"`;
    if (before)
        before();
    lib.saveTrack(file, track);
    const linked = after ? after() : '';
    console.log(linked ? `${msg}\n${linked}` : msg);
    console.log('');
    printTrack(file, track, renderOpts);
    if (stop && lib.activeBubble(track)) {
        console.log('');
        console.log(STOP);
    }
    return 0; // exit 3 is reserved for `show`, so a successful mutation never looks like an error
}
