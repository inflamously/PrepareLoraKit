// Track mutations: each changes the track in place and returns a short message for the CLI.
// One file per operation; ops that belong together share one.
export * from './add.js';
export * from './fog.js';
export * from './rename.js';
export * from './hint.js';
export * from './remove.js';
export * from './move.js';
export * from './handoff.js';
export * from './mark.js';
export * from './done.js';
