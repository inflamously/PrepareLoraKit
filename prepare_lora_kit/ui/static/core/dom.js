export const $ = (id) => document.getElementById(id);

export function setText(id, text) {
  $(id).textContent = text || "";
}

export function setShellStatus(status) {
  $("app").dataset.jobStatus = status || "idle";
}

export function stepLabel(type) {
  return type.replace(/Step$/, "").replace(/([a-z])([A-Z])/g, "$1 $2");
}

export function escapeText(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}
