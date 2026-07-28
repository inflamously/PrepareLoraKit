"""`plk step -s <name>` accepts both spellings of a step."""
import click
import pytest

from prepare_lora_kit.cli.step.resolve import _resolve_step_type


def test_resolves_a_step_type_case_insensitively():
    assert _resolve_step_type("CaptionBboxStep") == "CaptionBboxStep"
    assert _resolve_step_type("captionbboxstep") == "CaptionBboxStep"


def test_resolves_a_slug():
    """The slug is the name of the file the user most likely just edited."""
    assert _resolve_step_type("caption_bbox") == "CaptionBboxStep"
    assert _resolve_step_type("bucket_pools_check") == "BucketPoolsCheckStep"
    assert _resolve_step_type("  import  ") == "ImportStep"


def test_unknown_step_lists_both_types_and_slugs():
    with pytest.raises(click.BadParameter) as excinfo:
        _resolve_step_type("captions")

    message = str(excinfo.value)
    assert "CaptionBboxStep" in message
    assert "caption_bbox" in message
