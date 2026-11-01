"""CLI entry point; legacy helper imports remain available."""
import sys
from .cli import main
from .analysis import run_image
from .image_io import write_image
from .domain.geometry import export_solution

if __name__ == '__main__':
    sys.exit(main())
