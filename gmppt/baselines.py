"""
baselines.py  --  static GMPPT baseline methods.
REVISION 6 -- removes the invalid ahmed_salam_scan_g variant.

PLACE THIS FILE AT:   C:\\Users\\user\\gmppt\\gmppt\\baselines.py
                      OVERWRITE revision 5.

WHY REVISION 6 EXISTS -- a malformed variant of MINE, removed rather than repaired

    ahmed_salam_scan_g paired SCANNED current levels with TRUE group sizes, to
    isolate whether group-size knowledge carries any of the performance. Against
    the revision-5 detector it scored 3.32% on sub_substring -- WORSE than the
    fully inferred ahmed_salam_scan at 2.41%, which has strictly less
    information. Its worst absolute loss was 41.5 W against 13-16 W elsewhere.
    More information cannot make a method worse; the variant was malformed.

    Cause: when the scan detected a different number of groups than the true
    count, the code padded the level list by repeating the last level,
        levels = (levels + [levels[-1]] * len(sizes))[:len(sizes)]
    A repeated level gives a ratio of 1.0, so alpha reads 0.80 and the offset
    term degrades. The number measured the padding, not the method.

    REMOVED RATHER THAN FIXED. The variant existed to answer one question -- does
    knowing the group sizes help? -- and p3b answered it: scan-G and scan agreed
    to two decimals, so group-size knowledge buys nothing once the levels come
    from the scan. Repairing a diagnostic to re-answer a settled question is
    effort the objective does not require.

    Three variants remain: two oracle anchorings, and the realistic scan.

WHAT REVISION 5 FIXED (unchanged here)
    The step detector thresholded the drop between CONSECUTIVE SAMPLES, so
    denser sampling shrank every gap below the threshold. At 240 probes no step
    was detected, eq. (27) returned a single candidate, and the method scored
    worse than the fixed rule. Revision 5 detects PLATEAUS instead: runs holding
    current within PLATEAU_TOL of the run median and spanning at least
    MIN_RUN_FRAC of the budget. Both are dimensionless, so the detector is
    sampling-density independent. Verified by test_detector_invariance() and by
    p3c: 0.10 pt spread across probes {30,60,120,240} x tolerance {0.02,0.04,0.08}.

MEASURED RESULT AFTER THE FIX (p3b re-run, revision 5 detector)
    On whole_substring -- the fair comparison, since sub_substring geometry lies
    outside the method's design scope:
        fixed 0.80            3.32%   18.3 W worst    3 probes
        recalibrated 0.820    2.45%   12.9 W worst    3 probes
        Ahmed-Salam realistic 1.48%   15.6 W worst   ~33 probes
    p3c showed 30 probes achieves the same loss as 240, so ~33 is the honest
    cost: roughly 11x a constant, not the 21x the default 60-probe budget implies.

    NOTE FOR THE WRITE-UP: with alpha anchoring matched, the realistic scan
    slightly OUTPERFORMS the oracle it approximates (2.41% vs 2.50% on
    sub_substring; 1.48% vs 1.62% on whole_substring). Measured current ratios
    are better input than nominal irradiance ratios, because the current levels
    reflect what the composed curve actually does. There is therefore NO
    unrecovered information in the scan, and any claim that a learned method
    "extracts information the published rules leave behind" is unsupportable.
    What remains is measurement COST and the unbounded WORST CASE.

REFERENCE
    J. Ahmed and Z. Salam, "An Improved Method to Predict the Position of Maximum
    Power Point During Partial Shading for PV Arrays," IEEE Trans. Ind. Informat.,
    vol. 11, no. 6, pp. 1378-1387, Dec. 2015.

    Equation (27):  V_LP,k = (alpha * N_{k-1} + 0.8 * N_k) * Voc_element

ALPHA ANCHORING -- OURS, AND IT MATTERS
    Fig. 8 is read either at the group's absolute irradiance or at 1000 * the
    ratio to the previous group. The paper's survey was built from drops starting
    at 1000, so ratio anchoring is arguably more faithful, but the better choice
    FLIPS between geometries (absolute wins on sub_substring, ratio on
    whole_substring). Both are implemented; report both.

ALPHA RANGE LIMIT (measured, p3c)
    Fig. 8 is tabulated over 100-1000 W/m2. Under deep sub-substring shading the
    effective substring irradiance reaches 13.7 W/m2, and 12.2% of sub_substring
    scenarios read alpha at the 100 W/m2 floor where it stops discriminating
    (whole_substring 0.3%, uniform 0.0%). Clipping is a defensible extrapolation,
    but the method is being applied outside the range its survey covers.

SCOPE TRANSLATION AND ITS LIMIT
    The paper works on a string of N modules; this project is module-level with
    N_SUBSTRINGS substrings, so the substring takes the role of the module and
    Voc_element = Voc_module / N_SUBSTRINGS (per S5, a module is the N=1 string).

    Ahmed-Salam models each subassembly as UNIFORMLY IRRADIATED elements. A
    substring shaded below substring level has no representation in their model.
    Reducing it to the minimum across its cell groups is the closest faithful
    translation -- series current is set by the weakest element -- but it is our
    extension. The whole_substring rows are the fair comparison.
"""

