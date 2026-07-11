import json

from PIL import Image

from prepare_lora_kit.invoke.bucket_pools_check_step import invoke_bucket_pools_check_step
from prepare_lora_kit.pipeline.configs import BucketPoolsCheckConfig
from prepare_lora_kit.steps.bucket_pools_check import run


def _save_image(path, size):
    Image.new("RGB", size, "red").save(path)


def test_bucket_pools_check_assigns_buckets_reports_thin_and_writes_cache(tmp_path):
    dataset_dir = tmp_path / "dataset"
    output_dir = tmp_path / "output"
    report_path = tmp_path / "reports" / "BucketPoolsCheckStep_report.json"
    dataset_dir.mkdir()
    _save_image(dataset_dir / "square_a.png", (64, 64))
    _save_image(dataset_dir / "square_b.png", (32, 32))
    _save_image(dataset_dir / "wide.png", (96, 64))

    report = run(
        dataset_dir,
        [(512, 512), (768, 512)],
        display_name="test buckets",
        output_dir=output_dir,
        cache_mode=True,
        thin_threshold=1,
        report_path=report_path,
        enabled_substeps=[
            "assign_bucket_pools",
            "report_thin_buckets",
            "write_cache_info",
        ],
    )

    assert report["buckets"]["512x512"]["count"] == 2
    assert report["buckets"]["768x512"]["count"] == 1
    assert report["cache_mode"] is True
    assert report["thin_threshold"] == 1
    assert report["substeps"]["write_cache_info"]["enabled"] is True
    assert report["thin_buckets"][0]["bucket"] == [768, 512]
    assert report["thin_buckets"][0]["count"] == 1
    assert report["thin_buckets"][0]["paths"] == [str(dataset_dir / "wide.png")]

    saved_report = json.loads(report_path.read_text(encoding="utf-8"))
    assert saved_report == report

    cache_info = json.loads((output_dir / "cache_info.json").read_text(encoding="utf-8"))
    assert cache_info["bucket_source"] == "test buckets"
    assert cache_info["buckets"]["512x512"] == [
        str(dataset_dir / "square_a.png"),
        str(dataset_dir / "square_b.png"),
    ]
    assert cache_info["buckets"]["768x512"] == [str(dataset_dir / "wide.png")]


def test_bucket_pools_check_disabled_assignment_writes_skipped_report(tmp_path):
    dataset_dir = tmp_path / "dataset"
    output_dir = tmp_path / "output"
    report_path = tmp_path / "reports" / "BucketPoolsCheckStep_report.json"
    dataset_dir.mkdir()
    _save_image(dataset_dir / "image.png", (64, 64))

    report = run(
        dataset_dir,
        [(512, 512)],
        output_dir=output_dir,
        cache_mode=True,
        report_path=report_path,
        enabled_substeps=["report_thin_buckets", "write_cache_info"],
    )

    assert report == {
        "skipped": True,
        "reason": "assign_bucket_pools disabled",
        "buckets": {},
        "thin_buckets": [],
        "thin_threshold": 2,
        "cache_mode": False,
        "substeps": {
            "assign_bucket_pools": {"enabled": False},
            "report_thin_buckets": {"enabled": True},
            "write_cache_info": {"enabled": True},
        },
    }
    assert json.loads(report_path.read_text(encoding="utf-8")) == report
    assert not (output_dir / "cache_info.json").exists()


def test_bucket_pools_invoke_returns_report_for_post_step_interactions(tmp_path):
    working_dir = tmp_path / "dataset"
    output_dir = tmp_path / "output"
    working_dir.mkdir()
    _save_image(working_dir / "square.png", (64, 64))

    report = invoke_bucket_pools_check_step(
        working_dir,
        output_dir,
        BucketPoolsCheckConfig(resolution_buckets=[(512, 512)]),
        enabled_substeps=["assign_bucket_pools", "report_thin_buckets"],
    )

    assert report["buckets"]["512x512"]["count"] == 1
    assert report["thin_threshold"] == 2
