"""Compatibility import; implementation: recognition.connections."""
import sys
from .recognition import connections as _implementation
sys.modules[__name__]=_implementation
