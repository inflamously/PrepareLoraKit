import {$, setShellStatus, setText, stepLabel} from "../core/dom.js";
import {state} from "../+state/index.js";
import { renderCaptionStatus } from "../caption/status.js";

const TERMINAL_STATUSES = new Set(["completed", "failed", "cancelled"]);

/** Last log buffer rendered into a given console, so a poll that changed nothing
 *  is skipped. Keyed by the element rather than held in a plain variable so it
 *  dies with the DOM instead of leaking across it. It cannot be derived from the
 *  element any more: the lines are block elements, so the newlines live in line
 *  boxes and `textContent` returns them concatenated. */
const renderedLogs = new WeakMap();

export function renderJob() {
    const job = state.job;
    const cancelButton = $("cancelButton");
    const currentStepLabel = $("currentStepLabel");
    const captionStatusLabel = $("captionStatusLabel");
    const logRail = $("logOutput")
    const openOutput = $("openOutput")
    const runButton = $("runButton")

    if (!job) {
        setShellStatus("idle");
        setText("jobSummary", "Idle");
        currentStepLabel.classList.add("hidden");
        renderCaptionStatus(captionStatusLabel, null);
        currentStepLabel.textContent = "";
        clearLogs(logRail);
        cancelButton.disabled = true;
        cancelButton.textContent = "Cancel";
        renderOpenOutput(openOutput, null);
        runButton.disabled = state.runStarting;
        runButton.textContent = state.runStarting ? "Starting..." : "Run active";
        return;
    }

    setShellStatus(job.cancel_requested ? "cancelling" : job.status);
    setText(
        "jobSummary",
        job.cancel_requested ? "Cancellation requested" : job.status,
    );
    renderCurrentStep(job, currentStepLabel);
    renderCaptionStatus(captionStatusLabel, job.caption_status);

    const logs = job.logs || [];
    const nextLogs = logs.join("\n");
    if (renderedLogs.get(logRail) !== nextLogs && !hasSelectionInside(logRail)) {
        logRail.replaceChildren(...logs.map(toLogLine));
        renderedLogs.set(logRail, nextLogs);
        scrollLogsToBottom(logRail);
    }

    const cancelling = job.cancel_requested || job.status === "cancelling";
    const running = !TERMINAL_STATUSES.has(job.status);
    cancelButton.disabled = TERMINAL_STATUSES.has(job.status) || cancelling;
    cancelButton.textContent = cancelling ? "Cancelling..." : "Cancel";
    renderOpenOutput(openOutput, job);
    runButton.disabled = state.runStarting || running;
    runButton.textContent = state.runStarting ? "Starting..." : "Run active";
}

/** The folder is openable once it exists on disk — from an earlier session, a partial
 *  run, or the job that just completed. */
function renderOpenOutput(openOutput, job) {
    const canOpen = state.outputExists || Boolean(job?.result?.output_dir);
    openOutput.disabled = !canOpen;
    openOutput.title = canOpen ? "" : "No output folder yet - run the pipeline first";
}

function renderCurrentStep(job, currentStepLabel) {
    if (!job.current_step) {
        currentStepLabel.classList.add("hidden");
        currentStepLabel.textContent = "";
        return;
    }

    const substep = job.current_substep ? ` / ${job.current_substep}` : "";
    currentStepLabel.textContent = `Current step: ${stepLabel(job.current_step)}${substep}`;
    currentStepLabel.classList.remove("hidden");
}

/** A blank line would render as no line box at all, which is only harmless
 *  because the runner drops empty lines before they ever reach the buffer
 *  (`prepare_lora_kit_ui/runner/logging.py`). */
function toLogLine(text) {
    const line = document.createElement("span");
    line.className = "nf-console__line";
    line.textContent = text;
    return line;
}

function clearLogs(logRail) {
    logRail.replaceChildren();
    renderedLogs.delete(logRail);
}

export function scrollLogsToBottom(logRail = $("logOutput")) {
    if (!logRail || !$("autoScroll")?.checked) return;
    logRail.scrollTop = logRail.scrollHeight;
}

function hasSelectionInside(element) {
    const selection = globalThis.getSelection();
    if (!selection || selection.isCollapsed) return false;

    return (
        element.contains(selection.anchorNode) ||
        element.contains(selection.focusNode)
    );
}
