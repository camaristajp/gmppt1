"""
S7 - GMPP labelling and sweep-resolution convergence (Stage 4, step 2).

The labelling itself (find the true global peak, record the implied coefficient)
is performed by scenarios.evaluate_scenario and was exercised across all 2000
scenarios in S6. S7's distinct job is to VERIFY that labelling is trustworthy:
that the recorded GMPP does not depend on the sweep resolution.

Plan / WORKFLOW S7 checkpoint (verbatim): "dense sweep converged (halving the
step size does not change the recorded GMPP)." If the sweep is too coarse, a
peak is located at slightly the wrong voltage and every coefficient in S8
inherits that error silently. This step rules that out before S8 characterises
the distribution.

Checkpoints:
  1. RESOLUTION CONVERGENCE - on a seeded sample of scenarios, the GMPP voltage
     and power are stable when the sweep resolution is halved and doubled about
     the default (2000 / 4000 / 8000 points). "Stable" = GMPP voltage within a
     small tolerance and power within a small fraction, at every resolution.
  2. COEFFICIENT STABILITY - the implied coefficient (gmpp_V / Voc) is unchanged
     to 3 decimals across resolutions, since that coefficient is the S8 label.
  3. PEAK-COUNT STABILITY - analyse() reports the same number of peaks at each
     resolution (a coarse grid can merge or invent peaks).
"""
import numpy as np
import pandas as pd

from gmppt import config, device, scenarios
from gmppt.device import ModuleParams

RESOLUTIONS = (2000, 4000, 8000)   # halve / default / double
SAMPLE = 120                        # seeded sample of scenarios to test
V_TOL = 0.10                        # GMPP voltage tolerance (V)
P_TOL_FRAC = 0.002                  # GMPP power tolerance (fraction)
COEFF_DECIMALS = 3                  # coefficient must match to this many decimals


def _gmpp_at(mp, scenario, n_points):
    c = device.module_iv(mp, scenario.irradiances, scenario.temp_c,
                         n_points=n_points)
    a = device.analyse(c)
    return dict(V=a["gmpp"]["V"], P=a["gmpp"]["P"], voc=float(c["V"].max()),
                n_peaks=a["n_peaks"])


def check_resolution_convergence(pool):
    print("1-3) SWEEP-RESOLUTION CONVERGENCE")
    print(f"     resolutions {RESOLUTIONS} points, on {SAMPLE} seeded scenarios")
    scen = scenarios.generate(pool, SAMPLE)
    rng = np.random.default_rng(config.seed_for("s7_sample"))

    worst_dV = 0.0
    worst_dP = 0.0
    worst_dcoeff = 0.0
    peak_mismatch = 0
    ref_res = RESOLUTIONS[1]   # compare against the default 4000

    for s in scen:
        mp = ModuleParams.from_cec(s.module)
        vals = {r: _gmpp_at(mp, s, r) for r in RESOLUTIONS}
        ref = vals[ref_res]
        for r in RESOLUTIONS:
            v = vals[r]
            worst_dV = max(worst_dV, abs(v["V"] - ref["V"]))
            worst_dP = max(worst_dP, abs(v["P"] - ref["P"]) / max(ref["P"], 1e-9))
            c_r = v["V"] / v["voc"] if v["voc"] > 0 else 0.0
            c_ref = ref["V"] / ref["voc"] if ref["voc"] > 0 else 0.0
            worst_dcoeff = max(worst_dcoeff, abs(c_r - c_ref))
            if v["n_peaks"] != ref["n_peaks"]:
                peak_mismatch += 1

    v_ok = worst_dV < V_TOL
    p_ok = worst_dP < P_TOL_FRAC
    c_ok = worst_dcoeff < 10 ** (-COEFF_DECIMALS)
    pk_ok = peak_mismatch == 0

    print(f"     worst GMPP voltage drift : {worst_dV:.4f} V   "
          f"(< {V_TOL} V: {v_ok})")
    print(f"     worst GMPP power drift   : {worst_dP*100:.4f} %   "
          f"(< {P_TOL_FRAC*100:.1f} %: {p_ok})")
    print(f"     worst coefficient drift  : {worst_dcoeff:.5f}   "
          f"(< {10**(-COEFF_DECIMALS)}: {c_ok})")
    print(f"     peak-count mismatches    : {peak_mismatch} of "
          f"{SAMPLE*len(RESOLUTIONS)}   ({pk_ok})")
    ok = v_ok and p_ok and c_ok and pk_ok
    print(f"     dense sweep converged: {'OK' if ok else 'FAIL'}")
    return ok, dict(worst_dV=worst_dV, worst_dP=worst_dP,
                    worst_dcoeff=worst_dcoeff, peak_mismatch=peak_mismatch)


if __name__ == "__main__":
    print("S7  GMPP labelling — sweep-resolution convergence")
    print("  " + config.provenance())
    print("=" * 66)
    pool = pd.read_parquet(config.CEC_POOL)

    ok, stats = check_resolution_convergence(pool)

    pd.DataFrame([stats]).to_csv(
        config.RESULTS_DIR / "s7_resolution_convergence.csv", index=False)
    print(f"\n   stats -> results/s7_resolution_convergence.csv")

    print("\n" + "=" * 66)
    print(f"S7 checkpoint: {'PASS' if ok else 'FAIL'}  "
          f"(dense-sweep GMPP invariant to resolution)")
    print("  The GMPP labels (and the coefficients derived from them) are")
    print("  resolution-independent, so the S8 distribution rests on accurate")
    print("  peak locations, not on a sweep-grid artefact.")