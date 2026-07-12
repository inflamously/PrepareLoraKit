from prepare_lora_kit_ui.shutdown_diagnostics import ShutdownDiagnostics


def test_shutdown_diagnostics_records_timeline_and_thread_dump(tmp_path):
    path = tmp_path / "shutdown.log"
    diagnostics = ShutdownDiagnostics(
        path,
        watchdog_interval=0,
        register_atexit=False,
    )

    diagnostics.mark("test event", answer=42)
    diagnostics.runtime_snapshot("test")
    diagnostics.dump_threads("test")

    log = path.read_text(encoding="utf-8")
    assert "diagnostics started" in log
    assert "test event" in log
    assert "answer=42" in log
    assert "runtime snapshot: test" in log
    assert "thread name='MainThread'" in log
    assert "--- thread dump: test ---" in log
