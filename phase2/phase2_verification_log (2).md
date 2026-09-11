# Phase 2 Verification Log

**Project:** A Conditional Peak-Voltage Coefficient for Model-Based Global MPPT in Module-Level Solar Optimizers
**Department of Computer Engineering, Jeju National University**
Advisor: Prof. Young-Chul Byun · Industry collaboration: Nanum Energy Co., Ltd. (Jeju)

Companion to the Phase 1 verification log. Records each Phase 2 step, the tolerance declared before each comparison, the outcome, and the defects found. Entries are appended in execution order and are not rewritten after the fact; corrections appear as new entries so the sequence of what was believed, and when, remains legible.

Provenance for all entries: pvlib 0.15.2, CEC catalogue 21,535 rows, `MASTER_SEED = 20260901`, `BREAKDOWN_MODE = "on"`, `N_SUBSTRINGS = 3`.

**Status: the static half of Phase 2 is complete.** Five buildable baselines and two oracle reference rows are measured on one verified instrument; GMPP label integrity is screened. The remaining steps (Başoğlu, the time-domain layer with P&O/InC/PSO, EN 50530) are gated on confirmation of the Gate A redirection at the Month-3 technical meeting.

---

## Scope

Phase 2 produces the measuring instrument and the baselines against which the learned conditional coefficient (C3) will be assessed. It does not produce the learned coefficient.

The thesis reduces to one comparison: the adaptive coefficient against the baselines, on identical scenarios, scored by power loss relative to the true GMPP. For that comparison to carry weight the instrument and every baseline must exist and be fixed *before* the learned method does, so that the target cannot be adjusted afterwards.

---

## P2.1 — Comparison harness

**Deliverable:** `gmppt/harness.py` (revision 3)

A method-agnostic instrument. Any GMPPT method is a callable receiving a `Context` and returning a landing voltage; the harness scores it by power loss against the true GMPP.

**Design requirement, stated in advance rather than observed afterwards:** the method never receives the P–V array or the true GMPP. It sees open-circuit voltage, module identity, shading geometry, physical conditions, and a `probe(v)` callable returning power at a voltage. Every probe is counted, so measurement cost is recorded alongside accuracy. The seal is enforced by a unit test asserting that no field named `p_gmpp`, `v_gmpp`, `ceiling`, or `k_true` is publicly reachable on `Context`, so a later edit cannot silently widen the contract.

The harness calls `device.module_iv`, `device.analyse` and `scenarios.generate` directly, and reproduces S8's call pattern — same module parameters, same breakdown state, same sorting — so that it measures the quantity Phase 1 measured rather than a parallel reconstruction of it.

| Rev | Change | Reason |
|---|---|---|
| 1 | Initial | — |
| 2 | Adapter rewritten against verified signatures; fixed-coefficient baseline corrected; recalibration sweep aligned to S8 §C; per-scenario cross-check added | Defect 1 |
| 3 | `Context.conditions` added (irradiances, temperature) | Conditional methods require the physical inputs. Conditions are inputs, not answers; the ceiling remains sealed and the seal test still passes. |

---

## P2.2 — Harness regression against S8

**Deliverable:** `phase2/p1_harness_regression.py`

### Tolerances declared before the run

| Quantity | Target (S8) | Tolerance | Subset |
|---|---|---|---|
| Fixed-0.80 mean power loss | 4.1% | ±0.3 pt | recal sample |
| Best constant k | 0.82 | ±0.011 | recal sample |
| Best-constant mean loss | 3.5% | ±0.3 pt | recal sample |
| Costly fraction (>1%) | 77% | ±3 pt | sub-substring |
| Region-error rate | 6.7% | ±1.0 pt | sub-substring |
| Worst absolute loss | 18.3 W | ±1.0 W | all |

Subsets are recorded explicitly because these S8 figures originate from three different populations: §C uses a 300-scenario sub-substring sample under `seed_for("s8_recal")`; §B uses all sub-substring scenarios; §D uses the full set.

### Result: 6/6 PASS

