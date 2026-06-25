from prepare_lora_kit.ui.e2e import (
    MOCK_PROJECT_NAME,
    create_mock_ui_fixture,
    resolve_mock_steps,
)


def test_resolve_mock_steps_accepts_aliases_and_all():
    assert resolve_mock_steps("s0") == ["ImportStep"]
    assert resolve_mock_steps("0") == ["ImportStep"]
    assert resolve_mock_steps("s1") == ["QualityGateStep"]
    assert resolve_mock_steps("s2") == ["CurateStep"]
    assert resolve_mock_steps("2") == ["CurateStep"]
    assert resolve_mock_steps("curatestep") == ["CurateStep"]
    assert resolve_mock_steps("all")[0] == "ImportStep"
    assert resolve_mock_steps("all")[-1] == "BucketDryRunStep"


def test_dev_fixture_module_reexports_e2e_fixture_api():
    from prepare_lora_kit.ui import dev_fixture

    assert dev_fixture.MOCK_PROJECT_NAME == MOCK_PROJECT_NAME
    assert dev_fixture.create_mock_ui_fixture is create_mock_ui_fixture
    assert dev_fixture.resolve_mock_steps is resolve_mock_steps
