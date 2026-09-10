"""TRINETRA video sources — unified ingestion layer (M1).

VideoSource implementations:
  - FileSource    (MP4/MOV and other OpenCV-decodable containers)
  - WebcamSource  (macOS AVFoundation camera index)
  - (future, Phase 3) RtspSource
"""

from backend.sources.base import FramePacket, SourceError, SourceState, VideoSource
from backend.sources.file import FileSource
from backend.sources.rtsp import RtspSource
from backend.sources.webcam import WebcamSource, probe_webcams

__all__ = [
    "FramePacket",
    "SourceError",
    "SourceState",
    "VideoSource",
    "FileSource",
    "RtspSource",
    "WebcamSource",
    "probe_webcams",
]
