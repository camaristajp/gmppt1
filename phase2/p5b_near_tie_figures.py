"""
p5b_near_tie_figures.py  --  regenerate the near-tie figures, corrected.

PLACE THIS FILE AT:   C:\\Users\\user\\gmppt\\phase2\\p5b_near_tie_figures.py
                      NEW FILE. p5_near_tie_screen.py stays as it is -- its
                      numbers are correct and do not need re-running.

RUN FROM THE REPO ROOT (C:\\Users\\user\\gmppt):
    python phase2\\p5b_near_tie_figures.py

It reads results/phase2/near_tie_screen.json, so the screen is NOT re-run. Only
the four example curves are recomputed (a few seconds), because the JSON stores
peak coordinates rather than whole curves.

WHAT WAS WRONG WITH THE FIRST FIGURES

  1. TITLE COLLISION. The "N V apart" annotation was drawn at 1.09x the peak
     power, which is above the axes and lands on the subplot title. Fixed by
     adding headroom with set_ylim and placing the annotation inside it.

  2. CLIPPING ARTEFACT. np.clip(gaps, 0, 60) piled every scenario above 60% into
     the last histogram bin, producing a ~130-count spike that looks like a mode
     and is not one. Fixed by plotting the full range and marking the overflow
     bin explicitly where one is needed.

  Neither affected any reported number. Both would be misread by someone seeing
  the figure cold, which is reason enough to fix them before the Month-3 meeting.

WHAT THE FIGURES SHOW (for the caption)

  Figure 1: the four scenarios with the smallest power gap between the top two
  peaks. Gaps of 0.14-0.19% -- the peaks are visually indistinguishable in
  height, yet sit 11-15 V apart. This is the regime Betti et al. flagged, where
  a small modelling error decides the label and moves it a long way.

  Figure 2, right panel: voltage separation clusters near 12 V almost
  independently of the power gap. That is approximately V_oc/3 for these
  modules -- peaks sit at substring boundaries, so a label flip moves the target
  by one substring's worth of voltage rather than an arbitrary amount. The
  displacement is QUANTISED, which is a structural hint for C3: predict which
  substring boundary, then refine within it.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gmppt import config, device  # noqa: E402
from gmppt.device import ModuleParams  # noqa: E402
from gmppt.harness import scenario_set  # noqa: E402

OUT = Path("results/phase2")
FIGS = OUT / "figures"

NAVY, AMBER, CORAL, GREY = "#1F3864", "#C8842A", "#C0504D", "#BBBBBB"


def curve_of(sc):
    mp = ModuleParams.from_cec(sc.module)
    c = device.module_iv(mp, sc.irradiances, sc.temp_c, bd=config.breakdown())
    V = np.asarray(c["V"], float)
    P = np.asarray(c["P"], float)
    order = np.argsort(V)
    return V[order], P[order]


def main() -> int:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    src = OUT / "near_tie_screen.json"
    if not src.exists():
        print(f"ERROR: {src} not found. Run phase2\\p5_near_tie_screen.py first.")
        return 1

    data = json.loads(src.read_text(encoding="utf-8"))
    rows = data["rows"]
    FIGS.mkdir(parents=True, exist_ok=True)

    scenarios = scenario_set(2000)
    print(f"loaded {len(rows)} screened scenarios")

    # ---------------------------------------------------------------- fig 1
    cand = [r for r in rows
            if r["n_peaks"] >= 2 and np.isfinite(r.get("alt_v", np.nan))]
    cand = sorted(cand, key=lambda r: r["gap"])[:4]

    fig, axes = plt.subplots(2, 2, figsize=(11.5, 8))
    for ax, r in zip(axes.ravel(), cand):
        sc = scenarios[int(r["idx"])]
        V, P = curve_of(sc)
        top = max(r["p_gmpp"], r["alt_p"])

        ax.plot(V, P, color=NAVY, lw=1.7)
        ax.plot(r["v_gmpp"], r["p_gmpp"], "o", color=CORAL, ms=10, zorder=5,
                label=f"labelled GMPP  {r['v_gmpp']:.1f} V")
        ax.plot(r["alt_v"], r["alt_p"], "o", color=AMBER, ms=10, zorder=5,
                label=f"rival peak  {r['alt_v']:.1f} V")

        # headroom first, then annotate INSIDE the axes
        lo = min(float(P.min()), 0.0)
        ax.set_ylim(lo, top * 1.28)
        y_arrow = top * 1.13
        ax.annotate("", xy=(r["v_gmpp"], y_arrow), xytext=(r["alt_v"], y_arrow),
                    arrowprops=dict(arrowstyle="<->", color="#777", lw=1.2))
        ax.text((r["v_gmpp"] + r["alt_v"]) / 2, top * 1.17,
                f"{r['dv']:.1f} V apart", ha="center", va="bottom",
                fontsize=9.5, color="#444")

        ax.set_title(f"{r['geometry']}   ·   power gap {100*r['gap']:.2f}%",
                     fontsize=10.5, pad=8)
        ax.set_xlabel("voltage (V)", fontsize=9)
        ax.set_ylabel("power (W)", fontsize=9)
        ax.legend(fontsize=8.5, loc="lower center", framealpha=0.9)
        ax.grid(alpha=0.25)

    fig.suptitle("Closest rival peaks: a negligible power gap, "
                 "a large voltage gap", fontsize=13)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(FIGS / "near_tie_examples.png", dpi=150)
    plt.close(fig)
    print(f"   figure -> {FIGS / 'near_tie_examples.png'}")

    # ---------------------------------------------------------------- fig 2
    multi = [r for r in rows if r["n_peaks"] >= 2]
    gaps = 100 * np.array([r["gap"] for r in multi])
    dvs = np.array([r["dv"] for r in multi])
    near = gaps < 1.0

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11.5, 4.4))

    # full range -- no clipping, so no false spike at the axis limit
    ax1.hist(gaps, bins=np.arange(0, max(gaps.max(), 60) + 2, 2),
             color=NAVY, alpha=0.85)
    ax1.axvline(1.0, color=CORAL, ls="--", lw=1.6,
                label=f"1% near-tie margin  ({near.sum()} scenarios)")
    ax1.set_xlabel("power gap between top two peaks (%)", fontsize=9)
    ax1.set_ylabel("scenarios", fontsize=9)
    ax1.legend(fontsize=8.5)
    ax1.grid(alpha=0.25)
    ax1.set_title("Most peaks are clearly separated", fontsize=10.5)

    ax2.scatter(gaps[~near], dvs[~near], s=9, color=GREY, label="clear")
    ax2.scatter(gaps[near], dvs[near], s=22, color=CORAL, zorder=4,
                label=f"near-tie (<1%), n={near.sum()}")
    med = float(np.median(dvs))
    ax2.axhline(med, color=NAVY, ls=":", lw=1.4,
                label=f"median separation {med:.1f} V  ≈ Voc/3")
    ax2.set_xlabel("power gap between top two peaks (%)", fontsize=9)
    ax2.set_ylabel("voltage separation (V)", fontsize=9)
    ax2.legend(fontsize=8.5, loc="upper right")
    ax2.grid(alpha=0.25)
    ax2.set_title("Separation is quantised at the substring boundary",
                  fontsize=10.5)

    fig.suptitle("How often peaks are near-tied, and how far apart they sit",
                 fontsize=13)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    fig.savefig(FIGS / "near_tie_distribution.png", dpi=150)
    plt.close(fig)
    print(f"   figure -> {FIGS / 'near_tie_distribution.png'}")

    print(f"\n   median voltage separation across all multi-peak scenarios: "
          f"{med:.1f} V")
    print(f"   near-tie scenarios (<1% power gap): {near.sum()} of {len(multi)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())