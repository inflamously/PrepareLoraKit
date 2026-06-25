"""UI interaction provider used by background pipeline jobs."""
from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

from ...interaction import InteractionProvider, RegionCaptioner
from ...project.config_schema import schema_payload
from .job import PipelineJob
from .payloads import _image_payload, _jsonable


class UiInteractionProvider(InteractionProvider):
    """Provider that pauses a job and waits for frontend responses."""

    def __init__(self, job: PipelineJob, media_base_url: str | None = None) -> None:
        self._job = job
        self._media_base_url = media_base_url
        self._caption_lock = threading.Lock()
        self._captioner: RegionCaptioner | None = None
        self._caption_image: Path | None = None

    def step_config(self, step_type: str, current_config: Any, error: str | None = None) -> dict:
        """Pause before a step so the frontend can edit its config tunables.

        Returns the submitted overrides mapping (``{field: value}``); an empty
        mapping means "run with the project defaults".
        """

        payload = {
            "step_type": step_type,
            "fields": schema_payload(step_type),
            "values": _jsonable(current_config),
            "error": error,
        }
        answer = self._job.request_input("step_config", payload)
        if not isinstance(answer, dict):
            return {}
        overrides = answer.get("overrides", {})
        return overrides if isinstance(overrides, dict) else {}

    def source_review(self, scored: list[tuple[Path, dict]]) -> dict[str, str]:
        items = []
        for path, info in scored:
            item = _image_payload(path, self._media_base_url)
            item.update({
                "scores": _jsonable(info.get("scores", {})),
                "quality": info.get("quality"),
                "auto_reject": bool(info.get("auto_reject")),
                "auto_reasons": _jsonable(info.get("auto_reasons", [])),
                "initial_decision": "reject" if info.get("auto_reject") else "keep",
            })
            items.append(item)

        answer = self._job.request_input("source_review", {"items": items})
        decisions = answer.get("decisions", {}) if isinstance(answer, dict) else {}
        return {str(k): str(v) for k, v in decisions.items()}

    def annotate_image(
        self,
        path: Path,
        *,
        captioner: RegionCaptioner | None = None,
    ) -> tuple[list[dict], bool, bool]:
        with self._caption_lock:
            self._captioner = captioner
            self._caption_image = path
        try:
            payload = _image_payload(path, self._media_base_url)
            answer = self._job.request_input("bbox_annotation", payload)
        finally:
            with self._caption_lock:
                self._captioner = None
                self._caption_image = None

        if not isinstance(answer, dict):
            return [], True, False
        annotations = answer.get("annotations", [])
        if not isinstance(annotations, list):
            annotations = []
        return (
            annotations,
            bool(answer.get("skipped", False)),
            bool(answer.get("skip_all", False)),
        )

    def vae_review(self, items: list[dict]) -> dict[str, str]:
        payload_items = []
        for item in items:
            views = item.get("views", {}) if isinstance(item.get("views"), dict) else {}
            view_payloads = {
                name: _image_payload(Path(path), self._media_base_url)
                for name, path in views.items()
                if path
            }
            original_path = Path(str(item.get("path")))
            payload_items.append({
                "path": str(original_path.resolve()),
                "name": str(item.get("name") or original_path.name),
                "width": item.get("width"),
                "height": item.get("height"),
                "hf_loss": item.get("hf_loss"),
                "threshold": item.get("threshold"),
                "diff_threshold": item.get("diff_threshold"),
                "flagged": bool(item.get("flagged")),
                "initial_decision": str(item.get("initial_decision") or "keep"),
                "views": view_payloads,
            })

        answer = self._job.request_input("vae_review", {"items": payload_items})
        decisions = answer.get("decisions", {}) if isinstance(answer, dict) else {}
        return {str(k): str(v) for k, v in decisions.items()}

    def curate_details(self, report: dict[str, Any], report_path: Path) -> bool:
        coverage_path = report.get("coverage_image")
        coverage_image = None
        if coverage_path:
            path = Path(str(coverage_path))
            if path.is_file():
                coverage_image = _image_payload(path, self._media_base_url)

        coverage = report.get("coverage") if isinstance(report.get("coverage"), dict) else {}
        payload = {
            "report_path": str(report_path.resolve()),
            "coverage_image": coverage_image,
            "coverage_method": coverage.get("method"),
            "coverage": _jsonable(coverage),
            "summary": {
                "kept_images": len(report.get("kept_images") or []),
                "duplicate_pairs": len(report.get("duplicate_pairs") or []),
                "dropped_duplicates": len(report.get("dropped_duplicates") or []),
                "occluded_flagged": len(report.get("occluded_flagged") or []),
            },
        }
        answer = self._job.request_input("curate_details", payload)
        return bool(answer.get("confirmed", False)) if isinstance(answer, dict) else False

    def caption_region(self, image_path: str, box: dict[str, Any]) -> dict[str, Any]:
        self._job.raise_if_cancelled()
        with self._caption_lock:
            captioner = self._captioner
            active = self._caption_image
        if captioner is None or active is None:
            raise RuntimeError("No active caption annotation request")
        requested = Path(image_path).resolve()
        if requested != active.resolve():
            raise RuntimeError("Requested image is not the active annotation image")

        from PIL import Image

        with Image.open(active).convert("RGB") as img:
            w, h = img.size
            try:
                x1, x2 = sorted((float(box["x1"]), float(box["x2"])))
                y1, y2 = sorted((float(box["y1"]), float(box["y2"])))
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError("Bounding box must include numeric x1, y1, x2, and y2") from exc
            x1, x2 = max(0.0, x1), min(1.0, x2)
            y1, y2 = max(0.0, y1), min(1.0, y2)
            l = max(0, min(w - 1, int(x1 * w)))
            t = max(0, min(h - 1, int(y1 * h)))
            r = max(l + 1, min(w, int(x2 * w)))
            b = max(t + 1, min(h, int(y2 * h)))
            crop = img.crop((l, t, max(l + 1, r), max(t + 1, b)))
        result = captioner(crop, {"source_path": str(active), "box": box})
        self._job.raise_if_cancelled()
        if isinstance(result, dict):
            result["caption"] = str(result.get("caption") or "").strip()
            return result
        return {"caption": str(result or "").strip()}
