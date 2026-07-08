import sys
from pathlib import Path


SAFECLOUD_ROOT = Path(__file__).resolve().parents[1]
if str(SAFECLOUD_ROOT) not in sys.path:
    sys.path.insert(0, str(SAFECLOUD_ROOT))
