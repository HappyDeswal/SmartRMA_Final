"""Backward compatibility shim. Canonical implementation in backend.evaluation."""
import sys
from pathlib import Path
_ws_root = Path(__file__).resolve().parent.parent
if str(_ws_root) not in sys.path:
    sys.path.insert(0, str(_ws_root))

from backend.evaluation import *
