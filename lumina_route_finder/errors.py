"""Compatibility import; implementation: shared.errors."""
import sys
from .shared import errors as _implementation
sys.modules[__name__]=_implementation
