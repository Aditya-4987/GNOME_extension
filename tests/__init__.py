import sys
from pathlib import Path

# Add the src directory to sys.path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))