| Check | Value | Target |
|---|---|---|
| Fixed-0.80 mean loss | 4.092% | 4.1 ± 0.3 |
| Best k | 0.820 | 0.82 ± 0.011 |
| Best-k mean loss | 3.459% | 3.5 ± 0.3 |
| Costly fraction | 77.356% | 77.0 ± 3.0 |
| Region error | 6.732% | 6.7 ± 1.0 |
| Worst absolute loss | 18.271 W | 18.3 ± 1.0 |

### Supporting checks

- **Per-scenario cross-check against `evaluate_scenario`:** maximum absolute difference 0.00000, mean absolute difference 0.00000, zero scenarios differing by more than 0.005 across 2,000 cases. This is the load-bearing evidence: aggregate agreement can conceal compensating errors, per-scenario identity cannot.
- **Region-error attribution:** harness 6.7% against reference 6.7%.
- **Probe-path integrity:** dense-probing oracle returns 0.0008% mean loss, confirming the probe interface is itself lossless.

**Status: instrument verified. All subsequent Phase 2 comparisons are admissible.**

---

## P2.3 — Constant baselines

**Deliverable:** `phase2/p2_static_baselines.py` → `results/phase2/baseline_table.md`, `k_sweep.csv`

### Recalibrated-constant sweep (C2)

Thirteen constants from 0.62 to 0.86 on the S8 recalibration sample:

| k | 0.62 | 0.66 | 0.70 | 0.74 | 0.78 | 0.80 | **0.82** | 0.84 | 0.86 |
|---|---|---|---|---|---|---|---|---|---|
| mean loss % | 20.35 | 16.86 | 12.36 | 8.32 | 5.14 | 4.09 | **3.46** | 3.52 | 4.48 |

The curve has a single shallow minimum. Recording it in full rather than only its minimum forecloses the objection that some untested constant performs better: the entire return available from recalibration is 0.63 pt.

### Findings

1. **The failure is shading-specific.** Under uniform irradiance the fixed rule gives 0% region error and 0.84% mean loss. Fractional-Voc is not broken in general; it breaks under shading. This forecloses the reading that the thesis merely rediscovers a weak heuristic.

2. **Recalibration improves the centre and degrades the tail.** Moving from 0.80 to 0.82 improves mean, median, costly fraction, region error and worst watts, but worst-case *percentage* loss rises from 36.28% to 39.92%. The worst absolute case also relocates: under 0.80 it is a whole-substring scenario at 18.3 W; under 0.82 a **uniform** scenario at 15.3 W, where that geometry's worst case had been 7.4 W. A mean-optimised constant sits where the bulk of the distribution lies, and modules whose true coefficient is furthest from 0.82 absorb the cost — including unshaded ones.

3. **Recalibration does not clear the Gate A bar.** Sub-substring region error falls only from 6.7% to 5.6%, above the 5% negligibility threshold.

4. **The costly fraction barely moves.** 77.4% → 72.0% under sub-substring shading.

---

## P2.4 — Ahmed–Salam conditional α

**Reference:** J. Ahmed and Z. Salam, *An Improved Method to Predict the Position of Maximum Power Point During Partial Shading for PV Arrays*, IEEE Trans. Ind. Informat., 11(6), 1378–1387, Dec. 2015.

**Deliverables:** `gmppt/baselines.py` (revision 6), `phase2/p3_ahmed_salam.py`, `phase2/p3b_ahmed_salam_scan.py` (revision 2)

### Method

Equation (27): `V_LP,k = (α · N_{k−1} + 0.8 · N_k) · V_oc`. Two terms with distinct roles: α corrects **where the region begins**; the second term, still 0.8, sets **where the tracker lands inside it**. Irradiance is not measured but inferred from current-step ratios (eq. 14).

### Pre-comparison verification

Reproduction of the paper's own worked example (Case 2, MSX60, V_oc 21.1 V; groups 4×1000 / 4×700 / 2×300):

| Peak | Computed | Paper | Deviation |
|---|---|---|---|
| 1 | 67.52 V | 67.52 V | 0.00 V |
| 2 | 140.95 V | 140.94 V | 0.01 V |
| 3 | 193.28 V | 193.27 V | 0.01 V |

