import json

import cv2
import numpy as np
import pytest

from utility.depth_benchmark import (
    compare_depth_maps,
    depth_preview_from_map,
    load_depth_fixture,
    run_fixture_benchmark,
    update_benchmark_manifest,
)


def _fixture_frame(height=48, width=256):
    rng = np.random.default_rng(20261011 + height + width)
    left_gray = rng.integers(0, 256, size=(height, width), dtype=np.uint8)
    left = cv2.cvtColor(left_gray, cv2.COLOR_GRAY2BGR)
    right = np.zeros_like(left)
    right[:, :-8] = left[:, 8:]
    depth = np.full((height, width), 1.25, dtype=np.float32)
    depth[:, :128] = 0.0
    return {
        "left": left,
        "right": right,
        "depth_map_gt": depth,
        "stamp": 12.345,
        "depth_stamp": 12.345,
        "camera_info": {
            "focal_length": 100.0,
            "baseline": 0.1,
            "width": width,
            "height": height,
            "depth_units": "m",
            "left": {
                "width": width,
                "height": height,
                "k": [100.0, 0.0, width / 2.0, 0.0, 100.0, height / 2.0, 0.0, 0.0, 1.0],
                "p": [100.0, 0.0, width / 2.0, 0.0, 0.0, 100.0, height / 2.0, 0.0, 0.0, 0.0, 1.0, 0.0],
                "stamp": 12.345,
                "frame_id": "camera_left_optical_frame",
            },
            "right": {
                "width": width,
                "height": height,
                "k": [100.0, 0.0, width / 2.0, 0.0, 100.0, height / 2.0, 0.0, 0.0, 1.0],
                "p": [100.0, 0.0, width / 2.0, -10.0, 0.0, 100.0, height / 2.0, 0.0, 0.0, 0.0, 1.0, 0.0],
                "stamp": 12.345,
                "frame_id": "camera_right_optical_frame",
            },
        },
        "depth_config": {
            "min_depth": 0.1,
            "max_depth": 10.0,
            "width": width,
            "height": height,
            "baseline": 0.1,
            "min_disp": 0,
            "num_disp_multiplier": 8,
            "block_size": 5,
            "wls_lambda": 8000.0,
            "wls_sigma": 1.5,
        },
    }


def _write_fixture(directory, frame):
    directory.mkdir(parents=True, exist_ok=True)
    height, width = frame["depth_map_gt"].shape
    assert cv2.imwrite(str(directory / "left.jpg"), frame["left"])
    assert cv2.imwrite(str(directory / "right.jpg"), frame["right"])
    depth = frame["depth_map_gt"]
    depth.astype("<f4").tofile(directory / "depth_gt_f32le.bin")
    preview = depth_preview_from_map(depth, 0.1, 10.0)
    assert cv2.imwrite(str(directory / "depth_gt.png"), preview)
    stamp_seconds = float(frame.get("stamp", 12.345))
    stamp_sec = int(stamp_seconds)
    stamp = {"sec": stamp_sec, "nanosec": int(round((stamp_seconds - stamp_sec) * 1e9))}
    camera_info = {}
    for side in ("left", "right"):
        info = frame["camera_info"][side]
        camera_info[side] = {
            **info,
            "stamp": stamp,
            "distortion_model": "plumb_bob",
            "d": [0, 0, 0, 0, 0],
            "r": [1, 0, 0, 0, 1, 0, 0, 0, 1],
        }
    metadata = {
        "schema_version": 1,
        "width": width,
        "height": height,
        "depth_encoding": "32FC1",
        "depth_units": "m",
        "depth_byte_order": "little_endian",
        "depth_preview_encoding": "gray8_near_white",
        "depth_preview_row_order": "top_to_bottom",
        "depth_preview_min_m": 0.1,
        "depth_preview_max_m": 10.0,
        "timestamps": {"left": stamp, "right": stamp, "depth": stamp},
        "camera_info": camera_info,
        "config": frame["depth_config"],
    }
    (directory / "metadata.json").write_text(
        json.dumps(metadata), encoding="utf-8-sig"
    )
    return directory


