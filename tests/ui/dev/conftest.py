"""Shared helpers for the mock UI dev-fixture tests."""

import pytest


@pytest.fixture
def recording_curate_provider():
    """A ``UiInteractionProvider`` stub that records the curate report on the job."""

    class FakeInteractionProvider:
        def __init__(self, job, media_base_url=None):
            self.job = job
            self.media_base_url = media_base_url

        def curate_details(self, report, report_path):
            self.job.curate_report = report
            self.job.curate_report_path = report_path
            return True

    return FakeInteractionProvider


@pytest.fixture
def make_image():
    """Return a helper that writes a small RGB PNG at the given path."""

    def _make_image(path):
        from PIL import Image

        Image.new("RGB", (32, 24), (80, 120, 160)).save(path)

    return _make_image
