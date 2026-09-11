"""
p4_ablation_controls.py  --  Phase 3, step 4: is it the model, or the probes?

PLACE THIS FILE AT:   C:\\Users\\user\\gmppt\\phase3\\p4_ablation_controls.py
                      NEW FILE.

RUN FROM THE REPO ROOT (C:\\Users\\user\\gmppt):
    python phase3\\p4_ablation_controls.py

THE QUESTION THIS RUN EXISTS TO ANSWER
    P3.3 measured C3 at 0.28% mean loss on whole-substring validation modules,
    against Ahmed-Salam's 1.52% and the best constant's 2.18%, at 6 probes rather
    than 63.

    A reviewer's first question is not about the model. It is:

        C3 already probes five points on the curve. What happens if you simply
        LAND ON THE BEST OF THOSE FIVE and skip the model entirely?

    The probe schedule sits at 0.20, 0.40, 0.55, 0.70, 0.85 of V_oc. Peaks under
    three-substring shading cluster near 0.27, 0.55 and 0.82. The schedule
    therefore already brackets the peaks, and a naive best-of-five scan might do
    much of the work.

    This is the control that decides which contribution is being claimed:

        naive scan is far behind C3   -> the LEARNING is the contribution
        naive scan is close to C3     -> the PROBE SCHEDULE is the contribution,
                                         and the honest paper is a different one

    Either answer is publishable. Only one of them is the paper currently being
    written, so it has to be measured before any claim leaves this repository.

THE FOUR CONTROLS
    best-of-5 probes        land on the highest of the five feature probes. No
                            model. Same measurement cost as C3's feature step.
    best-of-5 + refine      the same, then a local hill-climb from the winner.
                            Tests whether a classical refinement on top of the
                            schedule matches the learned offset.
    region oracle           the TRUE region, with the model's offset regressor.
                            Upper bound on what stage 2 alone can deliver, and
                            therefore how much of C3 rests on the classifier.
    offset midpoint         the model's region, with the offset fixed at 0.5.
                            The mirror: how much rests on the classifier alone.

    Every control runs through the SAME harness as C3 and the baselines, so probe
    counts are measured rather than asserted and every row is comparable.

DECLARED BEFORE RUNNING
    If best-of-5 (or best-of-5 + refine) comes within 0.30 pt of C3 on
    whole-substring, the learning is NOT carrying the result and the framing must
    change to the probe schedule. If it is more than 1.0 pt behind, the learning
    is doing the work and the C3 claim stands as written. Between the two, both
    contribute and both must be reported.

    This threshold is fixed here, before the run, so the outcome is a test rather
    than an interpretation.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gmppt import baselines, config, datasheet, dataset  # noqa: F401,E402
from gmppt.features import (FEATURE_NAMES, PROBE_FRACTIONS,  # noqa: E402
                            extract_features)
from gmppt.harness import (METHODS, Context, metrics, run_method,  # noqa: E402
                           write_records)
from gmppt.model import TwoStageModel  # noqa: E402
from phase3.p3_final_comparison import scenarios_for_modules  # noqa: E402

OUT = config.RESULTS_DIR / "phase3"
N_SUB = int(config.N_SUBSTRINGS)
GEOMS = ("uniform", "whole_substring", "sub_substring")

CLOSE_PT = 0.30      # naive within this of C3 -> schedule carries the result
CLEAR_PT = 1.00      # naive behind by more than this -> learning carries it


# ---------------------------------------------------------------------------
# CONTROLS
# ---------------------------------------------------------------------------

def m_best_of_probes(ctx: Context) -> float:
    """Land on the highest of the five feature probes. No model.

    The control that matters most. Same probe positions and the same cost as
    C3's feature step, so any gap between this and C3 is attributable to the
    learning rather than to where the probes sit.
    """
    vs = [f * ctx.v_oc for f in PROBE_FRACTIONS]
    return max(vs, key=ctx.probe)


def m_best_of_probes_refine(ctx: Context, steps: int = 6) -> float:
    """Best-of-five, then a local hill-climb from the winner.

    Tests whether a classical refinement on top of the schedule reaches what the
    learned offset regressor reaches. Costs more probes than C3, which is part of
    the comparison.
    """
    vs = [f * ctx.v_oc for f in PROBE_FRACTIONS]
    powers = [ctx.probe(v) for v in vs]
    i = int(np.argmax(powers))
    v = vs[i]
    span = ctx.v_oc / (2.0 * N_SUB)
    best_v, best_p = v, powers[i]
    for _ in range(steps):
        span *= 0.5
        for cand in (best_v - span, best_v + span):
            cand = min(max(cand, 0.02 * ctx.v_oc), ctx.v_oc)
            p = ctx.probe(cand)
            if p > best_p:
                best_v, best_p = cand, p
    return best_v


def make_region_oracle(model: TwoStageModel):
    """True region, model's offset. Upper bound on stage 2 alone.

    The region is read from the scenario's own curve rather than predicted, so
    this is not a buildable method -- it isolates how much of C3 rests on the
    classifier being right.
    """
    from gmppt import device
    from gmppt.device import ModuleParams

    def fn(ctx: Context) -> float:
        temp = ctx.conditions.get("temp_c")
        x = extract_features(ctx.probe, ctx.v_oc, ctx.module,
                             float(temp) if temp is not None
                             else config.STC_TEMPERATURE)
        mp = ModuleParams.from_cec(ctx.module)
        c = device.module_iv(mp, ctx.conditions["irradiances"],
                             ctx.conditions["temp_c"], bd=config.breakdown())
        a = device.analyse(c)
        width = ctx.v_oc / N_SUB
        r = int(min(max(int(float(a["gmpp"]["V"]) // width), 0), N_SUB - 1))
        reg = model.offsets.get(r)
        off = (float(np.clip(reg.predict(x.reshape(1, -1))[0], 0, 1))
               if reg is not None else 0.5)
        v = (r + off) / N_SUB * ctx.v_oc
        ctx.probe(v)
        return v

    fn.__name__ = "region_oracle"
    return fn


def make_offset_midpoint(model: TwoStageModel):
    """Model's region, offset fixed at 0.5. How much rests on the classifier."""
    def fn(ctx: Context) -> float:
        temp = ctx.conditions.get("temp_c")
        x = extract_features(ctx.probe, ctx.v_oc, ctx.module,
                             float(temp) if temp is not None
                             else config.STC_TEMPERATURE)
        r = int(model.classifier.predict(x.reshape(1, -1))[0])
        v = (r + 0.5) / N_SUB * ctx.v_oc
        ctx.probe(v)
        return v

    fn.__name__ = "offset_midpoint"
    return fn


