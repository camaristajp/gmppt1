"""
S1 - CEC coefficient characterisation (simulator-INDEPENDENT).

Reads V_mp_ref / V_oc_ref straight from the CEC database. No device model is
run here, so this result does not depend on anything built later in Phase 1.
It reproduces the Section 4 preliminary figure and is the first sanity check
on the C1 premise (the STC coefficient is already spread widely around 0.8).

Two populations are reported and they play different roles:

  * FULL CATALOGUE (all technologies, N=21,535). This is the Section 4 headline
    figure (0.633-0.874, mean 0.810, s.d. 0.017). It is reported to show the
    preliminary premise reproduces exactly, but it includes thin-film / CdTe /
    CIGS parts that are out of scope (Section 8.2).

  * c-Si SUBSET (Mono + Multi, N=20,946). This is the study's in-scope
    population and the one saved to disk as the module pool. Every downstream
    step (S2 span, S3 canonical module, S6 held-out modules) draws from this
    file, so filtering to c-Si HERE - at pool construction - is what stops an
    out-of-scope technology from leaking into a later held-out set.

Section 4 targets to reproduce (full catalogue):
    V_mp/V_oc at STC across CEC:  0.633-0.874, mean 0.810, s.d. 0.017
    Modules within +/-0.01 of 0.80:  40.3%
    N = 21535
"""
import numpy as np
import pandas as pd
from pvlib import pvsystem

from gmppt import config


def load_cec():
    """Full CEC catalogue, all technologies, with the fields Phase 1 needs.

    No technology filter here: the caller reports the full-catalogue statistics
    (the Section 4 headline) before the c-Si filter is applied for the pool.
    """
    cec = pvsystem.retrieve_sam("CECMod").T  # rows = modules
    need = ["V_mp_ref", "V_oc_ref", "I_mp_ref", "I_sc_ref", "N_s", "Technology"]
    df = cec[need].copy()
    for c in ["V_mp_ref", "V_oc_ref", "I_mp_ref", "I_sc_ref", "N_s"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["V_mp_ref", "V_oc_ref"])
    df = df[(df["V_oc_ref"] > 0) & (df["V_mp_ref"] > 0)]
    return df


def csi_subset(df):
    """The in-scope c-Si population (Mono + Multi). This is what gets saved."""
    return df[df["Technology"].isin(config.CSI_TECHNOLOGIES)].copy()


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


def _make_figure(ratio, stats, name, title):
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
    ax.set_title(title)
    ax.legend(fontsize=8, loc="upper left")
    return viz.save_fig(fig, name)


if __name__ == "__main__":
    print("S1  CEC V_mp/V_oc characterisation (simulator-independent)")
    print("  " + config.provenance())
    print("=" * 66)

    df_full = load_cec()
    ratio_full, stats_full = characterise(df_full)

    # Guard: the full catalogue must be the size the pins expect. If pvlib ships
    # a different CEC database this number moves and every frozen figure is stale.
    assert stats_full["N"] == config.CEC_ROWS_EXPECTED, (
        f"CEC catalogue has {stats_full['N']} rows, expected "
        f"{config.CEC_ROWS_EXPECTED}. pvlib/CEC database changed; re-freeze the "
        f"population constants in config.py before trusting downstream figures.")

    df_csi = csi_subset(df_full)
    ratio_csi, stats_csi = characterise(df_csi)

    print("\n  FULL CATALOGUE (all technologies) -- Section 4 headline:")
    for k, v in stats_full.items():
        print(f"    {k:28s} {v}")
    print("    Section 4 target: 0.633-0.874, mean 0.810, sd 0.017, "
          "40.3% within +/-0.01, N=21535")

    print("\n  c-Si SUBSET (Mono + Multi) -- in-scope population, saved to pool:")
    for k, v in stats_csi.items():
        print(f"    {k:28s} {v}")
    print(f"    config expects: N={config.CSI_POOL_N}, mean "
          f"{config.CSI_COEFF_MEAN}, sd {config.CSI_COEFF_SD}, "
          f"range {config.CSI_COEFF_RANGE}")

    # Save the c-Si pool (in-scope population) for later steps.
    df_csi = df_csi.assign(vmp_voc=ratio_csi)
    df_csi.to_parquet(config.CEC_POOL)
    print(f"\n  Saved c-Si module pool ({len(df_csi):,} modules) -> "
          f"{config.CEC_POOL.relative_to(config.PROJECT_ROOT)}")

    # Two figures: the full-catalogue premise and the in-scope c-Si distribution.
    p_full = _make_figure(
        ratio_full, stats_full, "s1_coefficient_spread",
        f"CEC coefficient spread, all technologies ({stats_full['N']:,} modules)")
    p_csi = _make_figure(
        ratio_csi, stats_csi, "s1_coefficient_spread_csi",
        f"CEC coefficient spread, c-Si only ({stats_csi['N']:,} modules)")
    print(f"  Figures -> {p_full.relative_to(config.PROJECT_ROOT)}, "
          f"{p_csi.relative_to(config.PROJECT_ROOT)}")
