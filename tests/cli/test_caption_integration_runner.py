from types import SimpleNamespace

from scripts import run_caption_integration_tests as runner


def test_runner_enables_and_isolates_every_caption_model(monkeypatch):
    calls = []

    def fake_run(command, *, cwd, env, check):
        calls.append((command, cwd, env, check))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(runner.subprocess, "run", fake_run)

    assert runner.main(["--quantization", "4bit", "--", "--maxfail=1"]) == 0
    assert len(calls) == len(runner._RUNS)

    for call, integration in zip(calls, runner._RUNS, strict=True):
        command, cwd, env, check = call
        assert command[:5] == [runner.sys.executable, "-m", "pytest", "-q", "-s"]
        assert command[5:] == ["--maxfail=1", integration.node_id]
        assert cwd == runner._REPO_ROOT
        assert env[integration.env_flag] == "1"
        assert env[integration.quantization_env] == "4bit"
        assert check is False


def test_runner_continues_after_a_failure_and_returns_nonzero(monkeypatch):
    return_codes = iter([1, *(0 for _run in runner._RUNS[1:])])
    calls = []

    def fake_run(command, **_kwargs):
        calls.append(command)
        return SimpleNamespace(returncode=next(return_codes))

    monkeypatch.setattr(runner.subprocess, "run", fake_run)

    assert runner.main([]) == 1
    assert len(calls) == len(runner._RUNS)