SHOW = [
    ("mean_loss_pct", "mean loss %", "{:.2f}"),
    ("median_loss_pct", "median %", "{:.2f}"),
    ("worst_loss_pct", "worst %", "{:.2f}"),
    ("worst_loss_w", "worst W", "{:.1f}"),
    ("costly_frac_pct", "costly %", "{:.1f}"),
    ("region_error_pct", "region err %", "{:.1f}"),
    ("mean_probes", "probes", "{:.1f}"),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=800)
    args = ap.parse_args()

    print("PHASE 3 / P4  ablation controls -- is it the model, or the probes?")
    try:
        print("  " + config.provenance())
    except Exception:
        pass
    print("=" * 70)
    print(f"declared: naive within {CLOSE_PT} pt of C3 -> the schedule carries")
    print(f"          naive behind by > {CLEAR_PT} pt -> the learning carries")
    print(f"          between -> both contribute, both reported\n")

    try:
        model = TwoStageModel.load()
    except FileNotFoundError:
        print("trained model not found. Run  python -m gmppt.model  first.")
        return 1

    split = dataset.module_split()
    scenarios = scenarios_for_modules(split.val, args.n)
    print(f"{len(scenarios)} scenarios on validation modules")
    print(f"probe schedule: {[f'{f:.2f}' for f in PROBE_FRACTIONS]} of Voc\n")

    runs = [
        ("best-of-5 probes", m_best_of_probes),
        ("best-of-5 + refine", m_best_of_probes_refine),
        ("offset midpoint", make_offset_midpoint(model)),
        ("region oracle [not buildable]", make_region_oracle(model)),
        ("C3 two-stage", model.as_method()),
        ("ahmed-salam scan", METHODS["ahmed_salam_scan"]),
    ]

    geometries = [g for g in GEOMS if g in {s.geometry for s in scenarios}]
    results, table = {}, []
    for name, fn in runs:
        print(f"   running {name} ...")
        recs = run_method(fn, scenarios)
        slug = (name.replace(" ", "_").replace("[", "").replace("]", "")
                    .replace("+", "plus").replace("-", "_"))
        write_records(recs, OUT / f"ablation_{slug}.csv")
        results[name] = {"all": metrics(recs),
                         **{g: metrics(recs, geometry=g) for g in geometries}}
        for subset in ["all"] + geometries:
            m = results[name][subset]
            if m.get("n"):
                table.append({"method": name, "subset": subset, **m})

    head = "| method | subset | " + " | ".join(l for _, l, _ in SHOW) + " |"
    rule = "|---|---|" + "|".join("---" for _ in SHOW) + "|"
    body = [f"| {r['method']} | {r['subset']} | "
            + " | ".join(f.format(r[k]) for k, _, f in SHOW) + " |"
            for r in table]
    md = "\n".join([head, rule] + body)
    (OUT / "ablation_controls.md").write_text(md + "\n", encoding="utf-8")
    print("\n" + md)

    for g in geometries:
        print(f"\n{g}:")
        print(f"   {'method':<32} {'mean %':>8} {'worst W':>9} "
              f"{'costly %':>10} {'probes':>8}")
        for name, _ in runs:
            m = results[name][g]
            print(f"   {name:<32} {m['mean_loss_pct']:>8.2f} "
                  f"{m['worst_loss_w']:>9.1f} {m['costly_frac_pct']:>10.1f} "
                  f"{m['mean_probes']:>8.1f}")

    # -- the verdict ---------------------------------------------------------
    print("\n" + "=" * 70)
    key = "whole_substring" if "whole_substring" in geometries else "all"
    c3 = results["C3 two-stage"][key]["mean_loss_pct"]
    naive = results["best-of-5 probes"][key]["mean_loss_pct"]
    refine = results["best-of-5 + refine"][key]["mean_loss_pct"]
    best_naive = min(naive, refine)
    gap = best_naive - c3

    print(f"\nVERDICT on {key}:")
    print(f"   C3 two-stage        {c3:.2f}%   "
          f"{results['C3 two-stage'][key]['mean_probes']:.0f} probes")
    print(f"   best-of-5 probes    {naive:.2f}%   "
          f"{results['best-of-5 probes'][key]['mean_probes']:.0f} probes")
    print(f"   best-of-5 + refine  {refine:.2f}%   "
          f"{results['best-of-5 + refine'][key]['mean_probes']:.0f} probes")
    print(f"   gap to the better naive control: {gap:+.2f} pt")

    if gap <= CLOSE_PT:
        print("\n   -> THE PROBE SCHEDULE CARRIES THE RESULT. A naive scan at "
              "these\n      five positions performs comparably to the learned "
              "model. The\n      contribution is WHERE TO PROBE, not what to "
              "learn from it, and\n      the framing must change accordingly.")
    elif gap >= CLEAR_PT:
        print("\n   -> THE LEARNING CARRIES THE RESULT. The same five "
              "measurements,\n      used naively, are well behind the model. C3's "
              "claim stands as\n      written, and this control is the evidence "
              "for it.")
    else:
        print("\n   -> BOTH CONTRIBUTE. Report the schedule and the learning "
              "separately;\n      neither alone accounts for the result.")

    print("\nDECOMPOSITION  (which stage does the work?)")
    om = results["offset midpoint"][key]["mean_loss_pct"]
    ro = results["region oracle [not buildable]"][key]["mean_loss_pct"]
    print(f"   classifier alone (offset fixed at 0.5): {om:.2f}%")
    print(f"   offset alone (true region given):       {ro:.2f}%  [not buildable]")
    print(f"   both together (C3):                     {c3:.2f}%")
    print("   The larger drop from C3 identifies which stage is load-bearing,")
    print("   and therefore where further work should go.")

    (OUT / "ablation_controls.json").write_text(
        json.dumps(results, indent=2, default=float), encoding="utf-8")
    print(f"\nresults -> {OUT / 'ablation_controls.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())