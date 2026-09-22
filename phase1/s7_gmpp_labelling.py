"""
S7 - GMPP labelling and sweep-resolution convergence (Stage 4, step 2).
REVISION 2 -- runs under the breakdown mode the labels are actually built with.

PLACE THIS FILE AT:   C:\\Users\\user\\gmppt\\phase1\\s7_gmpp_labelling.py
                      OVERWRITE revision 1.

WHY REVISION 2 EXISTS -- a verification that verified the wrong configuration

    Revision 1 called device.module_iv WITHOUT a `bd` argument:

        c = device.module_iv(mp, scenario.irradiances, scenario.temp_c,
                             n_points=n_points)

    device.Breakdown()'s own default is factor=0.0, i.e. avalanche OFF. But
    config.BREAKDOWN_MODE is "on", and every consumer of the labels passes
    config.breakdown() explicitly:

        scenarios.evaluate_scenario  -> bd=config.breakdown()   ON
        dataset.build                -> bd=config.breakdown()   ON
        s8._loss_for_constant        -> bd=config.breakdown()   ON
        s7._gmpp_at  (revision 1)    -> default                 OFF   <-- here

    So the step that certifies "the GMPP labels are resolution-independent"
    certified a curve family that no downstream step uses. The certificate did
    not cover the labels it was issued for.

    This is not a cosmetic mismatch. config.py states the primary setting is ON
    because a cell driven into reverse bias under sub-substring shading really
    does avalanche, and device.py warns that the Bishop solver "may not converge
    at the handful of samples right at the avalanche knee." The ON path
    therefore has numerical structure in exactly the regime a resolution check
    exists to probe, and sub-substring is 40% of the scenario mix.

    FIX: _gmpp_at takes an explicit Breakdown and the runner sweeps the modes
    named in config, defaulting to both. The primary mode ("on") is the one that
    must pass; "off" is reported because config retains it as a documented
    bound, and a mode that is claimed as a bound should be shown to be sound.

THREE FURTHER CORRECTIONS, EACH SMALL AND EACH DELIBERATE

  1. PER-GEOMETRY REPORTING. Revision 1 reduced everything to one global worst
     drift. If breakdown-ON instability bites, it bites sub_substring and
     nothing else, and a single global number hides which geometry failed. The
     drifts are now reported per geometry, and the sample's geometry counts are
     printed so thin coverage is visible rather than assumed.

  2. WHICH TOLERANCE BINDS IS NOW STATED. V_TOL is 0.10 V absolute; COEFF_DECIMALS
     is 3, i.e. 0.001 in k, which on a ~45 V module is ~0.045 V. The coefficient
     criterion is therefore roughly 2x stricter than the voltage criterion, so a
     run can fail on coefficient while passing on voltage. Both are kept (strict
     is safe) but the report names the binding criterion, so a failure is
     diagnosable instead of mysterious.

  3. SOLVER FAILURES ARE COUNTED, NOT CRASHED ON. device.module_iv raises
     FloatingPointError if breakdown instability reaches the operating region.
     Under revision 1 that could never fire (avalanche was off). Under ON it can,
     and a scenario that cannot be evaluated at some resolution is a RESULT --
     the sweep is not resolution-independent there -- not a reason to abort the
     run before the other 119 scenarios are checked.

  Also removed: an unused `rng = np.random.default_rng(config.seed_for("s7_sample"))`.
  scenarios.generate is already seeded from MASTER_SEED, so the sample was never
  drawn through that generator and the line only implied a randomisation that
  did not exist.

WHAT IS UNCHANGED
    The checkpoint semantics and all four tolerances are exactly revision 1's.
    This revision changes the CONFIGURATION under test and the granularity of
    the report; it does not loosen a single criterion.

Plan / WORKFLOW S7 checkpoint (verbatim): "dense sweep converged (halving the
step size does not change the recorded GMPP)."

Checkpoints:
  1. RESOLUTION CONVERGENCE - GMPP voltage and power stable when the sweep
     resolution is halved and doubled about the default (2000 / 4000 / 8000).
  2. COEFFICIENT STABILITY - the implied coefficient (gmpp_V / Voc) unchanged to
     3 decimals across resolutions, since that coefficient is the S8 label.
  3. PEAK-COUNT STABILITY - analyse() reports the same number of peaks at each
     resolution (a coarse grid can merge or invent peaks).
  4. EVALUABILITY - every scenario evaluates at every resolution.

USAGE
    python -m phase1.s7_gmpp_labelling              # both modes, primary first
    python -m phase1.s7_gmpp_labelling --mode on    # primary only
    python -m phase1.s7_gmpp_labelling --sample 300 # wider sample
"""
import argparse
import sys

