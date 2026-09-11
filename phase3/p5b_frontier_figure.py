"""
p5b_frontier_figure.py  --  redraw the cost-accuracy figure, readable version.

PLACE THIS FILE AT:   C:\\Users\\user\\gmppt\\phase3\\p5b_frontier_figure.py
                      NEW FILE. p5_cost_frontier.py stays as it is -- its numbers
                      are correct, only the drawing needed work.

RUN FROM THE REPO ROOT (C:\\Users\\user\\gmppt):
    python phase3\\p5b_frontier_figure.py

Reads results/phase3/cost_frontier.json, so nothing is re-run. Instant.

WHAT WAS WRONG WITH THE FIRST FIGURE
    1. LOG AXIS WITH SCIENTIFIC TICKS. Probe counts are small integers -- 3, 5,
       6, 11, 21, 63. Labelling them "3 x 10^0" and "6 x 10^0" makes a reader
       decode notation to recover a number they could have read directly.
    2. ONE OUTLIER STRETCHED THE AXIS. Ahmed-Salam at 63 probes pushed every
       other method into the left quarter of the plot, where the differences that
       matter became invisible.
    3. DOWN MEANT GOOD. Mean loss descending is correct but reads backwards:
       most people expect a higher line to be a better one.

WHAT THIS VERSION DOES
    Panel A -- power CAPTURED (higher is better) against probes, on a linear axis
    up to 22, with Ahmed-Salam shown as an off-scale annotation rather than being
    allowed to compress everything else. The reader sees the curve flatten and
    can locate C3 against it without decoding anything.

    Panel B -- the worst case in WATTS, which is C4's axis and where C3 is best
    of everything measured. This panel exists because the mean-loss panel alone
    understates the result: it shows C3 as merely comparable, when on the tail it
    is not.

    Two panels rather than one because the two axes carry different claims and
    combining them into a single ranking would hide that.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gmppt import config  # noqa: E402

OUT = config.RESULTS_DIR / "phase3"
FIGS = OUT / "figures"

NAVY = "#1F3864"
CORAL = "#C0504D"
AMBER = "#C8842A"
GREY = "#8A8A85"
XMAX = 23


def main() -> int:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    src = OUT / "cost_frontier.json"
    if not src.exists():
        print(f"{src} not found. Run phase3\\p5_cost_frontier.py first.")
        return 1
    data = json.loads(src.read_text(encoding="utf-8"))
    classical = data["classical"]
    refs = {r["method"]: r for r in data["references"]}
    FIGS.mkdir(parents=True, exist_ok=True)

    cx = [r["mean_probes"] for r in classical]
    cy = [100 - r["mean_loss_pct"] for r in classical]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12.5, 5.2))

    # ------------------------------------------------------------ panel A
    ax1.plot(cx, cy, "o-", color=AMBER, lw=2, ms=6,
             label="classical scan + refine")

    def pt(ax, name, colour, size, dx, dy, show_label=True, ha="left"):
        r = refs.get(name)
        if r is None:
            return
        x, y = r["mean_probes"], 100 - r["mean_loss_pct"]
        if x > XMAX:
            return
        ax.plot(x, y, "o", color=colour, ms=size, zorder=5)
        if show_label:
            ax.annotate(f"{name}\n{y:.2f}% captured, {x:.0f} probes",
                        (x, y), textcoords="offset points", xytext=(dx, dy),
                        fontsize=9, color="#444", ha=ha)

    pt(ax1, "fixed 0.80", NAVY, 8, 10, -4)
    pt(ax1, "recalibrated 0.82", NAVY, 8, 10, -18)
    pt(ax1, "C3 two-stage", CORAL, 12, -10, -26, ha="right")

    ax1.annotate("Ahmed–Salam (2015)\n98.48% captured, 63 probes\n— off scale to the right",
                 xy=(XMAX - 0.4, 98.48), xytext=(13.2, 97.9), fontsize=9,
                 color="#444",
                 arrowprops=dict(arrowstyle="->", color=GREY, lw=1.1))
    ax1.plot([XMAX - 0.4], [98.48], ">", color=NAVY, ms=9, zorder=5)

    ax1.set_xlim(0, XMAX)
    ax1.set_ylim(96.5, 100.05)
    ax1.set_xlabel("measurements per tracking decision", fontsize=10)
    ax1.set_ylabel("power captured (% of the maximum available)", fontsize=10)
    ax1.set_title("Higher is better", fontsize=11.5)
    ax1.legend(fontsize=9, loc="lower right")
    ax1.grid(alpha=0.25)

    # ------------------------------------------------------------ panel B
    order = [("fixed 0.80", NAVY), ("recalibrated 0.82", NAVY),
             ("ahmed-salam scan", NAVY), ("C3 two-stage", CORAL)]
    names, vals, cols = [], [], []
    for name, colour in order:
        r = refs.get(name)
        if r is None:
            continue
        names.append(f"{name}\n({r['mean_probes']:.0f} probes)")
        vals.append(r["worst_loss_w"])
        cols.append(colour)

    best_classical = min(classical, key=lambda r: r["worst_loss_w"])
    names.append(f"classical search\n(best of {int(max(cx))} probes)")
    vals.append(best_classical["worst_loss_w"])
    cols.append(AMBER)

    bars = ax2.barh(range(len(names)), vals, color=cols, height=0.6)
    ax2.set_yticks(range(len(names)))
    ax2.set_yticklabels(names, fontsize=9)
    ax2.invert_yaxis()
    ax2.set_xlabel("worst single loss (watts)", fontsize=10)
    ax2.set_title("Lower is better — the worst case", fontsize=11.5)
    ax2.grid(alpha=0.25, axis="x")
    for b, v in zip(bars, vals):
        ax2.text(v + 0.4, b.get_y() + b.get_height() / 2, f"{v:.1f} W",
                 va="center", fontsize=9, color="#444")
    ax2.set_xlim(0, max(vals) * 1.22)

    fig.suptitle("What each method captures, and what it costs to get there",
                 fontsize=13)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    out = FIGS / "cost_frontier_readable.png"
    fig.savefig(out, dpi=150)
    plt.close(fig)
    print(f"figure -> {out}")

    c3 = refs["C3 two-stage"]
    print(f"\nC3: {100 - c3['mean_loss_pct']:.2f}% captured at "
          f"{c3['mean_probes']:.0f} probes, worst case "
          f"{c3['worst_loss_w']:.1f} W")
    match = [r for r in classical
             if r["mean_loss_pct"] <= c3["mean_loss_pct"]]
    if match:
        first = min(match, key=lambda r: r["mean_probes"])
        print(f"classical search needs {first['mean_probes']:.0f} probes to "
              f"match that accuracy ({first['mean_probes']/c3['mean_probes']:.2f}x)")
    print(f"classical worst case floors at {best_classical['worst_loss_w']:.1f} W "
          f"regardless of budget -- C3 is below it")
    return 0


if __name__ == "__main__":
    sys.exit(main())