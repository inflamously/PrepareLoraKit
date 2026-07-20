import pytest

from prepare_lora_kit.caption_prompts import prompt_registry
from prepare_lora_kit.utils import caption as cap_utils


@pytest.fixture()
def isolated_prompts(tmp_path, monkeypatch):
    """Point the prompt prompt_registry at an empty temp directory."""
    prompts_dir = tmp_path / "caption_prompts"
    monkeypatch.setattr(prompt_registry, "_PROMPTS_DIR", prompts_dir)
    return prompts_dir


def _saved_names(kind):
    """Names in the library excluding the virtual built-in 'Default'."""
    return [p.name for p in prompt_registry.list_prompts(kind) if p.name != "Default"]


def test_save_list_load_roundtrip(isolated_prompts):
    prompt_registry.save("full_image", "My Prompt", "describe {concept_token}")

    assert _saved_names("full_image") == ["My Prompt"]
    loaded = prompt_registry.load("full_image", "My Prompt")
    assert loaded.text == "describe {concept_token}"
    assert loaded.kind == "full_image"


def test_list_filters_by_kind(isolated_prompts):
    prompt_registry.save("full_image", "Full", "f")
    prompt_registry.save("region", "Region", "r")

    assert _saved_names("full_image") == ["Full"]
    assert _saved_names("region") == ["Region"]


def test_same_name_across_kinds_does_not_collide(isolated_prompts):
    prompt_registry.save("full_image", "Shared", "full text")
    prompt_registry.save("region", "Shared", "region text")

    assert prompt_registry.load("full_image", "Shared").text == "full text"
    assert prompt_registry.load("region", "Shared").text == "region text"


def test_save_overwrites_existing(isolated_prompts):
    prompt_registry.save("full_image", "P", "v1")
    prompt_registry.save("full_image", "P", "v2")

    assert prompt_registry.load("full_image", "P").text == "v2"
    assert _saved_names("full_image") == ["P"]


def test_delete_is_idempotent(isolated_prompts):
    prompt_registry.save("full_image", "P", "v")
    prompt_registry.delete("full_image", "P")
    prompt_registry.delete("full_image", "P")  # no error second time

    assert _saved_names("full_image") == []


def test_list_only_default_when_dir_missing(isolated_prompts):
    # The built-in Default is virtual, so it's present even with no files on disk.
    assert [p.name for p in prompt_registry.list_prompts("full_image")] == ["Default"]
    assert _saved_names("full_image") == []


def test_unknown_kind_raises(isolated_prompts):
    with pytest.raises(ValueError, match="Unknown caption prompt kind"):
        prompt_registry.list_prompts("bogus")


def test_blank_name_rejected(isolated_prompts):
    with pytest.raises(ValueError, match="name is required"):
        prompt_registry.save("full_image", "   ", "text")


# ── Virtual built-in "Default" ──────────────────────────────────────────────────

def test_default_always_present_and_matches_constants(isolated_prompts):
    for kind in ("full_image", "region"):
        names = [p.name for p in prompt_registry.list_prompts(kind)]
        assert "Default" in names
        loaded = prompt_registry.load(kind, "Default")
        assert loaded.text == cap_utils.default_prompt_text(kind)


def test_default_is_read_only(isolated_prompts):
    with pytest.raises(ValueError, match="read-only"):
        prompt_registry.save("full_image", "Default", "hijacked")
    with pytest.raises(ValueError, match="read-only"):
        prompt_registry.delete("region", "Default")


def test_disk_file_cannot_shadow_default(isolated_prompts):
    # A stray on-disk file slugged as 'default' must not override the virtual one.
    isolated_prompts.mkdir(parents=True, exist_ok=True)
    (isolated_prompts / "full_image__default.yaml").write_text(
        "name: Default\nkind: full_image\ntext: stale\n", encoding="utf-8"
    )
    defaults = [p for p in prompt_registry.list_prompts("full_image") if p.name == "Default"]
    assert len(defaults) == 1
    assert defaults[0].text == cap_utils.default_prompt_text("full_image")
