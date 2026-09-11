"""
v_l3b_coefficient_ratio.py  --  L3b: does the 75 C corner weakness matter?

PLACE THIS FILE AT:   C:\\Users\\user\\gmppt\\validation\\v_l3b_coefficient_ratio.py
                      (next to v_l3_offstc.py, NOT in phase1/ or phase2/)

RUN FROM THE REPO ROOT (C:\\Users\\user\\gmppt):
    python validation\\v_l3b_coefficient_ratio.py

THE QUESTION
    L3 found a 2.6% error on ABSOLUTE Voc at 75 C. But the thesis never reports
    an absolute voltage. It reports RATIOS on a single curve:
        the coefficient   = Vmp / Voc
        the loss metric   = (P_gmpp - P_landed) / P_gmpp
    A systematic single-diode error at high temperature moves Vmp and Voc in the
    same direction, because both derive from the same diode voltage terms. So the
    ratio error should be much smaller than the absolute error -- possibly nil.

    That is an ARGUMENT, not evidence. L3b measures it. Same certified data as
    L3, different question asked of it. No new measurement needed.

TOLERANCES -- DECLARED BEFORE RUNNING, NOT AFTER
    Coefficient (Vmp/Voc) error at 75 C, simulated vs certified:
        < 0.005 absolute  ->  IMMATERIAL. The corner does not touch C1 or C3.
                              State this with the number in the limitations text.
        0.005 to 0.010    ->  MINOR. Report it; no change of scope required.
        > 0.010           ->  MATERIAL. A real constraint. Belongs in the
                              limitations section with a stated temperature scope.

    Scope check, independent of the above:
        if under 5% of scenarios sit above 65 C, the corner is also out of scope
        on FREQUENCY grounds, regardless of the error magnitude.

PART 1 (scope) runs now with no configuration.
PART 2 (certified comparison) needs load_certified_matrix() filled in from
       v_l3_offstc.py -- see the marked block below.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gmppt import config, device                      # noqa: E402
from gmppt.device import ModuleParams                 # noqa: E402

HOT_THRESHOLD_C = 65.0
IMMATERIAL = 0.005
MATERIAL = 0.010


# ===========================================================================
# PART 1 -- SCOPE: does the scenario set even reach the corner?
# ===========================================================================

def part1_scope() -> dict:
    """Read the temperature distribution out of the S6 scenario set.

    If the scenarios rarely go near 75 C, the corner is out of scope on
    frequency grounds and the error magnitude matters less. This is a cheap,
    independent line of argument -- worth having even if Part 2 comes back clean.
    """
    print("PART 1  SCOPE -- temperature distribution of the scenario set")
    path = config.RESULTS_DIR / "s6_scenarios.csv"
    if not path.exists():
        print(f"   s6_scenarios.csv not found at {path}")
        print("   Run phase1/s6_scenario_generator.py first, or point at the file.")
        return {}

    df = pd.read_csv(path)
    tcol = next((c for c in df.columns
                 if c.lower() in ("temp_c", "temperature", "t", "tcell", "cell_temp")),
                None)
    if tcol is None:
        print(f"   no temperature column found. Columns are: {list(df.columns)}")
        print("   Tell me which one holds cell temperature and I will patch this.")
        return {}

    t = df[tcol].astype(float)
    hot = float((t > HOT_THRESHOLD_C).mean())
    print(f"   column '{tcol}', n = {len(t)}")
    print(f"   min {t.min():.1f} C   median {t.median():.1f} C   "
          f"mean {t.mean():.1f} C   max {t.max():.1f} C")
    print(f"   p95 {np.percentile(t, 95):.1f} C   p99 {np.percentile(t, 99):.1f} C")
    print(f"   above {HOT_THRESHOLD_C:.0f} C: {hot*100:.1f}% of scenarios")
    print(f"   above 70 C: {(t > 70).mean()*100:.1f}%   "
          f"above 75 C: {(t > 75).mean()*100:.1f}%")

    verdict = ("OUT OF SCOPE on frequency" if hot < 0.05
               else "IN SCOPE -- the corner is reached often enough to matter")
    print(f"   -> {verdict}")
    return {"frac_above_threshold": hot, "max_c": float(t.max())}


# ===========================================================================
# PART 2 -- THE MEASUREMENT: coefficient error vs the certified matrix
# ===========================================================================

# ---------------------------------------------------------------------------
# FILL THIS IN FROM v_l3_offstc.py. It must return a DataFrame with columns:
#     G     irradiance, W/m^2
#     T     cell temperature, C
#     voc   certified open-circuit voltage, V
#     vmp   certified maximum-power voltage, V
# and MODULE_NAME must be the CEC module v_l3 mapped the certified data to.
# Copy the loading logic verbatim from v_l3 -- do not re-derive it, or L3b
# risks reading the sheet differently than L3 did.
# ---------------------------------------------------------------------------

MODULE_NAME = None      # e.g. "Canadian_Solar_Inc__CS6U_310P"


def load_certified_matrix() -> pd.DataFrame:
    raise NotImplementedError(
        "load_certified_matrix() is not filled in yet.\n"
        "   Paste the loader from validation/v_l3_offstc.py: how it reads\n"
        "   data/IEC61853_1-2.xlsx and which CEC module it maps to.\n"
        "   Part 1 above still runs and is already informative."
    )


def simulate_coefficient(mp, G: float, T: float) -> tuple[float, float, float]:
    """Uniform (unshaded) curve at one grid point -> (voc, vmp, coeff).

    Uniform irradiance is correct here: the certified IEC 61853 matrix is
    measured unshaded, so this compares like with like. Breakdown is irrelevant
    with no shading, so bd is left at its default.
    """
    irr = [float(G)] * int(config.N_SUBSTRINGS)
    c = device.module_iv(mp, irr, float(T))
    a = device.analyse(c)
    V = np.asarray(c["V"], float)
    P = np.asarray(c["P"], float)
    order = np.argsort(V)
    V, P = V[order], P[order]
    voc = float(V[-1])
    gm = a["gmpp"]
    vmp = float(gm["V"]) if "V" in gm else float(V[int(np.argmax(P))])
    return voc, vmp, (vmp / voc if voc else float("nan"))


def part2_coefficient_error() -> dict:
    print("\nPART 2  COEFFICIENT ERROR vs certified IEC 61853 matrix")
    cert = load_certified_matrix()
    if MODULE_NAME is None:
        raise ValueError("MODULE_NAME is not set -- take it from v_l3_offstc.py")

    mp = ModuleParams.from_cec(MODULE_NAME)
    print(f"   module: {MODULE_NAME}")
    print(f"   grid points: {len(cert)}")

    rows = []
    for _, r in cert.iterrows():
        G, T = float(r["G"]), float(r["T"])
        cert_coeff = float(r["vmp"]) / float(r["voc"])
        sim_voc, sim_vmp, sim_coeff = simulate_coefficient(mp, G, T)
        rows.append({
            "G": G, "T": T,
            "cert_voc": float(r["voc"]), "sim_voc": sim_voc,
            "voc_err_pct": 100 * (sim_voc - float(r["voc"])) / float(r["voc"]),
            "cert_coeff": cert_coeff, "sim_coeff": sim_coeff,
            "coeff_err": sim_coeff - cert_coeff,
        })
    out = pd.DataFrame(rows)

    print(f"\n   {'G':>6} {'T':>6} {'cert k':>8} {'sim k':>8} "
          f"{'k err':>9} {'Voc err %':>10}")
    for _, r in out.sort_values(["T", "G"]).iterrows():
        print(f"   {r['G']:>6.0f} {r['T']:>6.0f} {r['cert_coeff']:>8.4f} "
              f"{r['sim_coeff']:>8.4f} {r['coeff_err']:>9.4f} "
              f"{r['voc_err_pct']:>10.2f}")

    abs_k = out["coeff_err"].abs()
    hot = out[out["T"] >= 70]
    hot_k = hot["coeff_err"].abs() if len(hot) else pd.Series(dtype=float)

    print(f"\n   coefficient error, whole grid : mean {abs_k.mean():.4f}   "
          f"max {abs_k.max():.4f}")
    if len(hot_k):
        print(f"   coefficient error, T >= 70 C  : mean {hot_k.mean():.4f}   "
              f"max {hot_k.max():.4f}")
        print(f"   Voc error,         T >= 70 C  : max "
              f"{hot['voc_err_pct'].abs().max():.2f}%  (L3 reported ~2.6%)")
    else:
        print("   no grid points at or above 70 C -- corner not covered by "
              "the certified matrix")

    worst_hot = float(hot_k.max()) if len(hot_k) else float(abs_k.max())
    if worst_hot < IMMATERIAL:
        verdict = "IMMATERIAL -- the corner does not affect C1 or C3"
    elif worst_hot < MATERIAL:
        verdict = "MINOR -- report the number, no scope change needed"
    else:
        verdict = "MATERIAL -- state a temperature scope in the limitations"
    print(f"\n   worst coefficient error at the corner: {worst_hot:.4f}")
    print(f"   -> {verdict}")

    out.to_csv(config.RESULTS_DIR / "l3b_coefficient_ratio.csv", index=False)
    print(f"   per-point table -> results/l3b_coefficient_ratio.csv")
    return {"worst_hot_coeff_err": worst_hot, "verdict": verdict}


if __name__ == "__main__":
    print("L3b  Does the 75 C corner weakness reach the reported quantities?")
    try:
        print("  " + config.provenance())
    except Exception:
        pass
    print("=" * 70)
    print(f"tolerances declared in advance: immaterial < {IMMATERIAL}, "
          f"material > {MATERIAL}\n")

    scope = part1_scope()

    try:
        part2_coefficient_error()
    except NotImplementedError as e:
        print(f"\nPART 2  NOT YET CONFIGURED\n   {e}")
    print("\n" + "=" * 70)
    print("L3b complete." if scope else "L3b partial.")