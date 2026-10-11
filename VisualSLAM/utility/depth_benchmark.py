"""Deterministic capture and comparison helpers for OpenCV-vs-Unity depth."""

import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone

import cv2
import numpy as np

from layer.depth_config import StereoDepthConfig
from layer.gt_depth_layer import GTDepthLayer
from layer.stereo_layer import StereoLayer


MANIFEST_SCHEMA_VERSION = 3
OPENCV_CONFIG_FIELDS = (
    "baseline",
    "min_disp",
    "num_disp_multiplier",
    "block_size",
    "p2_scale",
    "wls_lambda",
    "wls_sigma",
)


def load_depth_fixture(path):
    """Load Unity's atomically written multi-frame startup fixture."""
    directory = os.path.abspath(path)
    with open(os.path.join(directory, "metadata.json"), "r", encoding="utf-8-sig") as source:
        metadata = json.load(source)
    if metadata.get("schema_version") == 2:
        entries = metadata.get("frames")
        if not entries:
            raise ValueError("Unity fixture collection contains no frames")
        if int(metadata.get("frame_count", -1)) != len(entries):
            raise ValueError("Unity fixture collection frame count does not match its index")
        frames = []
        seen_ids = set()
        for index, entry in enumerate(entries):
            frame_id = str(entry.get("frame_id", "frame_%06d" % (index + 1)))
            if frame_id in seen_ids:
                raise ValueError("Unity fixture contains duplicate frame IDs")
            seen_ids.add(frame_id)
            relative_path = entry.get("directory")
            if not relative_path or os.path.isabs(relative_path):
                raise ValueError("Unity fixture frame directory must be relative")
            frame_directory = os.path.abspath(os.path.join(directory, relative_path))
            if os.path.commonpath((directory, frame_directory)) != directory:
                raise ValueError("Unity fixture frame directory escapes its collection")
            frame_metadata_path = os.path.join(frame_directory, "metadata.json")
            with open(frame_metadata_path, "r", encoding="utf-8-sig") as source:
                frame_metadata = json.load(source)
            frame = _load_single_fixture_frame(frame_directory, frame_metadata)
            if (int(metadata.get("width", frame["depth_gt"].shape[1])) != frame["depth_gt"].shape[1]
                    or int(metadata.get("height", frame["depth_gt"].shape[0])) != frame["depth_gt"].shape[0]):
                raise ValueError("Unity fixture frame dimensions do not match collection metadata")
            collection_config = metadata.get("config")
            if collection_config is not None and collection_config != frame["config"]:
                raise ValueError("Unity fixture frame configuration differs from collection snapshot")
            if entry.get("stamp") is not None and abs(
                    _stamp_seconds(entry["stamp"]) - float(frame["stamp"])) > 0.001:
                raise ValueError("Unity fixture index timestamp does not match frame metadata")
            frame["frame_id"] = frame_id
            frame["directory"] = relative_path.replace(os.sep, "/")
            frame["files"] = _fixture_file_inventory(frame_directory, directory)
            frames.append(frame)
        return _fixture_collection(frames, metadata, directory)
    # Schema 1 remains readable so an already captured local frame is usable
    # until Unity replaces it with the new atomic multi-frame collection.
    if metadata.get("schema_version") != 1:
        raise ValueError("unsupported Unity fixture metadata schema")
    frame = _load_single_fixture_frame(directory, metadata)
    frame["frame_id"] = "frame_000001"
    frame["directory"] = "."
    frame["files"] = _fixture_file_inventory(directory, directory)
    return _fixture_collection([frame], metadata, directory)


