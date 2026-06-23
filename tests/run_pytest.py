"""Run pytest using the repo-local virtualenv packages when needed.

This helps shells that can run ``python3`` but cannot execute the checked-out
``.venv/Scripts/python.exe`` directly.
"""
from __future__ import annotations

import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _venv_site_packages(root: Path) -> list[Path]:
    venv = root / ".venv"
    candidates = [venv / "Lib" / "site-packages"]
    candidates.extend(sorted((venv / "lib").glob("python*/site-packages")))
    return [path for path in candidates if path.exists()]


def _load_pytest():
    try:
        import pytest
    except ModuleNotFoundError as exc:
        if exc.name != "pytest":
            raise
        for site_packages in _venv_site_packages(_repo_root()):
            sys.path.insert(0, str(site_packages))
        try:
            import pytest
        except ModuleNotFoundError:
            print(
                "pytest is not installed for this interpreter and was not found "
                "in the repo .venv site-packages.",
                file=sys.stderr,
            )
            raise SystemExit(1) from None
    return pytest


def main(argv: list[str] | None = None) -> int:
    pytest = _load_pytest()
    args = list(sys.argv[1:] if argv is None else argv)
    return int(pytest.main(args or ["tests"]))


if __name__ == "__main__":
    raise SystemExit(main())
