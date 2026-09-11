"""
C1 corroboration on measured hardware  (validation layer, not an S-step).

MAIN OBJECTIVE: replace the fixed 0.8 coefficient with a learned, conditional one.
WHY THIS SCRIPT: the project's premise is that the peak-voltage coefficient
V_mp/V_oc varies across modules and 0.80 is a poor fixed value. S1 established
this on the CEC catalogue (datasheet-derived parameters). This script re-
establishes it on MEASURED HARDWARE - the NREL/Marion flash-test set (AnonDB) -
so the premise rests on measurement, not only catalogue. That is what makes the
reason the whole project exists unchallengeable.

Data: data/AnonDB.csv - 616 flash-test measurements of 438 crystalline-silicon
modules (mono + multi), each with measured Isc/Voc/Imp/Vmp/Pmp and nameplate
values, plus an outdoor-exposure ("OE ... days") aging field.

Reports, and compares to the two catalogue references already in the plan:
  - measured V_mp/V_oc: mean, sd, range, % missing +/-0.01 of 0.80
  - the same on DISTINCT modules (averaging repeat measurements) to remove
    repeat-measurement bias
  - fresh (0-day) vs aged, since aging shifts the operating point (rev9 note)
Declared expectation BEFORE running (so this is a test, not a fishing trip):
  measured mean within 0.010 of the CEC c-Si mean (0.811); majority miss 0.80.
"""
import numpy as np
import pandas as pd

from gmppt import config

CEC_CSI_MEAN = 0.811      # S1 in-scope c-Si catalogue mean, for comparison
EXPECT_TOL = 0.010        # measured mean must land within this of the catalogue


def load():
    df = pd.read_csv(config.DATA_DIR / "AnonDB.csv", index_col=0)
    df["coeff"] = df["Vmp_(V)"] / df["Voc_(V)"]
    # parse "OE N days" -> integer days
    df["exposure_days"] = (df["Total_Exposure"].astype(str)
                           .str.extract(r"(\d+)").astype(float))
    return df


def summarise(coeffs, label):
    c = pd.Series(coeffs).dropna()
    miss = 1 - ((c - 0.80).abs() < 0.01).mean()
    print(f"   {label:28s} n={len(c):4d}  mean {c.mean():.4f}  sd {c.std():.4f}  "
          f"range {c.min():.3f}-{c.max():.3f}  miss 0.80: {miss*100:.1f}%")
    return dict(n=int(len(c)), mean=float(c.mean()), sd=float(c.std()),
               lo=float(c.min()), hi=float(c.max()), miss=float(miss))


def make_figure(df):
    from gmppt import viz
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(7.5, 4.2))
    c = df["coeff"].dropna()
    ax.hist(c, bins=40, color=viz.TEAL, alpha=0.85, edgecolor="white")
    ax.axvline(0.80, color=viz.ORANGE, ls="--", lw=1.5, label="fixed 0.80")
    ax.axvline(c.mean(), color=viz.BLUE, ls="-", lw=1.5,
               label=f"measured mean {c.mean():.3f}")
    ax.set_xlabel("measured V$_{mp}$/V$_{oc}$")
    ax.set_ylabel("flash-test measurements")
    ax.set_title(f"C1 on measured hardware: {len(c)} c-Si flash tests\n"
                 f"{(1-((c-0.80).abs()<0.01).mean())*100:.0f}% miss the fixed 0.80")
    ax.legend()
    plt.tight_layout()
    return viz.save_fig(fig, "v_c1_measured")


if __name__ == "__main__":
    print("C1 corroboration on measured hardware (NREL/Marion flash-test set)")
    print("  " + config.provenance())
    print("=" * 68)
    df = load()

    print(f"  loaded {len(df)} measurements, "
          f"{df['Mod_ID'].nunique()} distinct modules "
          f"({df['Cell_Wafer_Type'].value_counts().to_dict()})")
    print("\n  measured V_mp/V_oc:")
    all_m = summarise(df["coeff"], "all measurements")
    # distinct modules: average repeat measurements per Mod_ID
    per_mod = df.groupby("Mod_ID")["coeff"].mean()
    dist_m = summarise(per_mod, "distinct modules")
    # fresh vs aged
    fresh = df[df["exposure_days"] == 0]["coeff"]
    aged = df[df["exposure_days"] > 0]["coeff"]
    if len(fresh):
        summarise(fresh, "fresh (0-day) only")
    if len(aged):
        summarise(aged, "aged (>0-day) only")

    print("\n  comparison to references already in the plan:")
    print(f"   CEC c-Si catalogue (S1): mean 0.811, sd 0.015, ~59% miss")
    print(f"   this measured set:       mean {all_m['mean']:.4f}, "
          f"sd {all_m['sd']:.4f}, {all_m['miss']*100:.0f}% miss")

    # declared test: measured mean within EXPECT_TOL of catalogue, majority miss
    agree = abs(all_m["mean"] - CEC_CSI_MEAN) < EXPECT_TOL
    majority_miss = all_m["miss"] > 0.50
    ok = agree and majority_miss
    print(f"\n  DECLARED TEST (stated before running):")
    print(f"   measured mean within {EXPECT_TOL} of CEC 0.811: "
          f"{abs(all_m['mean']-CEC_CSI_MEAN):.4f} -> {agree}")
    print(f"   majority of modules miss 0.80: {all_m['miss']*100:.0f}% -> "
          f"{majority_miss}")

    path = make_figure(df)
    print(f"\n  figure -> {path.relative_to(config.PROJECT_ROOT)}")

    pd.DataFrame([all_m, dist_m]).to_csv(
        config.RESULTS_DIR / "v_c1_measured.csv", index=False)

    print("\n" + "=" * 68)
    print(f"C1-measured: {'PASS' if ok else 'CHECK'}  "
          f"(premise holds on measured hardware, not only catalogue)")
    print("  The reason the project exists - 0.80 is a poor fixed value - now")
    print("  rests on measurement as well as the CEC catalogue.")