def _load_single_fixture_frame(directory, metadata):
    width, height = int(metadata["width"]), int(metadata["height"])
    if width <= 0 or height <= 0:
        raise ValueError("fixture dimensions must be positive")
    left = cv2.imread(os.path.join(directory, "left.jpg"), cv2.IMREAD_COLOR)
    right = cv2.imread(os.path.join(directory, "right.jpg"), cv2.IMREAD_COLOR)
    depth_preview = cv2.imread(
        os.path.join(directory, "depth_gt.png"), cv2.IMREAD_GRAYSCALE
    )
    if left is None or right is None or left.size == 0 or right.size == 0:
        raise ValueError("fixture needs non-empty left.jpg and right.jpg images")
    if depth_preview is None or depth_preview.size == 0:
        raise ValueError("fixture needs a non-empty depth_gt.png preview")
    if any(image.shape[:2] != (height, width) for image in (left, right, depth_preview)):
        raise ValueError("fixture image dimensions do not match metadata")
    with open(os.path.join(directory, "depth_gt_f32le.bin"), "rb") as source:
        depth_bytes = source.read()
    depth = np.frombuffer(depth_bytes, dtype="<f4")
    if depth.size != width * height:
        raise ValueError("fixture GT binary size does not match metadata dimensions")
    depth = depth.astype(np.float32, copy=False).reshape((height, width)).copy()
    if (metadata.get("depth_encoding") != "32FC1" or metadata.get("depth_units") != "m"
            or metadata.get("depth_byte_order") != "little_endian"
            or metadata.get("depth_preview_encoding") != "gray8_near_white"
            or metadata.get("depth_preview_row_order", "top_to_bottom") != "top_to_bottom"):
        raise ValueError("fixture GT must use 32FC1 depth in meters")

    timestamps = metadata["timestamps"]
    stamp = _stamp_seconds(timestamps["left"])
    right_stamp = _stamp_seconds(timestamps["right"])
    depth_stamp = _stamp_seconds(timestamps["depth"])
    if max(abs(stamp - right_stamp), abs(stamp - depth_stamp)) > 0.001:
        raise ValueError("fixture stereo and GT timestamps are not synchronized")
    camera_info = metadata["camera_info"]
    normalized_info = {"width": width, "height": height, "depth_units": "m"}
    for side in ("left", "right"):
        side_info = camera_info[side]
        if int(side_info["width"]) != width or int(side_info["height"]) != height:
            raise ValueError("fixture CameraInfo dimensions must match captured images")
        if len(side_info["k"]) != 9 or len(side_info["p"]) != 12:
            raise ValueError("fixture CameraInfo must include complete K and P matrices")
        info_stamp = _stamp_seconds(side_info["stamp"])
        if abs(info_stamp - stamp) > 0.001:
            raise ValueError("fixture CameraInfo timestamps are not synchronized")
        normalized_info[side] = side_info
    normalized_info["focal_length"] = float(normalized_info["left"]["p"][0])
    normalized_info["baseline"] = float(metadata["config"]["baseline"])
    preview_min = float(metadata["depth_preview_min_m"])
    preview_max = float(metadata["depth_preview_max_m"])
    if (not np.isclose(preview_min, float(metadata["config"]["min_depth"]))
            or not np.isclose(preview_max, float(metadata["config"]["max_depth"]))):
        raise ValueError("fixture preview range does not match the captured configuration")
    expected_preview = depth_preview_from_map(depth, preview_min, preview_max)
    if not np.all(np.abs(depth_preview.astype(np.int16) - expected_preview.astype(np.int16)) <= 1):
        raise ValueError("fixture depth preview orientation or values do not match GT data")
    if normalized_info["focal_length"] <= 0 or normalized_info["baseline"] <= 0:
        raise ValueError("fixture needs valid focal length and baseline metadata")
    return {
        "left": left,
        "right": right,
        "depth_gt": depth,
        "depth_gt_preview": depth_preview,
        "stamp": np.float64(stamp),
        "depth_stamp": np.float64(depth_stamp),
        "camera_info": normalized_info,
        "config": metadata["config"],
        "metadata": metadata,
    }


