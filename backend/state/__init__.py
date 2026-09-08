"""TRINETRA track state — application state keyed by authoritative IDs (M2).

ByteTrack is the object-identity authority. TrackStore NEVER assigns,
generates, or substitutes IDs — it only records what the detector produced.
"""

from backend.state.tracks import TrackState, TrackStore

__all__ = ["TrackState", "TrackStore"]