import numpy as np
import pandas as pd

from gmppt import config, device, scenarios
from gmppt.device import ModuleParams

RESOLUTIONS = (2000, 4000, 8000)   # halve / default / double
REF_RESOLUTION = 4000              # the default device.module_iv uses
SAMPLE = 120                       # seeded sample of scenarios to test
V_TOL = 0.10                       # GMPP voltage tolerance (V)
P_TOL_FRAC = 0.002                 # GMPP power tolerance (fraction)
COEFF_DECIMALS = 3                 # coefficient must match to this many decimals
COEFF_TOL = 10 ** (-COEFF_DECIMALS)

GEOMETRIES = ("uniform", "whole_substring", "sub_substring")


# ---------------------------------------------------------------------------
# Single-scenario evaluation
# ---------------------------------------------------------------------------

def _gmpp_at(mp, scenario, n_points, bd):
    """GMPP of one scenario at one sweep resolution, under an explicit breakdown.

    `bd` is REQUIRED -- passing it positionally is what revision 1 omitted, and
    defaulting it here would reintroduce exactly that bug.

    Returns None if the curve cannot be evaluated at this resolution, which is
    itself a convergence failure and is counted as one by the caller.
    """
    try:
        c = device.module_iv(mp, scenario.irradiances, scenario.temp_c,
                             bd=bd, n_points=n_points)
        a = device.analyse(c)
    except (FloatingPointError, ValueError, RuntimeError) as exc:
        return dict(failed=True, error=f"{type(exc).__name__}: {exc}")

    voc = float(np.asarray(c["V"], float).max())
    return dict(failed=False,
                V=float(a["gmpp"]["V"]),
                P=float(a["gmpp"]["P"]),
                voc=voc,
                coeff=(float(a["gmpp"]["V"]) / voc) if voc > 0 else float("nan"),
                n_peaks=int(a["n_peaks"]))


# ---------------------------------------------------------------------------
# The checkpoint
# ---------------------------------------------------------------------------

