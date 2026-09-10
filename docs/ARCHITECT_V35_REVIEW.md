# TRINETRA V3.5 — ARCHITECTURE REVIEW & BINDING GATE (Stage 3 of 5)

**Document Status:** OFFICIAL ARCHITECTURAL RULING & BINDING CONTRACT  
**Gate Verdict:** **`APPROVED-WITH-CORRECTIONS`**  
**Author:** `architect-and-pipeline-mtum77rw` (Stage 3 Architect)  
**Date:** 2026-09-10  
**Chain of Custody:** RESEARCHER (`mtumwxna`) → PLANNER (`mtumzx5p`) → **ARCHITECT (`mtum77rw`, this review)** → EXECUTOR (`executer-mtum4rce`) → VERIFIER (`oscar-mtt8m47c` + `god`)  
**Base Tree:** `HEAD 3d0c7e2` + uncommitted V3 light-theme sprint + M8 Re-ID working tree  
**Primary Review Target:** `Trinetra/docs/PLAN_V35_FINAL.md`  
**Reference Inputs:** `Trinetra/docs/RESEARCH_V35.md`, `Trinetra/TRINETRA_FULL_ARCHITECTURE_HANDOFF.md`, `Trinetra/backend/` working tree.

---

## 1. Executive Ruling & Gate Verdict

### 1.1 Gate Verdict: APPROVED-WITH-CORRECTIONS
The TRINETRA V3.5 Execution Task Graph (`docs/PLAN_V35_FINAL.md`) is **APPROVED-WITH-CORRECTIONS**. The plan is structurally rigorous, logically sound, respects all prior architectural baselines, and incorporates empirical findings from Stage-1 Research.

Execution by `executer-mtum4rce` is authorized to proceed immediately subject to strict compliance with the **Binding V-Series Architectural Corrections (V1–V8)** and pinned interface contracts defined herein.

### 1.2 Review Scope Assessments & Rulings

| Review Item | Planner Proposal | Architect Assessment & Ruling | Binding Status |
| :--- | :--- | :--- | :--- |
| **Phase Sequencing** | Phases 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 (with Phase 6 skippable if offline/unsupported) | **SOUND.** Strict dependency hierarchy: core models/infrastructure first, then analytics/heuristics, followed by persistence, specialized edge domains, and integration verification. | **APPROVED** (Phase 6 skippable per gate criteria) |
| **F1 Dynamic-Batch Re-ID** | Primary dynamic batch forwarding + batch-32 zero-padding fallback | **SOUND & VERIFIED.** Benchmarked at 5.5ms (single-crop) vs 69.8ms (batch-32 padded). Produces byte-identical embeddings. | **BOUND** in **V1** |
| **Phase 3 YuNet Lifecycle** | Relocate model from `/var/folders/` to `models/yunet.onnx`; dynamic `setInputSize` sync; faces layer default-OFF; detection-only boundary | **SOUND.** Eliminates temp-eviction crash risk; enforces dimension sync contract; prohibits unverified face recognition. | **BOUND** in **V2** |
| **Phase 4 AGPL Clean-Room & Density** | Mathematical kinematics over `TrackState.positions`; count-based density thresholds (4 medium / 8 high) | **SOUND.** Strict quarantine of AGPL codebase; prevents small-zone density false alarms; binds `_NEW_TYPE_BASE` in `backend/events/engine.py`. | **BOUND** in **V3 & V4** |
| **Phase 5 Trajectory DB Persistence** | God-applied Migration 3 (`ALTER TABLE tracks ADD COLUMN trajectory TEXT`) + DAO method; pre-hunk pragma degrade | **SOUND.** Non-blocking database schema evolution; executor degrades gracefully via column pragma checks before hunk application. | **BOUND** in **V5** |
| **Phase 6 ANPR Honesty** | Three-state engine (`ANPR_READ`, `OCR_UNCERTAIN`, `ANPR_PLATE_DETECTED`); color/geometry fallback; zero mock plates | **SOUND.** Hardware/network honesty enforced; regex corrected for standard and BH-series Indian plates. | **BOUND** in **V6** |
| **Phase 7 RTSP Ingestion** | `RtspSource` implementing `VideoSource`; `OPENCV_FFMPEG_CAPTURE_OPTIONS` set pre-capture; `is_live=True`; venv re-measure gate | **SOUND.** Enforces TCP transport; fixes DB source-type resolution; mandates virtual environment benchmark validation. | **BOUND** in **V7** |
| **Frontend Seams** | `LayerToggles.tsx` and Re-ID UI hook into existing session/layers API without disturbing V3 EventLog/Alerts/Analytics | **SOUND & VERIFIED.** Existing frontend components already landed cleanly; no rework or re-planning of V3 UI. | **BOUND** in **V8** |

