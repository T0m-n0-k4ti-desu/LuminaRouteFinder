"""Compatibility command; implementation: tools.build.smoke_tests."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tools.build.smoke_tests import *

if __name__=='__main__':test_executable()