def check_resolution_convergence(pool, mode, sample=SAMPLE, verbose=True):
    """Resolution convergence under one breakdown mode.

    Returns (ok, summary_dict, per_scenario_rows).
    """
    bd = config.breakdown(mode)
    bd_desc = (f"factor={bd.factor:g}, voltage={bd.voltage:g} V, exp={bd.exp:g}"
               if bd.factor > 0 else "factor=0 (no avalanche)")

    if verbose:
        print(f"1-4) SWEEP-RESOLUTION CONVERGENCE  [breakdown mode: {mode}]")
        print(f"     {bd_desc}")
        print(f"     resolutions {RESOLUTIONS} points, on {sample} seeded "
              f"scenarios, reference {REF_RESOLUTION}")

    scen = scenarios.generate(pool, sample)

    if verbose:
        counts = pd.Series([s.geometry for s in scen]).value_counts()
        mix = "  ".join(f"{g} {int(counts.get(g, 0))}" for g in GEOMETRIES)
        print(f"     sample geometry mix: {mix}")

    rows = []
    for s in scen:
        mp = ModuleParams.from_cec(s.module)
        vals = {r: _gmpp_at(mp, s, r, bd) for r in RESOLUTIONS}
        ref = vals[REF_RESOLUTION]

        # A scenario that fails at ANY resolution cannot be compared; record the
        # failure and move on rather than propagating NaNs into the drifts.
        failures = [r for r in RESOLUTIONS if vals[r]["failed"]]
        if failures:
            rows.append(dict(module=s.module, geometry=s.geometry,
                             near_threshold=s.near_threshold,
                             evaluable=False,
                             failed_at=",".join(str(r) for r in failures),
                             error=next(vals[r]["error"] for r in failures),
                             dV=np.nan, dP=np.nan, dcoeff=np.nan,
                             peak_mismatch=np.nan))
            continue

        dV = max(abs(vals[r]["V"] - ref["V"]) for r in RESOLUTIONS)
        dP = max(abs(vals[r]["P"] - ref["P"]) / max(ref["P"], 1e-9)
                 for r in RESOLUTIONS)
        dc = max(abs(vals[r]["coeff"] - ref["coeff"]) for r in RESOLUTIONS)
        pk = sum(1 for r in RESOLUTIONS
                 if vals[r]["n_peaks"] != ref["n_peaks"])

        rows.append(dict(module=s.module, geometry=s.geometry,
                         near_threshold=s.near_threshold,
                         evaluable=True, failed_at="", error="",
                         dV=dV, dP=dP, dcoeff=dc, peak_mismatch=pk,
                         ref_n_peaks=ref["n_peaks"], ref_coeff=ref["coeff"]))

    df = pd.DataFrame(rows)
    ev = df[df["evaluable"]]
    n_failed = int((~df["evaluable"]).sum())

    worst_dV = float(ev["dV"].max()) if len(ev) else float("nan")
    worst_dP = float(ev["dP"].max()) if len(ev) else float("nan")
    worst_dc = float(ev["dcoeff"].max()) if len(ev) else float("nan")
    peak_mismatch = int(ev["peak_mismatch"].sum()) if len(ev) else 0

    v_ok = worst_dV < V_TOL
    p_ok = worst_dP < P_TOL_FRAC
    c_ok = worst_dc < COEFF_TOL
    pk_ok = peak_mismatch == 0
    ev_ok = n_failed == 0
    ok = v_ok and p_ok and c_ok and pk_ok and ev_ok

    if verbose:
        print()
        print(f"     {'geometry':<16} {'n':>4} {'worst dV':>10} "
              f"{'worst dP':>10} {'worst dk':>10} {'pk mism':>8}")
        for g in GEOMETRIES:
            sub = ev[ev["geometry"] == g]
            if not len(sub):
                print(f"     {g:<16} {0:>4}  (none in sample)")
                continue
            print(f"     {g:<16} {len(sub):>4} {sub['dV'].max():>9.4f}V "
                  f"{sub['dP'].max()*100:>9.4f}% {sub['dcoeff'].max():>10.5f} "
                  f"{int(sub['peak_mismatch'].sum()):>8}")
        print()
        print(f"     worst GMPP voltage drift : {worst_dV:.4f} V     "
              f"(< {V_TOL} V: {v_ok})")
        print(f"     worst GMPP power drift   : {worst_dP*100:.4f} %     "
              f"(< {P_TOL_FRAC*100:.1f} %: {p_ok})")
        print(f"     worst coefficient drift  : {worst_dc:.5f}       "
              f"(< {COEFF_TOL}: {c_ok})")
        print(f"     peak-count mismatches    : {peak_mismatch} of "
              f"{len(ev) * len(RESOLUTIONS)}   ({pk_ok})")
        print(f"     unevaluable scenarios    : {n_failed} of {len(df)}   "
              f"({ev_ok})")

        # Which criterion binds -- see correction 2 in the docstring. The
        # coefficient tolerance is the tighter of the two on a typical module,
        # so a failure there does not necessarily mean the voltage moved much.
        if len(ev):
            headroom = {
                "voltage": worst_dV / V_TOL if V_TOL else np.inf,
                "power": worst_dP / P_TOL_FRAC if P_TOL_FRAC else np.inf,
                "coefficient": worst_dc / COEFF_TOL if COEFF_TOL else np.inf,
            }
            binding = max(headroom, key=headroom.get)
            print(f"     binding criterion        : {binding} "
                  f"({headroom[binding]*100:.1f}% of its tolerance used)")

        if n_failed:
            print()
            print("     UNEVALUABLE SCENARIOS (first 3):")
            for _, r in df[~df["evaluable"]].head(3).iterrows():
                print(f"       {r['geometry']:<16} at {r['failed_at']} pts: "
                      f"{r['error'][:70]}")

        print(f"     dense sweep converged: {'OK' if ok else 'FAIL'}")

    summary = dict(mode=mode, breakdown_factor=bd.factor,
                   breakdown_voltage=bd.voltage, breakdown_exp=bd.exp,
                   n_sample=len(df), n_unevaluable=n_failed,
                   worst_dV=worst_dV, worst_dP=worst_dP,
                   worst_dcoeff=worst_dc, peak_mismatch=peak_mismatch,
                   v_ok=v_ok, p_ok=p_ok, coeff_ok=c_ok, peaks_ok=pk_ok,
                   evaluable_ok=ev_ok, passed=ok)
    for g in GEOMETRIES:
        sub = ev[ev["geometry"] == g]
        summary[f"n_{g}"] = int(len(sub))
        summary[f"worst_dV_{g}"] = float(sub["dV"].max()) if len(sub) else np.nan
        summary[f"worst_dcoeff_{g}"] = (float(sub["dcoeff"].max())
                                        if len(sub) else np.nan)

    return ok, summary, df


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--mode", choices=("on", "off", "both"), default="both",
                    help="breakdown mode to test; 'both' runs the primary "
                         "(config.BREAKDOWN_MODE) first, then the other.")
    ap.add_argument("--sample", type=int, default=SAMPLE,
                    help=f"scenarios to test (default {SAMPLE})")
    args = ap.parse_args(argv)

    print("S7  GMPP labelling - sweep-resolution convergence  (revision 2)")
    print("  " + config.provenance())
    print(f"  config.BREAKDOWN_MODE = {config.BREAKDOWN_MODE!r}  (the primary "
          f"setting; labels downstream are built with this)")
    print("=" * 74)

    pool = pd.read_parquet(config.CEC_POOL)

    primary = config.BREAKDOWN_MODE
    other = "off" if primary == "on" else "on"
    modes = [primary, other] if args.mode == "both" else [args.mode]

    summaries, frames = [], []
    for i, mode in enumerate(modes):
        if i:
            print()
        tag = "PRIMARY" if mode == primary else "documented bound"
        print(f"--- breakdown mode {mode!r}  ({tag}) " + "-" * 28)
        ok, summary, df = check_resolution_convergence(pool, mode,
                                                       sample=args.sample)
        summary["role"] = tag
        summaries.append(summary)
        df.insert(0, "mode", mode)
        frames.append(df)

    sum_df = pd.DataFrame(summaries)
    sum_df.to_csv(config.RESULTS_DIR / "s7_resolution_convergence.csv",
                  index=False)
    pd.concat(frames, ignore_index=True).to_csv(
        config.RESULTS_DIR / "s7_resolution_per_scenario.csv", index=False)
    print(f"\n   summary      -> results/s7_resolution_convergence.csv")
    print(f"   per-scenario -> results/s7_resolution_per_scenario.csv")

    # The gate is the PRIMARY mode. The bound is reported, not gated on: config
    # keeps "off" as a conservative reference, and a bound that drifts is worth
    # seeing but does not invalidate labels nothing is built from.
    primary_row = next(s for s in summaries if s["mode"] == modes[0])
    ok = bool(primary_row["passed"])

    print("\n" + "=" * 74)
    for s in summaries:
        print(f"  mode {s['mode']:<4} ({s['role']:<16}): "
              f"{'PASS' if s['passed'] else 'FAIL'}   "
              f"worst dV {s['worst_dV']:.4f} V, dk {s['worst_dcoeff']:.5f}, "
              f"peak mismatches {s['peak_mismatch']}, "
              f"unevaluable {s['n_unevaluable']}")
    print(f"\nS7 checkpoint: {'PASS' if ok else 'FAIL'}  "
          f"(gated on the primary mode {modes[0]!r})")
    if ok:
        print("  The GMPP labels (and the coefficients derived from them) are")
        print("  resolution-independent UNDER THE BREAKDOWN SETTING THE LABELS")
        print("  ARE BUILT WITH, so the S8 distribution rests on accurate peak")
        print("  locations, not on a sweep-grid artefact.")
    else:
        print("  Labels are NOT certified at this resolution under the primary")
        print("  breakdown mode. Read the per-geometry table above: a failure")
        print("  confined to sub_substring points at the avalanche knee, and the")
        print("  remedy is a finer default sweep or a stiffer-region guard in")
        print("  device.substring_element_iv_subshaded -- not a looser tolerance.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())