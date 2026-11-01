"""Package-relative data paths (also valid in frozen distributions)."""
from pathlib import Path

ASSETS = Path(__file__).resolve().parents[1] / "assets"
