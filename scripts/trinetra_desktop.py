#!/usr/bin/env python3
"""Trinetra Native Desktop Command Center Launcher.

Runs the PySide6/QML desktop interface with in-memory zero-copy frame streaming,
SQLite database persistence, and P-HERMES grounded AI reasoning.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure repo root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.desktop.app import run_desktop_app

if __name__ == "__main__":
    run_desktop_app(sys.argv)
