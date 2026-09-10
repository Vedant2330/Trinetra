# RESEARCH V3.5 — Model/Stack Verification + Gap Research (Stage 1)

**Author:** RESEARCHER (researcher-and-ideator-mtumwxna) · **Date:** 2026-09-10
**Task:** Verify TRINETRA_RESOURCE_INVENTORY.md / TRINETRA_FULL_IMPLEMENTATION_PLAN.md / TRINETRA_FULL_ARCHITECTURE_HANDOFF.md claims against the actual machine; gap-research Phases 3/4/6/7. READ-ONLY — no production code touched, no suite runs, no :8000.
**Environment caveat:** web_search tool was DOWN during this pass (Nous gateway unreachable) — all upstream (GitHub/opencv_zoo/PaddleOCR) claims are labeled OFFLINE-UNVERIFIED. Everything marked MEASURED was run on this machine (Trinetra venv) today.

---

## 1. VERIFICATION RESULTS — plan/handoff claims vs machine

| # | Claim (source) | Verdict | Evidence |
|---|---|---|---|
| 1 | fast-reid ONNX md5 `77a97e84aac88bdb3eeaa17dd6c57180` (plan §Phase2) | **CONFIRMED** | `md5 Trinetra/models/fast-reid_mobilenetv2.onnx` = `77a97e84aac88bdb3eeaa17dd6c57180`; identical to `DeepCamera-master/src/yolov7_reid/src/models/` copy. 8,862,213 bytes (~8.5MB). |
| 2 | loads via cv2.dnn, `[32,3,128,256]→[32,1280]` (inventory §1) | **CONFIRMED + NEW FACT** | `cv2.dnn.readNetFromONNX` OK in venv cv2 5.0.0; forward → `(32,1280) float32`. **NEW: cv2.dnn also accepts dynamic batches — batch-1 → `(1,1280)` and batch-8 → `(8,1280)` work directly, and batch-1 output is byte-identical to batch-32 row 0 (max diff 0.0).** The "batch-1 = INVALID_ARGUMENT" claim came from the onnxruntime audit and does NOT apply to cv2.dnn. |
| 3 | reid latency: batch-32 96.9ms, single padded 90.2ms (inventory §1) | **RE-MEASURED, FASTER** | batch-32 median **69.7ms** (warm, 10 runs); single-crop padded-32 **69.8ms**; **true batch-1 5.5ms** (12.7× faster than the padded path). Planner numbers were honest but the pad-to-32 contract is unnecessary under cv2.dnn — see finding F1. |
| 4 | YuNet at temp path, 232,589 bytes (plan §Phase3) | **CONFIRMED** | `/var/folders/gj/.../T/opencode/trinetra_audit/yunet.onnx` exists, 232,589 bytes, mtime Sep 9 00:34. `cv2.FaceDetectorYN` exists in venv cv2 5.0.0. |
| 5 | YuNet works, 2.8ms CPU (inventory §1) | **CONFIRMED + EXTENDED** | MEASURED on intrusion.mp4 first frame (1080p): 320×320 → **2.2ms**, 640×640 → **6.2ms**, full 1920×1080 → **29.5ms**. Found **5 faces**, conf 0.61–0.88, output rows = 15 values (x,y,w,h + 5×2 landmarks + conf). Detection-only (no embeddings). API note: `setInputSize()` must match frame dims exactly, else cv2 error — either set per-frame or resize frame. |
| 6 | yolov8n.pt present; ByteTrack sole tracker (work order) | **CONFIRMED** | `Trinetra/models/yolov8n.pt` 6,549,796 bytes; `config/default.toml:69` "ByteTrack stays the ONLY tracker"; `backend/vision/tracker.py` is the sole tracker module. |
| 7 | M8 reid port landed 03:05–03:10 untracked (work order) | **CONFIRMED** | `backend/reid/` untracked, mtimes 03:05–03:10 Sep 10; `tests/test_reid.py` (23 tests) + `tests/test_reid_port.py` (11 tests) also untracked. Session/main/config/errors wiring present (session.py:98,114,204-208,399-406,458-460,577-587; main.py:75-111 health+gate). |
| 8 | "backend/reid = 11 modules" (plan §Phase2) | **OFF BY ONE** | Both m8 and main tree have **10 .py files** (__init__, correlation, embedder, gallery, history, identity, integration, matcher, sampling, summary). Diff m8↔main: only `__init__.py`, `embedder.py` (OpenCVDnnEmbedder added), `integration.py` differ — 7 of 10 byte-identical. |
| 9 | crowd repo is AGPL → reference-only (plan §Phase4) | **CONFIRMED** | `crowd-abnormal-behavior-detection-main/LICENSE` = GNU AGPL v3, © 2026 juzishazhou; README badge AGPL-3.0. Reimplementation-only rule is correct. |
| 10 | RTSP MediaMTX loopback 19.7fps / 1.6s TTFF (audit §21) | **DOC-CONFIRMED, NOT SCRIPT-CONFIRMED** | Claimed in TRINETRA_FINAL_CAPABILITY_INTEGRATION_AUDIT.md (§34, §67, §309, §320, §508, §561, §580) and ARCHITECTURE.md:20 — but **no script or log exists** (scripts/ = bench, m7_e2e, m7_smoke, phase0_upload_chain only). Caveat: audit used **system OpenCV 4.13**, venv has cv2 5.0.0 (FFMPEG: YES in build info — transport should hold, number not re-measured on venv build). |
| 11 | venv claims: cv2 5.0.0, ultralytics, fastapi, numpy, torch (work order) | **CONFIRMED** | venv python 3.11.9; opencv-python 5.0.0.93 (cv2 5.0.0, **FFMPEG YES**); ultralytics 8.4.144; fastapi 0.141.1; numpy 2.4.6; torch 2.14.0 (**MPS available ✓**); also pytest 9.1.1, uvicorn 0.52.4, torchvision 0.29.0, psutil 7.2.1, lap 0.5.13. |
| 12 | "NO paddle/onnxruntime/ncnn in venv" (implied by plan) | **CONFIRMED** | pip list grep = zero hits for paddle*, onnx*, ncnn*, playwright, easyocr, shapely. pip cache contains no paddle wheels. |
| 13 | suite 218 collected / 214P / 4S / 2W (handoff §2.2) | **NOT RE-RUN (discipline)** | Static count: **244 `def test_` functions** across tests/ (incl. test_layers 11, test_reid 23, test_reid_port 11). Handoff's 218-collected was measured at their run; the tree may have grown since. VERIFIER/EXECUTOR must re-baseline. |
| 14 | Playwright 1.63.0 outside venv (handoff §2.10) | **PLAUSIBLE, NOT RE-VERIFIED** | Not in venv pip list (consistent). CLI presence not re-checked this pass. |
| 15 | reid.ts 109MB proxy in m8, not shipped (R2/R8) | **CONFIRMED** | `Trinetra-m8/models/reid.ts` = 109,373,538 bytes; absent from Trinetra/models/ (correct). |

