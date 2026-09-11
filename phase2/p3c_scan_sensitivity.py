"""
p3c_scan_sensitivity.py  --  P2.4c: is the realistic figure the METHOD's ceiling?
REVISION 2 -- swept against the rewritten (revision 5) detector.

PLACE THIS FILE AT:   C:\\Users\\user\\gmppt\\phase2\\p3c_scan_sensitivity.py
                      OVERWRITE revision 1.

PREREQUISITE
    gmppt/baselines.py revision 5. This script REFUSES TO RUN if the detector
    invariance test fails -- sweeping a broken detector is what revision 1 did,
    and it produced a 29.6 pt spread that measured the bug rather than the method.

WHAT REVISION 1 FOUND, AND WHY ITS ANSWER WAS DISCARDED
    Loss rose with probe count (32% at 240 probes). More information cannot make
    a method worse, so that was a failing detector. Its threshold compared
    CONSECUTIVE SAMPLES, so denser sampling shrank every gap below the threshold,
    no steps were detected, and eq. (27) collapsed to a single candidate.

    Revision 1's declared rule said "improvement >= 0.20 pt -> report the best
    configuration". That rule was overridden deliberately: it assumed the sweep
    measured detector QUALITY. It measured a bug. Harvesting the best corner of a
    broken surface is exactly the cherry-picking the two-sided discipline exists
    to prevent. The instrument was fixed instead.

TOLERANCE -- DECLARED BEFORE THIS RUN
    Across the probe x tolerance grid, on sub_substring mean loss:
      spread < 0.30 pt   -> the detector is not the limitation. Report the
                            default-configuration figure with this sweep as
                            evidence, exactly as L4 did for breakdown.
      spread >= 0.30 pt  -> still parameter-sensitive. Do NOT pick the best
                            corner; report the range and say the realistic
                            figure is bounded rather than pinned.

    Note this is a SPREAD criterion, not a best-value criterion. After revision
    1, a rule that rewards finding a better corner is the wrong rule.

    Monotonicity guard: loss must not systematically worsen as probes increase.
    If it does, the detector is still density-coupled and the run is void.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gmppt import baselines  # noqa: E402
from gmppt.harness import Context, metrics, run_method, scenario_set  # noqa: E402

OUT = Path("results/phase2")
PRIMARY = "sub_substring"
FAIR = "whole_substring"

PROBE_GRID = (30, 60, 120, 240)
TOL_GRID = (0.02, 0.04, 0.08)          # plateau tolerance, fraction of Isc
SPREAD_TOL = 0.30                       # pt; declared above


def scan_method(n_probes: int, plateau_tol: float):
    """The realistic scan variant with detector parameters passed explicitly.

    Revision 5's scan_steps takes them as arguments, so nothing is mutated and
    grid points cannot influence one another.
    """
    def fn(ctx: Context) -> float:
        n_sub = int(baselines.config.N_SUBSTRINGS)
        levels, steps = baselines.scan_steps(
            ctx, n_probes=n_probes, plateau_tol=plateau_tol)
        sizes = baselines.infer_group_sizes(steps, len(levels), ctx.v_oc / n_sub)
        peaks = baselines.predicted_peaks(
            ctx.v_oc, list(zip(levels, sizes)), anchor="ratio")
        return baselines._land(ctx, peaks)

    fn.__name__ = f"scan_p{n_probes}_tol{plateau_tol:.2f}"
    return fn


def gate_detector() -> bool:
    """Refuse to sweep a detector that is not sampling-invariant."""
    print("GATE  detector invariance (revision 5)")
    ok = baselines.test_detector_invariance()
    if not ok:
        print("\n   STOP: the detector is still density-coupled. Sweeping it")
        print("   would measure the bug, not the method. Fix first.")
    return ok


def part1_sensitivity(scenarios) -> dict:
    print("\nPART 1  DETECTOR SENSITIVITY")
    print(f"   grid: probes {PROBE_GRID} x plateau tolerance {TOL_GRID}")
    print(f"   declared: spread < {SPREAD_TOL} pt means the detector is not the")
    print("   limitation. This is a SPREAD test, not a search for a better corner.\n")

    header = (f"   {'probes':>7} {'tol':>6} {'sub mean %':>11} {'sub costly %':>13} "
              f"{'whole mean %':>13} {'probes used':>12}")
    print(header)
    print("   " + "-" * (len(header) - 3))

    grid = {}
    for n_probes in PROBE_GRID:
        for tol in TOL_GRID:
            recs = run_method(scan_method(n_probes, tol), scenarios)
            m_sub = metrics(recs, geometry=PRIMARY)
            m_whole = metrics(recs, geometry=FAIR)
            grid[f"{n_probes}_{tol:.2f}"] = {
                "n_probes": n_probes, "plateau_tol": tol,
                "sub": m_sub, "whole": m_whole}
            print(f"   {n_probes:>7} {tol:>6.2f} {m_sub['mean_loss_pct']:>11.2f} "
                  f"{m_sub['costly_frac_pct']:>13.1f} "
                  f"{m_whole['mean_loss_pct']:>13.2f} "
                  f"{m_sub['mean_probes']:>12.1f}")

    means = {k: v["sub"]["mean_loss_pct"] for k, v in grid.items()}
    spread = max(means.values()) - min(means.values())

    # monotonicity guard: mean loss per probe budget, averaged over tolerances
    by_probe = {p: float(np.mean([v["sub"]["mean_loss_pct"]
                                  for v in grid.values() if v["n_probes"] == p]))
                for p in PROBE_GRID}
    worsening = all(by_probe[PROBE_GRID[i]] < by_probe[PROBE_GRID[i + 1]]
                    for i in range(len(PROBE_GRID) - 1))

    print(f"\n   mean loss by probe budget: "
          + "  ".join(f"{p}:{v:.2f}%" for p, v in by_probe.items()))
    print(f"   spread across the grid: {spread:.2f} pt "
          f"(min {min(means.values()):.2f}%, max {max(means.values()):.2f}%)")

    if worsening:
        verdict = ("VOID -- loss still rises monotonically with probe count. The "
                   "detector remains density-coupled; do not report these numbers.")
    elif spread < SPREAD_TOL:
        verdict = (f"ROBUST -- spread {spread:.2f} pt is below the {SPREAD_TOL} pt "
                   f"bar. The realistic figure is the METHOD's ceiling, not the "
                   f"detector's. Report it with this sweep as evidence.")
    else:
        verdict = (f"BOUNDED -- spread {spread:.2f} pt. Report the RANGE "
                   f"{min(means.values()):.2f}-{max(means.values()):.2f}%, not a "
                   f"single figure, and say the realistic result is bounded.")
    print(f"   -> {verdict}")

    return {"grid": grid, "spread": spread, "by_probe": by_probe,
            "monotonic_worsening": worsening, "verdict": verdict}


def part2_alpha_clipping(scenarios) -> dict:
    """How often alpha is read at the edge of the paper's 100-1000 table.

    Independent of the detector, so revision 1's numbers stand; repeated here so
    one artefact carries both results.
    """
    print("\nPART 2  ALPHA CLIPPING")
    g_lo = float(baselines.ALPHA_G.min())
    g_hi = float(baselines.ALPHA_G.max())
    print(f"   Ahmed-Salam alpha is tabulated over {g_lo:.0f}-{g_hi:.0f} W/m2")

    rows = []
    for sc in scenarios:
        try:
            g_sub = baselines.substring_irradiances(sc.irradiances)
        except Exception:
            continue
        rows.append({"geometry": sc.geometry, "min_g": float(min(g_sub)),
                     "below": bool(min(g_sub) < g_lo)})

    out = {}
    for geom in sorted({r["geometry"] for r in rows}) + ["all"]:
        sel = rows if geom == "all" else [r for r in rows if r["geometry"] == geom]
        if not sel:
            continue
        mins = np.array([r["min_g"] for r in sel])
        frac = float(np.mean([r["below"] for r in sel]))
        out[geom] = {"n": len(sel), "frac_clipped": 100 * frac,
                     "min_g": float(mins.min()),
                     "p05_g": float(np.percentile(mins, 5))}
        print(f"   {geom:<16} n={len(sel):>5}   clipped {100*frac:>5.1f}%   "
              f"lowest effective G {mins.min():>6.1f}   "
              f"p05 {np.percentile(mins, 5):>6.1f}")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=2000)
    args = ap.parse_args()

    if not gate_detector():
        return 1

    OUT.mkdir(parents=True, exist_ok=True)
    scenarios = scenario_set(args.n)
    print(f"\nscenarios: {len(scenarios)}")

    sens = part1_sensitivity(scenarios)
    clip = part2_alpha_clipping(scenarios)

    (OUT / "scan_sensitivity.json").write_text(
        json.dumps({"sensitivity": sens, "alpha_clipping": clip}, indent=2),
        encoding="utf-8")
    print(f"\nresults -> {OUT / 'scan_sensitivity.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())