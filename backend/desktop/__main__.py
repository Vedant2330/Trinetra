"""CLI entry point for running the Trinetra native desktop Command Center."""
from __future__ import annotations

import sys
from backend.desktop.app import run_desktop_app

def main() -> None:
    run_desktop_app(sys.argv)

if __name__ == "__main__":
    main()