### 1.3 Rulings on Planner Open Asks (Endorsing God Directives)
1. **Open Ask 1 (God-Hunk Timing for Phase 5):** **CONFIRMED.** The Orchestrator (`god`) will apply Migration 3 (`ALTER TABLE tracks ADD COLUMN trajectory TEXT`) and the `DAO.upsert_track_trajectories` implementation at the start of Phase 5 upon request from `executer-mtum4rce`. The executor's Phase 5 pre-hunk code must cleanly degrade without crashing via `PRAGMA table_info(tracks)` inspection.
2. **Open Ask 2 (Re-ID Router Placement):** **CONFIRMED.** Inline router endpoints in `backend/main.py` lines 217–250 are retained (per C7 minimal-churn discipline). A separate `backend/api/reid.py` is prohibited unless the router logic exceeds 40 lines.
3. **Open Ask 3 (Chain Hand-off):** **CONFIRMED.** Upon publication of this review and notification to `god`, the orchestrator will dispatch `executer-mtum4rce` for execution.

---

## 2. Binding Architectural Corrections (V-Series)

The Executor (`executer-mtum4rce`) must adhere strictly to the following binding corrections. No deviations are permitted without explicit sign-off.

### V1. Dynamic-Batch Re-ID Embedder & Invariance Acceptance Test
* **Context:** Empirical research established that `fast-reid_mobilenetv2.onnx` executed via `cv2.dnn.readNetFromONNX` supports dynamic batch dimensions natively. Single-crop latency is **5.5ms** (12.7x speedup over 69.8ms padded batch-32).
* **Binding Requirements:**
  1. `OpenCVDnnEmbedder.extract(crops: list[np.ndarray]) -> np.ndarray`:
     - Must first attempt native batch forwarding: `blob = cv2.dnn.blobFromImages(crops, ...)` where `blob.shape[0] == len(crops)`.
     - Must catch `cv2.error` and transparently fall back to batch-32 zero-padding: pad `blob` to `(32, 3, 256, 128)`, forward, and slice `features[:len(crops)]`.
     - Must output L2-normalized embeddings: `feats = feats / np.linalg.norm(feats, axis=1, keepdims=True)`.
  2. **Invariance Acceptance Test:** The test suite (`tests/test_reid.py`) must assert that:
     $$\text{cosine\_similarity}(\mathbf{e}_{\text{dynamic}}, \mathbf{e}_{\text{padded}}) \ge 0.99999$$
     for identical input crops across batch sizes $N \in \{1, 2, 5, 16, 32\}$.
  3. `PersonGallery.batch_match()`: Exemplar matching must process all active track crops in a single dynamic batch call to prevent per-track latency serialization.

