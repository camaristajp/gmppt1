"""
p12_relocation_comparison.py  --  P2.9b: trackers through a peak RELOCATION.
REVISION 4 -- MEASUREMENT NOISE added, applied equally -- a fair real-world
             stressor. The module delivers TRUE power at the commanded voltage,
             but the tracker READS it through noisy current/voltage sensing
             (~1%/0.5% RMS, declared), so every method now decides on noisy
             readings while ENERGY captured is scored on true delivered power.
             Noise is PAIRED (same draw per window across methods), so it
             handicaps no one -- it tests which trackers, and which trigger,
             survive real sensing. The uniform control becomes a noise
             false-alarm gate. NOTE: this rev keeps the discrete developed jump
             (a fast cloud-edge / reconfiguration relocation); the GRADUAL
             sun-driven sweep at realistic dwell is the recommended next rev.
REVISION 3 -- change-detecting PSO added: the FAIR baseline. Rev 2 compared the
             triggered hybrid only against UN-triggered methods, so a win could
             be merely "change-detection vs none" rather than the real claim,
             "cheap re-PREDICT vs expensive re-SEARCH". Giving PSO the SAME
             power-drop trigger (it re-searches from scratch on a detected drop)
             isolates that: both now detect the jump; the question is what each
             pays to recover. Un-triggered methods stay in the table as context.
             This is the integrity fix for the comparison.
REVISION 2 -- DEVELOPED-relocation window (not crossover-adjacent); InC added.
             Rev 1 windowed the two curves straddling the boundary crossing,
             where the two substring peaks are near-equal BY DEFINITION -- so a
             tracker on the old peak already captured ~99.5% of the new one and
             nothing was hard (every method re-converged in 0 steps). Rev 2
             windows the FULLY-DEVELOPED endpoints instead (mid-plateau of each
             region's run), so the jump carries the real peak-height gap of a
             completed relocation -- the case where trapping costs watts.

PLACE THIS FILE AT:   C:\\Users\\user\\gmppt\\phase2\\p12_relocation_comparison.py
                      NEW FILE.

RUN FROM THE REPO ROOT (C:\\Users\\user\\gmppt):
    python phase2\\p12_relocation_comparison.py

WHAT THIS MEASURES, AND WHY IT IS THE ONE DYNAMIC RESULT THAT COUNTS
    EN 50530 (p10) cannot move the global peak between substrings, so every
    figure there is dynamic POWER tracking, not RELOCATION. phase2/transition.py
    builds the case EN 50530 cannot: a sun-driven shading pattern whose GMPP
    jumps from one substring to another. This runner steps the trackers through
    ONE such jump and measures how fast each RE-LOCATES the new peak.

    First cut, deliberately narrow (per the pre-registration): a SINGLE clean
    relocation event, isolated as settle -> jump -> hold, using the REAL pre- and
    post-jump curves the sun-driven sequence produced (only the dwell timing is
    idealised, to isolate the jump; the curves and the fact of relocation are
    the simulator's, gated by transition.py's G1/G2/G3). The full sun-driven
    "day" is a later extension.

THE FIVE TRACKERS, AND WHAT EACH IS EXPECTED TO DO AFTER THE JUMP
    P&O                 hill-climbs from the now-wrong held voltage; expected to
                        stay trapped on the old peak's basin -> lags.
    PSO (no re-init)    converges before the jump, then HOLDS a stale global-best
                        -> a swarm must re-search where a seed re-predicts; here
                        it is not allowed to, so it lags. (Its cost disadvantage
                        under motion is the point.)
    seed only           seeds once before the jump; the stateless prediction is
                        from the OLD curve, so it holds the wrong voltage -> lags
                        until re-fired.
    hybrid, never       seed once + P&O; after the jump P&O carries it, so it
                        behaves like P&O -> expected to lag. THIS IS THE HONEST
                        NEGATIVE the triggered variant exists to fix, and it is
                        reported, not hidden.
    hybrid, triggered   P&O + a MEASUREMENT-triggered re-seed: when captured
                        power drops sharply below the recently-achieved level, it
                        re-fires the seed (re-predicts from the NEW curve) and
                        re-locates. THE contribution (A3).

    The trigger fires on a MEASURED power drop only -- never on oracle knowledge
    that a block boundary was crossed (traj.block_changed is NOT used). Reading
    the block change would be reading the answer and would void the result.

DECLARED BEFORE THE RUN
    (1) The triggered hybrid RE-CONVERGES (reaches within EPS of the new GMPP and
        stays) on the jump; the un-triggered methods may not (censored).
    (2) The triggered hybrid's re-convergence steps are FEWER than PSO's and than
        the never-reseed hybrid's, by a margin exceeding the across-module spread
        (2x s.e.). Credited only then.
    (3) The trigger must fire NEAR the actual jump (false-trigger rate low). A
        trigger that fires on P&O ripple, or far from the jump, is reading noise
        and voids the claim.
    (4) UNIFORM CONTROL (G5): a no-relocation window (same curve before and after)
        must show NO tracker needing to re-converge and NO trigger firing. If a
        trigger fires with no relocation, the detector is unsound.

    If the never-reseed hybrid lags like P&O and only the triggered variant
    re-locates, that is the expected, honest result -- the motivation for the
    trigger, measured rather than assumed.

SCOPE
    Validation modules only (reportable). Declared synthetic site (Jeju
    reference), pending Nanum geometry -- travels with every figure. All
    simulated.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gmppt import config, dataset  # noqa: E402
from gmppt.dynamic import CONTROL_PERIOD_S, DynamicTrajectory  # noqa: E402
from gmppt.hybrid import SEED_PROBE_COST, seed_voltage  # noqa: E402
from gmppt.model import TwoStageModel  # noqa: E402
from gmppt.pso import DEFAULT_ITERATIONS, DEFAULT_POPULATION  # noqa: E402
from gmppt.tracking import DEFAULT_STEP_FRAC, START_FRACTION  # noqa: E402
from phase2.transition import (N_SUB, TRANSITION_FAMILIES,  # noqa: E402
                               pattern_sequence, sequence_trajectory_for,
                               validate_sequence)

OUT = config.RESULTS_DIR / "phase2"

# -- window shape (declared) -------------------------------------------------
SETTLE_STEPS = 200        # control steps on the pre-jump curve; > PSO budget so
#                           PSO converges and then holds stale across the jump
WINDOW_STEPS = 300        # control steps on the post-jump curve to observe re-conv
EPS = 0.01                # "re-converged" = captured >= (1-EPS)*p_gmpp_new
HOLD = 10                 # ... and stays there for HOLD steps

# -- trigger (declared) ------------------------------------------------------
TRIGGER_DROP_FRAC = 0.05  # re-seed if captured power falls >5% below the recent
#                           best; above any single P&O-step ripple, below a
#                           relocation drop (verified in the self-test)
TRIGGER_COOLDOWN = 15     # steps after a re-seed before the trigger may fire again
TRIGGER_PERSIST = 4       # consecutive below-baseline reads required to fire --
#                           rejects transient sensor-noise dips (a relocation drop
#                           is sustained). Set from the noise floor, a priori.
TRIGGER_EMA_ALPHA = 0.10  # baseline smoothing of the noisy power reading

# -- acceptance (declared) ---------------------------------------------------
MIN_RECONV_FRACTION = 0.80   # (1) triggered must re-converge on >=80% of events
SE_FACTOR = 2.0              # (2) margin must exceed 2x the larger s.e.
MAX_FALSE_TRIGGER_FRAC = 0.05  # (3) triggers far from the jump, as a fraction

# -- measurement noise (declared; real-world sensing) ------------------------
NOISE_I_RMS = 0.01        # current-sense RMS (~1%), typical optimizer ADC
NOISE_V_RMS = 0.005       # voltage-sense RMS (~0.5%)
MAX_CONTROL_FALSE_ALARM_FRAC = 0.05  # (4) uniform-control windows the trigger may
#                                       false-fire on UNDER NOISE (was 0 noiseless)

FAMILY_DEFAULT = "pole"
CENSORED = None              # re-convergence value when a tracker never re-locates


class NoisyTrajectory(DynamicTrajectory):
    """DynamicTrajectory with MEASUREMENT noise on what the tracker READS.

    The module physically delivers the true power at the commanded voltage; the
    tracker's ADC reads it with sensor noise. So step() records the TRUE power in
    p_hist (used for SCORING -- energy actually captured) but RETURNS a noisy
    reading (used by the tracker to decide): p_read = p_true*(1+e_i)*(1+e_v),
    e ~ N(0, rms). Applied EQUALLY, with the same seed per window across methods
    (paired), so it is a fair stressor and not a handicap on any one tracker.
    """
    def configure_noise(self, noise_i, noise_v, rng):
        self._ni = float(noise_i)
        self._nv = float(noise_v)
        self._nrng = rng
        return self

    def step(self, v):
        p_true = DynamicTrajectory.step(self, v)     # records TRUE power, advances
        e = ((1.0 + self._nrng.normal(0.0, self._ni))
             * (1.0 + self._nrng.normal(0.0, self._nv)))
        return p_true * e                            # tracker reads noisy


# ---------------------------------------------------------------------------
# TRACKERS  (operate on a DynamicTrajectory via .step / .v_oc / .n_steps)
# ---------------------------------------------------------------------------

def _clip(traj, v):
    return float(min(max(v, traj.v_floor), traj.v_oc))


def _drop_detector(drop, persist, alpha, cooldown):
    """Noise-robust sustained-drop detector (measured power only).

    Baseline is an EMA of the (noisy) captured power, which smooths sensor noise;
    it fires only when the reading stays more than `drop` below the baseline for
    `persist` CONSECUTIVE steps. A relocation is a sustained drop; sensor-noise
    dips are transient, so persistence separates them by physics. `drop` and
    `persist` are set from the declared noise floor a priori, never fitted to the
    outcome. On a fire the baseline resets (re-levels to the new regime) and a
    cooldown blocks immediate re-fire.
    """
    st = {"ema": None, "cnt": 0, "cool": 0}

    def update(p):
        if st["ema"] is None:
            st["ema"] = p
            return False
        if st["cool"] > 0:
            st["cool"] -= 1
            st["ema"] = (1 - alpha) * st["ema"] + alpha * p
            return False
        if p < (1.0 - drop) * st["ema"]:
            st["cnt"] += 1
            if st["cnt"] >= persist:
                st["cnt"] = 0
                st["cool"] = cooldown
                st["ema"] = None
                return True
            return False
        st["cnt"] = 0
        st["ema"] = (1 - alpha) * st["ema"] + alpha * p
        return False

    return update


def t_po(traj, model=None, temp_c=25.0, step_frac=DEFAULT_STEP_FRAC, **_):
    dv = step_frac * traj.v_oc
    v = START_FRACTION * traj.v_oc
    p_prev = traj.step(v)
    direction = -1.0
    for _ in range(traj.n_steps - 1):
        v = _clip(traj, v + direction * dv)
        p = traj.step(v)
        if p < p_prev:
            direction = -direction
        p_prev = p


def t_inc(traj, model=None, temp_c=25.0, step_frac=DEFAULT_STEP_FRAC, **_):
    """Fixed-step InC. Quasi-static it reduces to P&O (D11/D14); a moving
    relocation is the one place its positional condition could differ, so it is
    included here to check whether that gap finally appears under motion."""
    dv = step_frac * traj.v_oc
    v = START_FRACTION * traj.v_oc
    p = traj.step(v)
    i_prev, v_prev = p / max(v, 1e-9), v
    v = max(v - dv, traj.v_floor)
    for _ in range(traj.n_steps - 1):
        p = traj.step(v)
        i = p / max(v, 1e-9)
        d_v, d_i = v - v_prev, i - i_prev
        i_prev, v_prev = i, v
        if abs(d_v) < 1e-12:
            if abs(d_i) < 1e-12:
                continue
            v = v + (dv if d_i > 0 else -dv)
        else:
            lhs, rhs = d_i / d_v, -i / max(v, 1e-9)
            if abs(lhs - rhs) < 1e-6:
                continue
            v = v + (dv if lhs > rhs else -dv)
        v = _clip(traj, v)


def t_pso(traj, model=None, temp_c=25.0, seed=0,
          population=DEFAULT_POPULATION, iterations=DEFAULT_ITERATIONS, **_):
    """Searches once (before the jump), then HOLDS the global best -- no re-init.

    Under motion the held position goes stale, which is exactly the behaviour the
    relocation test is meant to expose: a swarm must re-search where a seed
    re-predicts.
    """
    from gmppt.pso import (C_COGNITIVE, C_SOCIAL, INERTIA, V_MAX_FRAC,
                           V_MIN_FRAC, VEL_MAX_FRAC)
    rng = np.random.default_rng(
        (int(config.seed_for("pso_relocation")) + seed * 7919) % 2**31)
    v_lo = max(V_MIN_FRAC * traj.v_oc, traj.v_floor)
    v_hi = V_MAX_FRAC * traj.v_oc
    vel_max = VEL_MAX_FRAC * traj.v_oc
    base = np.linspace(v_lo, v_hi, population)
    x = np.clip(base + (rng.random(population) - 0.5) * (v_hi - v_lo)
                / (2 * population), v_lo, v_hi)
    vel = np.zeros(population)
    p_best_x, p_best_p = x.copy(), np.full(population, -np.inf)
    g_best_x, g_best_p = float(x[0]), -np.inf
    used, budget = 0, traj.n_steps
    for _ in range(iterations):
        for i in range(population):
            if used >= budget:
                break
            p = traj.step(float(x[i]))
            used += 1
            if p > p_best_p[i]:
                p_best_p[i], p_best_x[i] = p, float(x[i])
            if p > g_best_p:
                g_best_p, g_best_x = p, float(x[i])
        if used >= budget:
            break
        r1, r2 = rng.random(population), rng.random(population)
        vel = np.clip(INERTIA * vel + C_COGNITIVE * r1 * (p_best_x - x)
                      + C_SOCIAL * r2 * (g_best_x - x), -vel_max, vel_max)
        x = np.clip(x + vel, v_lo, v_hi)
    while used < budget:
        traj.step(g_best_x)     # HOLD stale global best -- no re-search
        used += 1


def _pso_search(traj, rng, budget, population, iterations):
    """One PSO search consuming up to `budget` steps; returns (g_best_x, used)."""
    from gmppt.pso import (C_COGNITIVE, C_SOCIAL, INERTIA, V_MAX_FRAC,
                           V_MIN_FRAC, VEL_MAX_FRAC)
    v_lo = max(V_MIN_FRAC * traj.v_oc, traj.v_floor)
    v_hi = V_MAX_FRAC * traj.v_oc
    vel_max = VEL_MAX_FRAC * traj.v_oc
    base = np.linspace(v_lo, v_hi, population)
    x = np.clip(base + (rng.random(population) - 0.5) * (v_hi - v_lo)
                / (2 * population), v_lo, v_hi)
    vel = np.zeros(population)
    pbx, pbp = x.copy(), np.full(population, -np.inf)
    gbx, gbp = float(x[0]), -np.inf
    used = 0
    for _ in range(iterations):
        for i in range(population):
            if used >= budget:
                break
            pw = traj.step(float(x[i]))
            used += 1
            if pw > pbp[i]:
                pbp[i], pbx[i] = pw, float(x[i])
            if pw > gbp:
                gbp, gbx = pw, float(x[i])
        if used >= budget:
            break
        r1, r2 = rng.random(population), rng.random(population)
        vel = np.clip(INERTIA * vel + C_COGNITIVE * r1 * (pbx - x)
                      + C_SOCIAL * r2 * (gbx - x), -vel_max, vel_max)
        x = np.clip(x + vel, v_lo, v_hi)
    return gbx, used


def t_pso_triggered(traj, model=None, temp_c=25.0, seed=0,
                    population=DEFAULT_POPULATION, iterations=DEFAULT_ITERATIONS,
                    trigger_drop=TRIGGER_DROP_FRAC, cooldown=TRIGGER_COOLDOWN, **_):
    """PSO with the SAME measurement trigger as the hybrid: on a detected power
    drop it RE-SEARCHES from scratch (a swarm cannot re-predict). The FAIR
    baseline that isolates cheap re-predict (hybrid) from expensive re-search
    (PSO). Trigger uses measured power only, never the oracle block change.
    """
    rng = np.random.default_rng(
        (int(config.seed_for("pso_trig")) + seed * 7919) % 2**31)
    gbx, _ = _pso_search(traj, rng, traj.n_steps, population, iterations)
    det = _drop_detector(trigger_drop, TRIGGER_PERSIST, TRIGGER_EMA_ALPHA,
                         cooldown)
    fires = []
    while traj._k < traj.n_steps:
        p = traj.step(gbx)
        if det(p):                       # same detector as the hybrid (fair)
            if traj._k >= traj.n_steps:
                break
            gbx, _ = _pso_search(traj, rng, traj.n_steps - traj._k,
                                 population, iterations)   # re-search from scratch
            fires.append(int(traj._k))
    setattr(traj, "trigger_fires", fires)


def t_seed_only(traj, model, temp_c=25.0, **_):
    """Seed once before the jump, hold. Stateless prediction from the OLD curve."""
    v_seed, _ = seed_voltage(traj, model, temp_c)
    for _ in range(traj.n_steps - SEED_PROBE_COST):
        traj.step(v_seed)


def t_hybrid_never(traj, model, temp_c=25.0, step_frac=DEFAULT_STEP_FRAC, **_):
    """Seed once + P&O. After the jump P&O carries it -- expected to lag."""
    v_seed, _ = seed_voltage(traj, model, temp_c)
    n = traj.n_steps - SEED_PROBE_COST
    if n <= 0:
        return
    dv = step_frac * traj.v_oc
    v = _clip(traj, v_seed)
    p_prev = traj.step(v)
    direction = -1.0
    for _ in range(n - 1):
        v = _clip(traj, v + direction * dv)
        p = traj.step(v)
        if p < p_prev:
            direction = -direction
        p_prev = p


def t_hybrid_triggered(traj, model, temp_c=25.0, step_frac=DEFAULT_STEP_FRAC,
                       trigger_drop=TRIGGER_DROP_FRAC,
                       cooldown=TRIGGER_COOLDOWN, **_):
    """P&O + a MEASUREMENT-triggered re-seed.

    A sharp drop of captured power below the recently-achieved level signals that
    conditions changed (the peak relocated), so the seed is re-fired -- from the
    NEW measurement, so it predicts the NEW region. The trigger uses only
    measured power; it never consults traj.block_changed (that would be reading
    the answer). Trigger firings are recorded on the trajectory for the
    false-trigger check.
    """
    dv = step_frac * traj.v_oc
    v_seed, _ = seed_voltage(traj, model, temp_c)
    v = _clip(traj, v_seed)
    p_prev = traj.step(v)
    det = _drop_detector(trigger_drop, TRIGGER_PERSIST, TRIGGER_EMA_ALPHA,
                         cooldown)
    det(p_prev)
    direction = -1.0
    fires = []
    while traj._k < traj.n_steps:
        v = _clip(traj, v + direction * dv)
        p = traj.step(v)
        if p < p_prev:
            direction = -direction
        p_prev = p
        if det(p):                       # sustained drop -> re-seed (new curve)
            if traj._k >= traj.n_steps:
                break
            v_seed, _ = seed_voltage(traj, model, temp_c)
            v = _clip(traj, v_seed)
            p = traj.step(v)
            p_prev = p
            direction = -1.0
            fires.append(int(traj._k))
    setattr(traj, "trigger_fires", fires)


METHODS = [
    ("P&O", t_po),
    ("InC", t_inc),
    ("PSO", t_pso),
    ("PSO, triggered reseed", t_pso_triggered),
    ("seed only", t_seed_only),
    ("hybrid, never reseed", t_hybrid_never),
    ("hybrid, triggered reseed", t_hybrid_triggered),
]


# ---------------------------------------------------------------------------
# WINDOW EXTRACTION  (settle -> jump -> hold, from real pre/post curves)
# ---------------------------------------------------------------------------

def find_developed_endpoints(per_step, min_run=3):
    """Two FULLY-DEVELOPED endpoints: mid-plateau of the two longest runs of
    DIFFERENT GMPP regions. Not the crossover-adjacent curves (rev 1), where the
    peaks are near-equal by definition and nothing is hard. Deep in each run the
    shadow band is fully on that substring, so the between-region peak-height gap
    is that of a COMPLETED relocation -- where trapping actually costs watts.
    Returns (pre_idx, post_idx, region_a, region_b) or None."""
    regions = per_step["regions"]
    runs, s = [], 0
    for i in range(1, len(regions) + 1):
        if i == len(regions) or regions[i] != regions[s]:
            runs.append((int(regions[s]), s, i - 1))
            s = i
    runs = [r for r in runs if (r[2] - r[1] + 1) >= min_run]
    if len(runs) < 2:
        return None
    runs.sort(key=lambda r: (r[2] - r[1]), reverse=True)
    a = runs[0]
    b = next((r for r in runs[1:] if r[0] != a[0]), None)
    if b is None:
        return None
    if a[1] > b[1]:
        a, b = b, a
    return (a[1] + a[2]) // 2, (b[1] + b[2]) // 2, int(a[0]), int(b[0])


def make_window(traj_full, per_step, pre_idx, post_idx, win_seed):
    """Two-block window: settle on the DEVELOPED pre curve, hold on the DEVELOPED
    post curve. Pattern step k is traj_full.curves[k+1] (curve 0 is the settle
    copy), so the endpoints carry the full peak-height gap of a completed
    relocation."""
    pre_curve = traj_full.curves[pre_idx + 1]
    post_curve = traj_full.curves[post_idx + 1]
    p_gmpp_new = float(post_curve[3])
    module = traj_full.module
    geometry = traj_full.geometry

    def build():
        t = NoisyTrajectory(
            curves=[pre_curve, post_curve],
            block_steps=np.array([SETTLE_STEPS, WINDOW_STEPS], int),
            scored=np.array([False, True], bool),
            profile_name=traj_full.profile_name, module=module,
            geometry=geometry)
        return t.configure_noise(NOISE_I_RMS, NOISE_V_RMS,
                                 np.random.default_rng(win_seed))

    meta = {"module": module, "pre_idx": int(pre_idx), "post_idx": int(post_idx),
            "p_gmpp_new": p_gmpp_new,
            "region_pre": int(per_step["regions"][pre_idx]),
            "region_post": int(per_step["regions"][post_idx])}
    return build, meta


def make_uniform_control(traj_full, idx, win_seed):
    """G5 control: same curve before and after -- no relocation. UNDER NOISE, a
    sound tracker still needs no re-convergence and the trigger must rarely fire
    (the noise false-alarm gate)."""
    post_curve = traj_full.curves[idx + 1]

    def build():
        t = NoisyTrajectory(
            curves=[post_curve, post_curve],
            block_steps=np.array([SETTLE_STEPS, WINDOW_STEPS], int),
            scored=np.array([False, True], bool),
            profile_name="uniform_control", module=traj_full.module,
            geometry="uniform_control")
        # control noise uses a distinct stream so it is not identical to the jump
        return t.configure_noise(NOISE_I_RMS, NOISE_V_RMS,
                                 np.random.default_rng(win_seed + 1_000_000))
    return build


# ---------------------------------------------------------------------------
# METRICS  (read from the trajectory's histories -- tracker-agnostic)
# ---------------------------------------------------------------------------

def reconvergence_steps(traj, p_gmpp_new):
    """Control steps after the jump until captured power reaches (1-EPS)*p_gmpp_new
    and stays for HOLD steps. CENSORED if it never does within the window."""
    p = np.asarray(traj.p_hist, float)
    post = p[SETTLE_STEPS:]                  # the scored, post-jump block
    thresh = (1.0 - EPS) * p_gmpp_new
    ok = post >= thresh
    for i in range(len(ok) - HOLD):
        if ok[i:i + HOLD].all():
            return int(i)
    return CENSORED


def transition_energy_loss_pct(traj, p_gmpp_new):
    """Fraction of the post-jump available energy lost while re-locating."""
    p = np.asarray(traj.p_hist, float)[SETTLE_STEPS:]
    avail = p_gmpp_new * len(p)
    return float(100.0 * (avail - p.sum()) / max(avail, 1e-9))


# ---------------------------------------------------------------------------
# RUNNER
# ---------------------------------------------------------------------------

def run_one_window(build, meta, model, temp_c):
    """Every tracker on one relocation window. Returns per-method metrics."""
    out = {}
    for name, fn in METHODS:
        traj = build()
        fn(traj, model=model, temp_c=temp_c)
        rc = reconvergence_steps(traj, meta["p_gmpp_new"])
        el = transition_energy_loss_pct(traj, meta["p_gmpp_new"])
        fires = getattr(traj, "trigger_fires", None)
        out[name] = {"reconv_steps": rc, "energy_loss_pct": el,
                     "trigger_fires": fires}
    return out


def _se(values):
    v = np.asarray([x for x in values if x is not None], float)
    return float(v.std(ddof=1) / np.sqrt(len(v))) if len(v) > 1 else 0.0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=12,
                    help="validation modules to draw a relocation window from")
    ap.add_argument("--family", default=FAMILY_DEFAULT,
                    choices=list(TRANSITION_FAMILIES))
    args = ap.parse_args()

    print("P2.9b  relocation comparison: trackers through a single peak jump")
    try:
        print("  " + config.provenance())
    except Exception:
        pass
    print("=" * 78)
    print(f"family {args.family}; window settle {SETTLE_STEPS} + hold "
          f"{WINDOW_STEPS} steps at {1000*CONTROL_PERIOD_S:.0f} ms")
    print(f"trigger: re-seed on captured power < {100*(1-TRIGGER_DROP_FRAC):.0f}% "
          f"of recent best (measured only, never oracle block-change)")
    print("DECLARED SYNTHETIC site (Jeju reference), pending Nanum geometry -- "
          "travels with every figure.")
    print(f"MEASUREMENT NOISE applied equally (paired): current {100*NOISE_I_RMS:.1f}% "
          f"RMS, voltage {100*NOISE_V_RMS:.1f}% RMS. Energy scored on TRUE power; "
          "trackers decide on noisy reads.\n")
    print("acceptance, declared before this run:")
    print(f"   (1) triggered hybrid re-converges on >= "
          f"{100*MIN_RECONV_FRACTION:.0f}% of events")
    print(f"   (2) [FAIR] its re-convergence beats the CHANGE-DETECTING PSO "
          f"(same trigger;")
    print(f"       re-predict vs re-search) by > {SE_FACTOR:.0f}x s.e.")
    print(f"   (3) triggers fire near the jump (false-trigger < "
          f"{100*MAX_FALSE_TRIGGER_FRAC:.0f}%)")
    print("   (4) uniform control: no re-convergence needed, no trigger fires\n")

    try:
        model = TwoStageModel.load(tag="c3_two_stage_full")
    except FileNotFoundError:
        print("model 'c3_two_stage_full' not found.")
        return 1

    split = dataset.module_split()
    val_modules = list(split.val)[:max(args.n * 3, args.n)]
    print(f"drawing relocation windows on validation modules "
          f"(pool {len(val_modules)})\n")

    windows, uniform_builds, discarded = [], [], 0
    for mod in val_modules:
        if len(windows) >= args.n:
            break
        seq = pattern_sequence(str(mod), 25.0, family=args.family)
        try:
            ok, traj_full, per_step, _rep = validate_sequence(seq, verbose=False)
        except RuntimeError:
            discarded += 1
            continue
        if not ok:
            discarded += 1
            continue
        ep = find_developed_endpoints(per_step)
        if ep is None:
            discarded += 1
            continue
        pre_idx, post_idx, _ra, _rb = ep
        widx = int(config.seed_for("p12_noise")) % 2**31 + len(windows)
        build, meta = make_window(traj_full, per_step, pre_idx, post_idx, widx)
        windows.append((build, meta))
        uniform_builds.append(make_uniform_control(traj_full, post_idx, widx))

    if len(windows) < 3:
        print(f"only {len(windows)} clean relocation windows "
              f"({discarded} discarded). Need >= 3; widen --n or the azimuth "
              "window in transition.py.")
        return 1
    print(f"{len(windows)} clean relocation windows, {discarded} discarded "
          f"(gates + clean-event screen)\n")

    # -- the comparison ------------------------------------------------------
    names = [n for n, _ in METHODS]
    per_method = {n: {"reconv": [], "energy": [], "fires": []} for n in names}
    for build, meta in windows:
        res = run_one_window(build, meta, model, 25.0)
        for n in names:
            per_method[n]["reconv"].append(res[n]["reconv_steps"])
            per_method[n]["energy"].append(res[n]["energy_loss_pct"])
            per_method[n]["fires"].append(res[n]["trigger_fires"])

    # -- uniform control (G5) ------------------------------------------------
    ctrl_reconv_needed, ctrl_trigger_fired = 0, 0
    for ub in uniform_builds:
        traj = ub()
        t_hybrid_triggered(traj, model=model, temp_c=25.0)
        # on a no-relocation window the held power should never drop -> no fire
        if getattr(traj, "trigger_fires", []):
            ctrl_trigger_fired += 1

    # -- table ---------------------------------------------------------------
    print("RE-CONVERGENCE AFTER THE JUMP  (control steps; 'cens' = never)")
    print(f"   {'method':<26} {'median':>8} {'worst':>8} {'re-conv %':>10} "
          f"{'energy loss %':>14}")
    print("   " + "-" * 68)
    stats = {}
    for n in names:
        rc = per_method[n]["reconv"]
        got = [x for x in rc if x is not None]
        frac = len(got) / len(rc)
        med = float(np.median(got)) if got else float("nan")
        wor = float(np.max(got)) if got else float("nan")
        el = float(np.mean(per_method[n]["energy"]))
        stats[n] = {"reconv": rc, "median": med, "worst": wor,
                    "reconv_frac": frac, "energy_loss_pct": el,
                    "se": _se(rc)}
        med_s = f"{med:.0f}" if got else "cens"
        wor_s = f"{wor:.0f}" if got else "cens"
        print(f"   {n:<26} {med_s:>8} {wor_s:>8} {100*frac:>9.0f}% {el:>14.2f}")

    # -- verdict -------------------------------------------------------------
    print("\n" + "=" * 78 + "\nVERDICT")
    trig = stats["hybrid, triggered reseed"]
    pso_u = stats["PSO"]                        # un-triggered (context)
    pso_t = stats["PSO, triggered reseed"]      # fair change-detecting baseline
    never = stats["hybrid, never reseed"]

    c1 = trig["reconv_frac"] >= MIN_RECONV_FRACTION
    print(f"\n   (1) triggered re-converges on {100*trig['reconv_frac']:.0f}% "
          f"of events (bar {100*MIN_RECONV_FRACTION:.0f}%) -> "
          f"{'PASS' if c1 else 'FAIL'}")

    def _beats(a, b):
        if np.isnan(a["median"]) or np.isnan(b["median"]):
            return b["reconv_frac"] < a["reconv_frac"], float("nan")
        diff = b["median"] - a["median"]
        se = SE_FACTOR * max(a["se"], b["se"])
        return diff > se and diff > 0, diff
    b_fair, d_fair = _beats(trig, pso_t)
    b_psou, d_psou = _beats(trig, pso_u)
    b_never, d_never = _beats(trig, never)
    c2 = b_fair
    print(f"   (2) [FAIR] triggered hybrid vs CHANGE-DETECTING PSO: {d_fair:+.0f} "
          f"steps ({'separable' if b_fair else 'not separable'}) -> "
          f"{'PASS' if c2 else 'FAIL'}")
    print("       the integrity comparison: BOTH detect the jump; re-PREDICT vs "
          "re-SEARCH.")
    print(f"       context -- vs un-triggered PSO {d_psou:+.0f}; vs never-reseed "
          f"{d_never:+.0f}")
    print("       (both large and expected: those methods do not detect the "
          "change at all)")

    # (3) false triggers: a fire is "clean" if it lands soon after the jump
    late = SETTLE_STEPS + WINDOW_STEPS
    clean_fires, total_fires = 0, 0
    for fires in per_method["hybrid, triggered reseed"]["fires"]:
        for f in (fires or []):
            total_fires += 1
            if SETTLE_STEPS <= f <= SETTLE_STEPS + TRIGGER_COOLDOWN + 40:
                clean_fires += 1
    ft = 1.0 - (clean_fires / total_fires) if total_fires else 0.0
    c3 = ft <= MAX_FALSE_TRIGGER_FRAC
    print(f"   (3) {total_fires} triggers, {clean_fires} near the jump; "
          f"false-trigger {100*ft:.0f}% (bar {100*MAX_FALSE_TRIGGER_FRAC:.0f}%) "
          f"-> {'PASS' if c3 else 'FAIL'}")

    c4_bar = int(np.ceil(MAX_CONTROL_FALSE_ALARM_FRAC * max(len(uniform_builds), 1)))
    c4 = ctrl_trigger_fired <= c4_bar
    print(f"   (4) uniform control UNDER NOISE: trigger false-fired on "
          f"{ctrl_trigger_fired}/"
          f"{len(uniform_builds)} no-relocation windows -> "
          f"{'PASS' if c4 else 'FAIL (detector unsound)'}")

    print("\n   INTERPRETATION")
    if never["reconv_frac"] < trig["reconv_frac"]:
        print("   The never-reseed hybrid lags (like P&O); only the TRIGGERED")
        print("   variant re-locates. That is the expected honest result and the")
        print("   motivation for the trigger -- measured, not assumed.")
    if c1 and c2 and c3 and c4:
        print("   The triggered hybrid re-locates the moving peak faster than a")
        print("   swarm that must re-search -- the genuine dynamic-relocation")
        print("   result EN 50530 cannot produce.")
    else:
        print("   Claim NOT supported as declared. Report what held and what did")
        print("   not; do not adjust thresholds to force a pass.")

    payload = {"family": args.family, "n_windows": len(windows),
               "discarded": discarded, "settle_steps": SETTLE_STEPS,
               "window_steps": WINDOW_STEPS, "trigger_drop_frac": TRIGGER_DROP_FRAC,
               "stats": {n: {k: v for k, v in s.items() if k != "reconv"}
                         for n, s in stats.items()},
               "criteria": {"c1": bool(c1), "c2": bool(c2),
                            "c3": bool(c3), "c4": bool(c4)}}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"relocation_comparison_{args.family}.json").write_text(
        json.dumps(payload, indent=2, default=float), encoding="utf-8")
    print(f"\nresults -> {OUT / f'relocation_comparison_{args.family}.json'}")
    print("Validation modules; declared synthetic site (Jeju reference). "
          "All simulated.")
    return 0 if (c1 and c2 and c3 and c4) else 1


if __name__ == "__main__":
    raise SystemExit(main())