def _fixture_file_inventory(frame_directory, collection_directory):
    inventory = []
    for filename in ("left.jpg", "right.jpg", "depth_gt_f32le.bin", "depth_gt.png", "metadata.json"):
        file_path = os.path.join(frame_directory, filename)
        inventory.append({
            "path": os.path.relpath(file_path, collection_directory).replace(os.sep, "/"),
            "size_bytes": os.path.getsize(file_path),
            "sha256": _sha256_file(file_path),
        })
    return inventory


def _fixture_collection(frames, metadata, directory):
    if not frames:
        raise ValueError("Unity fixture collection contains no frames")
    first = frames[0]
    return {
        **first,
        "frames": frames,
        "metadata": metadata,
        "frame_count": len(frames),
        "saved_artifacts": [artifact for frame in frames for artifact in frame["files"]]
        + ([{
            "path": "metadata.json",
            "size_bytes": os.path.getsize(os.path.join(directory, "metadata.json")),
            "sha256": _sha256_file(os.path.join(directory, "metadata.json")),
        }] if metadata.get("schema_version") == 2 else []),
    }


def _stamp_seconds(stamp):
    if isinstance(stamp, dict):
        seconds = float(stamp["sec"]) + float(stamp["nanosec"]) * 1e-9
    else:
        seconds = float(stamp)
    if not np.isfinite(seconds):
        raise ValueError("fixture contains an invalid timestamp")
    return seconds


def depth_preview_from_map(depth, min_depth, max_depth):
    """Map top-to-bottom camera rows to grayscale without changing image orientation."""
    depth_map = _depth_array(depth)
    if depth_map is None:
        raise ValueError("depth preview needs a non-empty HxW map")
    min_depth = float(min_depth)
    max_depth = float(max_depth)
    if not np.isfinite(min_depth) or not np.isfinite(max_depth) or max_depth <= min_depth:
        raise ValueError("depth preview range must be finite and increasing")
    valid = np.isfinite(depth_map) & (depth_map > 0.0)
    gray = np.zeros(depth_map.shape, dtype=np.uint8)
    scaled = np.clip(
        (max_depth - depth_map[valid].astype(np.float64)) / (max_depth - min_depth),
        0.0,
        1.0,
    )
    gray[valid] = np.rint(scaled * 255.0).astype(np.uint8)
    return gray


def compare_depth_maps(predicted, reference):
    """Compare depth in meters on the fixed valid-reference mask."""
    prediction = _depth_array(predicted)
    truth = _depth_array(reference)
    if prediction is None or truth is None or prediction.shape != truth.shape:
        raise ValueError("prediction and reference must be non-empty matching HxW maps")

    reference_mask = np.isfinite(truth) & (truth > 0.0)
    predicted_mask = np.isfinite(prediction) & (prediction > 0.0)
    reference_pixels = int(np.count_nonzero(reference_mask))
    if reference_pixels == 0:
        raise ValueError("reference map has no valid depth pixels")

    overlap = reference_mask & predicted_mask
    overlap_pixels = int(np.count_nonzero(overlap))
    if overlap_pixels == 0:
        raise ValueError("prediction and reference have no overlapping valid pixels")

    error = prediction[overlap].astype(np.float64) - truth[overlap].astype(np.float64)
    absolute_error = np.abs(error)
    return {
        "mae_m": float(np.mean(absolute_error)),
        "rmse_m": float(np.sqrt(np.mean(np.square(error)))),
        "bias_m": float(np.mean(error)),
        "valid_reference_pixels": reference_pixels,
        "valid_overlap_pixels": overlap_pixels,
        "opencv_coverage": float(overlap_pixels / reference_pixels),
        "reference": depth_range_statistics(truth[reference_mask]),
        "opencv_overlap": depth_range_statistics(prediction[overlap]),
    }


