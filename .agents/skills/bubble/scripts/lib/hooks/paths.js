// Which files a pre-tool call is about to edit, and whether one is part of the plan itself.
import * as path from 'node:path';
/** Pull target file paths from a pre-tool payload (absolute, resolved against `root`). */
export function extractTargetPaths(input, root) {
    const ti = (input && input.tool_input) || {};
    const found = [];
    for (const key of ['file_path', 'path', 'notebook_path']) {
        const val = ti[key];
        if (typeof val === 'string' && val)
            found.push(val);
    }
    // Codex apply_patch: raw patch text (in `command`, or `input`/`patch` in some versions).
    for (const key of ['command', 'input', 'patch']) {
        const raw = ti[key];
        const val = Array.isArray(raw) ? raw.join('\n') : raw;
        if (typeof val !== 'string')
            continue;
        const re = /^\*\*\* (?:Add|Update|Delete) File: (.+)$|^\*\*\* Move to: (.+)$/gm;
        let m;
        while ((m = re.exec(val)))
            found.push((m[1] || m[2]).trim());
    }
    return found.map((p) => path.resolve(root, p));
}
/** True if `file` is inside `<trackRoot>/.bubble-tracks`. */
export function isInsideBubblesDir(file, trackFile) {
    const bubblesDir = path.dirname(trackFile);
    const rel = path.relative(bubblesDir, file);
    return rel === '' || (!rel.startsWith('..') && !path.isAbsolute(rel));
}
