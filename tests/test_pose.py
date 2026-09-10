"""Tests for TRINETRA Human Pose Estimation (17 COCO Keypoints) & Annotation."""

from pathlib import Path
import numpy as np
import pytest

from backend.vision.annotation import _draw_pose, annotate
from backend.vision.pose import (
    COCO_SKELETON_EDGES,
    PoseDetection,
    YOLOv8PoseDetector,
)
from backend.vision.tracker import TrackedObject


def test_coco_skeleton_edges_structure():
    assert len(COCO_SKELETON_EDGES) == 16
    for p1, p2 in COCO_SKELETON_EDGES:
        assert 0 <= p1 < 17
        assert 0 <= p2 < 17


def test_pose_detector_nonexistent_model():
    det = YOLOv8PoseDetector(model_path="/tmp/nonexistent_pose.pt")
    assert not det.available
    poses = det.detect(np.zeros((480, 640, 3), dtype=np.uint8))
    assert poses == []


def test_pose_detector_available_with_default_model():
    det = YOLOv8PoseDetector()
    # If models/yolov8n-pose.pt exists, it should be available or loadable
    if Path("models/yolov8n-pose.pt").exists():
        assert det.available
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        poses = det.detect(frame)
        assert isinstance(poses, list)


def test_draw_pose_safe_on_invalid_and_empty():
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    _draw_pose(frame, None)
    _draw_pose(frame, {})
    _draw_pose(frame, {"keypoints": []})
    _draw_pose(frame, {"keypoints": [[10, 10, 0.9]] * 5})  # <17 keypoints
    assert frame.shape == (100, 100, 3)


def test_draw_pose_valid_keypoints():
    frame = np.zeros((200, 200, 3), dtype=np.uint8)
    kpts = [[float(i * 10), float(i * 10), 0.9] for i in range(17)]
    pose = PoseDetection(
        bbox=[10, 10, 180, 180],
        score=0.85,
        keypoints=kpts,
    )
    _draw_pose(frame, pose)
    assert frame.max() > 0  # Drew something


def test_annotate_with_pose_layer():
    frame = np.zeros((200, 200, 3), dtype=np.uint8)
    kpts = [[float(i * 10), float(i * 10), 0.9] for i in range(17)]
    pose = PoseDetection(
        bbox=[10, 10, 180, 180],
        score=0.85,
        keypoints=kpts,
    )
    # Pose layer OFF by default
    out_off = annotate(frame, [], layers={"pose": False}, poses=[pose])
    assert (out_off == frame).all()

    # Pose layer ON
    out_on = annotate(frame, [], layers={"pose": True}, poses=[pose])
    assert out_on.max() > 0
