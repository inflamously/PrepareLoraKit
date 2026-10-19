"""Minimal Textual viewer: case list on the left, every run's caption on the right.

Imports Textual at module level, so import this module only for the interactive view
(Textual is the optional ``[bench]`` extra).
"""
from __future__ import annotations

import click
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Footer, Header, Label, ListItem, ListView, Static

from prepare_lora_kit.caption_bench.render import RunSelection, render_case
from prepare_lora_kit.caption_bench.suite import BenchSuite


class BenchViewApp(App):
    """Arrow keys pick an image; captions are diffed against the baseline run."""

    CSS = """
    #cases { width: 36; border-right: solid $primary; }
    #detail-scroll { padding: 0 1; }
    """
    BINDINGS = (
        Binding("t", "toggle_trace", "Pass trace"),
        Binding("o", "open_image", "Open image"),
        Binding("q", "quit", "Quit"),
    )

    def __init__(self, suite: BenchSuite, selection: RunSelection) -> None:
        super().__init__()
        self.suite = suite
        self.selection = selection
        self.title = f"caption-bench · {suite.name}"
        self.show_trace = False
        self.index = 0

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            yield ListView(
                *(ListItem(Label(case.rel_path)) for case in self.suite.cases), id="cases",
            )
            with VerticalScroll(id="detail-scroll"):
                yield Static(id="detail")
        yield Footer()

    def on_mount(self) -> None:
        self._refresh()

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        if event.list_view.index is not None:
            self.index = event.list_view.index
            self._refresh()

    def action_toggle_trace(self) -> None:
        self.show_trace = not self.show_trace
        self._refresh()

    def action_open_image(self) -> None:
        if self.suite.cases:
            click.launch(str(self.suite.cases[self.index].image))

    def _refresh(self) -> None:
        detail = self.query_one("#detail", Static)
        if not self.suite.cases:
            detail.update("This suite has no images.")
            return
        detail.update(render_case(
            self.suite.cases[self.index], self.selection, show_trace=self.show_trace,
        ))


def run_viewer(suite: BenchSuite, selection: RunSelection) -> None:
    BenchViewApp(suite, selection).run()
