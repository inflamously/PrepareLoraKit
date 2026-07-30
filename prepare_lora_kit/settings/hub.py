"""Hugging Face Hub access: login status, repo reachability, readable failures.

The app deliberately stores no token of its own. ``huggingface_hub.get_token()``
already resolves the ``HF_TOKEN`` environment variable and the token file that
``hf auth login`` writes, so reusing it means there is exactly one place a
credential lives and we are not another one.

Everything here imports ``huggingface_hub`` *inside* functions. This module is
referenced from step packages, and ``tests/steps/test_imports.py`` walks every
module under ``steps/`` asserting that importing one stays cheap.
"""
from __future__ import annotations

import contextlib
import shutil
from collections.abc import Iterator
from typing import Any

HUB_URL = "https://huggingface.co"


def login_command() -> str:
    """The command to tell the user to run.

    ``huggingface-cli`` was removed in huggingface_hub 1.0 — its entry point now
    only prints a deprecation notice and exits — so showing it to a user on a
    current install would send them down a dead end.

    The installed version decides, not ``PATH``: on hub >= 1.0 with ``hf`` not
    yet on ``PATH`` the honest instruction is still ``hf auth login`` (they need
    to activate the venv), because ``huggingface-cli`` would not work either.
    ``PATH`` is only consulted when the version is unknown.
    """
    major = _hub_major_version()
    if major is None:
        return "hf auth login" if shutil.which("hf") else "huggingface-cli login"
    return "hf auth login" if major >= 1 else "huggingface-cli login"


def _hub_major_version() -> int | None:
    try:
        import huggingface_hub

        return int(str(huggingface_hub.__version__).split(".", 1)[0])
    except (ImportError, AttributeError, ValueError):
        return None


def repo_url(repo_id: str) -> str:
    return f"{HUB_URL}/{repo_id}"


def token_status() -> dict[str, Any]:
    """Whether a token is resolvable, and from where. Never touches the network."""
    try:
        from huggingface_hub import get_token
    except ImportError:
        return {"present": False, "source": None, "error": "huggingface_hub is not installed."}

    import os

    token = get_token()
    if not token:
        return {"present": False, "source": None, "error": None}
    source = "env" if os.environ.get("HF_TOKEN") else "stored"
    return {"present": True, "source": source, "error": None}


def account() -> dict[str, Any]:
    """Resolve the signed-in user. Network call — only ever run from a button."""
    status = token_status()
    if not status["present"]:
        return {"ok": False, "name": None, "error": status.get("error") or "No token found."}
    try:
        from huggingface_hub import whoami

        info = whoami()
    except Exception as exc:  # network, bad token, offline — all reported the same way
        return {"ok": False, "name": None, "error": _short(exc)}
    name = info.get("name") if isinstance(info, dict) else str(info)
    return {"ok": True, "name": name, "error": None}


def check_repo(repo_id: str) -> dict[str, Any]:
    """Can this machine read ``repo_id``? Network call — only ever run from a button.

    Uses ``auth_check``, which is purpose-built for exactly this question and is
    far cheaper than starting a download to find out.
    """
    result = {"repo_id": repo_id, "status": "ok", "message": "Accessible.",
              "url": repo_url(repo_id)}
    try:
        from huggingface_hub import auth_check
    except ImportError:
        return {**result, "status": "error", "message": "huggingface_hub is not installed."}

    try:
        auth_check(repo_id)
    except Exception as exc:
        return {**result, **_auth_failure(exc, repo_id)}
    return result


