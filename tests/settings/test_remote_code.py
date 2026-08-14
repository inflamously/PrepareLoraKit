"""The remote-code trust policy: default-deny, machine-local opt-in.

``trust_remote_code=True`` executes model-authored Python from the Hub, so the
default must be "no" and turning it on must be a deliberate, local act.
"""
import pytest

from prepare_lora_kit import settings
from prepare_lora_kit.settings import hub
from prepare_lora_kit.settings.model import HuggingFaceSettings


def _configure(value):
    settings.save_settings_dict({"huggingface": {"allow_remote_code": value}})
    settings.invalidate()


def test_remote_code_is_denied_when_nothing_is_configured():
    assert hub.remote_code_allowed() is False


def test_remote_code_is_denied_by_the_dataclass_default():
    assert HuggingFaceSettings().allow_remote_code is None
    assert hub.remote_code_allowed() is False


def test_explicit_opt_in_is_honoured():
    _configure(True)

    assert hub.remote_code_allowed() is True


def test_explicit_opt_out_is_honoured():
    _configure(False)

    assert hub.remote_code_allowed() is False


@pytest.mark.parametrize("value", ["true", "false", "yes", "no", 1, 0, "1"])
def test_non_boolean_values_are_rejected_rather_than_coerced(value):
    # The footgun this exists to stop: `allow_remote_code: "false"` is a truthy
    # string. A security flag must never be decided by str-to-bool coercion.
    with pytest.raises(ValueError, match="allow_remote_code"):
        HuggingFaceSettings.from_dict({"allow_remote_code": value})


def test_remote_code_hint_names_the_repo_and_how_to_allow_it():
    hint = hub.remote_code_hint("OpenGVLab/InternVL3-8B")

    assert "OpenGVLab/InternVL3-8B" in hint
    assert "allow_remote_code" in hint
    assert str(settings.settings_path()) in hint


def test_remote_code_error_is_recognised_by_its_message():
    refusal = ValueError(
        "The repository OpenGVLab/InternVL3-8B contains custom code which must be "
        "executed to correctly load the model. Please pass the argument "
        "`trust_remote_code=True` to allow custom code to be run."
    )

    assert hub.is_remote_code_error(refusal) is True


@pytest.mark.parametrize("exc", [
    ValueError("Unsupported caption quantization: potato"),
    RuntimeError("CUDA out of memory"),
    OSError("connection reset"),
])
def test_unrelated_errors_are_not_mistaken_for_a_remote_code_refusal(exc):
    assert hub.is_remote_code_error(exc) is False