Declared tolerance 0.5 V. **PASS.** The runner refuses to proceed to scenarios if this fails.

An independent confirmation emerged from the scenario run: on uniform scenarios the method reproduces the fixed-0.80 figures exactly (0.84% mean, 33.0% costly) using **1 probe instead of 3**, because a single subassembly collapses equation (27) to 0.8·V_oc with one candidate.

Three further checks run before every scenario execution: ragged-irradiance reduction, detector sampling invariance, and the group-size estimator. All pass.

### Scope translation and its limits

The paper addresses a string of N modules; this project is module-level with three substrings. Per S5 (module = N=1 string), the substring assumes the role of the module and `V_oc,element = V_oc,module / 3`.

- **Design regime.** The paper states that below five modules per string the 0.8 model is reasonably valid, and that deviation grows with string length. At three substrings this work operates inside the regime where the authors expect the fixed model to suffice. That it nonetheless fails here is a finding of this thesis, arising from within-module coefficient scatter rather than accumulation along a long string.
- **Sub-substring geometry lies outside the method's scope.** Ahmed–Salam models each subassembly as uniformly irradiated elements; a substring shaded below substring level has no representation in their model. Reducing such a substring to the minimum across its cell groups is the closest faithful translation, but it is this work's extension. **The `whole_substring` rows are the fair comparison.**
- **α is partly digitised.** Values at 1000, 900, 800, 700, 300 and 100 W/m² are stated in the paper text; those at 600, 500, 400 and 200 are read from Fig. 8 and carry roughly ±0.01.
- **α anchoring is undetermined by the paper.** Fig. 8 may be read at a group's absolute irradiance or at 1000 × its ratio to the previous group. The better choice **reverses between geometries** — absolute wins on sub-substring (1.91% vs 2.50%), ratio on whole-substring (1.62% vs 1.95%). Both are reported.

---

## P2.4b — Final baseline comparison

**Deliverable:** `phase2/p3b_ahmed_salam_scan.py` (revision 2) → `results/phase2/ahmed_salam_ladder.md`

### Whole-substring — the fair comparison

| Variant | Mean % | Worst W | Worst % | Costly % | Region err % | Probes |
|---|---|---|---|---|---|---|
| fixed 0.80 | 3.32 | 18.3 | 33.60 | 74.1 | 4.8 | 3.0 |
| recalibrated 0.820 | 2.45 | 12.9 | 39.92 | 61.7 | 3.8 | 3.0 |
| oracle, absolute α *(ceiling)* | 1.95 | 10.9 | 35.14 | 49.7 | 1.5 | 3.0 |
| oracle, ratio α *(ceiling)* | 1.62 | 14.1 | 32.22 | 47.3 | 2.7 | 3.0 |
| **scan, realistic** | **1.48** | 15.6 | 41.32 | 43.2 | 2.6 | 62.7 |

### Sub-substring — outside the method's design scope

| Variant | Mean % | Worst W | Costly % | Region err % | Probes |
|---|---|---|---|---|---|
| fixed 0.80 | 4.41 | 17.5 | 77.4 | 6.7 | 3.0 |
| recalibrated 0.820 | 3.81 | 14.3 | 72.0 | 5.6 | 3.0 |
| oracle, absolute α *(ceiling)* | 1.91 | 9.2 | 48.3 | 2.7 | 3.0 |
| oracle, ratio α *(ceiling)* | 2.50 | 13.2 | 57.3 | 3.3 | 3.0 |
| **scan, realistic** | **2.41** | 13.2 | 56.9 | 3.4 | 62.8 |

### Findings

1. **Equation (14) fully recovers the irradiance information.** Anchoring-matched, the realistic scan **outperforms** the oracle it approximates: 1.48% against 1.62% on whole-substring, 2.41% against 2.50% on sub-substring. Measured current ratios are better input than nominal irradiance ratios, because the current levels reflect what the composed curve actually does.

   **Consequence:** there is no unrecovered information in the scan. Any claim that a learned method extracts information the published rules leave behind is unsupportable. An interim framing to that effect (Defect 4) is withdrawn.

