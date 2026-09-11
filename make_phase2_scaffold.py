"""
make_phase2_scaffold.py  --  one-shot scaffold builder for Phase 2.

PLACE THIS FILE AT:   C:\\Users\\user\\gmppt\\make_phase2_scaffold.py
                      (repo ROOT -- same level as the gmppt\\ and phase1\\ folders)

RUN ONCE FROM THE REPO ROOT:
    python make_phase2_scaffold.py

It creates the phase2\\ folder, the results\\phase2\\ output folder, the two new
package modules, and the runner stubs. It NEVER overwrites an existing file --
anything already present is reported as SKIP and left untouched. Safe to re-run.

After running, move the harness file you already have into place:
    gmppt\\harness.py      (if it is not there yet)
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent

GATE_NOTE = (
    "Gate A returned (i) FAIL, (ii) HOLD. The region-selection framing returns to\n"
    "module level. That redirection is NOT confirmed until the Month-3 technical\n"
    "meeting. This script is gated behind that sign-off so no number leaves this\n"
    "folder that would have to be withdrawn later."
)


README = """# Phase 2 -- baselines and test harness

Phase 2 does not build the learned coefficient. It builds the instrument that will
measure it, and the baselines it will be measured against. The thesis reduces to one
comparison: adaptive coefficient vs baselines, same scenarios, power loss vs true GMPP.

## Acceptance criteria (declared before running -- see gmppt/harness.py ACCEPTANCE)

| Quantity | Target (S8) | Tolerance |
|---|---|---|
| Fixed-0.80 mean power loss | 4.1% | +/- 0.3 pt |
| Best constant k | 0.82 | +/- 0.01 |
| Best-constant mean loss | 3.5% | +/- 0.3 pt |
| Costly fraction, sub-substring (>1%) | 77% | +/- 3 pt |
| Region-error rate, sub-substring | 6.7% | +/- 1.0 pt |
| Worst-case absolute loss | 18.3 W | +/- 1.0 W |

A harness that cannot reproduce these on MASTER_SEED is a broken harness, not a new
finding. p1 is the gate on every downstream step.

## Method contract

    fn(ctx) -> float          # returns a landing voltage

ctx exposes v_oc, i_sc, module, geometry, rng, and probe(v) -> power. It does NOT
expose the P-V array or the true GMPP. The ceiling is sealed from the method by
construction, so no result can be contaminated by lookahead.

## Status ledger

| Step | Script | Depends on | Status |
|---|---|---|---|
| P2.1 | gmppt/harness.py | -- | handed over |
| P2.2 | p1_harness_regression.py | P2.1 | not run |
| P2.3 | p2_static_baselines.py | P2.2 pass | not run |
| P2.4 | p3_ahmed_salam.py | P2.2 pass | not written |
| P2.5 | p4_basoglu.py | Month-3 sign-off | GATED |
| P2.6 | p5_timedomain.py | Month-3 sign-off | GATED |
| P2.7 | p6_en50530.py | P2.6 | GATED |

Redirection-independent: P2.1 through P2.4. Safe to build now.
Redirection-dependent: P2.5 onward. Do not start before the Month-3 meeting.

## Outstanding dependency

Full multi-peak magnitude at module scale is deferred to Phase 8 and needs partner
measurement (swept I-V, or one module on loan). This is critical path. Raise it at
the Month-3 meeting.
"""


BASELINES = '''"""
gmppt/baselines.py -- static GMPPT baseline methods.

Every method here obeys the harness contract:  fn(ctx) -> landing voltage.
Methods see ctx.v_oc and ctx.probe(v). They never see the true GMPP.

Populated incrementally:
  - fixed-0.80 and the recalibrated-constant family live in harness.py already
  - Ahmed-Salam conditional alpha  -> P2.4
  - Basoglu reimplementation       -> P2.5 (gated)
"""

from __future__ import annotations

from .harness import Context, constant_method, register  # noqa: F401


# ---------------------------------------------------------------------------
# P2.4 -- Ahmed-Salam conditional alpha. The primary conditional comparison:
# it is the method that decides whether the learned coefficient has headroom.
# Implementation follows once p1 regression passes.
# ---------------------------------------------------------------------------

def ahmed_salam(ctx: Context) -> float:
    raise NotImplementedError(
        "P2.4 not implemented. Run phase2/p1_harness_regression.py first -- the "
        "harness must reproduce the S8 numbers before any new baseline is trusted."
    )
'''


TRACKERS = f'''"""
gmppt/trackers.py -- time-domain trackers (P&O, InC, PSO).

