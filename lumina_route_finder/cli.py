"""Compatibility import; implementation: application.cli."""
import sys
from .application import cli as _implementation
if __name__=='__main__':
    raise SystemExit(_implementation.main())
sys.modules[__name__]=_implementation