def depth_range_statistics(values):
    values = np.asarray(values, dtype=np.float32).reshape(-1)
    values = values[np.isfinite(values)]
    if values.size == 0:
        return {"count": 0}
    quantiles = np.percentile(values, (1, 10, 50, 90, 99))
    return {
        "count": int(values.size),
        "min_m": float(np.min(values)),
        "max_m": float(np.max(values)),
        "p01_m": float(quantiles[0]),
        "p10_m": float(quantiles[1]),
        "p50_m": float(quantiles[2]),
        "p90_m": float(quantiles[3]),
        "p99_m": float(quantiles[4]),
    }


def run_fixture_benchmark(fixture_path, config_overrides=None):
    fixture = load_depth_fixture(fixture_path)
    captured_config_values = {
        key: fixture["config"][key]
        for key in StereoDepthConfig.__dataclass_fields__
        if key in fixture["config"]
    }
    reference_config = StereoDepthConfig(**captured_config_values)
    opencv_config_values = dict(captured_config_values)
    for key, value in (config_overrides or {}).items():
        if key not in OPENCV_CONFIG_FIELDS:
            raise ValueError("unsupported OpenCV benchmark configuration: %s" % key)
        opencv_config_values[key] = value
    opencv_config = StereoDepthConfig(**opencv_config_values)
    if not reference_config.validate() or not opencv_config.validate():
        raise ValueError("OpenCV benchmark configuration is invalid")
    frame_results = []
    all_reference = []
    all_predictions = []
    for frame in fixture["frames"]:
        focal_length = float(frame["camera_info"]["focal_length"])
        baseline = float(frame["camera_info"]["baseline"])
        stereo = StereoLayer(depth_config=opencv_config)
        stereo_data = {
            "left": frame["left"],
            "right": frame["right"],
            "f": focal_length,
            "baseline": opencv_config.baseline,
            "_collect_depth_diagnostics": True,
        }
        stereo.process(stereo_data)
        predicted = stereo_data.get("depth_map")
        if predicted is None:
            raise ValueError("OpenCV could not produce depth for %s" % frame["frame_id"])

        gt_layer = GTDepthLayer(depth_config=reference_config)
        gt_data = {
            "left": frame["left"],
            "depth_map_gt": frame["depth_gt"],
            "f": focal_length,
            "baseline": baseline,
        }
        gt_layer.process(gt_data)
        reference = gt_data.get("depth_map_gt")
        if reference is None:
            raise ValueError("saved Unity GT depth is invalid for %s" % frame["frame_id"])
        frame_results.append({
            "frame_id": frame["frame_id"],
            "stamp": float(frame["stamp"]),
            "metrics": compare_depth_maps(predicted, reference),
            "diagnostics": stereo_data.get("_depth_diagnostics", {}).get("opencv", {}),
            "saved_files": frame["files"],
        })
        all_reference.append(reference)
        all_predictions.append(predicted)
    return {
        "metrics": _aggregate_frame_metrics(frame_results, all_predictions, all_reference),
        "frames": frame_results,
        "saved_artifacts": fixture["saved_artifacts"],
        "frame_count": fixture["frame_count"],
        "diagnostics": {
            "frame_count": len(frame_results),
            "frames": [
                {"frame_id": frame["frame_id"], **frame["diagnostics"]}
                for frame in frame_results
            ],
        },
        "fixture": fixture,
        "benchmark_config": opencv_config.to_dict(),
        "opencv_version": cv2.__version__,
    }