2. **The accuracy gain is bought with measurement cost.** The realistic method beats the best constant by 0.97 pt on whole-substring and 1.40 pt on sub-substring, at ~33 probes against 3 (P2.4c: 30 probes performs identically to 240, so the default 60-probe budget overstates the requirement). Eleven times the measurement cost, on every control cycle, on MCU-class optimizer hardware.

3. **Region selection at module level is already solved by prior art.** Sub-substring region error falls to 2.7–3.4%, below the 5% Gate A threshold. C3 must therefore **not** be positioned as a region-selection fix.

4. **No method occupies the low-mean, low-tail corner.** Among buildable methods on whole-substring, Ahmed–Salam has the best mean (1.48%) but a 15.6 W worst case and a 41.32% worst percentage — the latter worse than the fixed rule's 33.60%. The recalibrated constant has the best worst case (12.9 W) but a 2.45% mean. Every method that improves the average relocates its failures rather than removing them. This is a frontier, and nothing tested breaks it.

5. **A prediction was recorded and falsified.** Before P2.4 the expectation was that region error would improve while the costly fraction held roughly constant, on the reasoning that the landing term remains 0.8. The costly fraction in fact fell from 72.0% to 48.3%. The α offset does not only select the region; by displacing the whole candidate rightward it also changes the landing point within it.

---

## P2.4c — Detector sensitivity

**Deliverable:** `phase2/p3c_scan_sensitivity.py` (revision 2)

### Tolerance declared before the run

- Spread below 0.30 pt → the detector is not the limitation; report the default-configuration figure with the sweep as evidence.
- Spread at or above 0.30 pt → report the range, not a single figure.
- Monotonicity guard → if loss rises systematically with probe count, the detector remains density-coupled and the run is void.

The criterion is deliberately a *spread* test rather than a *best-value* test. Following Defect 2, a rule rewarding the discovery of a better corner is the wrong incentive.

### Result: ROBUST

Grid: probe budget {30, 60, 120, 240} × plateau tolerance {0.02, 0.04, 0.08}. Sub-substring mean loss ranged 2.41–2.51%, **spread 0.10 pt**. Mean loss by probe budget: 30 → 2.44%, 60 → 2.44%, 120 → 2.48%, 240 → 2.48%. Flat; the monotonicity guard is not triggered.

**Consequence:** the realistic figure is the method's ceiling, not the detector's, and **30 probes performs identically to 240**, so the honest measurement cost is ~33 probes.

### α range limit (detector-independent)

| Geometry | n | Clipped at 100 W/m² floor | Lowest effective G |
|---|---|---|---|
| sub_substring | 817 | 12.2% | 13.7 W/m² |
| whole_substring | 880 | 0.3% | 97.0 W/m² |
| uniform | 303 | 0.0% | 107.0 W/m² |

Ahmed–Salam's α curve is tabulated over 100–1000 W/m². Under deep sub-substring shading the minimum-reduction yields effective substring irradiance as low as 13.7 W/m², so one sub-substring scenario in eight reads α at the table floor where it no longer discriminates between shading depths. Clipping is a defensible extrapolation; recorded as a limitation, not a defect. Its significance is that the method is applied outside the range its survey covers, in precisely the regime this thesis targets.

---

## P2.4d — Datasheet baseline

**Deliverables:** `gmppt/datasheet.py` (revision 2), `phase2/p4_datasheet_baseline.py` (revision 2)

Addresses the gap previously recorded as limitation 8: the baseline set lacked the thing an engineer tries first — the module's own V_mp/V_oc from its datasheet. Two variants: per-module (nameplate only) and per-module with temperature correction (nameplate plus a back-of-module sensor). Both are already *conditional*, using only information a deployed optimizer has, and both cost the same three probes as a constant.

### Pre-comparison verification

| Check | Result |
|---|---|
| Canonical module coefficient vs the `config.py` pin | 0.8107 vs 0.8107 (±0.001). **PASS** |
| β_oc found and negative | −0.14004 V/°C = −0.3119 %/°C of V_oc. **PASS** |
| Temperature direction vs the simulator | datasheet −0.0232, simulated −0.0264 across 25→60 °C; same direction. **PASS** |