**Typos found in unverified-landed code (report-only):** `backend/reid/embedder.py` docstring says "HONST unavailable gate" (should be HONEST).

---

## 2. KEY FINDINGS (new information the plan/handoff lacks)

**F1 — OpenCVDnnEmbedder pads to 32 unnecessarily (12.7× latency penalty per single embed).**
The landed `_forward_batch` zero-pads every batch to 32 rows because the onnxruntime audit said batch-1 was invalid. Under cv2.dnn the graph runs any batch n≤32 directly and outputs are byte-identical (verified max diff 0.0). MEASURED: single crop padded = 69.8ms vs direct batch-1 = **5.5ms**; batch-32 = 69.7ms (≈2.2ms/crop). Recommendation for PLANNER: allow dynamic-batch path with pad-32 fallback (or keep pad-32 only for full batches). Not a correctness bug — pure performance. Sampling cadence (≤1 embed/25 ticks) means worst-case impact is one 70ms hitch per tick on the session thread.

**F2 — YuNet requires setInputSize == frame size.**
`cv2.FaceDetectorYN.create(path, "", (320,320))` then feeding a 1920×1080 frame raises a cv2 error. Correct usage: create at frame size, or call `setInputSize(frame.shape[:2])` per frame, or resize frame to 320×320 (2.2ms path) and scale boxes back. Phase-3 implementer must pick one; the 320 route is the fast one, the native-size route (29.5ms @1080p) is the accurate one. 640×640 (6.2ms) is a good middle.

