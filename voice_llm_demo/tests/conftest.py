import sys
from pathlib import Path


VOICE_ROOT = Path(__file__).resolve().parents[1]
if str(VOICE_ROOT) not in sys.path:
    sys.path.insert(0, str(VOICE_ROOT))
