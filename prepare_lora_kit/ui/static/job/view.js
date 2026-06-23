import {$, setShellStatus, setText, stepLabel} from "../core/dom.js";
import {state} from "../+state/index.js";

const TERMINAL_STATUSES = new Set(["completed", "failed", "cancelled"]);

export function renderJob() {
    const job = state.job;
    const cancelButton = $("cancelButton");
    const currentStepLabel = $("currentStepLabel");
    const logRail = $("logOutput")
    const openOutput = $("openOutput")
    const runButton = $("runButton")

    if (!job) {
        setShellStatus("idle");
        setText("jobSummary", "Idle");
        currentStepLabel.classList.add("hidden");
        currentStepLabel.textContent = "";
        logRail.textContent = "";
        cancelButton.disabled = true;
        cancelButton.textContent = "Cancel";
        openOutput.disabled = true;
        runButton.disabled = state.runStarting;
        runButton.textContent = state.runStarting ? "Starting..." : "Run selected";
        return;
    }

    setShellStatus(job.cancel_requested ? "cancelling" : job.status);
    setText(
        "jobSummary",
        job.cancel_requested ? "Cancellation requested" : job.status,
    );
    renderCurrentStep(job, currentStepLabel);

    const nextLogs = (job.logs || []).join("\n");
    if (logRail.textContent !== nextLogs && !hasSelectionInside(logRail)) {
        logRail.textContent = nextLogs;
    }

    const cancelling = job.cancel_requested || job.status === "cancelling";
    const running = !TERMINAL_STATUSES.has(job.status);
    cancelButton.disabled = TERMINAL_STATUSES.has(job.status) || cancelling;
    cancelButton.textContent = cancelling ? "Cancelling..." : "Cancel";
    openOutput.disabled = !job.result?.output_dir;
    runButton.disabled = state.runStarting || running;
    runButton.textContent = state.runStarting ? "Starting..." : "Run selected";
}

function renderCurrentStep(job, currentStepLabel) {
    if (!job.current_step) {
        currentStepLabel.classList.add("hidden");
        currentStepLabel.textContent = "";
        return;
    }

    currentStepLabel.textContent = `Current step: ${stepLabel(job.current_step)}`;
    currentStepLabel.classList.remove("hidden");
}

function hasSelectionInside(element) {
    const selection = globalThis.getSelection();
    if (!selection || selection.isCollapsed) return false;

    return (
        element.contains(selection.anchorNode) ||
        element.contains(selection.focusNode)
    );
}
