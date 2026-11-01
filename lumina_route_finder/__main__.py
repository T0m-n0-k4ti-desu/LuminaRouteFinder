"""CLI entry point; legacy helper imports remain available."""
import sys
from .application.cli import main
from .application.analysis import run_image
from .storage.images import write_image
from .domain.geometry import export_solution

if __name__ == '__main__':
    sys.exit(main())
