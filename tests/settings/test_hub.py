"""Hub access helpers. Nothing here touches the network — `auth_check` is stubbed.

The real error classes are used rather than fakes: ``HfHubHTTPError.__init__``
takes a required keyword ``response``, and that constraint is precisely why
``hub_error_context`` extends an error instead of rebuilding it. A stub would
hide the very thing these tests exist to pin down.
"""
from typing import ClassVar

import pytest

hub_errors = pytest.importorskip(
    "huggingface_hub.errors",
    reason="huggingface_hub is a declared dependency; skipped only on bare interpreters",
)

from prepare_lora_kit.settings import hub  # noqa: E402  (after importorskip by design)

REPO = "black-forest-labs/FLUX.2-klein-base-9B"


class _FakeResponse:
    headers: ClassVar[dict] = {}
    request = None


def _gated():
    return hub_errors.GatedRepoError("401 Client Error.", response=_FakeResponse())


def _not_found():
    return hub_errors.RepositoryNotFoundError("404 Client Error.", response=_FakeResponse())


def test_login_command_follows_the_installed_hub_version(monkeypatch):
    # huggingface-cli is a dead entry point on hub>=1.0 — it prints a deprecation
    # notice and exits — so the version decides, even when `hf` is not yet on PATH.
    monkeypatch.setattr(hub, "_hub_major_version", lambda: 1)
    monkeypatch.setattr(hub.shutil, "which", lambda name: None)
    assert hub.login_command() == "hf auth login"

    monkeypatch.setattr(hub, "_hub_major_version", lambda: 0)
    monkeypatch.setattr(hub.shutil, "which", lambda name: "/usr/bin/hf")
    assert hub.login_command() == "huggingface-cli login"


def test_login_command_falls_back_to_path_when_the_version_is_unknown(monkeypatch):
    monkeypatch.setattr(hub, "_hub_major_version", lambda: None)

    monkeypatch.setattr(hub.shutil, "which", lambda name: "/usr/bin/hf")
    assert hub.login_command() == "hf auth login"

    monkeypatch.setattr(hub.shutil, "which", lambda name: None)
    assert hub.login_command() == "huggingface-cli login"


def test_login_command_matches_the_real_installed_hub():
    import huggingface_hub

    expected = ("hf auth login" if int(huggingface_hub.__version__[0]) >= 1
                else "huggingface-cli login")
    assert hub.login_command() == expected


def test_token_status_reports_the_environment_source(monkeypatch):
    monkeypatch.setenv("HF_TOKEN", "hf_fake")
    monkeypatch.setattr("huggingface_hub.get_token", lambda: "hf_fake")

    assert hub.token_status() == {"present": True, "source": "env", "error": None}


def test_token_status_reports_a_stored_token(monkeypatch):
    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.setattr("huggingface_hub.get_token", lambda: "hf_fake")

    assert hub.token_status()["source"] == "stored"


def test_token_status_reports_no_token(monkeypatch):
    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.setattr("huggingface_hub.get_token", lambda: None)

    assert hub.token_status() == {"present": False, "source": None, "error": None}


def test_check_repo_ok(monkeypatch):
    monkeypatch.setattr("huggingface_hub.auth_check", lambda repo_id: None)

    result = hub.check_repo(REPO)

    assert result["status"] == "ok"
    assert result["url"] == f"https://huggingface.co/{REPO}"


def test_check_repo_gated_names_the_licence_page(monkeypatch):
    def boom(repo_id):
        raise _gated()

    monkeypatch.setattr("huggingface_hub.auth_check", boom)

    result = hub.check_repo(REPO)

    assert result["status"] == "gated"
    assert f"https://huggingface.co/{REPO}" in result["message"]
    assert "login" in result["message"]


def test_check_repo_not_found_distinguishes_signed_out_from_typo(monkeypatch):
    def boom(repo_id):
        raise _not_found()

    monkeypatch.setattr("huggingface_hub.auth_check", boom)

    monkeypatch.setattr("huggingface_hub.get_token", lambda: None)
    assert hub.check_repo(REPO)["status"] == "unauthorized"

    monkeypatch.setattr("huggingface_hub.get_token", lambda: "hf_fake")
    assert hub.check_repo(REPO)["status"] == "missing"


def test_check_repo_offline(monkeypatch):
    def boom(repo_id):
        raise OSError("Name or service not known")

    monkeypatch.setattr("huggingface_hub.auth_check", boom)

    result = hub.check_repo(REPO)

    assert result["status"] == "offline"


def test_check_repos_skips_blanks_sentinels_and_duplicates(monkeypatch):
    seen = []
    monkeypatch.setattr("huggingface_hub.auth_check", seen.append)

    hub.check_repos(["a/b", "", None, "auto", "a/b", "  ", "c/d"])

    assert seen == ["a/b", "c/d"]


def test_hub_error_context_appends_a_hint_and_keeps_the_type(monkeypatch):
    monkeypatch.setattr(hub.shutil, "which", lambda name: "/usr/bin/hf")

    with pytest.raises(hub_errors.GatedRepoError) as caught, hub.hub_error_context(REPO):
        raise _gated()

    message = str(caught.value)
    assert "401 Client Error." in message      # the original failure survives
    assert "hf auth login" in message
    assert f"https://huggingface.co/{REPO}" in message


def test_nested_contexts_append_the_hint_only_once(monkeypatch):
    monkeypatch.setattr(hub, "_hub_major_version", lambda: 1)

    # Two nested contexts is the subject of this test: the inner one must not
    # append a second copy of the hint the outer one already added.
    with (
        pytest.raises(hub_errors.GatedRepoError) as caught,
        hub.hub_error_context(REPO),
        hub.hub_error_context(REPO),
    ):
        raise _gated()

    assert str(caught.value).count("Accept the licence at") == 1


def test_hub_error_context_passes_unrelated_exceptions_through_untouched():
    class CancelledRun(Exception):
        pass

    with pytest.raises(CancelledRun) as caught, hub.hub_error_context(REPO):
        raise CancelledRun("stop")

    assert str(caught.value) == "stop"


def test_hub_error_context_is_transparent_on_success():
    with hub.hub_error_context(REPO):
        value = 1 + 1

    assert value == 2


def test_access_hint_returns_none_for_unrelated_errors():
    assert hub.access_hint(ValueError("nope"), REPO) is None
    assert hub.access_hint(RuntimeError("CUDA out of memory"), REPO) is None
