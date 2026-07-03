/**
 * Run/job slice of the global {@link state} object, tracking the run that the
 * shell is currently polling and any pending interactive prompt.
 *
 * @typedef {Object} JobState
 * @property {string | null} jobId - Id of the active run, used for status polling
 *   and `submit_interaction`/`cancel_job` calls; null when no run is in flight.
 * @property {import("../core/api.js").JobPayload | null} job - Latest polled job
 *   snapshot, or null before the first poll.
 * @property {boolean} runStarting - True between clicking "Run" and receiving the
 *   `job_id`, used to disable the button and show "Starting...".
 * @property {string | null} handledRequestId - Id of the last
 *   {@link import("../core/api.js").PendingInput} already surfaced to the user, so
 *   the same prompt is not handled twice across polls.
 */

/** @type {JobState} */
export const jobState = {
  jobId: null,
  job: null,
  runStarting: false,
  handledRequestId: null,
};
