import pytest

from prepare_lora_kit.caption_prompts import prompt_registry


@pytest.fixture()
def isolated_prompts(tmp_path, monkeypatch):
    """Point the prompt prompt_registry at an empty temp directory."""
    prompts_dir = tmp_path / "caption_prompts"
    monkeypatch.setattr(prompt_registry, "_PROMPTS_DIR", prompts_dir)
    return prompts_dir


def test_save_list_load_roundtrip(isolated_prompts):
    prompt_registry.save("full_image", "My Prompt", "describe {concept_token}")

    listed = prompt_registry.list_prompts("full_image")
    assert [p.name for p in listed] == ["My Prompt"]
    assert listed[0].text == "describe {concept_token}"
    assert listed[0].kind == "full_image"

    loaded = prompt_registry.load("full_image", "My Prompt")
    assert loaded.text == "describe {concept_token}"


def test_list_filters_by_kind(isolated_prompts):
    prompt_registry.save("full_image", "Full", "f")
    prompt_registry.save("region", "Region", "r")

    assert [p.name for p in prompt_registry.list_prompts("full_image")] == ["Full"]
    assert [p.name for p in prompt_registry.list_prompts("region")] == ["Region"]


def test_same_name_across_kinds_does_not_collide(isolated_prompts):
    prompt_registry.save("full_image", "Shared", "full text")
    prompt_registry.save("region", "Shared", "region text")

    assert prompt_registry.load("full_image", "Shared").text == "full text"
    assert prompt_registry.load("region", "Shared").text == "region text"


def test_save_overwrites_existing(isolated_prompts):
    prompt_registry.save("full_image", "P", "v1")
    prompt_registry.save("full_image", "P", "v2")

    assert prompt_registry.load("full_image", "P").text == "v2"
    assert len(prompt_registry.list_prompts("full_image")) == 1


def test_delete_is_idempotent(isolated_prompts):
    prompt_registry.save("full_image", "P", "v")
    prompt_registry.delete("full_image", "P")
    prompt_registry.delete("full_image", "P")  # no error second time

    assert prompt_registry.list_prompts("full_image") == []


def test_list_empty_when_dir_missing(isolated_prompts):
    assert prompt_registry.list_prompts("full_image") == []


def test_unknown_kind_raises(isolated_prompts):
    with pytest.raises(ValueError, match="Unknown caption prompt kind"):
        prompt_registry.list_prompts("bogus")


def test_blank_name_rejected(isolated_prompts):
    with pytest.raises(ValueError, match="name is required"):
        prompt_registry.save("full_image", "   ", "text")