from __future__ import annotations

import numpy as np

from . import config
from .harness import Context, constant_method, register  # noqa: F401


# ---------------------------------------------------------------------------
# The alpha curve, paper Fig. 8.
# EXPLICIT in the text: 1000 -> 0.80, 900 -> 0.83, 800 -> 0.85, 700 -> 0.87,
#                       300 -> 0.945, 100 -> 0.97
# DIGITISED from Fig. 8 (approximate, roughly +/- 0.01): 200, 400, 500, 600
# ---------------------------------------------------------------------------
ALPHA_G = np.array([100, 200, 300, 400, 500, 600, 700, 800, 900, 1000], float)
ALPHA_V = np.array([0.970, 0.960, 0.945, 0.920, 0.905, 0.890,
                    0.870, 0.850, 0.830, 0.800], float)
ALPHA_DIGITISED = {200, 400, 500, 600}     # not stated numerically in the paper

LEVEL_TOL = 1.0          # W/m2; irradiances closer than this are one subassembly

# --- detector parameters. BOTH ARE DIMENSIONLESS FRACTIONS, so neither is
# --- coupled to how densely the curve is sampled. That coupling was the rev-4 bug.
SCAN_PROBES = 60         # default probe budget; p3c shows 30 performs identically
PLATEAU_TOL = 0.04       # a plateau holds current within 4% of Isc of its median
MIN_RUN_FRAC = 0.06      # a plateau must span >= 6% of the probe budget
ALPHA_MID = 0.90         # mid-range alpha, used only for group-size estimation


def alpha_of(g: float) -> float:
    """alpha at irradiance g, linearly interpolated on the Fig. 8 curve.

    Clips at 100 and 1000 W/m2. See ALPHA RANGE LIMIT -- 12.2% of sub_substring
    scenarios land on the lower clip.
    """
    return float(np.interp(float(g), ALPHA_G, ALPHA_V))


# ---------------------------------------------------------------------------
# Irradiance handling (true-G path, used by the oracle variants)
# ---------------------------------------------------------------------------

def _reduce_entry(entry) -> float:
    """One substring's effective irradiance: the minimum across its cell groups,
    because series elements share a current set by the weakest."""
    arr = np.atleast_1d(np.asarray(entry, dtype=float))
    return float(arr.min())


def substring_irradiances(irr) -> list[float]:
    """Reduce a scenario's irradiance description to one value per substring.

    Handles RAGGED lists that mix scalars and sequences across substrings:
      [1000, 1000, 400]              -> [1000, 1000, 400]
      [1000, [600, 200], 1000]       -> [1000, 200, 1000]
      [[1000, 900], [400, 400], 800] -> [900, 400, 800]
    """
    n_sub = int(config.N_SUBSTRINGS)
    if irr is None:
        raise ValueError(
            "no irradiances on the Context -- gmppt/harness.py must be revision 3 "
            "or later (Context needs the `conditions` field).")
    entries = list(irr)
    if len(entries) == n_sub:
        return [_reduce_entry(e) for e in entries]
    flat = np.asarray(entries, dtype=float).ravel()
    if flat.size % n_sub == 0:
        return [float(x) for x in flat.reshape(n_sub, -1).min(axis=1)]
    raise ValueError(
        f"cannot map an irradiance list of length {len(entries)} onto {n_sub} "
        f"substrings")


def subassemblies(g_sub: list[float]) -> list[tuple[float, int]]:
    """Group substrings by irradiance level, brightest first: [(G, N), ...]."""
    groups: list[list[float]] = []
    for g in sorted(g_sub, reverse=True):
        if groups and abs(groups[-1][0] - g) <= LEVEL_TOL:
            groups[-1].append(g)
        else:
            groups.append([g])
    return [(float(np.mean(grp)), len(grp)) for grp in groups]


