# Stereo depth regression check

Run the verification command after every change that can affect stereo matching,
depth values or previews, camera calibration, fixture loading, or benchmark metrics.
Keep the Unity fixture fixed while comparing algorithm changes. This regression
workflow is the project's required depth verification skill; do not accept an
OpenCV change until it passes this workflow.

From the repository root, run:

```bash
VisualSLAM/scripts/verify_stereo_depth.sh \
  --change-id "<short-unique-id>" \
  --change-description "<what changed>"
```

The benchmark reads every synchronized frame under
`tests/fixtures/unity_startup/frames/` and compares OpenCV depth to the fixed
valid-pixel mask of that frame's `depth_gt_f32le.bin`; each frame also stores
`left.jpg`, `right.jpg`, `depth_gt.png`, and its own `metadata.json`. Unity writes
10 frames by default, then atomically replaces the complete fixture directory.
Stereo matching settings come from the Python UI's `config/gui_cfg.json`, while
camera calibration and each GT reference come from the captured fixture. Pass
`--use-captured-config` to explicitly use the OpenCV settings captured in its
metadata instead. The benchmark reads the previous best from
`tests/fixtures/unity_stereo_benchmark.json`. A change is accepted only when MAE
decreases and OpenCV coverage does not decrease. The command exits nonzero for a
rejected or invalid result, and rejected results do not modify the manifest.

The manifest contains only a valid baseline and accepted improvements in
`accepted_history`; each entry includes aggregate and per-frame MAE/RMSE/bias,
coverage, diagnostics, timestamps, and a `saved_artifacts` inventory containing
the relative path, byte size, and SHA-256 of every frame file plus the collection
index. `best` refers to the latest accepted result. A rejected candidate is not
written to the manifest. Never edit the best metrics by hand. If the command exits
nonzero after the tests pass, inspect the benchmark output: the candidate was
invalid or did not improve aggregate MAE without reducing coverage. If no Unity
fixture exists yet, start the Unity scene, wait for the configured capture count,
and confirm `metadata.json` reports the expected frame count before running this
command.
