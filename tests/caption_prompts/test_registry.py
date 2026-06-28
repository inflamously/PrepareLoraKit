import pytest

from prepare_lora_kit.caption_prompts import registry


@pytest.fixture()
def isolated_prompts(tmp_path, monkeypatch):
    """Point the prompt registry at an empty temp directory."""
    prompts_dir = tmp_path / "caption_prompts"
    monkeypatch.setattr(registry, "_PROMPTS_DIR", prompts_dir)
    return prompts_dir


def test_save_list_load_roundtrip(isolated_prompts):
    registry.save("full_image", "My Prompt", "describe {concept_token}")

    listed = registry.list_prompts("full_image")
    assert [p.name for p in listed] == ["My Prompt"]
    assert listed[0].text == "describe {concept_token}"
    assert listed[0].kind == "full_image"

    loaded = registry.load("full_image", "My Prompt")
    assert loaded.text == "describe {concept_token}"


def test_list_filters_by_kind(isolated_prompts):
    registry.save("full_image", "Full", "f")
    registry.save("region", "Region", "r")

    assert [p.name for p in registry.list_prompts("full_image")] == ["Full"]
    assert [p.name for p in registry.list_prompts("region")] == ["Region"]


def test_same_name_across_kinds_does_not_collide(isolated_prompts):
    registry.save("full_image", "Shared", "full text")
    registry.save("region", "Shared", "region text")

    assert registry.load("full_image", "Shared").text == "full text"
    assert registry.load("region", "Shared").text == "region text"


def test_save_overwrites_existing(isolated_prompts):
    registry.save("full_image", "P", "v1")
    registry.save("full_image", "P", "v2")

    assert registry.load("full_image", "P").text == "v2"
    assert len(registry.list_prompts("full_image")) == 1


def test_delete_is_idempotent(isolated_prompts):
    registry.save("full_image", "P", "v")
    registry.delete("full_image", "P")
    registry.delete("full_image", "P")  # no error second time

    assert registry.list_prompts("full_image") == []


def test_list_empty_when_dir_missing(isolated_prompts):
    assert registry.list_prompts("full_image") == []


def test_unknown_kind_raises(isolated_prompts):
    with pytest.raises(ValueError, match="Unknown caption prompt kind"):
        registry.list_prompts("bogus")


def test_blank_name_rejected(isolated_prompts):
    with pytest.raises(ValueError, match="name is required"):
        registry.save("full_image", "   ", "text")