def _write_fixture_collection(directory, frames):
    directory.mkdir(parents=True, exist_ok=True)
    index = []
    for frame_index, frame in enumerate(frames, start=1):
        frame_id = "frame_%06d" % frame_index
        relative_directory = "frames/" + frame_id
        frame_path = directory / relative_directory
        _write_fixture(frame_path, frame)
        index.append({
            "frame_id": frame_id,
            "directory": relative_directory,
            "stamp": frame.get("stamp", 12.345),
        })
    (directory / "metadata.json").write_text(json.dumps({
        "schema_version": 2,
        "frame_count": len(index),
        "frames": index,
    }), encoding="utf-8")
    return directory


def test_fixture_round_trips_images_gt_stamps_camera_metadata_and_config(tmp_path):
    frame = _fixture_frame()
    fixture_path = _write_fixture(tmp_path / "reference", frame)

    loaded = load_depth_fixture(fixture_path)

    np.testing.assert_array_equal(loaded["left"], cv2.imread(str(fixture_path / "left.jpg")))
    np.testing.assert_array_equal(loaded["right"], cv2.imread(str(fixture_path / "right.jpg")))
    np.testing.assert_array_equal(loaded["depth_gt"], frame["depth_map_gt"])
    assert float(loaded["stamp"]) == float(loaded["depth_stamp"]) == 12.345
    assert loaded["camera_info"]["focal_length"] == 100.0
    assert loaded["camera_info"]["left"]["frame_id"] == "camera_left_optical_frame"
    assert len(loaded["camera_info"]["left"]["k"]) == 9
    assert len(loaded["camera_info"]["right"]["p"]) == 12
    assert loaded["camera_info"]["right"]["p"][3] == -10.0
    assert loaded["config"]["max_depth"] == 10.0
    assert loaded["depth_gt"].dtype == np.float32
    assert loaded["depth_gt"].shape == (48, 256)
    assert loaded["depth_gt_preview"].dtype == np.uint8
    assert loaded["depth_gt_preview"].shape == (48, 256)
    assert loaded["depth_gt_preview"][0, 200] > loaded["depth_gt_preview"][0, 0]
    assert loaded["metadata"]["timestamps"]["depth"] == loaded["metadata"]["timestamps"]["left"]


def test_fixture_rejects_unsynchronized_stereo_and_gt(tmp_path):
    frame = _fixture_frame()
    frame["depth_stamp"] += 0.01

    fixture_path = _write_fixture(tmp_path / "reference", frame)
    metadata_path = fixture_path / "metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8-sig"))
    metadata["timestamps"]["depth"] = {"sec": 12, "nanosec": 355000000}
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8-sig")
    with pytest.raises(ValueError, match="not synchronized"):
        load_depth_fixture(fixture_path)


def test_metric_uses_fixed_valid_gt_mask_and_reports_coverage():
    reference = np.array([[1.0, 2.0, 0.0, np.nan]], dtype=np.float32)
    predicted = np.array([[1.5, 0.0, 9.0, 4.0]], dtype=np.float32)

    result = compare_depth_maps(predicted, reference)

    assert result["mae_m"] == pytest.approx(0.5)
    assert result["rmse_m"] == pytest.approx(0.5)
    assert result["bias_m"] == pytest.approx(0.5)
    assert result["valid_reference_pixels"] == 2
    assert result["valid_overlap_pixels"] == 1
    assert result["opencv_coverage"] == pytest.approx(0.5)


def test_gt_preview_preserves_camera_row_order():
    depth = np.array([[1.0, 10.0], [0.0, 5.0]], dtype=np.float32)

    preview = depth_preview_from_map(depth, 1.0, 10.0)

    np.testing.assert_array_equal(preview, np.array([[255, 0], [0, 142]], dtype=np.uint8))


def test_saved_fixture_benchmark_is_deterministic(tmp_path):
    fixture_path = _write_fixture(tmp_path / "reference", _fixture_frame())

    first = run_fixture_benchmark(fixture_path)
    second = run_fixture_benchmark(fixture_path)

    assert first["metrics"] == second["metrics"]
    assert first["diagnostics"]["frames"][0] == second["diagnostics"]["frames"][0]
    assert first["metrics"]["valid_reference_pixels"] > 0