**F3 — RTSP 19.7fps claim measured on system OpenCV 4.13, not venv cv2 5.0.0.**
Venv cv2 5.0.0 build info says FFMPEG: YES, so the transport approach (cv2.VideoCapture + CAP_FFMPEG + rtsp_transport=tcp) is sound; but the specific number was never measured on the shipping venv. Phase 7's `scripts/rtsp_test.py` should re-measure on the venv build. mediamtx ✓ present at homebrew/bin/mediamtx; ffmpeg 8.1.2 ✓ present.

**F4 — Nothing ANPR-capable exists offline.**
No paddle wheels in pip cache, no plate/LPD/anpr files anywhere in SIH26 (find-verified), no OCR deps in venv. Phase 6 requires either (a) network access to train/fetch yolov8n plate model + PP-OCRv4 ONNX files, or (b) honest detection-only fallback. Plan's gating logic already covers this correctly.

**F5 — ONNX graph internals (from raw protobuf parse, no onnx package needed):**
Producer `pytorch` v`1.7`; input tensor name `batched_inputs.1` fixed [32,3,128,256]; output 1280-d. 1280-d output = MobileNetV2 penultimate (pre-classifier) features — consistent with fast-reid MobileNetV2 backbone + embedding head.

---

## 3. GAP RESEARCH — per-item report format (Phase 3/4/6/7)

### 3.1 fast-reid_mobilenetv2.onnx (Re-ID embedder, Phase 2 — landed)

- **NAME:** fast-reid MobileNetV2 re-ID embedding (ONNX export)
- **PURPOSE:** 1280-d appearance embedding per person crop; L2-normalize → cosine similarity for cross-camera/single-video re-identification
- **VERSION-STATE:** LANDED untracked at `Trinetra/models/` (copy of DeepCamera file, md5-verified identical). Loads + infers in venv via cv2.dnn (MEASURED today). Discrimination margin 0.638 (same-track 0.84 / diff 0.20) — audit-measured on ORT, NOT re-measured by me on cv2.dnn path (embeddings are the same graph, so expected identical; labeled audit-sourced).
- **LICENSE:** fast-reid upstream = Apache-2.0 (JDAI-CV). DeepCamera umbrella repo = MIT (LICENSE verified). The specific mobilenetv2 export's exact upstream commit is OFFLINE-UNVERIFIED — DeepCamera READMEs cite linghu8812/yolov5_fastreid_deepsort_tensorrt + JDAI-CV/fast-reid; the R50-ibn sibling model in the same dir is documented as Market-1501-trained (market_mgn_R50-ibn.pth fetch link in yolov7_reid README). **Training dataset for THIS mobilenetv2 variant: UNVERIFIED — likely Market-1501 family, do not claim which in UI.**
- **HARDWARE NEEDS:** CPU-only, ~9MB RAM for weights + batch-32 activation workspace
- **MAC-M4 SUPPORT:** ✓ verified (all measurements above on this M4)
- **OFFLINE CAPABILITY:** ✓ fully offline once the file is committed (it is in the tree)
- **INTEGRATION COMPLEXITY:** LOW — already wired (OpenCVDnnEmbedder, session hooks, health gate, 34 reid tests landed). F1 tweak optional.
- **SHOULD-USE VERDICT:** **YES — as planned.** Only real embedder in workspace; margin 0.638 clean; zero new deps. Add honest label "trained-dataset undisclosed (Market-1501 family likely)" if provenance wording matters for the demo.

### 3.2 yunet.onnx (face detection, Phase 3 — not yet landed)

