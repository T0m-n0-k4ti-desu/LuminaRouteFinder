"""Compatibility import; implementation: shared.messages."""
import sys
from .shared import messages as _implementation
sys.modules[__name__]=_implementation
