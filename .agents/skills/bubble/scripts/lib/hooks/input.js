// The agent's JSON payload on stdin, and the workspace dir it names.
/** Read all of stdin and parse JSON; {} on empty/invalid input. */
export function readStdinJson() {
    return new Promise((resolve) => {
        if (process.stdin.isTTY)
            return resolve({});
        let data = '';
        process.stdin.setEncoding('utf8');
        process.stdin.on('data', (chunk) => (data += chunk));
        process.stdin.on('end', () => {
            try {
                resolve(data.trim() ? JSON.parse(data) : {});
            }
            catch {
                resolve({});
            }
        });
        process.stdin.on('error', () => resolve({}));
    });
}
/** Workspace dir from the agent's JSON payload (Claude / Codex / Gemini), never the process cwd first. */
export function resolveRoot(input) {
    const ws = (input && input.workspace) || {};
    return (ws.project_dir ||
        ws.current_dir ||
        (input && input.cwd) ||
        process.env.GEMINI_PROJECT_DIR ||
        process.env.CLAUDE_PROJECT_DIR ||
        process.cwd());
}