- **NAME:** YuNet 2023 face detection (opencv_zoo)
- **PURPOSE:** face bbox + 5-point landmarks + conf; detection ONLY (no recognition — recognition model is SFace, separate, and banned by master prompt)
- **VERSION-STATE:** present at temp path (232,589 bytes), MEASURED working today: 5 faces on intrusion.mp4 1080p frame @ conf 0.61–0.88; 2.2ms @ 320², 6.2ms @ 640², 29.5ms @ native 1920×1080. **Must be copied to `Trinetra/models/yunet.onnx` — temp dirs get swept by macOS; do this FIRST in Phase 3.**
- **LICENSE:** opencv_zoo = Apache-2.0 (standard; exact commit/license file OFFLINE-UNVERIFIED — web down)
- **HARDWARE NEEDS:** CPU only
- **MAC-M4 SUPPORT:** ✓ measured
- **OFFLINE CAPABILITY:** ✓ once copied into models/
- **INTEGRATION COMPLEXITY:** LOW — cv2.FaceDetectorYN native API; mind F2 (setInputSize contract)
- **SHOULD-USE VERDICT:** **YES — as planned.** Only face detector that runs in-venv with zero deps. 320×320 variant behavior confirmed (this file accepts dynamic input size — 320/640/native all worked).

### 3.3 Crowd/behavior reimplementations (Phase 4 — not yet landed)

- **AGPL status:** CONFIRMED — crowd-abnormal-behavior-detection-main LICENSE = AGPL-3.0 (© 2026 juzishazhou). Reference-only, no code copy — plan's rule is correct and binding.
- **Trajectory-only heuristics need NO external model:** CONFIRMED by construction — running/abnormal/loitering/night/crowd-density all read TrackState.positions (deque of (x,y,tick) maxlen 60, foot points — verified at tracks.py:51-67) + FenceAnalytic counts + ctx.is_night. Zero model loads, zero new deps. Pose/fall remains the only optional model-gated analytic (yolov8n-pose.pt sits in BorderSurvaillance/, not in Trinetra/models/ — copy only if fall ships).
- **SHOULD-USE VERDICT:** **YES — as planned (reimplement from math, own constants).** Constants in plan §4.2-4.5 (80px/s, 150px, W=10, 0.50 trigger, 20s loiter, 80px radius, luma<40 night) all reasonable vs the repo's published values; calibrate on running.mp4 as planned.

### 3.4 ANPR (Phase 6 — nothing exists)