### V2. YuNet Face Detection Lifecycle, Dimensions & Detection-Only Boundary
* **Context:** `yunet.onnx` currently resides in volatile macOS `/var/folders/` storage. `cv2.FaceDetectorYN` crashes if `setInputSize` does not match the incoming image shape.
* **Binding Requirements:**
  1. **Relocation:** At the start of Phase 3, copy `/var/folders/.../yunet.onnx` permanently to `Trinetra/models/yunet.onnx` (file size: 232,589 bytes; SHA256 verified).
  2. **Dimension Sync Contract:** `YuNetFaceDetector` must track `(current_w, current_h)` and call `self._detector.setInputSize((frame_w, frame_h))` whenever frame dimensions change prior to calling `self._detector.detect(frame)`.
  3. **Event-Gated Detection:** Face detection must not execute on every frame across the entire canvas. It must execute only on person bounding boxes where `bbox_h >= 80` pixels, throttled by a 5.0-second cooldown per track ID.
  4. **Strict Detection-Only Boundary:** The face pipeline is strictly detection-only (bounding box + 5 landmarks). No face recognition, face embedding extraction, face galleries, or identity matching models may be loaded or promised.
  5. **Honest Health Reporting:** `backend/main.py:_model_status()` must report:
     - `"faces": "available"` if `models/yunet.onnx` exists and loads.
     - `"faces": "unavailable"` (with reason) if absent.
  6. **Default State:** The `faces` layer toggle must default to `False` (OFF) in `LayerToggles.tsx` and session layer config.

### V3. AGPL-3.0 Clean-Room Kinematic Guardrails & Count-Based Density
* **Context:** `crowd-abnormal-behavior-detection-main` is licensed under AGPL-3.0. Direct inclusion, translation, or copying into Trinetra is prohibited. Small-zone polygon area density caused severe false positive alerts in prior tests.
* **Binding Requirements:**
  1. **Clean-Room Quarantine:** Zero imports, file copies, or structural clones from the crowd repo. All kinematic heuristics must be authored from mathematical first principles using `TrackState.positions` (deque of foot coordinates $(x, y)$ over maxlen=60 frames).
  2. **Kinematic Formulations:**
     - **Velocity:** $v_t = \frac{\|\mathbf{p}_t - \mathbf{p}_{t-k}\|_2}{k \cdot \Delta t}$ pixels/sec.
     - **Acceleration:** $a_t = \frac{v_t - v_{t-k}}{k \cdot \Delta t}$ pixels/sec$^2$.
     - **Abnormal Movement:** Sudden directional change $\Delta \theta > 90^\circ$ with $v_t > v_{\text{threshold}}$.
     - **Loitering:** Footprint bounding radius $R = \max_{i} \|\mathbf{p}_i - \mathbf{p}_{\text{centroid}}\|_2 < R_{\text{threshold}}$ sustained for duration $t_{\text{dwell}} \ge 15.0$ seconds.
     - **Night Movement:** Detection of motion while frame mean luminance $\bar{I} = \frac{1}{HW}\sum I(x,y) < 60$.
  3. **Count-Based Crowd Density:** Zone density alerts must be evaluated using integer counts of unique persons within the zone polygon via `FenceAnalytic.zone_person_counts()`:
     - `CROWD_DENSITY_MEDIUM`: $\ge 4$ persons inside zone for $\ge 2$ consecutive frames.
     - `CROWD_DENSITY_HIGH`: $\ge 8$ persons inside zone for $\ge 2$ consecutive frames.
     - Coordinate-area density ($\text{persons} / \text{unit}^2$) is permitted strictly as informational metadata in the event payload.

### V4. Additive Event Engine Severity Mapping (`backend/events/engine.py`)
* **Context:** The planner's documentation erroneously referenced `backend/analytics/engine.py`. The actual codebase path is `backend/events/engine.py`. Unmapped event types currently default to `INFO`.
* **Binding Requirements:**
  1. **Path Correction:** All event engine updates must be made in `backend/events/engine.py` (lines 203–239).
  2. **Additive Map:** Implement `_NEW_TYPE_BASE` in `EventEngine._severity_for()`:
     ```python
     _NEW_TYPE_BASE: dict[str, str] = {
         "SUSPECTED_RUNNING": "MEDIUM",
         "SUSPECTED_ABNORMAL_MOVEMENT": "MEDIUM",
         "LOITERING": "LOW",
         "NIGHT_MOVEMENT": "MEDIUM",
         "CROWD_DENSITY_HIGH": "HIGH",
         "CROWD_DENSITY_MEDIUM": "MEDIUM",
         "ANPR_READ": "INFO",
         "ANPR_PLATE_DETECTED": "INFO",
         "OCR_UNCERTAIN": "LOW",
     }
     ```
  3. **Severity Escalation Rules:**
     - Base severity is retrieved from `_NEW_TYPE_BASE.get(d.type, "INFO")`.
     - If `metadata.get("zone_type") == "RESTRICTED"`: elevate severity by +1 level (`LOW` → `MEDIUM`, `MEDIUM` → `HIGH`).
     - If `metadata.get("is_night") is True`: elevate severity by +1 level (capped at `HIGH`).

