// Track-level commands: which track is current (init, create, switch, tracks, close, delete, fork, diverge).
import * as fs from 'node:fs';
import * as path from 'node:path';
import * as lib from '../index.js';
import * as links from '../links/index.js';
import { isAddr } from './args.js';
import { printTrack } from './print.js';
/** Run a track-level command; returns an exit code, or undefined if `cmd` isn't one. */
export function runTrackCommand(cmd, args, { dir, opts, renderOpts }) {
    const bubblesDir = lib.findBubblesDir(dir) || path.join(dir, lib.TRACK_DIR);
    const create = (name, title) => {
        lib.checkName(name);
        const file = lib.trackPath(bubblesDir, name);
        const track = { title: title || name, bubbles: [] };
        lib.saveTrack(file, track);
        lib.setCurrent(bubblesDir, name);
        console.log(`created track "${name}" (${file})`);
        console.log('');
        printTrack(file, track, renderOpts);
        return 0;
    };
    switch (cmd) {
        case 'init': {
            const file = lib.trackPath(bubblesDir, lib.DEFAULT_NAME);
            if (fs.existsSync(file))
                throw new Error(`track already exists: ${file} — use: switch <name> for another track`);
            return create(lib.DEFAULT_NAME, args.join(' ') || path.basename(dir));
        }
        case 'create': {
            const name = lib.checkName(args.shift());
            if (fs.existsSync(lib.trackPath(bubblesDir, name)))
                throw new Error(`track "${name}" already exists — use: switch ${name}`);
            return create(name, args.join(' '));
        }
        case 'switch': {
            let name = args.shift();
            if (!name) {
                // bare switch: resume the current (last switched-to) track, else the default one
                name = [lib.currentName(bubblesDir), lib.DEFAULT_NAME].find((n) => fs.existsSync(lib.trackPath(bubblesDir, n)));
                if (!name)
                    throw new Error('no tracks yet — start one with: switch <name>');
            }
            lib.checkName(name);
            const file = lib.trackPath(bubblesDir, name);
            if (!fs.existsSync(file))
                return create(name, args.join(' '));
            const track = lib.loadTrack(file);
            lib.setCurrent(bubblesDir, name);
            console.log(`resumed track "${name}"`);
            console.log('');
            return printTrack(file, track, renderOpts);
        }
        case 'tracks': {
            const names = lib.listTracks(bubblesDir);
            if (!names.length) {
                console.log('no tracks yet — start one with: switch <name>');
                return 0;
            }
            const current = lib.currentName(bubblesDir);
            for (const name of names) {
                let line;
                try {
                    line = lib.render(lib.loadTrack(lib.trackPath(bubblesDir, name)), renderOpts);
                }
                catch (err) {
                    line = `invalid: ${err.message}`;
                }
                console.log(`${name === current ? '→' : ' '} ${name.padEnd(16)} ${line}`);
            }
            return 0;
        }
        case 'fork':
        case 'diverge': {
            // fork: build on the bubble (child.parent, the bubble waits). diverge: a different direction (child.origin, nothing waits).
            const found = lib.findTrack(dir);
            if (!found)
                throw new Error(`no current track to ${cmd} from — start one with: switch <name>`);
            if (!found.track)
                throw new Error(`invalid ${found.file}: ${found.error}`);
            const addr = isAddr(args[0]) ? args.shift() : undefined;
            const name = lib.checkName(args.shift());
            // A side track can have its own title; a fork's title follows its bubble.
            const title = args.join(' ').trim();
            if (title && cmd === 'fork')
                throw new Error(`fork takes no title — the fork is titled after its bubble and stays in sync (diverge takes one)`);
            const childFile = lib.trackPath(bubblesDir, name);
            if (fs.existsSync(childFile))
                throw new Error(`track "${name}" already exists — pick another name`);
            // References are relative paths with forward slashes, so tracks survive a moved checkout and other OSes.
            const rel = (from, to) => path.relative(path.dirname(from), to).split(path.sep).join('/');
            const bubble = (cmd === 'fork' ? lib.markFork : lib.markDiverge)(found.track, addr, rel(found.file, childFile));
            const link = { track: rel(childFile, found.file), bubble: bubble.id, title: bubble.title };
            const child = { title: title || bubble.title, [cmd === 'fork' ? 'parent' : 'origin']: link, bubbles: [] };
            lib.saveTrack(childFile, child);
            // A closed track stays untouched: the child links back to it, but it never learns about the child.
            if (!found.track.closed)
                lib.saveTrack(found.file, found.track);
            lib.setCurrent(bubblesDir, name);
            const verb = cmd === 'fork' ? 'forked' : 'diverged from';
            const from = found.track.closed ? ` of closed track "${found.name}"` : '';
            console.log(`${verb} "${bubble.title}"${from} into track "${name}" — a fresh track: ask the human what to do, sketch it, classify all fog`);
            console.log('');
            return printTrack(childFile, child, renderOpts);
        }
        case 'close': {
            // Closing cascades top down to every fork under the track, whatever its state; side tracks stay open.
            const name = lib.checkName(args.shift());
            const file = lib.trackPath(bubblesDir, name);
            if (!fs.existsSync(file))
                throw new Error(`no track "${name}"`);
            const track = lib.loadTrack(file);
            const forks = links.forkTree(file, track);
            const open = forks.filter((f) => f.track && !f.track.closed);
            const label = (f) => `"${path.basename(f.file, '.json')}"`;
            if (track.closed && !open.length)
                throw new Error(`track "${name}" is already closed`);
            if (!opts.force) {
                const also = open.length ? ` (and its forks ${open.map(label).join(', ')})` : '';
                throw new Error(`closing "${name}"${also} is permanent (read-only, no reopen) — confirm with the human, then re-run with --force`);
            }
            const at = new Date().toISOString();
            if (track.closed) {
                console.log(`track "${name}" is already closed — closing its open forks`);
            }
            else {
                track.closed = { at };
                lib.saveTrack(file, track);
                console.log(`closed track "${name}" — read-only from now on; fork, diverge or switch to keep working`);
                // A closed fork counts as finished, so its parent bubble pops (and on up the chain).
                for (const msg of links.popFinishedParents(file, track))
                    console.log(msg);
            }
            // Forks never pop anything: their parent is closed by now. One failing fork doesn't stop the rest.
            let failed = 0;
            for (const f of forks) {
                if (!f.track)
                    console.log(`  fork ${label(f)}: ${f.problem}`);
                else if (f.track.closed)
                    console.log(`  fork ${label(f)}: already closed`);
                else {
                    try {
                        f.track.closed = { at };
                        lib.saveTrack(f.file, f.track);
                        console.log(`  closed fork ${label(f)}`);
                    }
                    catch (err) {
                        failed++;
                        console.error(`  fork ${label(f)}: not closed (${err.message}) — re-run close to retry`);
                    }
                }
            }
            console.log('');
            printTrack(file, track, renderOpts);
            return failed ? 1 : 0;
        }
        case 'delete': {
            const name = lib.checkName(args.shift());
            const file = lib.trackPath(bubblesDir, name);
            if (!fs.existsSync(file))
                throw new Error(`no track "${name}"`);
            if (name === lib.currentName(bubblesDir))
                throw new Error(`"${name}" is the current track — switch to another one first`);
            if (!opts.force)
                throw new Error(`deleting "${name}" can't be undone — confirm with the human, then re-run with --force`);
            fs.unlinkSync(file);
            console.log(`deleted track "${name}"`);
            return 0;
        }
        default:
            return undefined;
    }
}