# ---------------------------------------------------------------------------
# Scan-based inference
# ---------------------------------------------------------------------------

def scan_steps(ctx: Context, n_probes: int = SCAN_PROBES,
               plateau_tol: float = PLATEAU_TOL,
               min_run_frac: float = MIN_RUN_FRAC):
    """Locate the I-V staircase by probing. Returns (levels, step_voltages).

    levels          plateau currents, brightest (highest) first
    step_voltages   voltage midway between consecutive plateaus, len(levels)-1

    Density-independent by construction: a plateau is a RUN of samples holding
    current within `plateau_tol` of the run median (a fraction of Isc, not of a
    neighbour gap), spanning at least `min_run_frac` of the budget. Both are
    dimensionless, so the same staircase is seen at 30 and at 240 probes.

    Current is recovered as I = P / V, so the power-only probe interface
    suffices. Every probe is counted by the harness -- that count is the
    measurement cost of not knowing the irradiance.
    """
    v_oc = float(ctx.v_oc)
    n_probes = max(8, int(n_probes))
    vs = np.linspace(0.03 * v_oc, 0.97 * v_oc, n_probes)
    ps = np.array([ctx.probe(float(v)) for v in vs], dtype=float)

    with np.errstate(divide="ignore", invalid="ignore"):
        cur = np.where(vs > 0, ps / vs, 0.0)
    cur = np.nan_to_num(cur, nan=0.0, posinf=0.0, neginf=0.0)

    i_max = float(cur.max())
    if not np.isfinite(i_max) or i_max <= 0:
        return [1.0], []

    tol = plateau_tol * i_max
    min_run = max(2, int(round(min_run_frac * n_probes)))

    runs, start = [], 0
    for j in range(1, n_probes):
        seg = cur[start:j + 1]
        if (seg.max() - seg.min()) > 2 * tol:
            runs.append((start, j - 1))
            start = j
    runs.append((start, n_probes - 1))

    plateaus = [(a, b) for (a, b) in runs if (b - a + 1) >= min_run]
    if not plateaus:
        return [float(i_max)], []

    levels = [float(np.median(cur[a:b + 1])) for a, b in plateaus]
    mids = [float(0.5 * (vs[plateaus[k][1]] + vs[plateaus[k + 1][0]]))
            for k in range(len(plateaus) - 1)]

    keep_levels, keep_steps = [levels[0]], []
    for lv, st in zip(levels[1:], mids):
        if lv < keep_levels[-1] * (1 - 1e-3):
            keep_levels.append(lv)
            keep_steps.append(st)

    # An optimizer knows its own module has N_SUBSTRINGS substrings, so more
    # levels than substrings is a detection artefact -- merge the shallowest gaps.
    n_sub = int(config.N_SUBSTRINGS)
    while len(keep_levels) > n_sub:
        gaps = [keep_levels[k] - keep_levels[k + 1]
                for k in range(len(keep_levels) - 1)]
        k = int(np.argmin(gaps))
        keep_levels.pop(k + 1)
        keep_steps.pop(k)

    return keep_levels, keep_steps


def infer_group_sizes(step_voltages, n_groups: int, v_oc_elem: float) -> list[int]:
    """Estimate N_k from the step voltages. OUR EXTENSION -- the paper is silent
    on recovering group sizes from a scan; its examples simply state them.

    Region k ends near (N_1+...+N_k) * alpha * Voc_element, so the cumulative
    element count is read off each step voltage and differenced. Clipped so every
    group holds at least one element and the total is exactly N_SUBSTRINGS.

    p3b showed this is not load-bearing.
    """
    n_sub = int(config.N_SUBSTRINGS)
    if n_groups <= 1:
        return [n_sub]
    if n_groups >= n_sub:
        return [1] * n_sub

    cums, prev = [], 0
    for k, v_step in enumerate(step_voltages[:n_groups - 1]):
        raw = v_step / (ALPHA_MID * v_oc_elem) if v_oc_elem > 0 else k + 1
        lo = prev + 1
        hi = n_sub - (n_groups - 1 - k)
        cum = int(min(max(round(raw), lo), hi))
        cums.append(cum)
        prev = cum

    sizes, prev = [], 0
    for cum in cums:
        sizes.append(cum - prev)
        prev = cum
    sizes.append(n_sub - prev)
    return sizes


# ---------------------------------------------------------------------------
# Equation (27)
# ---------------------------------------------------------------------------