def _aggregate_frame_metrics(frame_results, predictions, references):
    metrics = [frame["metrics"] for frame in frame_results]
    total_overlap = sum(item["valid_overlap_pixels"] for item in metrics)
    total_reference = sum(item["valid_reference_pixels"] for item in metrics)
    if total_overlap <= 0 or total_reference <= 0:
        raise ValueError("fixture collection has no comparable depth pixels")
    mae = sum(item["mae_m"] * item["valid_overlap_pixels"] for item in metrics) / total_overlap
    squared_error = sum(
        item["rmse_m"] ** 2 * item["valid_overlap_pixels"] for item in metrics
    ) / total_overlap
    bias = sum(item["bias_m"] * item["valid_overlap_pixels"] for item in metrics) / total_overlap
    reference_values = np.concatenate([
        reference[np.isfinite(reference) & (reference > 0.0)].reshape(-1)
        for reference in references
    ])
    prediction_values = np.concatenate([
        prediction[np.isfinite(prediction) & (prediction > 0.0)].reshape(-1)
        for prediction in predictions
    ])
    return {
        "mae_m": float(mae),
        "rmse_m": float(np.sqrt(squared_error)),
        "bias_m": float(bias),
        "valid_reference_pixels": int(total_reference),
        "valid_overlap_pixels": int(total_overlap),
        "opencv_coverage": float(total_overlap / total_reference),
        "reference": depth_range_statistics(reference_values),
        "opencv": depth_range_statistics(prediction_values),
        "frame_count": len(frame_results),
    }


def update_benchmark_manifest(
    manifest_path,
    fixture_path,
    result,
    change_id,
    change_description,
    source_revision,
    source_signature=None,
):
    metrics = result["metrics"]
    _validate_benchmark_metrics(metrics)
    fixture_hash = _sha256_file(fixture_path)
    previous = _load_manifest(manifest_path)
    same_fixture = previous.get("fixture_sha256") == fixture_hash
    best = previous.get("best") if same_fixture else None

    if best is None:
        status = "baseline"
        accepted = True
        reason = "Initial benchmark result establishes the baseline."
    elif (
        metrics["mae_m"] < best["metrics"]["mae_m"]
        and metrics["opencv_coverage"] >= best["metrics"]["opencv_coverage"]
    ):
        status = "accepted"
        accepted = True
        reason = "MAE improved and OpenCV coverage did not decrease."
    else:
        # Add the file inventory and per-frame measurements to an existing
        # numerically identical accepted result when upgrading the manifest.
        comparable_metric_keys = (
            "mae_m", "rmse_m", "bias_m", "opencv_coverage",
            "valid_reference_pixels", "valid_overlap_pixels",
        )
        same_best_result = best is not None and all(
            metrics.get(key) == best.get("metrics", {}).get(key)
            for key in comparable_metric_keys
        )
        if (same_fixture and same_best_result and result.get("saved_artifacts")
                and not best.get("saved_artifacts")):
            enriched = dict(best)
            enriched.update({
                "frame_count": int(result.get("frame_count", len(result.get("frames", [])) or 1)),
                "frame_results": result.get("frames", []),
                "saved_artifacts": result["saved_artifacts"],
                "diagnostics": result.get("diagnostics", best.get("diagnostics", {})),
            })
            previous["schema_version"] = MANIFEST_SCHEMA_VERSION
            previous["best"] = enriched
            previous["saved_artifacts"] = result["saved_artifacts"]
            last_metrics = previous.get("last_attempt", {}).get("metrics", {})
            if all(metrics.get(key) == last_metrics.get(key) for key in comparable_metric_keys):
                previous["last_attempt"] = enriched
            history = previous.get("accepted_history", [])
            history_metrics = history[-1].get("metrics", {}) if history else {}
            if history and all(
                    metrics.get(key) == history_metrics.get(key) for key in comparable_metric_keys):
                history[-1] = enriched
            _atomic_write_json(manifest_path, previous)
        return False, previous

    attempt = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "reason": reason,
        "change_id": str(change_id),
        "change_description": str(change_description),
        "source_revision": str(source_revision),
        "source_signature": source_signature or {},
        "fixture_sha256": fixture_hash,
        "opencv_version": result["opencv_version"],
        "config": result.get("benchmark_config", result["fixture"]["config"]),
        "captured_fixture_config": result["fixture"]["config"],
        "captured_calibration": result.get("fixture", {}).get("camera_info", {}),
        "metrics": metrics,
        "diagnostics": result.get("diagnostics", {}),
        "frame_count": int(result.get("frame_count", len(result.get("frames", [])) or 1)),
        "frame_results": result.get("frames", []),
        "saved_artifacts": result.get(
            "saved_artifacts", result.get("fixture", {}).get("saved_artifacts", [])
        ),
    }
    if accepted:
        best = attempt

    manifest = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "fixture_path": os.path.relpath(fixture_path, os.path.dirname(manifest_path)),
        "fixture_sha256": fixture_hash,
        "best": best,
        "last_attempt": attempt,
        "saved_artifacts": attempt["saved_artifacts"],
        "previous_fixtures": _previous_fixture_history(previous, fixture_hash),
        "accepted_history": (previous.get("accepted_history", []) if same_fixture else [])
        + [attempt],
    }
    _atomic_write_json(manifest_path, manifest)
    return accepted, manifest