def test_multi_frame_fixture_benchmarks_every_frame_and_lists_saved_files(tmp_path):
    first_frame = _fixture_frame()
    second_frame = _fixture_frame()
    second_frame["stamp"] = 13.25
    second_frame["depth_stamp"] = 13.25
    second_frame["depth_map_gt"] = np.full_like(second_frame["depth_map_gt"], 2.0)
    second_frame["depth_map_gt"][:, :64] = 0.0
    fixture_path = _write_fixture_collection(tmp_path / "collection", [first_frame, second_frame])

    loaded = load_depth_fixture(fixture_path)
    result = run_fixture_benchmark(fixture_path)

    assert loaded["frame_count"] == 2
    assert [frame["frame_id"] for frame in loaded["frames"]] == ["frame_000001", "frame_000002"]
    assert len(result["frames"]) == 2
    assert [frame["stamp"] for frame in result["frames"]] == [12.345, 13.25]
    assert result["metrics"]["frame_count"] == 2
    assert result["metrics"]["valid_reference_pixels"] == sum(
        frame["metrics"]["valid_reference_pixels"] for frame in result["frames"]
    )
    assert {item["path"] for item in result["saved_artifacts"]} >= {
        "frames/frame_000001/left.jpg",
        "frames/frame_000002/right.jpg",
        "frames/frame_000002/depth_gt_f32le.bin",
        "metadata.json",
    }
    assert all(item["sha256"] and item["size_bytes"] > 0 for item in result["saved_artifacts"])


def test_multi_frame_benchmark_and_manifest_record_per_frame_metrics_and_artifacts(tmp_path):
    frame_a = _fixture_frame()
    frame_b = _fixture_frame()
    frame_b["stamp"] = frame_b["depth_stamp"] = 13.25
    fixture_path = _write_fixture_collection(tmp_path / "collection", [frame_a, frame_b])
    manifest_path = tmp_path / "benchmark.json"
    result = run_fixture_benchmark(fixture_path)

    accepted, manifest = update_benchmark_manifest(
        manifest_path, fixture_path, result, "multi-frame", "record all captures", "rev1"
    )

    assert accepted
    attempt = manifest["last_attempt"]
    assert attempt["frame_count"] == 2
    assert len(attempt["frame_results"]) == 2
    assert all("metrics" in frame and "stamp" in frame for frame in attempt["frame_results"])
    assert manifest["saved_artifacts"] == result["saved_artifacts"]
    assert len(manifest["saved_artifacts"]) == 11


def test_saved_fixture_benchmark_uses_python_opencv_config_overrides(tmp_path):
    fixture_path = _write_fixture(tmp_path / "reference", _fixture_frame())
    overrides = {
        "block_size": 3,
        "p2_scale": 8.0,
        "wls_lambda": 100000.0,
        "wls_sigma": 7.5,
    }

    result = run_fixture_benchmark(fixture_path, overrides)

    assert result["benchmark_config"]["block_size"] == 3
    assert result["benchmark_config"]["p2_scale"] == 8.0
    assert result["benchmark_config"]["wls_lambda"] == 100000.0
    assert result["benchmark_config"]["wls_sigma"] == 7.5


def test_baseline_override_changes_opencv_calibration_not_fixed_gt_mask(tmp_path):
    fixture_path = _write_fixture(tmp_path / "reference", _fixture_frame())

    captured = run_fixture_benchmark(fixture_path)
    calibrated = run_fixture_benchmark(fixture_path, {"baseline": 0.38})

    assert captured["metrics"]["valid_reference_pixels"] == calibrated["metrics"]["valid_reference_pixels"]
    assert calibrated["benchmark_config"]["baseline"] == pytest.approx(0.38)


def test_opencv_search_keeps_gt_reference_mask_fixed(tmp_path):
    fixture_path = _write_fixture(tmp_path / "reference", _fixture_frame())

    captured = run_fixture_benchmark(fixture_path)
    candidate = run_fixture_benchmark(
        fixture_path,
        {"min_disp": 4, "num_disp_multiplier": 4, "baseline": 0.38},
    )

    assert candidate["metrics"]["valid_reference_pixels"] == captured["metrics"]["valid_reference_pixels"]
    assert candidate["metrics"]["reference"] == captured["metrics"]["reference"]


def test_saved_fixture_benchmark_rejects_unsupported_config_override(tmp_path):
    fixture_path = _write_fixture(tmp_path / "reference", _fixture_frame())

    with pytest.raises(ValueError, match="unsupported OpenCV benchmark configuration"):
        run_fixture_benchmark(fixture_path, {"depth_magic": 1})


