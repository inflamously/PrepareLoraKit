"""Caption-verification half of the UI interaction provider, mixed into
:class:`UiInteractionProvider`.
"""
from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

from prepare_lora_kit_ui.runner.payloads import _image_payload, _jsonable

VERDICTS = ("correct", "generic", "wrong")
# "correct" is the no-op default (same role as vae_review's "keep"): reviewCard
# always lands an item on one of the decision options at construction, and a
# fourth "unreviewed" option would pollute the right-click cycle.
DEFAULT_VERDICT = "correct"
_MAX_PROMPT_CHARS = 4000


class CaptionVerifyInteractionMixin:
    """``caption_verify`` plus the live ``generate_caption_preview`` RPC."""

    def _init_caption_verify(self) -> None:
        # Guards the small state below and is never held across a render: holding it for the
        # 30 s a diffusion call takes would block teardown and every cancel path.
        self._verify_lock = threading.Lock()
        self._generate_lock = threading.Lock()
        self._verify_generator = None
        self._verify_paths: set[Path] = set()
        self._verify_settings: dict[str, Any] = {}

    # --- the blocking review ---------------------------------------------

    def caption_verify(
            self,
            items: list[dict],
            *,
            generator: Any | None = None,
            preview_dir: Path | None = None,
            settings: dict[str, Any] | None = None,
    ) -> dict[str, dict]:
        payload_items = [self._verify_item_payload(item) for item in items]

        with self._verify_lock:
            self._verify_generator = generator
            self._verify_paths = {
                Path(entry["path"]).resolve() for entry in payload_items
            }
            self._verify_settings = dict(settings or {})
        try:
            answer = self._job.request_input("caption_verify", {
                "step_type": "CaptionVerifierStep",
                "settings": _jsonable(settings or {}),
                "verdicts": list(VERDICTS),
                "items": payload_items,
            })
        finally:
            with self._verify_lock:
                self._verify_generator = None
                self._verify_paths = set()
                self._verify_settings = {}
        return self._parse_caption_verify_answer(answer, payload_items)

    def _verify_item_payload(self, item: dict) -> dict:
        source = Path(str(item["path"]))
        caption = str(item.get("caption") or "")
        entry = _image_payload(source, self._media_base_url)
        width, height = _image_size(source)
        caption_path = item.get("caption_path") or source.with_suffix(".txt")
        entry.update({
            "width": width,
            "height": height,
            "caption": caption,
            "caption_path": str(Path(str(caption_path)).resolve()),
            "has_caption": bool(caption.strip()),
            # Seeded by the step from the verdict ledger so re-entering the
            # review remembers earlier judgements. Absent for any caller that
            # hand-builds items (the CLI, tests), hence the default.
            "initial_verdict": _verdict_or_default(item.get("initial_verdict")),
        })
        return entry

    def _parse_caption_verify_answer(
            self, answer: Any, payload_items: list[dict],
    ) -> dict[str, dict]:
        originals = {entry["path"]: entry["caption"] for entry in payload_items}
        raw = answer.get("items") if isinstance(answer, dict) else None
        if not isinstance(raw, dict):
            return {}

        parsed: dict[str, dict] = {}
        for key, value in raw.items():
            if not isinstance(value, dict):
                continue
            path = str(key)
            verdict = str(value.get("verdict") or DEFAULT_VERDICT)
            caption = str(value.get("caption") or "")
            parsed[path] = {
                "verdict": verdict if verdict in VERDICTS else DEFAULT_VERDICT,
                "caption": caption,
                # Recomputed from the payload snapshot rather than trusting the
                # frontend's flag — one line, removes a class of "the UI said it
                # was unchanged so we skipped the write" bugs.
                "edited": caption.strip() != originals.get(path, caption).strip(),
            }
        return parsed

    # --- the live RPC -----------------------------------------------------

    def generate_caption_preview(
            self, image_path: str, caption: str, options: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Render one caption while the review modal is open.

        Called on a pywebview RPC thread while the pipeline thread is parked in
        ``PipelineJob.request_input``.
        """
        self._job.raise_if_cancelled()
        requested = Path(image_path).resolve()
        prompt = str(caption or "").strip()
        if not prompt:
            raise ValueError("Caption text is required to generate a preview")
        if len(prompt) > _MAX_PROMPT_CHARS:
            raise ValueError("Caption is too long to render")

        with self._verify_lock:
            generator = self._verify_generator
            in_batch = requested in self._verify_paths
            settings = dict(self._verify_settings)
        if generator is None:
            raise RuntimeError("No active caption verification request")
        if not in_batch:
            raise RuntimeError(
                "Requested image is not in the active caption verification batch"
            )

        # Held for the whole render, acquired non-blocking: a second concurrent click fails
        # fast instead of queueing a thread for half a minute and then drawing a caption the
        # user has already changed.
        if not self._generate_lock.acquire(blocking=False):
            raise RuntimeError("A preview is already being generated")
        try:
            result = generator(prompt, {
                **settings,
                **(options or {}),
                "source_path": str(requested),
            })
        finally:
            self._generate_lock.release()

        self._job.raise_if_cancelled()
        return self._preview_payload(result, prompt)

    def _preview_payload(self, result: Any, prompt: str) -> dict[str, Any]:
        record = dict(result) if isinstance(result, dict) else {}
        payload: dict[str, Any] = {
            "seed": record.get("seed"),
            "caption": prompt,
            "elapsed_ms": record.get("elapsed_ms"),
            "steps": record.get("steps"),
            "guidance": record.get("guidance"),
            "width": record.get("width"),
            "height": record.get("height"),
            "model_id": record.get("model_id"),
            "truncated": bool(record.get("truncated")),
            "token_count": record.get("token_count"),
        }
        saved = record.get("path")
        if saved:
            # The step writes a fresh filename per render on purpose: the media
            # endpoint sends Cache-Control: max-age=86400, so reusing a path
            # would serve a re-roll from the browser cache without revalidating.
            payload.update(_image_payload(Path(str(saved)), self._media_base_url))
        return payload


def _verdict_or_default(value: Any) -> str:
    return str(value) if value in VERDICTS else DEFAULT_VERDICT


def _image_size(path: Path) -> tuple[int | None, int | None]:
    try:
        from PIL import Image

        with Image.open(path) as image:
            return image.size
    except (OSError, ValueError):
        return None, None
