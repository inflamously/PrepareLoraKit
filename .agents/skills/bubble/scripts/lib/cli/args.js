// CLI language: help text and argument parsing. A leading "bubble" word is optional,
// and a whole phrase can be passed as one quoted argument: node bubble.js "move 2 to 5".
import { TYPES } from '../model.js';
export const HELP = `bubble-tracks — the bubble language

  switch [name] [title]         resume track <name>, or create it; no name = the current (else default) track
  create <name> [title]         create a new track (refuses if it exists) and make it current
  tracks                        list all tracks, current marked →
  close <name> --force          finish and archive a track: read-only for good, no reopen. Also closes
                                all its forks (side tracks stay open) and pops its parent bubble
  delete <name> --force         delete a track (not the current one)
  fork [N] <name>               build on bubble N in a child track <name>; the bubble waits for it. Makes it current
  diverge [N] <name> [title]    go a different direction from bubble N in a side track <name> (titled after
                                the bubble unless given); nothing waits. Makes it current
  init <title>                  create the default track (.bubble-tracks/track.json)

  show                          render the current track + list its bubbles
  add <title>   | add ?         append a todo (or fog) bubble
  insert at N <title> | insert at N ?
                                insert a todo (or fog) bubble at position N
  remove N | N:M                delete a bubble or a range
  move N to M | move N:M to M   move a bubble or block so it starts at M
  move N | N:M --to <track>     move a bubble or block to the end of another track
  rename N <title>              retitle a planned bubble
  title <text>                  rename the track itself
  handoff <note> | handoff -    save (or clear) the note a fresh chat reads to resume
  hint N <text> | hint N -      attach (or clear) a note for that bubble
  fog [N | N:M] [TYPE]          turn bubbles into fog (done ones need --force)
  type [N] <TYPE>               classify a fog bubble
  fill [N] <title>              the human's content for a fog bubble: fog -> todo
  done                          pop the active bubble, then ⏸ stop

  N: position on the track (omitted = the active bubble). N:M: N through M, inclusive.
  TYPE: ${TYPES.join(' | ')}  (or kk | ku | uk | uu)
  Options: --dir <repo> (default: cwd)   --ascii (or BUBBLES_ASCII=1)   --force
           --to <track>: add, insert and hint write into that track; the current track stays current
           color on a terminal; BUBBLES_COLOR=1/0 forces it, NO_COLOR disables it
           add <title> --at N  and  add --fog [title]  still work.
  Exit codes: 0 ok, 1 error, 3 (show only) active bubble is fog — needs the human`;
export function parseArgs(argv) {
    const pos = [];
    const opts = {};
    for (let i = 0; i < argv.length; i++) {
        const a = argv[i];
        if (a === '--ascii')
            opts.ascii = true;
        else if (a === '--fog')
            opts.fog = true;
        else if (a === '--force')
            opts.force = true;
        else if (a === '--dir')
            opts.dir = argv[++i];
        else if (a === '--at')
            opts.at = argv[++i];
        else if (a === '--to') {
            opts.to = argv[++i];
            if (!opts.to || opts.to.startsWith('--'))
                throw new Error('--to needs a track name');
        }
        else if (a === '-h' || a === '--help')
            opts.help = true;
        else if (a.startsWith('--'))
            throw new Error(`unknown option "${a}" — try: help`);
        else
            pos.push(a);
    }
    // A whole phrase passed as one argument: "move 2 to 5".
    if (pos.length === 1 && /\s/.test(pos[0].trim()))
        pos.splice(0, 1, ...pos[0].trim().split(/\s+/));
    if (pos[0] === 'bubble')
        pos.shift();
    return { cmd: pos[0], args: pos.slice(1), opts };
}
export const isAddr = (s) => typeof s === 'string' && /^\d+$/.test(s);
export const isRange = (s) => typeof s === 'string' && /^\d+(:\d+)?$/.test(s);
export function needAddr(args, usage) {
    if (!isAddr(args[0]))
        throw new Error(`usage: ${usage}`);
    return args.shift();
}