def test_manifest_only_records_valid_best_results_and_ignores_rejections(tmp_path):
    fixture_path = _write_fixture(tmp_path / "reference", _fixture_frame())
    manifest_path = tmp_path / "benchmark.json"

    def result(mae, coverage):
        return {
            "metrics": {
                "mae_m": mae,
                "rmse_m": mae,
                "bias_m": 0.0,
                "opencv_coverage": coverage,
                "valid_reference_pixels": 100,
                "valid_overlap_pixels": round(coverage * 100),
            },
            "opencv_version": "test-version",
            "fixture": {"config": {"max_depth": 10.0}},
            "diagnostics": {},
        }

    accepted, baseline = update_benchmark_manifest(
        manifest_path, fixture_path, result(0.5, 0.8), "base", "baseline", "rev1"
    )
    assert accepted is True
    assert baseline["best"]["status"] == "baseline"
    initial_manifest = manifest_path.read_text()

    accepted, rejected = update_benchmark_manifest(
        manifest_path, fixture_path, result(0.4, 0.7), "coverage-loss", "trial", "rev2"
    )
    assert accepted is False
    assert rejected["best"]["metrics"]["mae_m"] == 0.5
    assert manifest_path.read_text() == initial_manifest

    accepted, tied = update_benchmark_manifest(
        manifest_path, fixture_path, result(0.5, 0.8), "tie", "trial", "rev-tie"
    )
    assert accepted is False
    assert manifest_path.read_text() == initial_manifest

    accepted, improved = update_benchmark_manifest(
        manifest_path, fixture_path, result(0.4, 0.8), "improvement", "trial", "rev3"
    )
    assert accepted is True
    assert improved["best"]["metrics"]["mae_m"] == 0.4
    assert len(improved["accepted_history"]) == 2
    assert json.loads(manifest_path.read_text())["last_attempt"]["source_revision"] == "rev3"


def test_invalid_benchmark_result_does_not_create_or_replace_manifest(tmp_path):
    fixture_path = _write_fixture(tmp_path / "reference", _fixture_frame())
    manifest_path = tmp_path / "benchmark.json"
    valid = {
        "metrics": compare_depth_maps(
            np.ones((1, 2), dtype=np.float32), np.ones((1, 2), dtype=np.float32)
        ),
        "opencv_version": "test-version",
        "fixture": {"config": {"max_depth": 10.0}},
    }
    accepted, _manifest = update_benchmark_manifest(
        manifest_path, fixture_path, valid, "baseline", "baseline", "rev1"
    )
    assert accepted is True
    baseline_bytes = manifest_path.read_bytes()
    invalid = {
        "metrics": {"mae_m": float("nan")},
        "opencv_version": "test-version",
        "fixture": {"config": {}},
    }

    with pytest.raises(ValueError, match="incomplete metrics"):
        update_benchmark_manifest(manifest_path, fixture_path, invalid, "bad", "bad", "rev0")
    assert manifest_path.read_bytes() == baseline_bytes


def test_manifest_keeps_previous_best_when_fixture_dataset_changes(tmp_path):
    fixture_path = _write_fixture(tmp_path / "reference", _fixture_frame())
    manifest_path = tmp_path / "benchmark.json"
    result = {
        "metrics": compare_depth_maps(
            np.ones((1, 2), dtype=np.float32), np.ones((1, 2), dtype=np.float32)
        ),
        "opencv_version": "test-version",
        "fixture": {"config": {"max_depth": 10.0}},
    }
    accepted, first = update_benchmark_manifest(
        manifest_path, fixture_path, result, "first-dataset", "baseline", "rev1"
    )
    assert accepted
    old_hash = first["fixture_sha256"]

    (fixture_path / "capture-note.txt").write_text("a new capture set", encoding="utf-8")
    accepted, updated = update_benchmark_manifest(
        manifest_path, fixture_path, result, "second-dataset", "new capture", "rev2"
    )

    assert accepted
    assert updated["fixture_sha256"] != old_hash
    assert updated["previous_fixtures"][0]["fixture_sha256"] == old_hash
    assert updated["previous_fixtures"][0]["best"]["change_id"] == "first-dataset"
