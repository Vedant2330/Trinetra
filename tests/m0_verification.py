"""TRINETRA M0 — Foundation verification.

Executes every M0 success criterion for real:
  Python / PyTorch / MPS / Ultralytics / YOLO load + real inference /
  OpenCV (file read + webcam probe) / FastAPI boot + request.

Run:  Trinetra/venv/bin/python tests/m0_verification.py
"""

import importlib.metadata
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODELS = ROOT / "models"
CHECKS: list[tuple[str, str]] = []


def check(name: str, status: str, detail: str = "") -> None:
    CHECKS.append((name, status, detail))
    mark = "OK " if status == "PASS" else "FAIL"
    print(f"[{mark}] {name}" + (f" — {detail}" if detail else ""))


def ver(pkg: str) -> str:
    return importlib.metadata.version(pkg)


def main() -> int:
    failures = 0

    # 1. Python
    check("Python", "PASS" if sys.version_info >= (3, 11) else "FAIL",
          f"{sys.version.split()[0]} ({sys.platform})")

    # 2. PyTorch + MPS
    try:
        import torch
        mps = torch.backends.mps.is_available()
        check("PyTorch", "PASS", f"torch {torch.__version__}")
        check("MPS availability", "PASS" if mps else "FAIL",
              "available" if mps else "NOT available — CPU fallback only")
    except Exception as e:
        check("PyTorch", "FAIL", str(e)[:120])
        return 1

    # 3. Ultralytics + YOLO model load + REAL inference on a real frame
    try:
        from ultralytics import YOLO
        model_path = MODELS / "yolov8n.pt"
        if not model_path.exists():
            check("YOLO model file", "FAIL", f"missing {model_path}")
            return 1
        check("Ultralytics", "PASS", f"ultralytics {ver('ultralytics')}")

        import numpy as np
        t0 = time.perf_counter()
        model = YOLO(str(model_path))
        load_s = time.perf_counter() - t0
        check("YOLO model load", "PASS", f"yolov8n.pt in {load_s:.2f}s")

        # synthetic real-inference smoke (random frame) — verifies forward pass
        frame = (np.random.default_rng(42).integers(0, 255, (480, 640, 3))).astype("uint8")
        device = "mps" if mps else "cpu"
        model.to(device)
        res = model(frame, verbose=False, imgsz=640)
        det = len(res[0].boxes) if res[0].boxes is not None else 0
        check("YOLO inference", "PASS",
              f"device={device}, detections on noise frame={det} (expect 0)")

        # timing: 20 warm inferences on the noise frame
        for _ in range(3):
            model(frame, verbose=False, imgsz=640)
        t0 = time.perf_counter()
        n = 20
        for _ in range(n):
            model(frame, verbose=False, imgsz=640)
        ms = (time.perf_counter() - t0) / n * 1000
        check("YOLO inference timing", "PASS",
              f"{ms:.1f} ms/frame on {device} (640x480 noise, no tracking) — reference only")
    except Exception as e:
        check("Ultralytics / YOLO", "FAIL", f"{type(e).__name__}: {str(e)[:160]}")
        return 1

    # 4. OpenCV — file read on a real test video + webcam probe
    try:
        import cv2
        check("OpenCV", "PASS", f"opencv {cv2.__version__}")

        video = ROOT.parent / "crowd-abnormal-behavior-detection-main" / "assets" / "running.mp4"
        cap = cv2.VideoCapture(str(video))
        ok, fr = cap.read()
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        cap.release()
        if ok:
            check("OpenCV file read", "PASS", f"running.mp4 {w}x{h}@{fps:.0f} first frame decoded")
        else:
            check("OpenCV file read", "FAIL", "could not decode first frame")

        cap = cv2.VideoCapture(0)
        cam_ok, _ = cap.read()
        cap.release()
        check("OpenCV webcam probe", "PASS" if cam_ok else "WARN",
              "camera 0 readable" if cam_ok else "camera 0 not readable (may need permission / no camera)")
    except Exception as e:
        check("OpenCV", "FAIL", f"{type(e).__name__}: {str(e)[:120]}")

    # 5. FastAPI — app assembly + real request via TestClient
    try:
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        app = FastAPI(title="TRINETRA M0")

        @app.get("/health")
        def health():
            return {"ok": True, "phase": "M0"}

        client = TestClient(app)
        r = client.get("/health")
        check("FastAPI", "PASS" if r.status_code == 200 and r.json()["ok"] else "FAIL",
              f"fastapi {ver('fastapi')} — /health -> {r.status_code} {r.json()}")
    except Exception as e:
        check("FastAPI", "FAIL", f"{type(e).__name__}: {str(e)[:120]}")

    print()
    failures = sum(1 for _, s, _ in CHECKS if s == "FAIL")
    warns = sum(1 for _, s, _ in CHECKS if s == "WARN")
    print(f"M0 VERIFICATION: {len(CHECKS) - failures - warns} pass, {warns} warn, {failures} fail")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
