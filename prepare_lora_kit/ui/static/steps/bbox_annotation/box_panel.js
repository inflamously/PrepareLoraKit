import { escapeText } from "../../core/dom.js";

export function createBoxPanel({
  boxList,
  bboxStatus,
  captionBoxButton,
  boxes,
  getSelected,
  setSelected,
  onChange,
}) {
  function render() {
    const selected = getSelected();
    const selectedBox = boxes[selected];
    bboxStatus.textContent = selectedBox
      ? `Selected: Region ${selected + 1}${selectedBox.label ? ` - ${selectedBox.label}` : ""}`
      : "No box selected";
    captionBoxButton.disabled = selected < 0;
    boxList.replaceChildren();
    boxes.forEach((box, index) => {
      const item = document.createElement("div");
      item.className = `box-item${index === selected ? " selected" : ""}`;
      item.innerHTML = `
        <strong>Region ${index + 1}</strong>
        <input value="${escapeText(box.label || "")}" placeholder="Description" />
        ${box.crop_name ? `<small>${escapeText(box.crop_name)}</small>` : ""}
        <button class="secondary">Select</button>
        <button class="danger">Delete</button>
      `;
      const input = item.querySelector("input");
      input.addEventListener("input", () => {
        box.label = input.value;
        onChange();
      });
      item.querySelector(".secondary").addEventListener("click", () => {
        setSelected(index);
        onChange();
      });
      item.querySelector(".danger").addEventListener("click", () => {
        boxes.splice(index, 1);
        setSelected(-1);
        onChange();
      });
      boxList.appendChild(item);
    });
  }

  return { render };
}