def predicted_peaks(v_oc_module: float,
                    groups: list[tuple[float, int]],
                    anchor: str = "absolute") -> list[float]:
    """Equation (27) per subassembly. groups = [(level, N_k), ...] brightest first.

    anchor="absolute"  alpha at the group's own irradiance (Fig. 8 as printed);
                       `level` must be an irradiance.
    anchor="ratio"     alpha at 1000 * level_k / level_{k-1}; works with any
                       proportional quantity, so scanned current levels are used
                       directly with no absolute calibration -- eq. (14).
    """
    n_sub = int(config.N_SUBSTRINGS)
    v_oc_elem = v_oc_module / n_sub

    peaks, cumulative = [], 0
    for idx, (level, n_k) in enumerate(groups):
        if idx == 0:
            offset = 0.0
        elif anchor == "ratio":
            prev = groups[idx - 1][0]
            ratio = (level / prev) if prev > 0 else 1.0
            offset = alpha_of(1000.0 * min(max(ratio, 0.0), 1.0)) * cumulative
        else:
            offset = alpha_of(level) * cumulative
        peaks.append((offset + 0.80 * n_k) * v_oc_elem)
        cumulative += n_k
    return peaks


def _land(ctx: Context, peaks: list[float]) -> float:
    """Probe each predicted peak, keep the highest-power one."""
    cands = [min(max(v, 0.0), ctx.v_oc) for v in peaks]
    return max(cands, key=ctx.probe)


# ---------------------------------------------------------------------------
# The three registered variants
# ---------------------------------------------------------------------------

@register("ahmed_salam")
def ahmed_salam(ctx: Context) -> float:
    """True G, true group sizes, alpha at absolute irradiance.

    UPPER BOUND: the paper states per-module irradiance cannot feasibly be
    measured, so this variant cannot be built as tested. Reported as a ceiling.
    """
    groups = subassemblies(substring_irradiances(ctx.conditions.get("irradiances")))
    return _land(ctx, predicted_peaks(ctx.v_oc, groups, anchor="absolute"))


@register("ahmed_salam_ratio")
def ahmed_salam_ratio(ctx: Context) -> float:
    """True G, true group sizes, alpha at the irradiance RATIO. UPPER BOUND."""
    groups = subassemblies(substring_irradiances(ctx.conditions.get("irradiances")))
    return _land(ctx, predicted_peaks(ctx.v_oc, groups, anchor="ratio"))


@register("ahmed_salam_scan")
def ahmed_salam_scan(ctx: Context) -> float:
    """Fully scan-based: G and group sizes both inferred. THE REALISTIC METHOD.

    Uses only what an optimizer can observe -- a sweep of its own module. This is
    the row C3 must be compared against, and the probe count is half the claim.
    """
    n_sub = int(config.N_SUBSTRINGS)
    levels, steps = scan_steps(ctx)
    sizes = infer_group_sizes(steps, len(levels), ctx.v_oc / n_sub)
    return _land(ctx, predicted_peaks(ctx.v_oc, list(zip(levels, sizes)),
                                      anchor="ratio"))


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------

class _FakeContext:
    """A synthetic staircase, for testing the detector without the simulator."""

    def __init__(self, levels, break_fracs, v_oc=36.0):
        self.v_oc = float(v_oc)
        self._levels = list(levels)
        self._breaks = list(break_fracs)
        self.n_probes = 0
        self.conditions = {}

    def probe(self, v):
        self.n_probes += 1
        frac = float(v) / self.v_oc
        cur = self._levels[-1]
        for lv, br in zip(self._levels, self._breaks + [1.1]):
            if frac < br:
                cur = lv
                break
        return cur * float(v)


def test_ahmed_salam_paper_example(verbose: bool = True) -> bool:
    """Equation (27) against the paper's Case 2. Pure arithmetic, no simulator."""
    v_oc_elem = 21.1
    groups = [(1000.0, 4), (700.0, 4), (300.0, 2)]
    expected = [67.52, 140.94, 193.27]

    got, cumulative = [], 0
    for idx, (g_k, n_k) in enumerate(groups):
        offset = 0.0 if idx == 0 else alpha_of(g_k) * cumulative
        got.append((offset + 0.80 * n_k) * v_oc_elem)
        cumulative += n_k

    ok = all(abs(a - b) < 0.5 for a, b in zip(got, expected))
    if verbose:
        print("Ahmed-Salam equation (27) vs paper Case 2 (MSX60, Voc 21.1 V):")
        for i, (a, b) in enumerate(zip(got, expected), start=1):
            print(f"   peak {i}: computed {a:7.2f} V   paper {b:7.2f} V   "
                  f"diff {abs(a-b):.2f} V")
        print(f"   -> {'PASS' if ok else 'FAIL'} (tolerance 0.5 V)")
    return ok


