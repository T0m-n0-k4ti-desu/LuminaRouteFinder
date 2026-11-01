"""Compatibility import; implementation: application.analysis."""
import sys
from .application import analysis as _implementation
sys.modules[__name__]=_implementation
