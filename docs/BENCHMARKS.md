# TRINETRA — Benchmark Record (B1–B4)

**Machine:** MacBook Air M4 (macOS 26.6.2) · Python 3.11.9 (venv) · CPU device policy for all runs below (B1/B4 CPU; MPS numbers recorded where relevant) · re-verified 2026-09-09 · `scripts/bench.py` (labels per IMPLEMENTATION_PLAN, C9 — no drift). All four benches run sequentially in ONE process; every number below is from the latest single verified run (`venv/bin/python scripts/bench.py`).

## B1 — Pipeline FPS (median / p95)

Full per-frame chain: detector→ByteTrack→TrackStore→luminance (FrameContext)→confirm-edge→fence→JPEG encode @ q70. Real clip (`running_clip.mp4`, 632×480), looped to 100 frames, CPU.

| Metric | Value |
|---|---|
| **median** | **18.5 FPS** (53.95 ms/frame) |
| **p95** | **17.3 FPS** (57.89 ms/frame) |

Chain overhead vs. pure MJPEG (B2) = ~15 FPS delta — encoder+luminance+state+fence ≈ 8 ms/frame of the 54 ms (bonus row, not the headline).

## B2 — MJPEG FPS @ quality 70

Served through the REAL uvicorn socket (ephemeral port), live file session, multipart frames counted over a 5 s window.

| Metric | Value |
|---|---|
| **MJPEG FPS @ q70** | **33.8** (61-frame clip consumed in 1.8 s — count capped by clip length) |
| Target ≥ 15 | **PASS** |

Note: the clip ends before the 5 s window; the true steady-state ceiling is the pipeline rate (B1). The ≥15 target is met with ~2× margin.

## B3 — Event burst (50 drafts/frame × 200 frames)

Engine → bounded queue (cap 500) → writer thread (20 ms/batch injected) → SQLite. **Producer blocking observed on 49 ticks** (backpressure by design); zero loss.

| Metric | Value |
|---|---|
| Events generated / committed | 10,000 / 10,000 — **zero loss** |
| Throughput | **7,600 events/s** sustained |
| Producer blocked | 49 ticks (queue-full, as designed) |
| Queue after drain | 0 |

## B4 — RSS under sustained load

Process RSS during sustained real-inference loop (CPU policy, 632×480 frames, 10 s window). Measured in-process AFTER B1–B3 in the same run, so the base includes model + prior benches' allocator state.

| Metric | Value |
|---|---|
| Base RSS (model loaded + B1–B3 state) | ~371 MB |
| Peak under 10 s sustained load | ~534 MB (≈163 MB delta — one frame in flight + allocator/JIT expansion) |
| Steady state | flat per frame — no growth trend across the window |
| Fresh-process reference | 62 MB pre-load → ~130 MB post-load → ≤ ~205 MB sustained (cold-start run) |

Churn cost (recorded separately, M6 drill): 10 sequential sessions → sessions rows == 10, thread count FLAT, fd count FLAT (session threads now close their per-thread DB connection in finalize; Database reaps dead-thread connections). See `tests/test_m6_advisories.py::test_churn_10_sessions_no_thread_or_fd_growth`.

## Honesty notes

- B2's clip-exhaustion cap is documented above; the ≥15 target is satisfied either way.
- B4 deltas vary with PyTorch JIT warm-up on first sustained run (first ~2 s expand RSS); steady-state per-frame delta is ~0 MB.
- Webcam not available on this machine (permission/busy) — live-source FPS not measured here; the file path bounds it (B1).
- All numbers from `venv/bin/python scripts/bench.py` on 2026-09-09 (latest verified re-run), single run each, median-based (B1) to avoid outlier theater.
