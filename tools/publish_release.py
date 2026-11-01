"""Compatibility command; implementation: tools.release.publish."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tools.release.publish import *

if __name__=='__main__':main()