def _previous_fixture_history(previous, current_fixture_hash):
    history = list(previous.get("previous_fixtures", []))
    previous_hash = previous.get("fixture_sha256")
    if (previous_hash and previous_hash != current_fixture_hash
            and previous.get("best") is not None
            and all(item.get("fixture_sha256") != previous_hash for item in history)):
        history.append({
            "fixture_sha256": previous_hash,
            "fixture_path": previous.get("fixture_path"),
            "best": previous["best"],
            "accepted_history": previous.get("accepted_history", []),
        })
    return history


def _validate_benchmark_metrics(metrics):
    required_finite = ("mae_m", "rmse_m", "bias_m", "opencv_coverage")
    try:
        values = {key: float(metrics[key]) for key in required_finite}
        reference_pixels = int(metrics["valid_reference_pixels"])
        overlap_pixels = int(metrics["valid_overlap_pixels"])
    except (KeyError, TypeError, ValueError, OverflowError) as error:
        raise ValueError("benchmark result has incomplete metrics") from error
    if not all(np.isfinite(value) for value in values.values()):
        raise ValueError("benchmark result has non-finite metrics")
    if (values["mae_m"] < 0 or values["rmse_m"] < 0
            or not 0.0 <= values["opencv_coverage"] <= 1.0
            or reference_pixels <= 0 or overlap_pixels <= 0
            or overlap_pixels > reference_pixels):
        raise ValueError("benchmark result metrics are outside valid ranges")


def _depth_array(depth):
    if depth is None:
        return None
    try:
        result = np.asarray(depth, dtype=np.float32)
    except (TypeError, ValueError, OverflowError):
        return None
    if result.ndim != 2 or result.size == 0:
        return None
    return result


def _finite_float(value):
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return result if np.isfinite(result) else None


def _sha256_file(path):
    digest = hashlib.sha256()
    if os.path.isdir(path):
        for root, directories, filenames in os.walk(path):
            directories.sort()
            for filename in sorted(filenames):
                file_path = os.path.join(root, filename)
                relative_path = os.path.relpath(file_path, path).replace(os.sep, "/")
                digest.update(relative_path.encode("utf-8"))
                with open(file_path, "rb") as source:
                    for chunk in iter(lambda: source.read(1024 * 1024), b""):
                        digest.update(chunk)
    else:
        with open(path, "rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
    return digest.hexdigest()


def _load_manifest(path):
    try:
        with open(path, "r", encoding="utf-8") as source:
            manifest = json.load(source)
        if manifest.get("schema_version") in (2, MANIFEST_SCHEMA_VERSION):
            return manifest
    except (OSError, ValueError, TypeError):
        pass
    return {}


def _atomic_write_json(path, data):
    destination = os.path.abspath(path)
    os.makedirs(os.path.dirname(destination), exist_ok=True)
    fd, temporary_path = tempfile.mkstemp(
        prefix=".depth-manifest-", suffix=".json", dir=os.path.dirname(destination)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            json.dump(data, output, indent=2, sort_keys=True)
            output.write("\n")
        os.replace(temporary_path, destination)
    except Exception:
        try:
            os.unlink(temporary_path)
        except OSError:
            pass
        raise
