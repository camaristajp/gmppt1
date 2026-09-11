"""
features.py  --  the C3 feature and target contract.

PLACE THIS FILE AT:   C:\\Users\\user\\gmppt\\gmppt\\features.py
                      NEW FILE in the package, beside harness.py.

SELF-TEST (run first, takes seconds):
    python -m gmppt.features

WHY THIS FILE IS THE FOUNDATION

    C3 sees the world through this module and nothing else. Two paths must agree
    exactly:

      TRAINING  the curve is in memory; features are read from it
      SERVING   there is no curve, only ctx.probe(v); features are read from that

    If those paths compute features differently in any way -- different probe
    positions, different ordering, different normalisation -- the model learns
    one thing and is asked another at evaluation time. That is train-serve skew,
    and it is the standard reason a model that scores well offline fails in
    evaluation.

    The defence is structural: ONE extractor, called by both. `extract_features`
    takes a `sample(v) -> power` callable and does not know or care where the
    power came from. Training passes an interpolator over a stored curve; serving
    passes `ctx.probe`. test_train_serve_parity() asserts the two produce
    identical vectors.

    Corollary worth stating: if a feature cannot be computed through `sample`
    plus the scalars below, the hardware cannot supply it and it does not belong
    in the set.

WHAT THE MODEL IS ALLOWED TO SEE -- and why each entry is here

    PROBES          power at PROBE_FRACTIONS x V_oc, normalised by the largest
                    probed power. Normalising makes the vector scale-free across
                    modules of different wattage, so the model learns curve SHAPE
                    rather than module size.
    v_oc            the one voltage a tracker measures directly and cheaply.
    module scalars  V_mp/V_oc from the datasheet, N_s, and I_sc/V_oc as a coarse
                    shape hint. All available from nameplate data. P2.4d showed
                    the datasheet coefficient is worth 0.35 pt under uniform
                    light and little under shading -- so it is a useful prior,
                    not a solution.
    temp_c          ONE module temperature. NOT per-substring.

    THE TEMPERATURE CONSTRAINT IS DELIBERATE. The simulator knows the temperature
    of each substring; a real optimizer has a single back-of-module sensor. A
    model trained on per-substring temperature would learn to exploit an input
    that does not exist in deployment. This is the train-serve mismatch already
    on the project's flaw list, and it is closed here by construction:
    build_features_offline never receives per-substring temperature.

PROBE BUDGET
    PROBE_FRACTIONS has five entries. That number is the cost claim: Ahmed-Salam
    needs ~33 probes to reach 1.48% on whole-substring geometry (P2.4c showed 30
    performs the same as 240). Anything under ~10 wins the cost argument
    outright. Five is the starting point, not a fixed decision -- the count is a
    tunable the Phase 3 sweep should vary.

    Positions are FIXED, not learned. Learned probe placement is a strictly
    harder problem and would confound the cost claim with an architecture claim.

TARGETS -- three of them, because the objective is not yet decided
    k_true      V_gmpp / V_oc, scale-free across modules. The supervised target.
    region      which substring interval the GMPP falls in, 0..n_sub-1. P2.5
                found peak separation is quantised at about V_oc/3, so the error
                structure is discrete; a two-stage model (pick the interval, then
                refine inside it) can use this.
    offset      position within that interval, 0..1. The refinement target.

    A power-based objective needs no target at all -- it reads power off the
    curve -- so nothing here forecloses it.

WHAT THIS MODULE DOES NOT DO
    No model, no training, no scoring. It defines what the model sees and what it
    is asked to predict. Everything downstream depends on this interface, which
    is why it ships with a parity test rather than a promise.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Callable, Sequence

import numpy as np
import pandas as pd

from . import config
from . import device
from .device import ModuleParams


# ---------------------------------------------------------------------------
# The probe schedule. Changing this changes the model's input space AND the
# reported measurement cost, so it is pinned here and nowhere else.
# ---------------------------------------------------------------------------
PROBE_FRACTIONS: tuple[float, ...] = (0.20, 0.40, 0.55, 0.70, 0.85)

FEATURE_NAMES: tuple[str, ...] = (
    tuple(f"p{int(f*100):02d}" for f in PROBE_FRACTIONS)
    + ("p_max_norm", "v_oc", "k_datasheet", "n_cells", "isc_over_voc", "temp_c")
)
N_FEATURES = len(FEATURE_NAMES)

_POOL = None


def pool() -> pd.DataFrame:
    global _POOL
    if _POOL is None:
        _POOL = pd.read_parquet(config.CEC_POOL)
    return _POOL


def module_scalars(module_name: str) -> tuple[float, float, float]:
    """(k_datasheet, n_cells, isc_over_voc) -- all from nameplate data."""
    row = pool().loc[module_name]
    k = float(row["vmp_voc"])
    n_s = float(row["N_s"])
    v_oc = float(row["V_oc_ref"])
    i_sc = float(row["I_sc_ref"])
    return k, n_s, (i_sc / v_oc if v_oc > 0 else 0.0)


# ---------------------------------------------------------------------------
# THE SHARED EXTRACTOR -- the only place features are defined
# ---------------------------------------------------------------------------

def extract_features(sample: Callable[[float], float],
                     v_oc: float,
                     module_name: str,
                     temp_c: float) -> np.ndarray:
    """Build the model's input vector.

    `sample(v) -> power` is the ONLY window onto the curve. Training passes an
    interpolator over a stored curve; serving passes ctx.probe. Neither path can
    diverge, because there is one implementation.

    Probed powers are normalised by the largest probed power, so the vector
    describes curve SHAPE rather than module wattage. The normaliser itself is
    kept as a feature (p_max_norm, scaled by V_oc to a current-like quantity) so
    absolute scale is not lost entirely.
    """
    v_oc = float(v_oc)
    powers = np.array([float(sample(f * v_oc)) for f in PROBE_FRACTIONS],
                      dtype=float)

    p_max = float(powers.max())
    shape = powers / p_max if p_max > 0 else np.zeros_like(powers)

    k_ds, n_s, isc_voc = module_scalars(module_name)
    p_max_norm = p_max / v_oc if v_oc > 0 else 0.0     # current-like, ~I_mp

    return np.concatenate([
        shape,
        [p_max_norm, v_oc, k_ds, n_s, isc_voc, float(temp_c)],
    ]).astype(np.float64)


def curve_sampler(V: np.ndarray, P: np.ndarray) -> Callable[[float], float]:
    """A `sample` callable backed by a stored curve. Training-side only.

    Clamps to the curve's voltage range exactly as Context.probe does, so the two
    paths agree at the edges too.
    """
    V = np.asarray(V, float)
    P = np.asarray(P, float)
    lo, hi = float(V[0]), float(V[-1])

    def sample(v: float) -> float:
        return float(np.interp(min(max(float(v), lo), hi), V, P))

    return sample


# ---------------------------------------------------------------------------
# TARGETS
# ---------------------------------------------------------------------------

@dataclass
class Targets:
    k_true: float          # V_gmpp / V_oc -- the supervised regression target
    region: int            # which substring interval, 0..n_sub-1
    offset: float          # position within that interval, 0..1
    v_gmpp: float
    p_gmpp: float
    n_peaks: int


def extract_targets(V: np.ndarray, P: np.ndarray, analysis: dict) -> Targets:
    """True GMPP, expressed three ways.

    The region/offset decomposition follows P2.5: peak separation is quantised at
    roughly V_oc/3 because peaks sit at substring boundaries, so the error
    structure is discrete rather than continuous. A model that picks the interval
    and then refines inside it matches that structure.
    """
    n_sub = int(config.N_SUBSTRINGS)
    v_oc = float(np.asarray(V, float)[-1])
    gm = analysis["gmpp"]
    v_gmpp = float(gm["V"])
    p_gmpp = float(gm["P"])

    k_true = v_gmpp / v_oc if v_oc > 0 else float("nan")
    width = v_oc / n_sub
    region = int(min(max(int(v_gmpp // width), 0), n_sub - 1))
    offset = (v_gmpp - region * width) / width if width > 0 else 0.0

    return Targets(k_true=k_true, region=region,
                   offset=float(min(max(offset, 0.0), 1.0)),
                   v_gmpp=v_gmpp, p_gmpp=p_gmpp,
                   n_peaks=int(analysis.get("n_peaks", 1)))


# ---------------------------------------------------------------------------
# OFFLINE DATASET BUILD
# ---------------------------------------------------------------------------

def build_row(sc) -> dict | None:
    """One scenario -> features + targets + provenance. None if unusable."""
    mp = ModuleParams.from_cec(sc.module)
    c = device.module_iv(mp, sc.irradiances, sc.temp_c, bd=config.breakdown())
    a = device.analyse(c)

    V = np.asarray(c["V"], float)
    P = np.asarray(c["P"], float)
    order = np.argsort(V)
    V, P = V[order], P[order]
    v_oc = float(V[-1])
    if v_oc <= 0 or float(a["gmpp"]["P"]) <= 0:
        return None

    # NOTE: sc.temp_c is the MODULE temperature, one scalar. Per-substring
    # temperature is never passed, so the model cannot learn to use it.
    x = extract_features(curve_sampler(V, P), v_oc, sc.module, sc.temp_c)
    y = extract_targets(V, P, a)

    row = {name: float(val) for name, val in zip(FEATURE_NAMES, x)}
    row.update(asdict(y))
    row.update(module=sc.module, geometry=sc.geometry,
               near_threshold=bool(getattr(sc, "near_threshold", False)))
    return row


def build_dataset(scenarios: Sequence, verbose: bool = True) -> pd.DataFrame:
    """Features and targets for a scenario list. The expensive step; do it once."""
    rows = []
    for i, sc in enumerate(scenarios):
        r = build_row(sc)
        if r is not None:
            rows.append(r)
        if verbose and (i + 1) % 500 == 0:
            print(f"   ...{i + 1}/{len(scenarios)}")
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# VERIFICATION
# ---------------------------------------------------------------------------

def test_train_serve_parity(verbose: bool = True) -> bool:
    """THE LOAD-BEARING TEST.

    Build features for the same scenario twice: once through a stored curve
    (the training path) and once through a harness Context (the serving path).
    The vectors must be identical. If they are not, the model would be trained on
    one thing and evaluated on another.

    Also asserts the serving path spends exactly len(PROBE_FRACTIONS) probes --
    the measurement cost must be what the cost claim says it is.
    """
    from .harness import Context, scenario_set

    scenarios = scenario_set(40)
    ok = True
    checked = 0

    for sc in scenarios[:12]:
        mp = ModuleParams.from_cec(sc.module)
        c = device.module_iv(mp, sc.irradiances, sc.temp_c, bd=config.breakdown())
        V = np.asarray(c["V"], float)
        P = np.asarray(c["P"], float)
        order = np.argsort(V)
        V, P = V[order], P[order]
        v_oc = float(V[-1])

        x_train = extract_features(curve_sampler(V, P), v_oc, sc.module, sc.temp_c)

        ctx = Context(v_oc=v_oc, i_sc=None, module=str(sc.module),
                      geometry=str(sc.geometry),
                      rng=np.random.default_rng(0), _V=V, _P=P,
                      conditions={"irradiances": sc.irradiances,
                                  "temp_c": sc.temp_c})
        x_serve = extract_features(ctx.probe, v_oc, sc.module, sc.temp_c)

        same = np.allclose(x_train, x_serve, rtol=0, atol=1e-12)
        cost_ok = ctx.n_probes == len(PROBE_FRACTIONS)
        ok &= same and cost_ok
        checked += 1
        if not (same and cost_ok) and verbose:
            print(f"   MISMATCH on {sc.module[:34]} ({sc.geometry})")
            print(f"      max abs diff {np.max(np.abs(x_train - x_serve)):.3e}")
            print(f"      probes spent {ctx.n_probes}, expected "
                  f"{len(PROBE_FRACTIONS)}")

    if verbose:
        print(f"   {checked} scenarios, training path vs serving path")
        print(f"   probe cost per call: {len(PROBE_FRACTIONS)}")
        print(f"   -> {'PASS' if ok else 'FAIL'}")
    return ok


def test_feature_vector_shape(verbose: bool = True) -> bool:
    """Names and values must line up, and nothing may be NaN or infinite."""
    from .harness import scenario_set
    scenarios = scenario_set(20)
    ok = True
    for sc in scenarios[:8]:
        r = build_row(sc)
        if r is None:
            continue
        x = np.array([r[n] for n in FEATURE_NAMES], float)
        if x.size != N_FEATURES or not np.all(np.isfinite(x)):
            ok = False
            if verbose:
                print(f"   bad vector on {sc.module[:34]}: size {x.size}, "
                      f"finite {np.all(np.isfinite(x))}")
    if verbose:
        print(f"   {N_FEATURES} features: {', '.join(FEATURE_NAMES)}")
        print(f"   -> {'PASS' if ok else 'FAIL'}")
    return ok


def test_targets_reconstruct(verbose: bool = True) -> bool:
    """region and offset must rebuild v_gmpp, and k_true must agree with it.

    Guards the two-stage decomposition: if (region, offset) cannot reproduce the
    voltage, a two-stage model would be predicting something that is not the
    answer.
    """
    from .harness import scenario_set
    n_sub = int(config.N_SUBSTRINGS)
    scenarios = scenario_set(30)
    worst = 0.0
    ok = True

    for sc in scenarios[:15]:
        mp = ModuleParams.from_cec(sc.module)
        c = device.module_iv(mp, sc.irradiances, sc.temp_c, bd=config.breakdown())
        a = device.analyse(c)
        V = np.asarray(c["V"], float)
        P = np.asarray(c["P"], float)
        order = np.argsort(V)
        V, P = V[order], P[order]
        v_oc = float(V[-1])

        t = extract_targets(V, P, a)
        width = v_oc / n_sub
        v_rebuilt = (t.region + t.offset) * width
        d = abs(v_rebuilt - t.v_gmpp)
        worst = max(worst, d)
        if d > 1e-6 * max(1.0, v_oc):
            ok = False
        if abs(t.k_true * v_oc - t.v_gmpp) > 1e-6 * max(1.0, v_oc):
            ok = False

    if verbose:
        print(f"   worst reconstruction error: {worst:.3e} V")
        print(f"   -> {'PASS' if ok else 'FAIL'}")
    return ok


def describe_targets(verbose: bool = True) -> dict:
    """Target distribution -- context for what the model has to learn."""
    from .harness import scenario_set
    df = build_dataset(scenario_set(300), verbose=False)
    out = {}
    if verbose:
        print(f"   n = {len(df)}")
        print(f"   k_true   mean {df['k_true'].mean():.4f}  "
              f"sd {df['k_true'].std():.4f}  "
              f"range {df['k_true'].min():.3f}-{df['k_true'].max():.3f}")
        print("   region distribution (which substring interval holds the GMPP):")
        for r, cnt in df["region"].value_counts().sort_index().items():
            print(f"     region {r}: {cnt:>4}  ({100*cnt/len(df):>4.1f}%)")
        print("   by geometry:")
        for g, sub in df.groupby("geometry"):
            print(f"     {g:<18} k mean {sub['k_true'].mean():.4f}  "
                  f"sd {sub['k_true'].std():.4f}")
    out["n"] = len(df)
    return out


if __name__ == "__main__":
    print("C3 feature and target contract")
    try:
        print("  " + config.provenance())
    except Exception:
        pass
    print("=" * 70)

    print("\n1. FEATURE VECTOR SHAPE")
    a = test_feature_vector_shape()

    print("\n2. TARGET RECONSTRUCTION  (region + offset must rebuild v_gmpp)")
    b = test_targets_reconstruct()

    print("\n3. TRAIN-SERVE PARITY  (the load-bearing test)")
    c = test_train_serve_parity()

    print("\n4. TARGET DISTRIBUTION  (context, not a test)")
    describe_targets()

    print("\n" + "=" * 70)
    passed = sum([a, b, c])
    print(f"{passed}/3 checks passed")
    raise SystemExit(0 if passed == 3 else 1)
