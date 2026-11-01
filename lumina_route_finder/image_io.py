"""Compatibility import; implementation: storage.images."""
import sys
from .storage import images as _implementation
sys.modules[__name__]=_implementation
