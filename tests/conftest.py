import sys
from pathlib import Path

# Make the phase-step scripts importable as modules in tests. Their heavy work
# is guarded by `if __name__ == "__main__"`, so importing is cheap.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
