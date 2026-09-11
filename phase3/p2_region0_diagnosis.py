"""
p2_region0_diagnosis.py  --  Phase 3, step 2: why does region 0 carry half the loss?

PLACE THIS FILE AT:   C:\\Users\\user\\gmppt\\phase3\\p2_region0_diagnosis.py
                      NEW FILE. p1_dataset_sizing.py stays as it is.

RUN FROM THE REPO ROOT (C:\\Users\\user\\gmppt):
    python phase3\\p2_region0_diagnosis.py

Reads the pilot dataset p1 already saved, so nothing is re-simulated. Seconds,
not minutes.

WHY THIS RUN EXISTS
    p1 found the pilot model at 2.74% mean loss, with the loss concentrated in
    one thin class: region 0 is 8.5% of validation scenarios and about 50% of all
    power lost (16.12% mean loss there, against 1.37% and 1.58% elsewhere).
    Adding data barely helped -- the last doubling bought 0.078 pt.

    So the bottleneck is not the row count. This run asks WHICH bottleneck it is,
    and tests three candidate fixes against the same validation rows.

A CORRECTION CARRIED FROM p1 -- read this before comparing anything
    p1's "fixed 0.80" reference scored 22.18%. That is NOT the Phase 2
    fixed-0.80 baseline. p1 landed once at 0.80*Voc; the Phase 2 baseline uses
    the three-candidate rule (n*0.80*Voc/3 for n = 1..3, keep the highest-power
    one) and scores 3.32% on whole-substring. Comparing a model against the
    single-landing figure would flatter it roughly eightfold.

    This script implements BOTH reference forms and labels them distinctly, so
    the mistake cannot be repeated. The three-candidate figures are the ones that
    belong beside a model result.

THE FOUR CANDIDATES TESTED
    baseline        plain regression on k, as p1 ran it. The control.
    weighted        same model, region-0 rows upweighted. Tests whether the class
                    is simply under-represented in the gradient.
    power-weighted  rows weighted by the power at stake (p_gmpp), which is what a
                    power-based objective does implicitly. Tests the Month-3
                    objective question with evidence rather than preference.
    two-stage       classify the region, then regress the offset within it. Tests
                    the architecture hint from the near-tie screen: peak
                    separation is quantised at about Voc/3, so the error
                    structure is discrete rather than continuous.

    Each is scored on the SAME validation rows, in both metrics, with a per-region
    breakdown. If none of them moves region 0, the problem is the FEATURES -- the
    five probes may simply not distinguish these curves -- and the diagnostic
    section below says so.

DECLARED BEFORE RUNNING
    A candidate is worth adopting if it reduces region-0 mean loss by at least
    3 percentage points (from 16.12%) WITHOUT raising overall mean loss. A fix
    that trades the thin class against the bulk is not a fix.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gmppt import config, dataset  # noqa: E402
from gmppt.features import FEATURE_NAMES  # noqa: E402

OUT = config.RESULTS_DIR / "phase3"
FIGS = OUT / "figures"
N_SUB = int(config.N_SUBSTRINGS)

REGION0_TARGET_GAIN = 3.0      # pt off region-0 mean loss to be worth adopting


def make_regressor(seed_tag="c3_diag"):
    from sklearn.ensemble import HistGradientBoostingRegressor
    return HistGradientBoostingRegressor(
        max_iter=400, learning_rate=0.06, early_stopping=False,
        random_state=int(config.seed_for(seed_tag)) % 2**31)


def make_classifier(seed_tag="c3_diag_clf"):
    from sklearn.ensemble import HistGradientBoostingClassifier
    return HistGradientBoostingClassifier(
        max_iter=400, learning_rate=0.06, early_stopping=False,
        random_state=int(config.seed_for(seed_tag)) % 2**31)


def score(va: pd.DataFrame, curves: np.ndarray, k_pred: np.ndarray,
          label: str) -> dict:
    """Both metrics plus the per-region split, on the validation rows."""
    y = va["k_true"].to_numpy(float)
    loss = dataset.power_loss_for_k(curves, va["row_id"].to_numpy(int),
                                    k_pred, va["p_gmpp"].to_numpy(float))
    m = {"label": label, "n": int(len(va)),
         "k_mae": float(np.mean(np.abs(k_pred - y))),
         "mean_loss_pct": 100 * float(loss.mean()),
         "worst_loss_pct": 100 * float(loss.max()),
         "costly_frac_pct": 100 * float((loss > 0.01).mean())}
    regions = va["region"].to_numpy(int)
    for r in range(N_SUB):
        sel = regions == r
        m[f"r{r}_loss_pct"] = (100 * float(loss[sel].mean())
                               if sel.any() else float("nan"))
        m[f"r{r}_share_of_loss_pct"] = (100 * float(loss[sel].sum() / loss.sum())
                                        if loss.sum() > 0 and sel.any() else 0.0)
    return m


def landing_three_candidate(curves: np.ndarray, rows: np.ndarray,
                            k: float) -> np.ndarray:
    """The Phase 2 baseline rule expressed as an effective coefficient.

    Candidates sit at n*k/N_SUB of Voc for n = 1..N_SUB; the one returning the
    most power wins. Returned as the winning coefficient so it can be scored by
    the same path as a model prediction.
    """
    cands = np.array([n * k / N_SUB for n in range(1, N_SUB + 1)], dtype=float)
    best = np.empty(len(rows), dtype=float)
    for i, r in enumerate(rows):
        powers = dataset.power_at_k(curves, np.full(len(cands), r), cands)
        best[i] = cands[int(np.argmax(powers))]
    return best


def main() -> int:
    try:
        import sklearn  # noqa: F401
    except ImportError:
        print("scikit-learn is required:  pip install scikit-learn")
        return 1

    print("PHASE 3 / P2  region-0 diagnosis")
    try:
        print("  " + config.provenance())
    except Exception:
        pass
    print("=" * 70)

    try:
        df, curves = dataset.load(tag="pilot")
    except FileNotFoundError:
        print("pilot dataset not found. Run phase3\\p1_dataset_sizing.py first.")
        return 1

    df["row_id"] = np.arange(len(df))
    df = dataset.assign_split(df, dataset.module_split())
    tr = df[df["split"] == "train"].reset_index(drop=True)
    va = df[df["split"] == "val"].reset_index(drop=True)
    print(f"loaded {len(df)} rows: train {len(tr)}, val {len(va)}")

    x_tr = tr[list(FEATURE_NAMES)].to_numpy(float)
    y_tr = tr["k_true"].to_numpy(float)
    r_tr = tr["region"].to_numpy(int)
    x_va = va[list(FEATURE_NAMES)].to_numpy(float)
    rows_va = va["row_id"].to_numpy(int)

    # -- 1. references, both forms, clearly separated ------------------------
    print("\n1. REFERENCE POINTS  (note the two forms of the 0.80 rule)")
    refs = []
    refs.append(score(va, curves, np.full(len(va), 0.80),
                      "0.80 single landing"))
    refs.append(score(va, curves,
                      landing_three_candidate(curves, rows_va, 0.80),
                      "0.80 three-candidate"))
    refs.append(score(va, curves,
                      landing_three_candidate(curves, rows_va, 0.82),
                      "0.82 three-candidate"))
    hdr = (f"   {'method':<24} {'k MAE':>7} {'mean %':>8} {'worst %':>8} "
           f"{'r0 %':>7} {'r1 %':>7} {'r2 %':>7}")
    print(hdr)
    print("   " + "-" * (len(hdr) - 3))
    for m in refs:
        print(f"   {m['label']:<24} {m['k_mae']:>7.4f} "
              f"{m['mean_loss_pct']:>8.2f} {m['worst_loss_pct']:>8.1f} "
              f"{m['r0_loss_pct']:>7.2f} {m['r1_loss_pct']:>7.2f} "
              f"{m['r2_loss_pct']:>7.2f}")
    print("   The THREE-CANDIDATE rows are the Phase 2 baselines. The single")
    print("   landing is much worse and must not be used as a comparison.")

    # -- 2. candidate models -------------------------------------------------
    print("\n2. CANDIDATE MODELS  (same validation rows)")
    results = []

    m0 = make_regressor()
    m0.fit(x_tr, y_tr)
    results.append(score(va, curves, m0.predict(x_va), "baseline regression"))

    w = np.where(r_tr == 0, 6.0, 1.0)
    m1 = make_regressor("c3_diag_w")
    m1.fit(x_tr, y_tr, sample_weight=w)
    results.append(score(va, curves, m1.predict(x_va), "region-0 upweighted x6"))

    pw = tr["p_gmpp"].to_numpy(float)
    pw = pw / pw.mean()
    m2 = make_regressor("c3_diag_pw")
    m2.fit(x_tr, y_tr, sample_weight=pw)
    results.append(score(va, curves, m2.predict(x_va), "power-weighted"))

    clf = make_classifier()
    clf.fit(x_tr, r_tr)
    r_hat = clf.predict(x_va)
    off_models = {}
    for r in range(N_SUB):
        sel = r_tr == r
        if sel.sum() < 20:
            off_models[r] = None
            continue
        mm = make_regressor(f"c3_diag_off{r}")
        mm.fit(x_tr[sel], tr["offset"].to_numpy(float)[sel])
        off_models[r] = mm
    k_two = np.empty(len(va), dtype=float)
    for i in range(len(va)):
        r = int(r_hat[i])
        mm = off_models.get(r)
        off = float(mm.predict(x_va[i:i + 1])[0]) if mm is not None else 0.5
        k_two[i] = (r + min(max(off, 0.0), 1.0)) / N_SUB
    results.append(score(va, curves, k_two, "two-stage region+offset"))

    print(hdr)
    print("   " + "-" * (len(hdr) - 3))
    for m in results:
        print(f"   {m['label']:<24} {m['k_mae']:>7.4f} "
              f"{m['mean_loss_pct']:>8.2f} {m['worst_loss_pct']:>8.1f} "
              f"{m['r0_loss_pct']:>7.2f} {m['r1_loss_pct']:>7.2f} "
              f"{m['r2_loss_pct']:>7.2f}")

    # -- 3. verdict against the declared criterion ---------------------------
    print("\n3. VERDICT  (declared before the run)")
    base = results[0]
    print(f"   a candidate must cut region-0 loss by >= "
          f"{REGION0_TARGET_GAIN:.0f} pt from {base['r0_loss_pct']:.2f}%")
    print("   WITHOUT raising overall mean loss above "
          f"{base['mean_loss_pct']:.2f}%")
    adopted = []
    for m in results[1:]:
        gain = base["r0_loss_pct"] - m["r0_loss_pct"]
        held = m["mean_loss_pct"] <= base["mean_loss_pct"] + 1e-9
        ok = gain >= REGION0_TARGET_GAIN and held
        adopted.append((m["label"], ok))
        print(f"   {'ADOPT ' if ok else 'reject'}  {m['label']:<24} "
              f"region-0 {gain:+.2f} pt, overall "
              f"{m['mean_loss_pct'] - base['mean_loss_pct']:+.2f} pt")

    # -- 4. is it the features? ---------------------------------------------
    print("\n4. IS IT THE FEATURES?  (if nothing above worked, this is why)")
    print("   Region-0 curves have their global peak below Voc/3, meaning two")
    print("   substrings are bypassed. Separability check on the probe vector:")
    for name in list(FEATURE_NAMES)[:5]:
        a = tr[tr["region"] == 0][name]
        b = tr[tr["region"] != 0][name]
        if len(a) < 5:
            continue
        pooled = np.sqrt((a.var() + b.var()) / 2) or 1.0
        d = abs(a.mean() - b.mean()) / pooled
        print(f"     {name:<6} region0 {a.mean():.3f}  other {b.mean():.3f}  "
              f"separation {d:.2f} sd")
    print("   A separation below ~0.5 sd on every probe means the five samples")
    print("   do not distinguish region-0 curves, and no reweighting can fix")
    print("   that -- the probe SCHEDULE would need to change.")

    clf_acc = float((r_hat == va["region"].to_numpy(int)).mean())
    r0_recall = float((r_hat[va["region"].to_numpy(int) == 0] == 0).mean()) \
        if (va["region"] == 0).any() else float("nan")
    print(f"\n   region classifier: overall accuracy {100*clf_acc:.1f}%, "
          f"region-0 recall {100*r0_recall:.1f}%")
    print(f"   (always predicting region 2 would score "
          f"{100*float((va['region'] == 2).mean()):.1f}% -- beat that or the")
    print("    classifier has learned nothing)")

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "region0_diagnosis.json").write_text(
        json.dumps({"references": refs, "candidates": results,
                    "classifier_accuracy": clf_acc,
                    "region0_recall": r0_recall}, indent=2, default=float),
        encoding="utf-8")
    print(f"\nresults -> {OUT / 'region0_diagnosis.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())