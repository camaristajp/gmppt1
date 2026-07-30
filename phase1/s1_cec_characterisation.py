"""
S1 - CEC coefficient characterisation (simulator-INDEPENDENT).

Reads V_mp_ref / V_oc_ref straight from the CEC database. No device model is
run here, so this result does not depend on anything built later in Phase 1.
It reproduces the Section 4 preliminary figure and is the first sanity check
on the C1 premise (the STC coefficient is already spread widely around 0.8).

Section 4 target to reproduce:
    V_mp/V_oc at STC across CEC:  0.633-0.874, mean 0.810, s.d. 0.017
    Modules within +/-0.01 of 0.80:  40.3%
    N = 21535
"""
import numpy as np
import pandas as pd
from pvlib import pvsystem

from gmppt import config


def load_cec():
    cec = pvsystem.retrieve_sam("CECMod").T  # rows = modules
    # Keep only physically sane silicon modules with the fields we need
    need = ["V_mp_ref", "V_oc_ref", "I_mp_ref", "I_sc_ref", "N_s", "Technology"]
    df = cec[need].copy()
    for c in ["V_mp_ref", "V_oc_ref", "I_mp_ref", "I_sc_ref", "N_s"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["V_mp_ref", "V_oc_ref"])
    df = df[(df["V_oc_ref"] > 0) & (df["V_mp_ref"] > 0)]
    return df


def characterise(df):
    ratio = df["V_mp_ref"] / df["V_oc_ref"]
    stats = {
        "N": int(len(ratio)),
        "min": float(ratio.min()),
        "max": float(ratio.max()),
        "mean": float(ratio.mean()),
        "sd": float(ratio.std(ddof=0)),
        "pct_within_0.01_of_0.80": float((ratio.sub(0.80).abs() <= 0.01).mean() * 100),
    }
    return ratio, stats


if __name__ == "__main__":
    df = load_cec()
    ratio, stats = characterise(df)
    print("S1  CEC V_mp/V_oc characterisation (simulator-independent)")
    print("-" * 60)
    for k, v in stats.items():
        print(f"  {k:28s} {v}")

    print("\n  Section 4 targets: range 0.633-0.874, mean 0.810, sd 0.017, "
          "40.3% within +/-0.01, N=21535")

    # Save the stratified module pool for later steps (span the ratio range)
    df = df.assign(vmp_voc=ratio)
    df.to_parquet(config.CEC_POOL)
    print(f"\n  Saved module pool -> {config.CEC_POOL.relative_to(config.PROJECT_ROOT)}")

    # Figure: the coefficient spread (the C1 premise)
    from gmppt import viz
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(6.4, 3.6))
    ax.hist(ratio, bins=120, color=viz.BLUE, alpha=0.85)
    ax.axvspan(0.79, 0.81, color=viz.GRAY, alpha=0.25,
               label=f"within ±0.01 of 0.80 ({stats['pct_within_0.01_of_0.80']:.1f}%)")
    ax.axvline(0.80, color=viz.GRAY, lw=1.2, ls="--", label="conventional 0.80")
    ax.axvline(stats["mean"], color=viz.ORANGE, lw=1.5,
               label=f"population mean {stats['mean']:.3f}")
    ax.set_xlabel("STC coefficient  V$_{mp}$/V$_{oc}$")
    ax.set_ylabel("modules")
    ax.set_title(f"CEC coefficient spread across {stats['N']:,} modules")
    ax.legend(fontsize=8, loc="upper left")
    path = viz.save_fig(fig, "s1_coefficient_spread")
    print(f"  Figure -> {path.relative_to(config.PROJECT_ROOT)}")