- **Plate detection:** plan's recommendation (fine-tune yolov8n single-class `plate` → `yolov8n_plate.pt`) is the only zero-new-dep route. OFFLINE: no Indian-plate dataset or trained model exists locally (find-verified). Requires network + training time (M4 30-min class or Colab). GATED as planned.
- **OCR — PaddleOCR CPU:** pip has NO cached paddle wheels; install requires network. PP-OCRv4 mobile ONNX via cv2.dnn (architect's PRIMARY) also requires downloading model files (none local). **OFFLINE-UNVERIFIED: current PaddleOCR Apache-2.0 runtime status + macOS ARM wheel availability — could not check, web down.**
- **SHOULD-USE VERDICT:** **YES with gates as written.** If network stays down: ship `ANPR_PLATE_DETECTED`-only via the sanctioned vehicle-bbox heuristic fallback; never fabricate reads. Regex fix from handoff §2.8 (BH-series `^\d{2}BH\d{4}[A-Z]{1,2}$`) is correct per Indian BH-series format.

### 3.5 RTSP ingestion (Phase 7)

- **NAME:** cv2.VideoCapture + CAP_FFMPEG + `OPENCV_FFMPEG_CAPTURE_OPTIONS=rtsp_transport;tcp`
- **VERSION-STATE:** venv cv2 5.0.0 build = **FFMPEG: YES** (verified). Transport claim (19.7fps/1.6s TTFF MediaMTX loopback) is DOC-CONFIRMED only — measured on system OpenCV 4.13 during audit; no script/log artifact survives; not re-measured on venv build (F3). mediamtx ✓ + ffmpeg 8.1.2 ✓ installed.
- **LICENSE:** n/a (OpenCV Apache-2.0; mediamtx/ffmpeg local binaries already installed)
- **HARDWARE NEEDS:** CPU; loopback rig needs no camera
- **MAC-M4 SUPPORT:** ✓ (audit machine = this machine)
- **OFFLINE CAPABILITY:** ✓ fully — rig is local
- **INTEGRATION COMPLEXITY:** LOW-MEDIUM — plan §7.1/§2.9 design (source protocol + type_name + backoff ladder) is sound; session backoff ladder verified present.
- **SHOULD-USE VERDICT:** **YES — as planned**, with Phase 7 rig re-measuring fps/TTFF on the venv cv2 5.0.0 build and logging honestly.

---

## 4. STACK SANITY — verified venv inventory (Trinetra/venv, python 3.11.9)

| Package | Version | Plan assumes | Status |
|---|---|---|---|
| opencv-python | 5.0.0.93 (cv2 5.0.0) | cv2 5.0.0 | ✓ (FFMPEG YES, FaceDetectorYN YES, dnn ONNX OK) |
| ultralytics | 8.4.144 | present | ✓ |
| fastapi | 0.141.1 | present | ✓ |
| numpy | 2.4.6 | present | ✓ |
| torch | 2.14.0 (MPS ✓) | present | ✓ |
| torchvision | 0.29.0 | (implicit) | ✓ |
| pytest | 9.1.1 | present | ✓ |
| uvicorn | 0.52.4 | present | ✓ |
| psutil | 7.2.1 | present | ✓ |
| lap | 0.5.13 | (ByteTrack dep) | ✓ |
| paddle / onnxruntime / ncnn / easyocr / shapely | ABSENT | plan assumes absent (gates) | ✓ consistent — all gated capabilities degrade honestly |

Frontend: react 18.3.1, vite 6, typescript 5.6.2 (package.json verified). No playwright in venv (correct — use CLI/npx outside venv per plan).

**Nothing the plan assumes is missing from the venv.** The only environment gap is network (web down this pass).

---

## 5. HONEST UNKNOWNS

1. **fast-reid training dataset** — likely Market-1501 family (sibling model documented as such) but the mobilenetv2 file's exact provenance is untraceable offline. Do not claim a dataset in UI/docs.
2. **YuNet exact upstream version/license file** — Apache-2.0 is the opencv_zoo standard; could not fetch the repo to pin the commit.
3. **PaddleOCR current license/wheel state** — OFFLINE-UNVERIFIED; re-check when network returns before any MICHAEL gate decision.
4. **Suite pass state** — not run (discipline); static 244 test defs exist; handoff measured 214P/4S/2W earlier. VERIFIER re-baselines.
5. **RTSP numbers on venv cv2 build** — 19.7fps/1.6s were measured on system OpenCV 4.13; re-measure in Phase 7 rig.
6. **Discrimination margin on the cv2.dnn path** — 0.638 was measured via ORT in the audit; same graph via cv2.dnn is expected identical (outputs verified byte-stable across batch shapes) but the same-track/different-track footage test itself was not re-run.

---

## 6. VERDICT SUMMARY for PLANNER (stage 2)

- **Plan/handoff model claims: VERIFIED (15/15 core claims confirmed; 3 corrections — latency numbers re-measured faster, "11 modules" is 10, batch-1 works in cv2.dnn).**
- **Phase 2 (reid): landed state is sound; consider F1 dynamic-batch optimization (5.5ms vs 69.8ms single-crop).**
- **Phase 3 (YuNet): GO — copy model out of temp FIRST (macOS sweeps /var/folders), mind setInputSize contract (F2).**
- **Phase 4 (behavior): GO — AGPL confirmed, pure-trajectory heuristics need no model; constants ready.**
- **Phase 6 (ANPR): GATED on network — nothing offline; honest fallback path already specced.**
- **Phase 7 (RTSP): GO — design sound; re-measure on venv build in the rig; evidence for 19.7fps exists only in audit docs, no script.**
- **Stack: clean — every assumption holds; only network is missing.**
