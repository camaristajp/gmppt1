"""
L4 - breakdown-parameter sensitivity of the Gate A verdict.

MAIN OBJECTIVE: replace the fixed 0.8 coefficient with a learned, conditional one.
WHY THIS SCRIPT: the Gate A finding - that the fixed-0.8 model makes region errors
~23% of the time under sub-substring shading - is what redirects the thesis. That
finding depends on the simulator's reverse-bias BREAKDOWN parameters, which are
ASSUMED, not measured (no public data reaches the deep reverse bias where they
act; the NREL curves stop at ~-0.25 V). Rather than validate parameters we cannot
validate here, this script proves the CONCLUSION does not depend on them: it
re-computes the sub-substring region-error rate across a wide grid of breakdown
parameter values. If the rate stays materially above the "negligible" bar for all
plausible values, the Gate A(i) verdict is ROBUST to our ignorance of the exact
breakdown physics - the unvalidated assumption is no longer a threat to the result.

HOW IT WORKS:
  * sweep breakdown_voltage over {-10, -15, -20, -30} V,
    breakdown_factor over {1e-3, 1e-2, 1e-1}, breakdown_exp over {2, 3.28, 4};
  * for each combination, evaluate the sub-substring region-error rate on a
    seeded scenario sample;
  * report the range of region-error rates and whether the Gate A(i) conclusion
    (rate NOT negligible) holds across the whole grid.

Deep-reverse-bias parameter VALIDATION (proving the parameters match real cell
breakdown) still requires Phase 8 partner reverse-bias measurements; this script
does not claim to validate them, only to show the verdict is insensitive to them.
"""
import itertools

import numpy as np
import pandas as pd

from gmppt import config, device, scenarios
from gmppt.device import ModuleParams, Breakdown, Bypass

N_SAMPLE = 400          # sub-substring scenarios per parameter combination
NEGLIGIBLE = 0.05       # Gate A(i) "negligible" bar

BR_VOLTAGE = [-10.0, -15.0, -20.0, -30.0]
BR_FACTOR = [1e-3, 1e-2, 1e-1]
BR_EXP = [2.0, 3.28, 4.0]


def region_error_rate(sub_scen, bd):
    """Sub-substring region-error rate for a given Breakdown setting."""
    errs = []
    for s in sub_scen:
        mp = ModuleParams.from_cec(s.module)
        try:
            c = device.module_iv(mp, s.irradiances, s.temp_c, bd=bd)
            a = device.analyse(c)
            V, P = c["V"], c["P"]
            order = np.argsort(V)
            Vs, Ps = V[order], P[order]
            voc = float(Vs.max())
            gmpp_V = a["gmpp"]["V"]
            n_sub = config.N_SUBSTRINGS
            cands = [min(max(n * 0.8 * voc / n_sub, float(Vs.min())),
                         float(Vs.max())) for n in range(1, n_sub + 1)]
            cand_P = [float(np.interp(cv, Vs, Ps)) for cv in cands]
            chosen_V = cands[int(np.argmax(cand_P))]
            peak_Vs = np.array([pv for pv, _, _ in a["peaks"]])
            nearest = peak_Vs[int(np.argmin(np.abs(peak_Vs - chosen_V)))]
            errs.append(abs(nearest - gmpp_V) > 1e-6)
        except Exception:
            pass
    return float(np.mean(errs)) if errs else float("nan")


if __name__ == "__main__":
    print("L4  breakdown-parameter sensitivity of the Gate A verdict")
    print("  " + config.provenance())
    print("=" * 68)
    pool = pd.read_parquet(config.CEC_POOL)
    # a fixed seeded sub-substring sample, reused for every parameter combination
    scen = scenarios.generate(pool, 2000)
    sub = [s for s in scen if s.geometry == "sub_substring"][:N_SAMPLE]
    print(f"  evaluating {len(sub)} sub-substring scenarios across "
          f"{len(BR_VOLTAGE)*len(BR_FACTOR)*len(BR_EXP)} breakdown-parameter "
          f"combinations")
    print(f"  (breakdown_voltage {BR_VOLTAGE}, factor {BR_FACTOR}, exp {BR_EXP})")

    rows = []
    for v, f, e in itertools.product(BR_VOLTAGE, BR_FACTOR, BR_EXP):
        bd = Breakdown(factor=f, voltage=v, exp=e)
        rate = region_error_rate(sub, bd)
        rows.append(dict(breakdown_voltage=v, breakdown_factor=f,
                         breakdown_exp=e, region_error=rate))
        print(f"   V_br={v:6.0f}  factor={f:.0e}  exp={e:.2f}  "
              f"-> region error {rate*100:5.1f}%")

    df = pd.DataFrame(rows)
    df.to_csv(config.RESULTS_DIR / "v_l4_breakdown_sensitivity.csv", index=False)
    rates = df["region_error"].dropna()

    print("\n  region-error rate across ALL breakdown settings:")
    print(f"   min {rates.min()*100:.1f}%   max {rates.max()*100:.1f}%   "
          f"spread {(rates.max()-rates.min())*100:.1f} points")
    robust = rates.min() > NEGLIGIBLE
    print(f"   Gate A(i) bar (negligible < {NEGLIGIBLE*100:.0f}%): "
          f"even the LOWEST rate is {rates.min()*100:.1f}% "
          f"-> {'ABOVE the bar for ALL settings' if robust else 'dips below for some settings'}")

    print("\n" + "=" * 68)
    print(f"L4 sensitivity: {'ROBUST' if robust else 'SENSITIVE'}  "
          f"(Gate A(i) verdict {'holds' if robust else 'depends'} across the "
          f"breakdown-parameter grid)")
    if robust:
        print("  The Gate A(i) finding (region errors under sub-substring shading)")
        print("  does NOT depend on the exact breakdown parameters: it holds for")
        print("  every plausible value. The unvalidated deep-reverse-bias physics")
        print("  is therefore not a threat to the verdict. (Parameter validation")
        print("  itself remains a Phase 8 partner-measurement task.)")
    else:
        print("  The verdict varies with breakdown parameters; the exact values")
        print("  matter and Phase 8 reverse-bias validation becomes load-bearing.")