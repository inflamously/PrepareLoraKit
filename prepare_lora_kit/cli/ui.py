"""`ui` command - launch the desktop webview interface."""
from __future__ import annotations

from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from mimetypes import guess_type
from pathlib import Path
import shutil
import sys
from threading import Thread
from time import perf_counter
from urllib.parse import parse_qs, urlparse

import click

from prepare_lora_kit.paths import PROJECT_ROOT
from prepare_lora_kit_ui import media

from prepare_lora_kit.cli._shared import cli
_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff", ".tif"}


class _StaticServer(ThreadingHTTPServer):
    daemon_threads = True
    block_on_close = False


class _StaticHandler(SimpleHTTPRequestHandler):
    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/media":
            self._serve_media(parsed.query, include_body=True)
            return
        super().do_GET()

    def do_HEAD(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/media":
            self._serve_media(parsed.query, include_body=False)
            return
        super().do_HEAD()

    def log_message(self, format: str, *args) -> None:
        return

    def _serve_media(self, query: str, *, include_body: bool) -> None:
        params = parse_qs(query)
        raw_path = params.get("path", [""])[0]
        if not raw_path:
            self.send_error(400, "Missing media path")
            return

        path = Path(raw_path).expanduser().resolve()
        if not path.is_file() or path.suffix.lower() not in _IMAGE_EXTS:
            self.send_error(404, "Media file not found")
            return

        width = self._parse_width(params.get("w", [""])[0])
        if width:
            self._serve_variant(path, width, include_body=include_body)
            return

        content_type = guess_type(str(path))[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(path.stat().st_size))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if include_body:
            with path.open("rb") as fh:
                shutil.copyfileobj(fh, self.wfile)

    @staticmethod
    def _parse_width(raw: str) -> int | None:
        try:
            width = int(raw)
        except (TypeError, ValueError):
            return None
        return width if width > 0 else None

    def _serve_variant(self, path: Path, width: int, *, include_body: bool) -> None:
        # Variants are deterministic per (path, mtime, width), so a strong ETag lets the browser
        # cache them across navigation instead of re-fetching full bytes every time.
        stat = path.stat()
        etag = f'"{stat.st_mtime_ns}-{stat.st_size}-{width}"'
        if self.headers.get("If-None-Match") == etag:
            self.send_response(304)
            self.send_header("ETag", etag)
            self.send_header("Cache-Control", "private, max-age=86400")
            self.end_headers()

            return
        try:
            body, content_type = media.render_variant(path, width)
        except Exception:
            self.send_error(500, "Could not render media variant")
            return

        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("ETag", etag)
        self.send_header("Cache-Control", "private, max-age=86400")
        self.end_headers()
        if include_body:
            self.wfile.write(body)


def _static_server(static_dir):
    handler = partial(_StaticHandler, directory=str(static_dir))
    server = _StaticServer(("127.0.0.1", 0), handler)
    thread = Thread(
        target=partial(server.serve_forever, poll_interval=0.1),
        name="plk-static-server",
        daemon=True,
    )
    thread.start()
    return server


@cli.command()
@click.option("--debug", is_flag=True, help="Open webview developer tools where supported.")
@click.option(
    "--diagnose-shutdown",
    is_flag=True,
    help="Record shutdown timings and thread dumps under outputs/.",
)
@click.option(
    "--mock",
    "mock_step",
    default=None,
    help="Launch with a generated UI smoke-test fixture and preselect STEP type or all.",
)
@click.option(
    "--mock-output",
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
    help="Root directory for --mock fixture data (default: outputs/_ui_mock).",
)
@click.option(
    "--mock-curate-coverage",
    type=click.Choice(["auto", "pca", "umap"], case_sensitive=False),
    default="auto",
    show_default=True,
    help="Coverage branch to exercise for --mock CurateStep runs.",
)
def ui(
        debug: bool,
        diagnose_shutdown: bool,
        mock_step: str | None,
        mock_output: Path | None,
        mock_curate_coverage: str,
) -> None:
    """Launch the PrepareLoraKit desktop UI."""
    try:
        import webview
    except ImportError as exc:
        raise click.ClickException(
            "pywebview is not installed. Install requirements or run: pip install pywebview"
        ) from exc

    from prepare_lora_kit_ui.dev_fixture import create_mock_ui_fixture
    from prepare_lora_kit_ui.bridge import UiBridge
    from prepare_lora_kit_ui.shutdown_diagnostics import ShutdownDiagnostics

    diagnostics = (
        ShutdownDiagnostics(PROJECT_ROOT / "outputs" / "shutdown-diagnostics.log")
        if diagnose_shutdown
        else None
    )
    if diagnostics is not None:
        diagnostics.mark("UI initialization started")

    projects = None
    bootstrap = None
    if mock_step:
        try:
            fixture = create_mock_ui_fixture(
                mock_step,
                root=mock_output,
                curate_coverage=mock_curate_coverage,
            )
        except ValueError as exc:
            raise click.ClickException(str(exc)) from exc
        projects = {fixture.project.name: fixture.project}
        bootstrap = fixture.bootstrap_payload()

    index = PROJECT_ROOT / "prepare_lora_kit_ui" / "static" / "index.html"
    if not index.exists():
        raise click.ClickException(f"UI asset is missing: {index}")

    server = _static_server(index.parent)
    host, port = server.server_address
    origin = f"http://{host}:{port}"
    bridge = UiBridge(
        media_base_url=f"{origin}/media",
        projects=projects,
        bootstrap=bootstrap,
    )
    window = webview.create_window(
        "PrepareLoraKit",
        f"{origin}/index.html",
        js_api=bridge,
        width=1320,
        height=860,
        min_size=(1040, 680),
    )

    def _shutdown_on_close(*_args) -> None:
        if diagnostics is not None:
            diagnostics.begin_shutdown("window closing event")
            diagnostics.mark(
                "closing handler started",
                jobs=bridge.jobs.diagnostic_snapshot(),
            )
        started = perf_counter()
        result = bridge.shutdown()
        if diagnostics is not None:
            diagnostics.mark(
                "closing handler completed",
                duration=perf_counter() - started,
                result=result,
            )

    try:
        window.events.closing += _shutdown_on_close
    except AttributeError:
        pass
    try:
        if diagnostics is not None:
            diagnostics.mark("webview.start entering")
        webview.start(debug=debug)
    finally:
        if diagnostics is not None:
            diagnostics.begin_shutdown("webview.start exited before closing event")
            diagnostics.mark("webview.start returned")

        started = perf_counter()
        result = bridge.shutdown()
        if diagnostics is not None:
            diagnostics.mark(
                "final bridge shutdown completed",
                duration=perf_counter() - started,
                result=result,
            )

        started = perf_counter()
        server.shutdown()
        if diagnostics is not None:
            diagnostics.mark(
                "static server shutdown completed",
                duration=perf_counter() - started,
            )

        started = perf_counter()
        server.server_close()
        jobs = bridge.jobs.diagnostic_snapshot()
        pipeline_alive = any(job["thread_alive"] for job in jobs["jobs"])
        netfx_finalizer_suppressed = False
        if sys.platform == "win32" and not pipeline_alive:
            from prepare_lora_kit_ui.windows_shutdown import suppress_netfx_process_finalizer

            netfx_finalizer_suppressed = suppress_netfx_process_finalizer()
        if diagnostics is not None:
            diagnostics.mark(
                "static server close completed",
                duration=perf_counter() - started,
            )
            if sys.platform == "win32":
                diagnostics.mark(
                    "Windows CLR exit policy selected",
                    netfx_finalizer_suppressed=netfx_finalizer_suppressed,
                    pipeline_alive=pipeline_alive,
                )
            diagnostics.runtime_snapshot("application cleanup complete")
            diagnostics.mark(
                "pipeline jobs after application cleanup",
                jobs=jobs,
            )
            diagnostics.dump_threads("application cleanup complete")
            diagnostics.mark("UI command returning")
