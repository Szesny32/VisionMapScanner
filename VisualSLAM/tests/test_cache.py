from layer.base_layer import BaseLayer


def make_layer():
    return BaseLayer(name="l")


def test_cache_stores_and_retrieves_by_frame_and_key():
    layer = make_layer()
    layer.process = lambda data: None
    layer.draw = lambda data: None

    assert layer._get_from_cache(1, "a") is None
    layer._save_to_cache(1, "a", "value_a")
    layer._save_to_cache(1, "b", "value_b")
    layer._save_to_cache(2, "a", "value2")

    assert layer._get_from_cache(1, "a") == "value_a"
    assert layer._get_from_cache(1, "b") == "value_b"
    assert layer._get_from_cache(2, "a") == "value2"
    assert layer._get_from_cache(2, "b") is None


def test_check_cache_restores_context():
    layer = make_layer()
    layer.process = lambda data: None
    layer.draw = lambda data: None

    layer._save_to_cache(7, "out", "cached")
    assert layer._check_cache(7, "out") is True
    assert layer.context["out"] == "cached"
    assert layer._check_cache(8, "out") is False
    assert layer._check_cache(7, "missing") is False


def test_cache_evicts_oldest_frame():
    layer = make_layer()
    layer.max_cache_frames = 2
    layer.process = lambda data: None
    layer.draw = lambda data: None

    layer._save_to_cache(1, "a", "1")
    layer._save_to_cache(2, "a", "2")
    layer._save_to_cache(3, "a", "3")

    assert layer._get_from_cache(1, "a") is None
    assert layer._get_from_cache(2, "a") == "2"
    assert layer._get_from_cache(3, "a") == "3"


def test_frames_saved_without_validation_do_not_count():
    layer = make_layer()
    layer.max_cache_frames = 1
    layer.process = lambda data: None
    layer.draw = lambda data: None

    layer._save_to_cache(None, "a", "x")

    assert layer._get_from_cache(None, "a") is None
    assert len(layer._cache) == 0