"""`ui` command - launch the desktop webview interface."""
from __future__ import annotations

from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from mimetypes import guess_type
from pathlib import Path
import shutil
from threading import Thread
from urllib.parse import parse_qs, urlparse

import click

from ._shared import cli


_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff", ".tif"}


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

        content_type = guess_type(str(path))[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(path.stat().st_size))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if include_body:
            with path.open("rb") as fh:
                shutil.copyfileobj(fh, self.wfile)


def _static_server(static_dir):
    handler = partial(_StaticHandler, directory=str(static_dir))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


@cli.command()
@click.option("--debug", is_flag=True, help="Open webview developer tools where supported.")
@click.option(
    "--mock",
    "mock_step",
    default=None,
    help="Launch with a generated UI smoke-test fixture and preselect STEP, alias s1..s8, or all.",
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

    from ..paths import PACKAGE_ROOT
    from ..ui.dev_fixture import create_mock_ui_fixture
    from ..ui.bridge import UiBridge

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

    index = PACKAGE_ROOT / "ui" / "static" / "index.html"
    if not index.exists():
        raise click.ClickException(f"UI asset is missing: {index}")

    server = _static_server(index.parent)
    host, port = server.server_address
    origin = f"http://{host}:{port}"
    webview.create_window(
        "PrepareLoraKit",
        f"{origin}/index.html",
        js_api=UiBridge(
            media_base_url=f"{origin}/media",
            projects=projects,
            bootstrap=bootstrap,
        ),
        width=1320,
        height=860,
        min_size=(1040, 680),
    )
    try:
        webview.start(debug=debug)
    finally:
        server.shutdown()
        server.server_close()