The direction check is worth recording for its own sake: a catalogue value plus a single temperature coefficient reproduces the full single-diode model's temperature behaviour to within about 0.003 in k. That is a small independent corroboration of the simulator from a direction L3 did not cover.

**Approximation declared:** the CEC entry carries no separate V_mp temperature coefficient, so β_oc is applied to both voltages. Direction correct, magnitude approximate.

**A prior error is recorded:** revision 1 of the direction test asserted that k *rises* with temperature. This was wrong arithmetic — applying the same absolute shift to both voltages gives (V_mp − d)/(V_oc − d), which *falls* since V_mp < V_oc. Revision 2 verifies the direction against the simulator rather than asserting it.

### Expectations declared before the run

1. On uniform scenarios the datasheet coefficient should clearly beat fixed 0.80 (0.84%).
2. On sub-substring scenarios it should help little — under 0.5 pt.

### Result: both hold

| Method | Uniform | Whole-substring | Sub-substring | Probes |
|---|---|---|---|---|
| fixed 0.80 | 0.84% | 3.32% | 4.41% | 3.0 |
| datasheet (per module) | **0.49%** | 2.75% | 3.92% | 3.0 |
| datasheet + temperature | 0.69% | 3.36% | 4.35% | 3.0 |

Uniform: 0.84% → 0.49% (+0.35 pt), worst case 7.4 W → 2.8 W, costly fraction 33.0% → 14.2%. Sub-substring: 4.41% → 3.92% (+0.49 pt), a tenth of the available loss.

### Findings

1. **Module-to-module variation is not the problem.** The datasheet coefficient is *correct* about each module — it nearly halves the loss under uniform light. Under shading it recovers almost nothing. The measured spreads make the reason plain: module-to-module s.d. 0.0152, temperature 25→60 °C about 0.023 total, shading (sub-substring) s.d. 0.21. Shading dominates both others combined by roughly an order of magnitude.

2. **Temperature correction makes things worse under shading.** 3.92% → 4.35% on sub-substring; 2.75% → 3.36% on whole-substring, worse than plain fixed 0.80. It helps in one place only: worst-percentage loss, 33.89% → 24.95%.

   No expectation was declared on this, so the following is a hypothesis stated after the fact. The correction is physically sound and lowers k with temperature, but under shading the true coefficient has already collapsed toward 0.64 for unrelated reasons; lowering the estimate further moves away from a target that has moved elsewhere. Correct physics applied to a situation it does not describe. Recorded with the numbers, not asserted as a mechanism.

3. **The two cheap conditional alternatives are closed off.** Per-module conditioning recovers a tenth of the loss under shading; per-module plus temperature actively hurts. Only conditioning on the *shading* works, and the one published method that does costs eleven times the measurement.

---

## P2.5 — Near-tie peak screen

**Deliverables:** `phase2/p5_near_tie_screen.py` (revision 2), `phase2/p5b_near_tie_figures.py`

The project checklist flagged this screen as needing to **precede** Phase 2 baseline scoring. It did not; this run closes that gap retrospectively, and the result determines whether the preceding tables stand.

**Motivation.** Betti et al. (Energies 17(10):2276, 2024) observed against measured hardware that where two peaks were close in magnitude, the measured maximum power point occurred at 19 V while their simulation placed it at 34.2 V, and noted that special care is needed when local and global maxima become close.

**Method.** The label cannot be checked against a truth outside the simulator — there is none. Following the L4 pattern, each substring irradiance is perturbed by ±1% (the accuracy class of the I-V tracer Betti used) and the run counts how often the labelled GMPP jumps to a different peak.

### Tolerances declared before the run

| Quantity | Bar | Result | |
|---|---|---|---|
| Near-tie fraction (top two within 1%) | < 5% | 1.95% | **PASS** |
| Label flip rate under ±1% irradiance | < 2% | 0.20% (4 of 2000) | **PASS** |
| Power-loss impact of a flip | < 1 pt | 0.99 pt | **PASS** |
| Region-error impact | reported, no bar | 1.9% of scenarios | — |

### Near-tie count