### V5. Database Migration 3 & Safe Degrade Contract
* **Context:** Database schema updates must not break backward compatibility or cause runtime SQLite exceptions on unmigrated databases.
* **Binding Requirements:**
  1. **Schema DDL:**
     ```sql
     -- Migration 3 (God-Managed)
     ALTER TABLE tracks ADD COLUMN trajectory TEXT DEFAULT NULL;
     ```
  2. **DAO Method Contract:**
     ```python
     def upsert_track_trajectories(self, session_id: str,
                                   trajectories: list[tuple[int, str]]) -> None:
         """Persist serialized trajectory JSON for track IDs in session."""
     ```
  3. **Pre-Hunk Degrade:** Before Migration 3 is applied, `TrackManager` and `DAO` must inspect `PRAGMA table_info(tracks)` or check `hasattr(self._dao, "upsert_track_trajectories")`. If the column/method is absent, trajectory persistence is silently skipped without throwing exceptions.

### V6. Three-State ANPR Honesty, Network Gate & Regex Validation
* **Context:** LPD/OCR dependencies and cloud network access are unavailable in offline environments. Simulated plate data is strictly forbidden.
* **Binding Requirements:**
  1. **Three-State State Machine:**
     - `ANPR_READ`: Plate localized, OCR extracted text with confidence $\ge 0.60$, and text matches validated Indian plate regex. Severity: `INFO`.
     - `OCR_UNCERTAIN`: Plate localized, but OCR confidence $< 0.60$ or regex match failed. Severity: `LOW`.
     - `ANPR_PLATE_DETECTED`: Plate localized via aspect-ratio/color heuristic, but OCR engine is unavailable/offline. Severity: `INFO`.
  2. **Indian License Plate Regex Formats:**
     - Standard Indian Plate: `^[A-Z]{2}[0-9]{1,2}[A-Z]{0,3}[0-9]{4}$`
     - Bharat (BH) Series (Fixed Regex): `^[0-9]{2}BH[0-9]{4}[A-Z]{1,2}$` *(Corrected from planner's 4-digit prefix)*.
  3. **Honesty Ban:** Hardcoded, random, or mock license plate strings (e.g., `"MH12AB1234"`, `"DL01AB1234"`) are strictly banned. If text cannot be read, the system must emit `ANPR_PLATE_DETECTED` with `plate_text: None`.

### V7. RTSP Ingestion Pipeline & OpenCV Environment Binding
* **Context:** OpenCV VideoCapture over RTSP defaults to UDP, leading to packet drops, frame tearing, and lockups.
* **Binding Requirements:**
  1. **Environment Flag:** In `backend/video/rtsp.py`, `os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp"` must be set before any call to `cv2.VideoCapture()`.
  2. **Class Properties:** `RtspSource.type_name = "rtsp"` and `RtspSource.is_live = True`.
  3. **Source Resolution in Session:** Verified in `backend/services/session.py:194`:
     ```python
     src_type = getattr(self._source, "type_name", "file")
     self._dao.upsert_source(self.source_id, src_type)
     ```
  4. **Authentication Labeling:** Basic/digest RTSP credentials in URLs must be parsed securely, with unsupported auth mechanisms honestly marked `"UNTESTED-auth"`.
  5. **Venv Re-measurement Gate:** Performance benchmarks for RTSP (FPS and TTFF) must be executed using the project virtual environment Python binary (`.venv/bin/python`, OpenCV 5.0.0).

### V8. Router Organization & Working-Tree State Preservation
* **Context:** Uncommitted working-tree changes already include Phase 1 frontend components and inline Re-ID endpoints.
* **Binding Requirements:**
  1. **Inline Endpoints:** Keep Re-ID endpoints (`/api/reid/persons`, `/api/reid/search`, `/api/reid/stats`) inline in `backend/main.py` lines 217–250. Do not create `backend/api/reid.py` unless router length exceeds 40 lines.
  2. **Layer Endpoints:** Keep layer endpoints (`GET /api/session/layers`, `POST /api/session/layers`) inline in `backend/main.py` lines 191–209.
  3. **Frontend Preservation:** Preserve existing working-tree additions (`frontend/src/components/LayerToggles.tsx`, `EventSummary.tsx`, `EventLog.tsx`, `App.tsx`). Do not regress or re-plan already working UI components.

---

## 3. Pinned Class Signatures & Data Contracts

The Executor must implement the exact interfaces and signatures below.

### 3.1 Re-ID Embedder & Service (`backend/reid/`)
```python
# backend/reid/embedder.py
class OpenCVDnnEmbedder:
    def __init__(self, model_path: str = "models/fast-reid_mobilenetv2.onnx") -> None: ...
    def extract(self, crops: list[np.ndarray]) -> np.ndarray:
        """Extract L2-normalized 512-d feature vectors for N image crops.
        
        Args:
            crops: List of BGR image crops (H x W x 3).
        Returns:
            np.ndarray of shape (N, 512), dtype float32, L2-normalized.
        """
        ...

# backend/reid/gallery.py
class PersonGallery:
    def __init__(self, similarity_threshold: float = 0.70, max_exemplars: int = 10) -> None: ...
    def match_or_create(self, track_id: int, embedding: np.ndarray, crop: np.ndarray,
                        camera_id: str, ts: float) -> tuple[str, float, bool]:
        """Match embedding against gallery or create new global person ID.
        
        Returns:
            (person_id, max_similarity, is_new_identity)
        """
        ...
    def batch_match(self, tracks: list[tuple[int, np.ndarray, np.ndarray]],
                    camera_id: str, ts: float) -> list[tuple[int, str, float, bool]]:
        """Batch match multiple track crops against gallery."""
        ...
```

### 3.2 Face Detector (`backend/analytics/face_detector.py`)
```python
class YuNetFaceDetector:
    def __init__(self, model_path: str = "models/yunet.onnx",
                 conf_threshold: float = 0.60, nms_threshold: float = 0.30) -> None: ...
    def detect(self, frame: np.ndarray) -> list[dict]:
        """Detect faces in frame with dynamic input size synchronization.
        
        Returns:
            List of dicts: {
                "bbox": [x, y, w, h],
                "confidence": float,
                "landmarks": list of 5 (x, y) tuples
            }
        """
        ...
```

### 3.3 Kinematic & Crowd Analytics (`backend/analytics/`)
```python
# backend/analytics/kinematics.py
class KinematicTrajectoryAnalytic:
    def __init__(self, fps: float = 25.0, velocity_thresh: float = 150.0,
                 loiter_dwell_sec: float = 15.0) -> None: ...
    def update(self, tracks: list[Any], frame: np.ndarray,
               video_ts: float) -> list[EventDraft]:
        """Evaluate running, loitering, and abnormal directional movement."""
        ...

# backend/analytics/crowd.py
class CrowdDensityAnalytic:
    def __init__(self, medium_thresh: int = 4, high_thresh: int = 8,
                 sustain_frames: int = 2) -> None: ...
    def update(self, zone_counts: dict[str, int], video_ts: float) -> list[EventDraft]:
        """Evaluate count-based crowd density per zone."""
        ...
```

### 3.4 RTSP Video Source (`backend/video/rtsp.py`)
```python
class RtspSource:
    type_name: str = "rtsp"
    is_live: bool = True
    
    def __init__(self, url: str, reconnect_delay_sec: float = 2.0) -> None: ...
    def open(self) -> bool: ...
    def read(self) -> tuple[bool, Optional[np.ndarray]]: ...
    def release(self) -> None: ...
    def get_info(self) -> dict: ...
```

---

## 4. Tree-Truth Verification Matrix

| Claimed File & Line | Claimed Purpose | Verified Tree Status (`HEAD 3d0c7e2` + working tree) | Action Required by Executor |
| :--- | :--- | :--- | :--- |
| `backend/main.py:50-56` | Router mount region | **VERIFIED.** Lines 50–56 mount `api_router`. | Keep mounts clean; add Re-ID routes inline in session region. |
| `backend/main.py:73-93` | `_model_status()` reporting | **VERIFIED.** Reports YOLO, Re-ID, Face models. | Update with Phase 3/6 status keys. |
| `backend/main.py:191-209` | Inline layer toggle endpoints | **VERIFIED.** `GET/POST /api/session/layers` landed. | No changes needed. |
| `backend/main.py:217-250` | Inline Re-ID endpoints | **VERIFIED.** `/api/reid/persons`, `/api/reid/search` present. | Polish response serialization. |
| `backend/services/session.py:194` | Source type resolution | **VERIFIED.** `getattr(self._source, "type_name", "file")` landed. | Retain as authoritative. |
| `backend/services/session.py:204-208` | Re-ID camera registration | **VERIFIED.** `register_camera` block with BLE001 exception catch landed. | Retain as authoritative. |
| `backend/events/engine.py:203-239` | Severity ladder `_severity_for` | **VERIFIED.** Line 204 defines `_severity_for`. *(Planner path corrected)*. | Add `_NEW_TYPE_BASE` dictionary (**V4**). |
| `backend/storage/dao.py` | Schema & DAO methods | **VERIFIED.** Awaiting Migration 3 god-hunk. | Apply column-pragma fallback pre-hunk (**V5**). |
| `frontend/src/components/LayerToggles.tsx` | Visual layer switch panel | **VERIFIED.** Component created in working tree. | Wire to `App.tsx` state and API. |

---

## 5. Execution Risk & Gate Acceptance Criteria

The Verifier (`oscar-mtt8m47c` + `god`) must test against the following mandatory acceptance gates:

| Gate ID | Subsystem | Mandatory Verification Requirement | Failure Action |
| :--- | :--- | :--- | :--- |
| **G-BATCH** | Re-ID Embedder | Single-crop latency $< 10\text{ms}$ on CPU; dynamic batch invariance $\ge 0.99999$ vs padded batch-32. | BLOCK Phase 2 |
| **G-YUNET** | Face Detection | `yunet.onnx` located in `models/`; dynamic resize works across 320x320 and 1080p without OpenCV assertions; detection-only. | BLOCK Phase 3 |
| **G-CLEAN** | Kinematics | Zero imports from AGPL crowd repo; running/loitering detected on benchmark tracks without false-positive cascades. | BLOCK Phase 4 |
| **G-DENSITY**| Crowd Analytics | Crowd alerts fire on count thresholds (4/8 persons), not small-zone pixel area. | BLOCK Phase 4 |
| **G-MIGRATE**| Persistence | DB gracefully handles absence of `trajectory` column pre-hunk; persists serialized points post-hunk. | BLOCK Phase 5 |
| **G-ANPR** | License Plates | Zero fabricated plate numbers; regex rejects invalid formats; three-state status accurately reflected in UI. | BLOCK Phase 6 |
| **G-RTSP** | RTSP Ingestion | `OPENCV_FFMPEG_CAPTURE_OPTIONS` set to TCP; reconnect ladder handles dropped stream without server crash. | BLOCK Phase 7 |

---

## 6. Architect Handoff Sign-Off

The architecture gate for TRINETRA V3.5 is formally **CLOSED: APPROVED-WITH-CORRECTIONS**.

Stage 4 Execution (`executer-mtum4rce`) is cleared to begin immediately upon dispatch from Orchestrator (`god`).

*Signed,*  
**Architect and Pipeline Agent (`architect-and-pipeline-mtum77rw`)**  
*TRINETRA V3.5 Core Engineering Fleet*