GATED.
{GATE_NOTE}

These trackers also need a time-domain simulation layer that does not exist yet:
the tracker must step along the curve over successive samples rather than
returning a single voltage. The harness probe interface already supports this
(probe calls are counted), but the stepping loop and the irradiance-vs-time
driver are still to be built.
"""

from __future__ import annotations


def _gated(name: str):
    raise NotImplementedError(
        f"{{name}} is gated on Month-3 sign-off of the Gate A redirection, and on "
        "the time-domain layer. Do not implement before both are in place."
    )


def perturb_and_observe(ctx):
    _gated("P&O")


def incremental_conductance(ctx):
    _gated("InC")


def pso(ctx):
    _gated("PSO")
'''


P1 = '''"""
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
'''


P2 = '''"""
phase2/p2_static_baselines.py -- P2.3: the two static baselines on one table.

RUN FROM REPO ROOT:   python phase2/p2_static_baselines.py --n 2000

Runs fixed-0.80 and the recalibrated-constant family (C2) through the harness and
writes a single comparison table to results/phase2/. Both are already-known
quantities -- the point is not to discover them again but to establish the table
format that every later method, including the learned coefficient, drops into.

Reports two-sided: mean AND worst, raw loss AND costly fraction.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gmppt.harness import (  # noqa: E402
    METHODS, best_constant, constant_method, metrics, run_method,
    scenario_set, write_records,
)

OUT = Path("results/phase2")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=2000)
    ap.add_argument("--geometry", default="sub")
    args = ap.parse_args()

    scenarios = scenario_set(args.n)
    print(f"scenarios: {len(scenarios)}")

    table = {}

    recs = run_method(METHODS["fixed_0.80"], scenarios)
    write_records(recs, OUT / "fixed_080.csv")
    table["fixed_0.80"] = {
        "all": metrics(recs),
        "sub_substring": metrics(recs, geometry=args.geometry),
    }

    k, _ = best_constant(scenarios)
    recs_k = run_method(constant_method(k), scenarios)
    write_records(recs_k, OUT / f"constant_{k:.3f}.csv")
    table[f"recalibrated_{k:.3f}"] = {
        "all": metrics(recs_k),
        "sub_substring": metrics(recs_k, geometry=args.geometry),
    }

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "static_baselines.json").write_text(json.dumps(table, indent=2),
                                               encoding="utf-8")

    hdr = f"{"method":<22}{"mean %":>9}{"worst %":>9}{"worst W":>9}{"costly %":>10}{"region err %":>14}"
    print("\\n" + hdr)
    print("-" * len(hdr))
    for name, blk in table.items():
        m = blk["sub_substring"]
        print(f"{name:<22}{m['mean_loss_pct']:>9.3f}{m['worst_loss_pct']:>9.3f}"
              f"{m['worst_loss_w']:>9.2f}{m['costly_frac_pct']:>10.1f}"
              f"{m['region_error_pct']:>14.1f}")
    print("\\n(sub-substring subset; full set in static_baselines.json)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
'''


P3 = '''"""
phase2/p3_ahmed_salam.py -- P2.4: Ahmed-Salam conditional alpha baseline.

RUN FROM REPO ROOT:   python phase2/p3_ahmed_salam.py --n 2000

The primary conditional comparison. Fixed-0.80 and C2 are static, so beating them
proves little on its own; Ahmed-Salam already adapts alpha to conditions. If the
learned coefficient cannot beat this, the core contribution has no headroom, and it
is better to find that out in Phase 2 than in Phase 3.

Implementation goes in gmppt/baselines.py. Do not start until p1 passes.
"""

import sys

raise SystemExit(
    "P2.4 not implemented yet. Prerequisite: phase2/p1_harness_regression.py "
    "must exit 0. Implement ahmed_salam() in gmppt/baselines.py first."
)
'''


def gated_stub(step: str, title: str, why: str) -> str:
    return f'''"""
phase2/{title}

GATED -- {step}.

{GATE_NOTE}

