"""
fallback.py  --  the confidence-gated fallback, and what it can certify.

PLACE THIS FILE AT:   C:\\Users\\user\\gmppt\\gmppt\\fallback.py
                      OVERWRITE the existing file.

SELF-TEST:
    python -m gmppt.fallback

REVISION 3 -- four corrections, all made after the revision-2 quick check and
before any reportable run.

  1. A FALSE PREMISE IN THE DESIGN, CORRECTED. Revision 2 claimed the fallback
     rule "cannot be wrong about the REGION -- it measures all three and takes
     the best, so the failure mode is eliminated by construction."

     That is not what the rule does. It probes n * 0.80 * V_oc / 3 for n = 1,2,3
     -- one point per region, sitting at 80% of the way through each region,
     NOT at each region's peak. If the true peak in a region sits far from that
     point, the probe there can return less power than a probe landing near a
     different region's peak, and the rule picks the wrong region.

     The quick check measured the consequence: the rule alone scores 2.964% mean
     loss with an 11.92 W worst case, against the unguarded model's 0.047% and
     4.22 W. A rule that genuinely could not be wrong about the region would not
     have a tail three times the model it is insuring.

     The premise is withdrawn. What the rule actually provides is a DETERMINISTIC
     worst case -- a property of a fixed rule over the scenario distribution
     rather than of a learned model -- which is still the only part of the claim
     that can be stated as a bound. It is simply a worse bound than hoped.

  2. THRESHOLD KEYS AT .3f. Revision 2 formatted keys with .2f, so a grid
     containing both 0.99 and 0.995 produced the key "guarded @ 0.99" twice and
     the second run silently overwrote the first. A row vanished with no warning.
     Recorded as D6.

  3. TRIGGER RATE MEASURED ON THE SAME POPULATION AS THE LOSS. Revision 2
     computed trigger_frac_pct as n_fallback / n_calls over EVERY scenario, while
     mean_loss_pct and worst_loss_w came from metrics(geometry=...) over a
     filtered subset. Condition (iii) was therefore evaluated on a different
     population from conditions (i) and (ii).

     Same class as the defect recorded at D2: a comparison across conditions not
     held equal, producing a plausible number and no error. Revision 3 logs the
     geometry of every call alongside whether it fired, so the trigger rate is
     computed on exactly the rows the loss metrics describe. Recorded as D7.

  4. GRID RESOLVED WHERE THE SIGNAL VARIES. The quick check showed thresholds
     0.50-0.80 catching nothing and 0.90-0.995 catching the same single scenario,
     so the classifier's confidence on the interesting case lies between 0.80 and
     0.90 -- and the revision-2 extension above 0.95 resolved the wrong end.
     Points added at 0.82, 0.85 and 0.88; 0.995 dropped.

  5. EACH CONFIGURATION RUNS ONCE, SCORED THREE WAYS. Revision 2's caller invoked
     this sweep once per geometry, re-simulating the whole scenario set each
     time. The records already carry the geometry, so one pass can be scored for
     every geometry. Roughly a threefold saving on the reportable run.

WHAT THIS ADDS, AND WHAT WAS MISSING
    P3.7 MEASURED a worst case of 2.4 W on held-out whole-substring scenarios --
    the best of every method tested, and better than a classical search spending
    nearly twice the probes. But a measured worst case is not a certified one. It
    is the largest loss that happened to occur on 800 scenarios; it is not a
    bound, and nothing prevents a worse one on the 801st.

    A bound needs a rule that acts when the model is unreliable rather than
    hoping it never is. That rule is what this file adds.

THE TRIGGER -- already present, and unused
    The two-stage model's first stage is a CLASSIFIER, which reports a
    probability per region, not just an argmax. Its confidence is therefore
    available for free and has been discarded until now.

    P3.3 established where the failure lives: the classifier reaches 99.5%
    accuracy, and P3.4's decomposition showed a perfect classifier would buy only
    0.14 pt of mean loss. So classifier errors are rare -- but when the region is
    wrong the landing is a whole substring away (approximately V_oc/3, per P2.5),
    which is the shape of a catastrophic loss rather than a small one.

    Low classifier confidence is a direct indicator of the failure mode that
    produces the tail. Using it as the trigger needs no new model and no new
    measurement.

THE FALLBACK -- deliberately not another model
    When confidence falls below a threshold, the method stops trusting the
    prediction, probes the three substring-boundary candidates directly, and
    lands on whichever returns the most power.

    The reason for that choice rather than a cleverer one is that its behaviour
    is FIXED: it contains no learned component, so its worst case over the
    scenario distribution is a property of the rule and not an artefact of
    training. A second learned model as fallback would reintroduce the same class
    of failure it is meant to catch.

    Its cost is known and small: n_sub extra probes, only on the scenarios that
    trigger it.

WHAT CAN AND CANNOT BE CLAIMED
    With the fallback active, worst-case loss is bounded by the WORSE of two
    measurable quantities: the guarded model's worst case, and the fallback
    rule's own worst case.

    THE SECOND DOMINATES, AND THAT IS THE PROBLEM. The quick check put the rule's
    tail at 11.92 W against the unguarded model's 4.22 W, so the "bound" the
    mechanism yields is nearly three times worse than the figure obtained by not
    certifying at all. A bound worse than the measurement it replaces is not
    worth reporting as a bound.

    choose_threshold() therefore returns a VACUOUS flag whenever the bound
    exceeds the unguarded worst case, and the caller must not print a claim in
    that case. The honest outcome, pre-authorised in the declared protocol, is to
    report the measured worst case and state that no certified bound is claimed
    -- a finding about the confidence signal and the available fallback, not a
    failure.

    Note what remains reportable and is not nothing: the learned model beats its
    own fallback on mean loss AND on worst case. The seed is strictly better than
    the classical rule it was meant to be insured by.

DECLARED BEFORE TUNING THE THRESHOLD -- unchanged from revision 1
    A threshold is acceptable only if, on validation:
      (i)   worst-case watts improve by at least 20% against no fallback, AND
      (ii)  mean loss does not worsen by more than 0.02 pt, AND
      (iii) the fallback fires on no more than 5% of scenarios.

    All three are now evaluated on the same population.

A KNOWN WEAKNESS IN THE SELECTION METRIC
    Condition (i) and the final selection use worst_loss_w, the single largest
    loss over the scenario set. P3.8 revision 2 established that this statistic
    is too noisy to select on and moved to the 99th percentile.

    metrics() exposes no percentile and changing the harness immediately before a
    reportable run is not worth the risk. The substitute costs nothing: READ THE
    worst W COLUMN ACROSS THE WHOLE SWEEP. Monotone in the threshold means the
    signal is real; jumping around means the single maximum is noise and nothing
    should be adopted on it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import numpy as np

from . import config
from .features import PROBE_FRACTIONS, extract_features
from .harness import Context
from .model import TwoStageModel

N_SUB = int(config.N_SUBSTRINGS)

# Probes: features + fallback candidates + landing. Asserted by test, not assumed.
PROBES_CONFIDENT = len(PROBE_FRACTIONS) + 1
PROBES_FALLBACK = len(PROBE_FRACTIONS) + N_SUB + 1

# Resolved where the signal varies. The quick check showed nothing firing below
# 0.80 and everything above 0.90 catching the same single scenario, so the
# interesting confidences lie in 0.80-0.90.
CANDIDATE_THRESHOLDS = (0.50, 0.60, 0.70, 0.80, 0.82, 0.85, 0.88,
                        0.90, 0.95, 0.97, 0.99)

GEOMETRIES = ("whole_substring", "sub_substring", "all")

# Acceptance, declared before any threshold is chosen.
MIN_WORST_GAIN_FRAC = 0.20     # worst-case watts must improve by >= 20%
MAX_MEAN_PENALTY_PT = 0.02     # mean loss may worsen by at most 0.02 pt
MAX_TRIGGER_FRAC = 0.05        # fallback may fire on at most 5% of scenarios

NO_FALLBACK = "no fallback"
RULE_ALONE = "fallback rule alone"


def _key(t: float) -> str:
    """Threshold keys at three decimals: .2f collided 0.99 with 0.995 (D6)."""
    return f"guarded @ {t:.3f}"


@dataclass
class GuardedModel:
    """The two-stage model with a confidence-gated fallback.

    Below `threshold` confidence in the region, the prediction is discarded and
    the three substring-boundary candidates are probed directly. Above it, the
    model's landing is used unchanged.
    """
    model: TwoStageModel
    threshold: float = 0.80
    fallback_k: float = 0.80       # candidate spacing for the probe rule

    # -- diagnostics, reset per run -------------------------------------
    n_calls: int = 0
    n_fallback: int = 0
    # (geometry, fired) per call, so the trigger rate can be computed on the
    # same rows the loss metrics describe rather than on the whole set (D7).
    log: list = field(default_factory=list)

    def reset(self) -> None:
        self.n_calls = 0
        self.n_fallback = 0
        self.log = []

    def confidence(self, x: np.ndarray) -> tuple[int, float]:
        """(predicted region, probability of that region).

        Falls back to full confidence if the classifier exposes no probabilities,
        so a classifier without predict_proba degrades to the unguarded model
        rather than silently reporting zero confidence and firing every time.
        """
        clf = self.model.classifier
        if not hasattr(clf, "predict_proba"):
            return int(clf.predict(x)[0]), 1.0
        p = np.asarray(clf.predict_proba(x))[0]
        classes = getattr(clf, "classes_", np.arange(len(p)))
        j = int(np.argmax(p))
        return int(classes[j]), float(p[j])

    def as_method(self) -> Callable[[Context], float]:
        """Wrap as fn(ctx) -> landing voltage, for the harness."""
        def fn(ctx: Context) -> float:
            self.n_calls += 1
            temp = ctx.conditions.get("temp_c")
            x = extract_features(ctx.probe, ctx.v_oc, ctx.module,
                                 float(temp) if temp is not None
                                 else config.STC_TEMPERATURE).reshape(1, -1)

            region, conf = self.confidence(x)

            if conf >= self.threshold:
                self.log.append((str(ctx.geometry), False))
                k = float(self.model.predict_k(x)[0])
                v = min(max(k * ctx.v_oc, 0.0), ctx.v_oc)
                ctx.probe(v)
                return v

            # -- fallback: measure all three boundaries, take the best --------
            self.n_fallback += 1
            self.log.append((str(ctx.geometry), True))
            cands = [n * self.fallback_k * ctx.v_oc / N_SUB
                     for n in range(1, N_SUB + 1)]
            cands = [min(max(v, 0.0), ctx.v_oc) for v in cands]
            best = max(cands, key=ctx.probe)
            ctx.probe(best)
            return best

        fn.__name__ = f"seed_guarded_t{self.threshold:.3f}"
        return fn


def three_candidate_method(k: float = 0.80) -> Callable[[Context], float]:
    """The fallback rule alone, as a method. Its worst case is the bound.

    Note the correction in the module docstring: this rule probes one point per
    region, not each region's peak, so it CAN pick the wrong region. Its value
    here is that its behaviour is deterministic, not that it is reliable.
    """
    def fn(ctx: Context) -> float:
        cands = [n * k * ctx.v_oc / N_SUB for n in range(1, N_SUB + 1)]
        return max(cands, key=ctx.probe)
    fn.__name__ = f"three_candidate_{k:.2f}"
    return fn


# ---------------------------------------------------------------------------
# VERIFICATION
# ---------------------------------------------------------------------------

def _probe_counts_at(guarded: GuardedModel, scenarios, threshold: float) -> set:
    """Observed probe counts over `scenarios` with the threshold pinned."""
    from .harness import curve_and_ceiling

    saved = guarded.threshold
    guarded.threshold = threshold
    fn = guarded.as_method()
    seen = set()
    try:
        for sc in scenarios:
            V, P, _, _ = curve_and_ceiling(sc)
            ctx = Context(v_oc=float(V[-1]), i_sc=None, module=str(sc.module),
                          geometry=str(sc.geometry),
                          rng=np.random.default_rng(0), _V=V, _P=P,
                          conditions={"irradiances": sc.irradiances,
                                      "temp_c": sc.temp_c})
            fn(ctx)
            seen.add(ctx.n_probes)
    finally:
        guarded.threshold = saved
    return seen


def test_probe_cost(guarded: GuardedModel, verbose: bool = True) -> bool:
    """Both paths must be OBSERVED at exactly their expected cost.

    An earlier revision ran at the default threshold and asked whether the
    observed counts were a SUBSET of the two expected values. At a threshold of
    0.80 the guard rarely fires, so the observed set was {confident} alone -- a
    subset, and therefore a pass, with the fallback cost never measured.

    This version pins the threshold at 0.0 (never fires) and then at 1.01
    (always fires) and requires each to produce EXACTLY its expected count.
    """
    from .harness import scenario_set

    scenarios = scenario_set(60)[:30]
    confident = _probe_counts_at(guarded, scenarios, 0.0)
    fired = _probe_counts_at(guarded, scenarios, 1.01)

    ok = (confident == {PROBES_CONFIDENT}) and (fired == {PROBES_FALLBACK})
    if verbose:
        print(f"   threshold 0.00 (never fires): observed {sorted(confident)}, "
              f"expected [{PROBES_CONFIDENT}]")
        print(f"   threshold 1.01 (always fires): observed {sorted(fired)}, "
              f"expected [{PROBES_FALLBACK}]")
        print("   both paths exercised, exact counts required")
        print(f"   -> {'PASS' if ok else 'FAIL'}")
    return ok


def test_threshold_extremes(guarded: GuardedModel, verbose: bool = True) -> bool:
    """A threshold of 0 must never fire; a threshold above 1 must always fire.

    Guards against the defect pattern recorded in the Phase 3 log: a guard that
    cannot fire, or one that fires unconditionally, passes silently and gives
    false assurance. Confirm it can do both before trusting anything between.
    """
    from .harness import run_method, scenario_set

    saved = guarded.threshold
    scenarios = scenario_set(120)
    try:
        guarded.threshold = 0.0
        guarded.reset()
        run_method(guarded.as_method(), scenarios)
        never, n_never = guarded.n_fallback, guarded.n_calls

        guarded.threshold = 1.01
        guarded.reset()
        run_method(guarded.as_method(), scenarios)
        always, n_always = guarded.n_fallback, guarded.n_calls
    finally:
        guarded.threshold = saved
        guarded.reset()

    ok = (never == 0) and (always == n_always) and (n_never > 0)
    if verbose:
        print(f"   threshold 0.00 -> fired {never}/{n_never} times (expect 0)")
        print(f"   threshold 1.01 -> fired {always}/{n_always} times "
              f"(expect all)")
        print(f"   -> {'PASS' if ok else 'FAIL'}")
    return ok


# ---------------------------------------------------------------------------
# SWEEP
# ---------------------------------------------------------------------------

def _trigger_pct(log: list, geometry: str) -> float:
    """Trigger rate over the rows the loss metrics describe, not over all rows.

    The fix for D7. Passing a log of (geometry, fired) pairs lets the same filter
    that selects the loss rows select the trigger rows.
    """
    if geometry == "all":
        rows = [fired for _, fired in log]
    else:
        rows = [fired for g, fired in log if g == geometry]
    if not rows:
        return 0.0
    return 100.0 * sum(rows) / len(rows)


def _score(recs, log, threshold, geometries) -> dict:
    """One set of records scored for every geometry. Returns {geometry: metrics}."""
    from .harness import metrics

    out = {}
    for g in geometries:
        m = metrics(recs, geometry=(None if g == "all" else g))
        if not m.get("n"):
            continue
        m = dict(m)
        m["threshold"] = threshold
        if log is None:
            m["trigger_frac_pct"] = 0.0 if threshold is None else 100.0
        else:
            m["trigger_frac_pct"] = _trigger_pct(log, g)
        out[g] = m
    return out


def sweep_thresholds(model: TwoStageModel, scenarios,
                     geometries: tuple = GEOMETRIES,
                     verbose: bool = True) -> dict:
    """Score the guarded model across thresholds, for every geometry at once.

    Each configuration is simulated ONCE and scored for every geometry, because
    the records already carry the geometry. Returns:

        {geometry: {configuration_name: metrics}}

    Reference rows: the unguarded model, and the fallback rule alone.
    """
    from .harness import run_method

    results = {g: {} for g in geometries}

    def stash(name: str, per_geom: dict) -> None:
        for g, m in per_geom.items():
            results.setdefault(g, {})[name] = m

    recs = run_method(model.as_method(), scenarios)
    per = _score(recs, None, None, geometries)
    for g in per:
        per[g]["trigger_frac_pct"] = 0.0
    stash(NO_FALLBACK, per)

    recs = run_method(three_candidate_method(0.80), scenarios)
    per = _score(recs, None, None, geometries)
    for g in per:
        per[g]["trigger_frac_pct"] = 100.0
    stash(RULE_ALONE, per)

    for t in CANDIDATE_THRESHOLDS:
        g_model = GuardedModel(model=model, threshold=t)
        g_model.reset()
        recs = run_method(g_model.as_method(), scenarios)
        stash(_key(t), _score(recs, g_model.log, t, geometries))

    if verbose:
        for g in geometries:
            if g not in results or not results[g]:
                continue
            print(f"\n   --- {g} ---")
            print(f"   {'configuration':<22} {'mean %':>8} {'worst W':>9} "
                  f"{'worst %':>9} {'fires %':>9} {'probes':>8}")
            print("   " + "-" * 70)
            for name, m in results[g].items():
                print(f"   {name:<22} {m['mean_loss_pct']:>8.3f} "
                      f"{m['worst_loss_w']:>9.2f} {m['worst_loss_pct']:>9.1f} "
                      f"{m['trigger_frac_pct']:>9.1f} {m['mean_probes']:>8.1f}")
        print("\n   Read the worst W column as a COLUMN. Monotone in the")
        print("   threshold means the signal is real; jumping around means the")
        print("   single maximum is noise and nothing should be adopted on it.")
    return results


def choose_threshold(sweep_one_geometry: dict, verbose: bool = True):
    """Apply the declared acceptance rule to ONE geometry's sweep.

    Takes the inner dict from sweep_thresholds, i.e. sweep[geometry].

    Returns (threshold, reason, info) where info carries the bound and whether it
    is VACUOUS -- that is, no better than the unguarded measured worst case. A
    bound worse than the measurement it replaces must not be printed as a claim,
    so the caller checks this flag rather than inferring success from a non-None
    threshold.
    """
    base = sweep_one_geometry[NO_FALLBACK]
    rule = sweep_one_geometry[RULE_ALONE]

    info = {"base_worst_w": base["worst_loss_w"],
            "rule_worst_w": rule["worst_loss_w"],
            "bound_w": None, "vacuous": None}

    if verbose:
        print(f"\n   declared: worst-case watts must improve by >= "
              f"{100*MIN_WORST_GAIN_FRAC:.0f}%,")
        print(f"   mean loss may worsen by at most {MAX_MEAN_PENALTY_PT} pt,")
        print(f"   and the fallback may fire on at most "
              f"{100*MAX_TRIGGER_FRAC:.0f}% of scenarios.")
        print("   All three are measured on the same rows.\n")

    triggered_any = False
    accepted = []
    for name, m in sweep_one_geometry.items():
        if m.get("threshold") is None:
            continue
        gain = ((base["worst_loss_w"] - m["worst_loss_w"])
                / max(base["worst_loss_w"], 1e-9))
        penalty = m["mean_loss_pct"] - base["mean_loss_pct"]
        fires = m["trigger_frac_pct"] / 100.0
        if fires > 0:
            triggered_any = True
        ok = (gain >= MIN_WORST_GAIN_FRAC
              and penalty <= MAX_MEAN_PENALTY_PT
              and fires <= MAX_TRIGGER_FRAC)
        if verbose:
            print(f"   {'ACCEPT' if ok else 'reject'}  "
                  f"t={m['threshold']:.3f}  "
                  f"worst {gain*100:+.1f}%, mean {penalty:+.3f} pt, "
                  f"fires {m['trigger_frac_pct']:.1f}%")
        if ok:
            accepted.append(m)

    if not accepted:
        if not triggered_any:
            return None, ("No threshold in the grid fired on a single scenario. "
                          "This is a property of the GRID, not of the confidence "
                          "signal: the classifier's probabilities all sit above "
                          f"{max(CANDIDATE_THRESHOLDS):.3f}. Extend "
                          "CANDIDATE_THRESHOLDS upward and re-run before drawing "
                          "any conclusion about the signal."), info
        return None, ("No threshold satisfies all three conditions. Either the "
                      "model's tail is already at the fallback rule's level, or "
                      "the confidence signal does not separate the failures. "
                      "Report the measured worst case and state that no "
                      "certified bound is claimed."), info

    best = min(accepted, key=lambda m: m["worst_loss_w"])
    bound = max(best["worst_loss_w"], rule["worst_loss_w"])
    vacuous = bound >= base["worst_loss_w"]
    info.update(bound_w=bound, vacuous=bool(vacuous),
                threshold=best["threshold"],
                guarded_worst_w=best["worst_loss_w"],
                guarded_mean_pct=best["mean_loss_pct"],
                trigger_frac_pct=best["trigger_frac_pct"],
                mean_probes=best["mean_probes"])

    if vacuous:
        reason = (f"threshold {best['threshold']:.3f} satisfies all three "
                  f"conditions (guarded worst case {best['worst_loss_w']:.2f} W, "
                  f"fires on {best['trigger_frac_pct']:.1f}%), BUT the resulting "
                  f"bound of {bound:.2f} W is no better than the unguarded "
                  f"measured worst case of {base['worst_loss_w']:.2f} W. The "
                  f"fallback rule's own tail ({rule['worst_loss_w']:.2f} W) "
                  f"dominates. NO CERTIFIED BOUND SHOULD BE CLAIMED -- report "
                  f"the measured worst case instead.")
    else:
        reason = (f"threshold {best['threshold']:.3f}: worst case "
                  f"{best['worst_loss_w']:.2f} W, fires on "
                  f"{best['trigger_frac_pct']:.1f}% of scenarios, mean loss "
                  f"{best['mean_loss_pct']:.3f}%. Bound on the declared "
                  f"distribution: {bound:.2f} W -- the worse of the guarded "
                  f"model and the fallback rule it defers to.")
    return best["threshold"], reason, info


if __name__ == "__main__":
    from . import dataset  # noqa: F401  (kept for parity with other entrypoints)
    from .harness import scenario_set

    print("Confidence-gated fallback: what it can and cannot certify")
    try:
        print("  " + config.provenance())
    except Exception:
        pass
    print("=" * 74)

    try:
        model = TwoStageModel.load(tag="c3_two_stage_full")
    except FileNotFoundError:
        print("model 'c3_two_stage_full' not found.")
        print("Run  python phase3\\p6_build_full_dataset.py --n 20000 --retrain")
        raise SystemExit(1)

    guarded = GuardedModel(model=model)

    print("\n1. PROBE COST  (both paths exercised)")
    a = test_probe_cost(guarded)

    print("\n2. THE GUARD CAN FIRE, AND CAN STAY SILENT")
    b = test_threshold_extremes(guarded)

    print("\n" + "=" * 74)
    passed = sum([a, b])
    print(f"{passed}/2 mechanical checks passed")
    if passed < 2:
        print("Fix these before sweeping thresholds -- a guard that cannot fire")
        print("would pass a threshold sweep silently.")
        raise SystemExit(1)

    print("\n3. THRESHOLD SWEEP  (quick check only, TRAINING modules)")
    print("   NOT the reportable figure. Run phase3/p8_c4_fallback.py for the")
    print("   validation-module evaluation.\n")
    sweep = sweep_thresholds(model, scenario_set(400))
    key_geom = "whole_substring" if "whole_substring" in sweep else "all"
    t, reason, info = choose_threshold(sweep[key_geom])
    print(f"\n   [{key_geom}] -> {reason}")
    raise SystemExit(0)