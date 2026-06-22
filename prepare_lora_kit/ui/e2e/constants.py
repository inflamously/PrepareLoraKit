"""Shared constants for UI end-to-end mock fixtures."""
from __future__ import annotations


MOCK_PROJECT_NAME = "plk-ui-mock"
MOCK_TOKEN = "plk_mock"

FIXTURE_MARKER = ".plk_ui_mock_fixture"
QUALITY_GATE_MIN_SIDE = 1024.0

MOCK_SOURCE_SPECS = [
    ("mock_square.png", (1536, 1536), (46, 88, 138), True),
    ("mock_landscape.png", (1792, 1536), (121, 78, 55), True),
    ("mock_portrait.png", (1536, 1792), (65, 112, 82), True),
    ("mock_bad_too_small.png", (384, 384), (130, 45, 58), False),
]
MOCK_DUPLICATE_SOURCE = "mock_square.png"
MOCK_DUPLICATE_NAME = "mock_square_duplicate.png"
