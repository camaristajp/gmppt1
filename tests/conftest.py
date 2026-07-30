import sys
from pathlib import Path

# Make the phase-step scripts importable in tests, whether the folder is named
# `scripts/` or `phase1/`. Their heavy work is guarded by __main__, so importing
# is cheap. (S3+ tests import from the gmppt package directly and don't need this.)
root = Path(__file__).resolve().parents[1]
for name in ("scripts", "phase1"):
    d = root / name
    if d.is_dir():
        sys.path.insert(0, str(d))
