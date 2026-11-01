"""Compatibility import; implementation: storage.settings."""
import sys
from .storage import settings as _implementation
sys.modules[__name__]=_implementation
