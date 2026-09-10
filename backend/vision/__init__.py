"""TRINETRA vision layer — detection + tracking (M2).

ONE detection code path, ONE tracking authority (Ultralytics ByteTrack),
one DetectorTracker instance per processing session.
"""

from backend.vision.face import FaceDetection, YuNetFaceDetector
from backend.vision.pose import COCO_SKELETON_EDGES, PoseDetection, YOLOv8PoseDetector
from backend.vision.tracker import DetectorError, DetectorTracker, TrackedObject

__all__ = [
    "COCO_SKELETON_EDGES",
    "DetectorError",
    "DetectorTracker",
    "FaceDetection",
    "PoseDetection",
    "TrackedObject",
    "YOLOv8PoseDetector",
    "YuNetFaceDetector",
]
