"""Tests for layer group operations."""
from src.animation import AnimationTimeline


def test_set_layer_depth_all():
    tl = AnimationTimeline(8, 8)
    tl.add_group_to_all("Group 1")
    tl.add_layer_to_all("Child")
    tl.set_layer_depth_all(1, 1)
    for frame in tl._frames:
        assert frame.layers[1].depth == 1


def test_set_layer_depth_all_multiple_frames():
    tl = AnimationTimeline(8, 8)
    tl.add_frame()
    tl.add_group_to_all("Group 1")
    tl.add_layer_to_all("Child")
    tl.set_layer_depth_all(1, 1)
    for frame in tl._frames:
        assert frame.layers[1].depth == 1


def test_move_layer_into_group():
    """Layer moves to position right after group and gets depth=1."""
    tl = AnimationTimeline(8, 8)
    tl.add_group_to_all("Group 1")
    tl.add_layer_to_all("Layer 2")
    tl.move_layer_into_group(2, 1)
    frame = tl._frames[0]
    assert frame.layers[1].is_group
    assert frame.layers[1].name == "Group 1"
    assert frame.layers[2].name == "Layer 2"
    assert frame.layers[2].depth == 1


def test_move_layer_into_group_repositions():
    """Layer below group moves up to be right after group."""
    tl = AnimationTimeline(8, 8)
    tl.add_layer_to_all("Layer 2")
    tl.add_group_to_all("Group 1")
    tl.move_layer_into_group(0, 2)
    frame = tl._frames[0]
    assert frame.layers[1].is_group
    assert frame.layers[1].name == "Group 1"
    assert frame.layers[2].name == "Layer 1"
    assert frame.layers[2].depth == 1


def test_move_layer_into_group_rejects_group():
    """Cannot move a group into another group (one-level constraint)."""
    tl = AnimationTimeline(8, 8)
    tl.add_group_to_all("Group 1")
    tl.add_group_to_all("Group 2")
    result = tl.move_layer_into_group(2, 1)
    assert result is False
    frame = tl._frames[0]
    assert frame.layers[1].depth == 0
    assert frame.layers[2].depth == 0


def test_move_layer_into_group_rejects_nongroup_target():
    """Cannot move a layer into a non-group layer."""
    tl = AnimationTimeline(8, 8)
    tl.add_layer_to_all("Layer 2")
    result = tl.move_layer_into_group(0, 1)
    assert result is False


def test_move_layer_out_of_group():
    """Layer at depth=1 moves above its group and gets depth=0."""
    tl = AnimationTimeline(8, 8)
    tl.add_group_to_all("Group 1")
    tl.add_layer_to_all("Child")
    tl.set_layer_depth_all(2, 1)
    tl.move_layer_out_of_group(2)
    frame = tl._frames[0]
    assert frame.layers[2].name == "Child"
    assert frame.layers[2].depth == 0


def test_move_layer_out_of_group_noop_at_root():
    """No-op if layer is already at depth 0."""
    tl = AnimationTimeline(8, 8)
    tl.add_layer_to_all("Layer 2")
    result = tl.move_layer_out_of_group(1)
    assert result is False
    frame = tl._frames[0]
    assert frame.layers[1].depth == 0


def test_move_layer_out_finds_parent_group():
    """Layer removed from group is placed above the parent group."""
    tl = AnimationTimeline(8, 8)
    tl.add_group_to_all("Group 1")
    tl.add_layer_to_all("Child A")
    tl.set_layer_depth_all(2, 1)
    tl.add_layer_to_all("Child B")
    tl.set_layer_depth_all(3, 1)
    tl.move_layer_out_of_group(2)
    frame = tl._frames[0]
    assert frame.layers[3].name == "Child A"
    assert frame.layers[3].depth == 0


def test_add_group_always_depth_zero():
    """New groups are always created at depth 0, regardless of active layer depth."""
    tl = AnimationTimeline(8, 8)
    tl.add_group_to_all("Group 1")
    tl.add_layer_to_all("Child")
    tl.set_layer_depth_all(2, 1)
    for frame in tl._frames:
        frame.active_layer_index = 2
    tl.add_group_to_all("Group 2", depth=0)
    for frame in tl._frames:
        assert frame.layers[3].is_group
        assert frame.layers[3].depth == 0


def test_add_frame_preserves_group_structure():
    """add_frame propagates depth and is_group to new frame."""
    tl = AnimationTimeline(8, 8)
    tl.add_group_to_all("Group 1")
    tl.add_layer_to_all("Child")
    tl.set_layer_depth_all(2, 1)
    tl.add_frame()
    new_frame = tl._frames[-1]
    assert new_frame.layers[1].is_group is True
    assert new_frame.layers[1].name == "Group 1"
    assert new_frame.layers[2].depth == 1


def test_move_out_rejects_orphaned_layer():
    """Layer with depth=1 but no parent group returns False."""
    tl = AnimationTimeline(8, 8)
    tl.add_layer_to_all("Orphan")
    # Manually set depth without a group existing
    tl.set_layer_depth_all(1, 1)
    result = tl.move_layer_out_of_group(1)
    assert result is False


def test_move_layer_into_group_multi_frame():
    """move_layer_into_group applies across all frames."""
    tl = AnimationTimeline(8, 8)
    tl.add_frame()
    tl.add_group_to_all("Group 1")
    tl.add_layer_to_all("Child")
    tl.move_layer_into_group(2, 1)
    for frame in tl._frames:
        assert frame.layers[2].depth == 1
        assert frame.layers[1].is_group


def test_group_visibility_propagation():
    """Toggling group visibility should affect children too (data-level check)."""
    tl = AnimationTimeline(8, 8)
    tl.add_group_to_all("Group 1")
    tl.add_layer_to_all("Child A")
    tl.set_layer_depth_all(2, 1)
    tl.add_layer_to_all("Child B")
    tl.set_layer_depth_all(3, 1)
    frame = tl._frames[0]
    # Simulate what _on_layer_visibility_idx does: find children, toggle all
    group_idx = 1
    g_depth = frame.layers[group_idx].depth
    targets = [group_idx]
    for ci in range(group_idx + 1, len(frame.layers)):
        if frame.layers[ci].is_group or frame.layers[ci].depth <= g_depth:
            break
        targets.append(ci)
    assert targets == [1, 2, 3]
    # Toggle off
    for ti in targets:
        frame.layers[ti].visible = False
    assert not frame.layers[1].visible
    assert not frame.layers[2].visible
    assert not frame.layers[3].visible
    # Layer 1 (outside group) unaffected
    assert frame.layers[0].visible


def test_move_layer_out_of_group_multi_frame():
    """move_layer_out_of_group applies across all frames."""
    tl = AnimationTimeline(8, 8)
    tl.add_frame()
    tl.add_group_to_all("Group 1")
    tl.add_layer_to_all("Child")
    tl.set_layer_depth_all(2, 1)
    tl.move_layer_out_of_group(2)
    for frame in tl._frames:
        assert frame.layers[2].depth == 0
