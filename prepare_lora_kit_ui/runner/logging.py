"""Log capture and ANSI cleanup for background jobs."""
from __future__ import annotations

import io
import re

ANSI_ESCAPE_RE = re.compile(
    r"""
    \x1B
    (?:
        \][^\x07]*(?:\x07|\x1B\\)      # OSC: ESC ] ... BEL/ST
        |
        [@-Z\\-_]                       # 7-bit C1 Fe
        |
        \[[0-?]*[ -/]*[@-~]             # CSI
    )
    """,
    re.VERBOSE,
)


def _plain_log_line(line: str) -> str:
    return ANSI_ESCAPE_RE.sub("", line)


class _LogStream(io.TextIOBase):
    encoding = "utf-8"
    errors = "replace"

    def __init__(self, job: "PipelineJob") -> None:
        self._job = job
        self._buf = ""

    def isatty(self) -> bool:
        return False

    def writable(self) -> bool:
        return True

    def write(self, text: str) -> int:
        if not text:
            return 0
        self._buf += text
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            clean = _plain_log_line(line.rstrip())
            if clean.strip():
                self._job.add_log(clean)
        return len(text)

    def flush(self) -> None:
        clean = _plain_log_line(self._buf.rstrip())
        if clean.strip():
            self._job.add_log(clean)
        self._buf = ""
