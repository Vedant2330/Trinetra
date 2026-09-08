"""TRINETRA vision layer — detection + tracking (M2).

ONE detection code path, ONE tracking authority (Ultralytics ByteTrack),
one DetectorTracker instance per processing session.
"""

from backend.vision.tracker import DetectorError, DetectorTracker, TrackedObject

__all__ = ["DetectorError", "DetectorTracker", "TrackedObject"]