| Margin | Scenarios | Of all | Median ΔV | Max ΔV |
|---|---|---|---|---|
| 0.5% | 18 | 0.9% | 12.6 V | 24.3 V |
| 1.0% | 39 | 1.9% | 12.4 V | 29.9 V |
| 2.0% | 65 | 3.2% | 12.7 V | 29.9 V |
| 5.0% | 158 | 7.9% | 12.8 V | 29.9 V |

By geometry at the 1% margin: sub-substring 2.4%, whole-substring 2.2%, **uniform 0.0%** — correct, since single-peak curves have no rival.

### Findings

1. **The baseline tables stand.** Near-tie peaks are near-tie *in power*, so a mislabelled peak costs at most 0.99 pt and only on the 1.9% of scenarios where it could occur. The power-loss metric is self-protecting by construction; this run measures that rather than assuming it. Every Phase 2 number is unaffected.

2. **Region-error rates carry an ambiguity that must be quoted.** 1.9% of scenarios could flip that binary flag at near-zero power cost. The headline sub-substring region error of 6.7% should therefore be reported as *6.7%, of which up to ~1.9 pt is near-tie ambiguity* rather than as a clean figure. Unlike power loss, this metric cannot protect itself.

3. **Labels are robust enough to train on, but the failure mode is large when it occurs.** Flip rate 0.2%; among the four flipped, median power gap 0.70% — small, as a flip requires. But a flip moves a supervised target by a median **12.4 V, up to 29.9 V**, against Betti's measured 15 V. The simulator reproduces the same failure mode at the same magnitude, independently.

4. **Voltage separation is quantised at approximately V_oc/3.** Separation clusters near 12 V almost independently of the power gap, because peaks sit at substring boundaries. A label flip therefore displaces the target by one substring's worth of voltage rather than an arbitrary amount.

   This is a structural hint for C3 that emerged from a screen run for a different purpose: the error structure is discrete, suggesting a model that predicts *which* substring boundary and then refines within it, rather than regressing a free voltage. Raised as an architecture question for the Month-3 meeting, not adopted here.

**Consequence for Phase 3.** The two candidate training objectives behave differently on the same 39 scenarios: a supervised target is wrong by 12–30 V, a power-based target by under 1%. This does not make supervised training wrong — 1.9% of scenarios at a 0.7% power consequence is tolerable — but it converts the objective choice from a preference into a decision with numbers attached. Recommendation for the Month-3 meeting: train supervised, report power loss as the primary metric, and down-weight or exclude near-tie scenarios if label error dominates the residual.

---

## Defect register

Six defects were found in Phase 2, all in this work's own code. Each is recorded with its mechanism and resolution, since the pattern of failure is itself methodologically informative.

### Defect 1 — Baseline definition mismatch (harness rev 1)

The fixed-coefficient baseline was implemented as a single landing at `k·V_oc`. S8's `_loss_for_constant` builds candidates at `n·k·V_oc/n_sub` for n = 1…3 and keeps the highest-power one. The harness would have measured a different method and failed regression for a reason unrelated to the instrument. Detected by reading `s8_characterisation.py` before writing the adapter rather than inferring the API from signatures. Corrected in rev 2; verified by per-scenario identity.

### Defect 2 — Density-coupled step detector (baselines rev 4)

`scan_steps()` thresholded the drop between consecutive samples, `cur[j] − cur[j+1] > STEP_FRAC · I_max`. The left-hand side shrinks with sampling density while the right-hand side is fixed. At 240 probes no physical step cleared the threshold, the detector reported a single uniform group, and equation (27) returned one candidate — strictly worse than the three-candidate fixed rule.

**Symptom.** P2.4c revision 1 produced a 29.6 pt spread with mean loss **rising monotonically with probe count**, reaching 32.06% at 240 probes.

**Declared-rule override.** Revision 1's rule stated "improvement ≥ 0.20 pt → report the best configuration". It was overridden deliberately: the rule presupposed the sweep measured detector *quality*; it measured a defect, and selecting the most favourable corner of a defective surface is precisely the cherry-picking the two-sided reporting discipline exists to prevent.

