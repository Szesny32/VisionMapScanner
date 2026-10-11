def gt_depth_stream_requested(layers):
    """Return whether an enabled GT layer needs Unity depth frames for its preview."""
    return any(
        layer.enabled and layer.provides.get("depth_map") == "depth_map_gt"
        for layer in layers
    )
