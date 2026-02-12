"""Configuration for pytest."""

import sys
from pathlib import Path

# Add .opencode directory to Python path
opencode_path = Path(__file__).parent.parent
if str(opencode_path) not in sys.path:
    sys.path.insert(0, str(opencode_path))