**Resolution.** Revision 5 detects plateaus rather than edges, using two dimensionless criteria so neither is coupled to sampling density. `test_detector_invariance()` requires the same level count within 2% at 30/60/120/240 probes on a synthetic staircase.

**Effect on results.** The realistic figure moved from 3.07% to 2.41% on sub-substring — the defect had been penalising the competing method by roughly 0.6 pt.

### Defect 3 — Malformed scan-G variant (baselines rev 5)

`ahmed_salam_scan_g` padded the level list by repeating the last level where scanned and true group counts disagreed. A repeated level yields a ratio of 1.0, so α reads 0.80 and the offset degrades. It scored 3.32% against the fully inferred variant's 2.41% despite more information, with a 41.5 W worst case against 13–16 W elsewhere. **Removed rather than repaired** (rev 6): it existed to answer whether group-size knowledge helps, and P2.4b had already answered it.

### Defect 4 — Mis-decomposed information cost (reporting)

The P2.4b runner compared the oracle-**absolute** row against the realistic row and labelled the difference an information cost, conflating α anchoring with information. An interim framing — that ~1.16 pt of information sits unrecovered in the scan and that C3 would recover it — was stated and is **withdrawn**. Recorded because a reporting error that survives into a thesis is more damaging than a code error that produces an implausible number.

### Defect 5 — Wrong peak-tuple index (near-tie screen rev 1)

`device.analyse()` returns peaks as `(V, I, P)` triples; revision 1 read position 1 as power. Every power gap was computed as roughly (186 W − 4.9 A)/186 W ≈ 97%, so **no scenario ever appeared near-tied** — the reported zero near-ties at every margin was an artefact. Sorting by position 1 also ordered peaks by current, placing the lowest-voltage peak first and mis-selecting the rival.

**Detected by implausibility, not by a test.** Zero near-ties at a 5% margin across 1,604 multi-peak curves is not credible for a continuous quantity, and a reported 90.9% power gap among *flipped* labels contradicted the flip itself.

**Resolution.** Revision 2 names the indices as module constants and adds a pre-check that verifies the highest peak's power equals `gmpp["P"]` on 50 scenarios before screening anything, exiting if it does not.

### Defect 6 — Figure artefacts (near-tie figures)

Two presentation defects, no effect on any number. The "N V apart" annotation was drawn above the axes and collided with the subplot title. `np.clip(gaps, 0, 60)` piled all scenarios above 60% into the final histogram bin, producing a ~130-count spike that reads as a mode and is not one. Both corrected in `p5b_near_tie_figures.py`, which regenerates from the saved JSON without re-screening.

### Pattern across the six

Three were caught by a declared check (1, 3, 6). Two were caught only by an implausible downstream result (2, 5), each after a run costing hours, and each detectable in milliseconds by a direct property test. **Where a property is assumed — an index layout, an invariance — test it directly rather than waiting for a result to look wrong.** Both P2.4c and P2.5 now carry such a gate.

---

## Consolidated limitations register

| # | Limitation | Status |
|---|---|---|
| 1 | Multi-peak magnitude at full module scale unverified; no public data exists | Deferred to Phase 8 partner measurement (critical path) |
| 2 | Ahmed–Salam applied outside its design regime on sub-substring geometry | Disclosed; whole_substring identified as the fair comparison |
| 3 | α values at 600, 500, 400, 200 W/m² digitised from Fig. 8, ±0.01 | Disclosed |
| 4 | 12.2% of sub-substring scenarios read α at the 100 W/m² table floor | Quantified |
| 5 | α anchoring (absolute vs ratio) reverses between geometries | Both reported |
| 6 | Group-size estimator is this work's extension; the paper is silent | Shown not load-bearing |
| 7 | All results scoped to cell temperature ≤ 60 °C | Recorded as deliberate scope (L3b) |
| 8 | Datasheet baseline absent | **Closed** — P2.4d |
| 9 | Region-error rates carry up to ~1.9 pt of near-tie ambiguity | Quantified (P2.5); quote with the caveat |
| 10 | Datasheet temperature correction uses β_oc for both voltages (CEC has no V_mp coefficient) | Disclosed |
| 11 | Repository not under version control; `provenance()` reports `nogit` | Open |

