"""
phase2/p1_harness_regression.py -- P2.2: prove the harness reproduces Phase 1.

RUN FROM REPO ROOT:   python phase2/p1_harness_regression.py --n 2000

This is the gate on all of Phase 2. The harness computes the true GMPP itself; if
its fixed-0.80 numbers do not match S8 within the declared tolerances, the harness
is measuring something other than what Phase 1 measured, and every downstream
comparison inherits that error.

Exit code 0 = all checks pass. Non-zero = do not proceed to p2.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gmppt.harness import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
