# Phase 1 Workflow — Stages, Done-Criteria, Invariants

Phase 1 goal: a *verified* simulator plus a coefficient characterisation that
terminates in **Gate A**. The eight S-steps are grouped into four stages for
reporting and checkpointing. Grouping does **not** remove any per-step gate or
convergence check — each S-step still proves its own number before the next.

## Stages

| Stage | S-steps | What | Done when |
|---|---|---|---|
| 1 | S1, S2 | Environment + STC verification | S1 reproduces the full-catalogue CEC spread AND saves the c-Si-only pool (in-scope population); S2 gated quantities (V_oc, V_mp, I_mp — the STC operating point) match datasheet to 3 sig figs across the design span. **Gate amended:** temperature coefficients are *not* held to 3 sig figs — unachievable under the CEC parameterisation (only 0.19% of c-Si modules qualify), the beta_oc deviation equals \|Adjust\| and is carried as a documented bias, not a failure. See plan Section 9.2 and the verification log. **DONE.** |
| 2 | S3, S4 | Shading physics + external validation | Stepped I-V / multi-peak P-V correct, reverse-bias params recorded as a **swept range** (S3 done). S4 external validation in three legs: **leg 1** Basoglu structural (peak count/region/ordering reproduced — magnitude gap expected, his source under-specified); **leg 2** single-diode vs Sandia *measurement* model, ~2% near STC and ~2.5% at 55C across 108 c-Si twin pairs (the off-STC error bar, corroborating S2's beta_oc finding independently); **leg 3** quantitative multi-peak validation deferred to Phase 8 (no public dataset exists — confirmed by evaluating Basoglu, a Mendeley set, and a literature search). **DONE.** |
| 3 | S5 | Array generalisation | Single module is the N=1 special case; a short string composes correctly. Standalone (see note). |
| 4 | S6, S7, S8 | Scenario gen -> labelling -> characterisation -> **Gate A** | S6 seeded generator + by-module split; S7 GMPP labelling passes its step-halving convergence check; S8 statistics converge and the three headline numbers (coefficient distribution, region-error rate, worst case in watts) are stable. Ends in Gate A. |

## Invariants (cannot move)

1. **S2 green before S3 is built.** (Met.)
2. **S4 green before anything in the S6-S8 block runs.** (Met — S4 validates the
   single-diode layer against measurement, structurally reproduces Basoglu, and
   documents the multi-peak-composition deferral to Phase 8.) Merging stages
   changes how we report and checkpoint; it is NOT permission to run a merged
   stage and only test at the end. Each S-step is proven before the next.
3. Every S-step keeps its own convergence check: S7 step-halving on the dense
   sweep; S8 statistics-convergence on scenario count.
4. **Determinism across machines.** The c-Si pool, the S2 span, and the S3
   canonical module are all selected by stable sorts with alphabetical
   tie-breaks; the canonical module is pinned in `config.CANONICAL_DEMO_MODULE`
   and its selection criterion re-asserted at run time. Every S-step output
   carries a `config.provenance()` stamp (pvlib version, CEC row count, seed,
   git hash) so a stale artefact is visible rather than silent. S1 asserts the
   CEC catalogue row count against `CEC_ROWS_EXPECTED`.

## S5 placement decision — standalone, scheduled early

S5 is kept a **standalone Stage 3** (not folded into Stage 2). Rationale: the
plan (Section 9.2 and the Gate A note in Section 10) treats array-capability as
insurance that must exist *before* Gate A, so that a Gate A(ii) redirect to
string level costs 2-3 weeks, not two months. Folding S5 into Stage 2 makes it
the first casualty of a Stage 2 overrun — exactly the outcome that insurance is
meant to prevent. To keep the freshness benefit (S5 extends S3's substring
composition), it is **scheduled immediately after Stage 2**, but remains its own
checkpointed stage so it cannot be quietly dropped.

## Gate A (end of Stage 4) — both conditions must hold
(i) region-error rate under sub-substring geometry stays negligible;
(ii) a recalibrated constant does not already solve it AND the worst case is
non-trivial in watts.
Fail (i) -> return to multi-peak framing. Fail (ii) -> redirect to string level
(uses the Stage 3 array-capable simulator).

## Figures produced (regenerable, git-ignored)
- `s1_coefficient_spread.png` — the C1 premise, full catalogue (all technologies).
- `s1_coefficient_spread_csi.png` — the in-scope c-Si distribution (the one C1 claims about).
- `s2_tempcoeff_error.png` — gamma_r faithful, beta_oc deviation == |Adjust| (resolved, not open).
- `s3_multipeak.png` — stepped I-V and multi-peak P-V (canonical module).
- `s3_reverse_bias_sweep.png` — avalanche params cannot act in this regime (scoped claim, not "invariant generally").
- `s4_sandia_crosscheck.png` — single-diode layer validated vs Sandia measurement (~2% near STC, ~2.5% at 55 °C) across 108 c-Si twin pairs.
