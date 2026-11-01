"""Compatibility command; implementation: tools.build.build_exe."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tools.build.build_exe import *

if __name__=='__main__':main()