def test_ragged_irradiances(verbose: bool = True) -> bool:
    """Ragged irradiance reduction. Assumes N_SUBSTRINGS == 3."""
    if int(config.N_SUBSTRINGS) != 3:
        if verbose:
            print(f"   skipped: N_SUBSTRINGS is {config.N_SUBSTRINGS}, not 3")
        return True
    cases = [
        ([1000, 1000, 400], [1000.0, 1000.0, 400.0]),
        ([1000, [600, 200], 1000], [1000.0, 200.0, 1000.0]),
        ([[1000, 900], [400, 400], 800], [900.0, 400.0, 800.0]),
        ([[1000, 1000], [500, 300], [200, 900]], [1000.0, 300.0, 200.0]),
    ]
    ok = True
    for raw, want in cases:
        got = substring_irradiances(raw)
        hit = all(abs(a - b) < 1e-9 for a, b in zip(got, want))
        ok &= hit
        if verbose:
            print(f"   {str(raw):<34} -> {got}  {'ok' if hit else 'MISMATCH'}")
    if verbose:
        print(f"   -> {'PASS' if ok else 'FAIL'}")
    return ok


def test_detector_invariance(verbose: bool = True) -> bool:
    """The detector must see the same staircase regardless of sampling density.

    This is what revision 4 failed, and no loss number would have revealed it --
    only invariance does. Criterion: across 30/60/120/240 probes the detected
    level COUNT must be identical and each level value agree within 2%.
    """
    cases = [
        ("three levels", [5.0, 3.2, 1.4], [0.34, 0.67]),
        ("two levels",   [4.5, 2.0],      [0.5]),
        ("one level",    [4.0],           []),
    ]
    budgets = (30, 60, 120, 240)
    ok = True

    for name, levels, breaks in cases:
        seen = []
        for n in budgets:
            ctx = _FakeContext(levels, breaks)
            got, _ = scan_steps(ctx, n_probes=n)
            seen.append(got)
        counts = {len(g) for g in seen}
        same_count = len(counts) == 1
        stable = True
        if same_count:
            for k in range(len(seen[0])):
                vals = [g[k] for g in seen]
                if max(vals) - min(vals) > 0.02 * max(vals):
                    stable = False
        hit = same_count and stable and len(seen[0]) == len(levels)
        ok &= hit
        if verbose:
            print(f"   {name:<14} true {len(levels)} level(s); detected "
                  f"{[len(g) for g in seen]} at probes {list(budgets)}  "
                  f"{'ok' if hit else 'UNSTABLE'}")
            if not hit:
                for n, g in zip(budgets, seen):
                    print(f"      {n:>4} probes -> {[round(x, 3) for x in g]}")
    if verbose:
        print(f"   -> {'PASS' if ok else 'FAIL'}")
    return ok


def test_group_size_estimator(verbose: bool = True) -> bool:
    """The group-size estimator on synthetic step voltages. OUR extension."""
    if int(config.N_SUBSTRINGS) != 3:
        if verbose:
            print(f"   skipped: N_SUBSTRINGS is {config.N_SUBSTRINGS}, not 3")
        return True
    v_elem = 12.0
    cases = [
        ([], 1, [3]),
        ([1 * ALPHA_MID * v_elem], 2, [1, 2]),
        ([2 * ALPHA_MID * v_elem], 2, [2, 1]),
        ([1 * ALPHA_MID * v_elem, 2 * ALPHA_MID * v_elem], 3, [1, 1, 1]),
    ]
    ok = True
    for steps, n_groups, want in cases:
        got = infer_group_sizes(steps, n_groups, v_elem)
        hit = (got == want) and (sum(got) == int(config.N_SUBSTRINGS))
        ok &= hit
        if verbose:
            print(f"   steps={[round(s,1) for s in steps]} n={n_groups} -> "
                  f"{got}  {'ok' if hit else f'MISMATCH (want {want})'}")
    if verbose:
        print(f"   -> {'PASS' if ok else 'FAIL'}")
    return ok


if __name__ == "__main__":
    a = test_ahmed_salam_paper_example()
    print("\nragged irradiance reduction:")
    b = test_ragged_irradiances()
    print("\ndetector invariance:")
    c = test_detector_invariance()
    print("\ngroup-size estimator (our extension):")
    d = test_group_size_estimator()
    raise SystemExit(0 if (a and b and c and d) else 1)