---

## L3b — Closure of the 75 °C corner (carried from Phase 1)

L3 recorded a 2.6% error on absolute V_oc at 75 °C. Every quantity this thesis reports is a ratio on a single curve, so the ratio error should be smaller — an argument, not evidence.

**Resolved by scope rather than by measurement.** The scenario set's temperature distribution: minimum 25 °C, median 45 °C, mean 43.2 °C, **maximum 60 °C**, 0.0% above 65 °C. The corner lies outside the range of every reported quantity.

**Recorded statement:** *the single-diode corner weakness at 75 °C lies outside the scenario temperature range (maximum 60 °C, 0% of scenarios above 65 °C) and therefore does not affect C1, the Gate A verdict, or any Phase 2 baseline.*

The planned coefficient-ratio comparison against the certified IEC 61853 matrix was **not executed**, deliberately: it would have measured error at a corner no scenario visits.

**Consequent disclosure.** The 60 °C ceiling is a generator setting, not a physical limit; c-Si modules under high irradiance reach 65–75 °C. All Phase 2 results are scoped to ≤ 60 °C, recorded as a deliberate scope decision.

---

## Status

| Step | Deliverable | Status |
|---|---|---|
| P2.1 | `gmppt/harness.py` (rev 3) | Complete, verified |
| P2.2 | `phase2/p1_harness_regression.py` | Complete, 6/6 pass, per-scenario identity |
| P2.3 | `phase2/p2_static_baselines.py` | Complete |
| P2.4 | Ahmed–Salam, oracle variants | Complete, verified against the paper |
| P2.4b | Final baseline comparison | Complete |
| P2.4c | Detector sensitivity | Complete, ROBUST |
| P2.4d | Datasheet baseline | Complete, both expectations held |
| P2.5 | Near-tie peak screen | Complete, 3/3 pass |
| P2.6 | Başoğlu reimplementation | **Gated** on Month-3 sign-off |
| P2.7 | Time-domain layer; P&O, InC, PSO | **Gated** |
| P2.8 | EN 50530 dynamic harness | **Gated**, depends on P2.7 |

### The buildable baseline set (whole-substring, the fair comparison)

| Method | Mean % | Worst W | Costly % | Probes |
|---|---|---|---|---|
| datasheet + temperature | 3.36 | 17.0 | 77.0 | 3 |
| fixed 0.80 | 3.32 | 18.3 | 74.1 | 3 |
| datasheet (per module) | 2.75 | 17.0 | 66.4 | 3 |
| recalibrated 0.820 | 2.45 | 12.9 | 61.7 | 3 |
| Ahmed–Salam scan | 1.48 | 15.6 | 43.2 | ~33 |

---

## Position after Phase 2's static half

Phase 2 sharpened the contribution. Before P2.4 the claim was that a learned coefficient would outperform a fixed one — soft, since any conditional method should outperform a constant. Two interim framings were subsequently tested and withdrawn: that C3 would fix region selection (already solved by prior art, 2.7–3.4% region error), and that C3 would recover unextracted information from the scan (equation 14 recovers it fully).

What survives is measured and specific:

- **Every cheap alternative is closed with a number.** No constant works (full sweep, 0.63 pt available). Per-module conditioning recovers a tenth of the loss under shading. Per-module plus temperature actively hurts. Only conditioning on the shading works.
- **The published method that does condition on shading costs ~11× the measurement** for 0.97 pt on whole-substring.
- **No method occupies the low-mean, low-tail corner.** The best mean carries a 15.6 W worst case; the best worst case carries a 2.45% mean.
- **The GMPP labels are sound**, with the near-tie ambiguity quantified at 1.9% of scenarios and no effect on the power-loss tables.

C3 and C4 accordingly state one joint claim: **reach Ahmed–Salam's accuracy at constant-like probe cost, while bounding a worst case that no method tested — and no prior art — addresses.**

C1 is untouched by any of the above. It rests on catalogue arithmetic over the CEC c-Si population and 616 measured flash tests, independent of the simulator and of every result in this log.
