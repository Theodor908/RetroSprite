"""Tests for Linked Cels feature."""
from src.animation import AnimationTimeline, Frame
from src.layer import Layer
from src.pixel_data import PixelGrid


def test_layer_has_cel_id():
    layer = Layer("Test", 4, 4)
    assert hasattr(layer, 'cel_id')
    assert isinstance(layer.cel_id, str)
    assert len(layer.cel_id) > 0


def test_new_layers_have_unique_cel_ids():
    l1 = Layer("A", 4, 4)
    l2 = Layer("B", 4, 4)
    assert l1.cel_id != l2.cel_id


def test_frame_copy_linked_shares_pixels():
    frame = Frame(4, 4)
    frame.layers[0].pixels.set_pixel(0, 0, (255, 0, 0, 255))
    linked = frame.copy(linked=True)
    assert linked.layers[0].pixels is frame.layers[0].pixels
    assert linked.layers[0].cel_id == frame.layers[0].cel_id


def test_frame_copy_unlinked_copies_pixels():
    frame = Frame(4, 4)
    frame.layers[0].pixels.set_pixel(0, 0, (255, 0, 0, 255))
    independent = frame.copy(linked=False)
    assert independent.layers[0].pixels is not frame.layers[0].pixels
    assert independent.layers[0].cel_id != frame.layers[0].cel_id
    assert independent.layers[0].pixels.get_pixel(0, 0) == (255, 0, 0, 255)


def test_linked_edit_propagates():
    frame1 = Frame(4, 4)
    frame2 = frame1.copy(linked=True)
    frame2.layers[0].pixels.set_pixel(1, 1, (0, 255, 0, 255))
    assert frame1.layers[0].pixels.get_pixel(1, 1) == (0, 255, 0, 255)


def test_unlink_creates_independence():
    frame1 = Frame(4, 4)
    frame2 = frame1.copy(linked=True)
    frame2.layers[0].unlink()
    assert frame2.layers[0].cel_id != frame1.layers[0].cel_id
    frame2.layers[0].pixels.set_pixel(2, 2, (0, 0, 255, 255))
    assert frame1.layers[0].pixels.get_pixel(2, 2) == (0, 0, 0, 0)


def test_duplicate_frame_creates_independent():
    tl = AnimationTimeline(4, 4)
    tl.current_layer().set_pixel(0, 0, (255, 0, 0, 255))
    tl.duplicate_frame(0)
    f0 = tl.get_frame_obj(0)
    f1 = tl.get_frame_obj(1)
    assert f0.layers[0].pixels is not f1.layers[0].pixels
    assert f0.layers[0].cel_id != f1.layers[0].cel_id
    # Content is copied
    assert f1.layers[0].pixels.get_pixel(0, 0) == (255, 0, 0, 255)


def test_linked_via_frame_copy():
    """Linked cels can still be created via Frame.copy(linked=True)."""
    tl = AnimationTimeline(4, 4)
    linked_copy = tl.get_frame_obj(0).copy(linked=True)
    tl._frames.append(linked_copy)
    assert tl.is_linked(0, 0) is True
    assert tl.is_linked(1, 0) is True


def test_is_not_linked_after_duplicate():
    tl = AnimationTimeline(4, 4)
    tl.duplicate_frame(0)
    assert tl.is_linked(0, 0) is False
    assert tl.is_linked(1, 0) is False


def test_merge_down_auto_unlinks():
    tl = AnimationTimeline(4, 4)
    tl.current_frame_obj().add_layer("Top")
    tl.duplicate_frame(0)
    f0 = tl.get_frame_obj(0)
    f1 = tl.get_frame_obj(1)
    f0.merge_down(1)
    assert f0.layers[0].cel_id != f1.layers[0].cel_id


def test_layer_copy_creates_new_cel_id():
    layer = Layer("Test", 4, 4)
    layer.pixels.set_pixel(0, 0, (255, 0, 0, 255))
    copied = layer.copy()
    assert copied.cel_id != layer.cel_id
    assert copied.pixels is not layer.pixels
    assert copied.pixels.get_pixel(0, 0) == (255, 0, 0, 255)