def _auth_failure(exc: Exception, repo_id: str) -> dict[str, str]:
    """Classify an ``auth_check`` failure into a status and a message.

    "Not found" is deliberately split: without a token the hub reports a private
    repo as missing, so saying "typo?" to a signed-out user sends them chasing the
    wrong problem. Checked in most- to least-specific order — ``GatedRepoError``
    and ``RepositoryNotFoundError`` are both ``HfHubHTTPError`` subclasses.
    """
    from huggingface_hub.errors import (
        GatedRepoError,
        HfHubHTTPError,
        RepositoryNotFoundError,
    )

    if isinstance(exc, GatedRepoError):
        return {"status": "gated", "message": _gated_message(repo_id)}
    if isinstance(exc, RepositoryNotFoundError):
        if token_status()["present"]:
            return {"status": "missing", "message": f"No repo '{repo_id}' (typo?)."}
        return {"status": "unauthorized", "message": _signed_out_message(repo_id)}
    if isinstance(exc, HfHubHTTPError):
        return {"status": "offline", "message": f"Hub error: {_short(exc)}"}
    if isinstance(exc, OSError):
        return {"status": "offline", "message": f"Could not reach {HUB_URL}: {_short(exc)}"}
    return {"status": "error", "message": _short(exc)}


def check_repos(repo_ids: list[str]) -> list[dict[str, Any]]:
    """Check several repos, skipping blanks and duplicates while keeping order."""
    seen: set[str] = set()
    results = []
    for repo_id in repo_ids:
        cleaned = (repo_id or "").strip()
        if not cleaned or cleaned in seen or cleaned in {"auto", "none"}:
            continue
        seen.add(cleaned)
        results.append(check_repo(cleaned))
    return results


@contextlib.contextmanager
def hub_error_context(model_id: str | None) -> Iterator[None]:
    """Turn a Hub access failure into something the user can act on.

    A gated repo otherwise surfaces deep inside diffusers/transformers as a bare
    401, which reads as "the model is broken" rather than "you need to accept a
    licence". The exception *type* is preserved so existing handlers keep
    working, and anything that is not a Hub access error — ``CancelledRun``
    included — passes through completely untouched.

    Hub errors are extended through their own ``append_to_message`` rather than
    rebuilt: ``HfHubHTTPError.__init__`` takes a required keyword ``response``,
    so reconstructing one from a message alone raises ``TypeError`` and would
    replace the real failure with a bug in this helper.
    """
    try:
        yield
    except Exception as exc:
        # append_to_message mutates the exception, so a nested context would
        # stack the same paragraph twice. Mark it once and let it through after.
        if getattr(exc, "_plk_hub_hint", False):
            raise
        hint = access_hint(exc, model_id)
        if hint is None:
            raise
        append = getattr(exc, "append_to_message", None)
        if callable(append):
            append(f"\n\n{hint}")
            with contextlib.suppress(AttributeError):   # exotic exceptions with __slots__
                exc._plk_hub_hint = True
            raise
        raise RuntimeError(f"{exc}\n\n{hint}") from exc


def access_hint(exc: BaseException, model_id: str | None) -> str | None:
    """The actionable message for a Hub access error, or ``None`` if unrelated."""
    try:
        from huggingface_hub.errors import GatedRepoError, RepositoryNotFoundError
    except ImportError:
        return None

    name = model_id or "the requested model"
    if isinstance(exc, GatedRepoError):
        return _gated_message(name)
    if isinstance(exc, RepositoryNotFoundError):
        if token_status()["present"]:
            return (
                f"'{name}' was not found on the Hub. Check the id for a typo, or open "
                f"{repo_url(name)} to confirm it exists."
            )
        return _signed_out_message(name)
    return None


def _gated_message(repo_id: str) -> str:
    return (
        f"'{repo_id}' is a gated repository and this machine has not been granted access.\n"
        f"  1. Run `{login_command()}`\n"
        f"  2. Accept the licence at {repo_url(repo_id)}\n"
        f"  3. Re-run this step."
    )


def _signed_out_message(repo_id: str) -> str:
    return (
        f"'{repo_id}' is not visible without a Hugging Face login — "
        f"it is either gated or private.\n"
        f"  1. Run `{login_command()}`\n"
        f"  2. If it is gated, accept the licence at {repo_url(repo_id)}\n"
        f"  3. Re-run this step."
    )


def _short(exc: BaseException) -> str:
    """First line only — Hub errors carry multi-paragraph request-id blocks."""
    text = str(exc).strip()
    return text.splitlines()[0] if text else exc.__class__.__name__
