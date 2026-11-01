"""Compatibility import; implementation: storage.session_outputs."""
import sys
from .storage import session_outputs as _implementation
sys.modules[__name__]=_implementation