{why}
"""

raise SystemExit(
    "GATED: this step depends on Month-3 sign-off of the Gate A redirection. "
    "Confirm the redirection with the advisor before implementing."
)
'''


FILES = {
    "phase2/README.md": README,
    "phase2/__init__.py": "",
    "gmppt/baselines.py": BASELINES,
    "gmppt/trackers.py": TRACKERS,
    "phase2/p1_harness_regression.py": P1,
    "phase2/p2_static_baselines.py": P2,
    "phase2/p3_ahmed_salam.py": P3,
    "phase2/p4_basoglu.py": gated_stub(
        "P2.5",
        "p4_basoglu.py -- Basoglu reimplementation",
        "Basoglu scans peak regions explicitly, so it sits directly on the\n"
        "redirected framing. Sequence it after sign-off, not before.",
    ),
    "phase2/p5_timedomain.py": gated_stub(
        "P2.6",
        "p5_timedomain.py -- P&O / InC / PSO on a time-domain layer",
        "Needs the time-domain stepping layer in gmppt/trackers.py, which does not\n"
        "exist yet. Largest build in Phase 2 and the most redirection-dependent.",
    ),
    "phase2/p6_en50530.py": gated_stub(
        "P2.7",
        "p6_en50530.py -- EN 50530 dynamic test harness",
        "Depends on the time-domain layer from P2.6. The funded proposal targets\n"
        ">= 99% dynamic tracking efficiency against this profile.",
    ),
    "tests/test_harness.py": '''"""Tests for the Phase 2 comparison harness.

RUN:   python -m pytest tests/test_harness.py -v

These are unit tests on the harness mechanics, not on PV physics. They use a
synthetic two-peak curve so they run in milliseconds and do not depend on the
CEC database or pvlib.
"""

import numpy as np
import pytest

from gmppt.harness import Context, _peak_regions, metrics


def _synthetic():
    v = np.linspace(0, 40, 401)
    p = 100 * np.exp(-((v - 12) ** 2) / 8) + 160 * np.exp(-((v - 30) ** 2) / 10)
    return v, p


def test_two_peaks_detected():
    v, p = _synthetic()
    regions = _peak_regions(v, p)
    assert regions.max() == 1, "synthetic curve must split into two regions"


def test_single_peak_is_one_region():
    v = np.linspace(0, 40, 401)
    p = 160 * np.exp(-((v - 30) ** 2) / 10)
    assert _peak_regions(v, p).max() == 0


def test_probe_is_counted():
    v, p = _synthetic()
    ctx = Context(v_oc=40.0, i_sc=None, module="m", geometry="g",
                  rng=np.random.default_rng(0), _V=v, _P=p)
    for x in (10.0, 20.0, 30.0):
        ctx.probe(x)
    assert ctx.n_probes == 3


def test_probe_returns_power_at_voltage():
    v, p = _synthetic()
    ctx = Context(v_oc=40.0, i_sc=None, module="m", geometry="g",
                  rng=np.random.default_rng(0), _V=v, _P=p)
    assert ctx.probe(30.0) == pytest.approx(160.0, rel=0.02)


def test_context_hides_the_ceiling():
    """The method-facing contract must not expose the answer."""
    public = {f for f in dir(Context) if not f.startswith("_")}
    assert not {"p_gmpp", "v_gmpp", "ceiling", "k_true"} & public


def test_metrics_empty_set():
    assert metrics([])["n"] == 0
''',
}


def main() -> int:
    if not (ROOT / "gmppt").is_dir():
        print(f"ERROR: no gmppt\\ package found under {ROOT}.")
        print("Place this script at the repo ROOT (C:\\Users\\user\\gmppt) and re-run.")
        return 1

    for d in ("phase2", "results/phase2", "tests"):
        (ROOT / d).mkdir(parents=True, exist_ok=True)

    created, skipped = 0, 0
    for rel, body in FILES.items():
        path = ROOT / rel
        if path.exists():
            print(f"SKIP    {rel}  (already exists, left untouched)")
            skipped += 1
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
        print(f"CREATE  {rel}")
        created += 1

    print(f"\n{created} created, {skipped} skipped.")

    if not (ROOT / "gmppt" / "harness.py").exists():
        print("\nNEXT: gmppt\\harness.py is missing. Copy the harness file there "
              "before running phase2\\p1_harness_regression.py.")
    else:
        print("\nNEXT: python phase2\\p1_harness_regression.py --n 2000")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())