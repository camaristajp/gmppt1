# Phase 1 Workflow — Stages, Done-Criteria, Invariants

Phase 1 goal: a *verified* simulator plus a coefficient characterisation that
terminates in **Gate A**. The eight S-steps are grouped into four stages for
reporting and checkpointing. Grouping does **not** remove any per-step gate or
convergence check — each S-step still proves its own number before the next.

## Stages

| Stage | S-steps | What | Done when |
|---|---|---|---|
| 1 | S1, S2 | Environment + STC verification | S1 reproduces the CEC spread; S2 gated quantities (V_oc, V_mp, I_mp) match datasheet to 3 sig figs across the design span. **DONE.** |
| 2 | S3, S4 | Shading physics + external validation | Stepped I-V / multi-peak P-V correct, reverse-bias params recorded as a **swept range**; Basoglu + one baseline reproduce to reported precision. (S3 done; S4 pending source cases.) |
| 3 | S5 | Array generalisation | Single module is the N=1 special case; a short string composes correctly. Standalone (see note). |
| 4 | S6, S7, S8 | Scenario gen -> labelling -> characterisation -> **Gate A** | S6 seeded generator + by-module split; S7 GMPP labelling passes its step-halving convergence check; S8 statistics converge and the three headline numbers (coefficient distribution, region-error rate, worst case in watts) are stable. Ends in Gate A. |

## Invariants (cannot move)

1. **S2 green before S3 is built.** (Met.)
2. **S4 green before anything in the S6-S8 block runs.** No exceptions. Merging
   stages changes how we report and checkpoint; it is NOT permission to run a
   merged stage and only test at the end. Each S-step is proven before the next.
3. Every S-step keeps its own convergence check: S7 step-halving on the dense
   sweep; S8 statistics-convergence on scenario count.

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
- `s1_coefficient_spread.png` — the C1 premise (coefficient distribution).
- `s2_tempcoeff_error.png` — gamma_r faithful, beta_oc ~10% off (open finding).
- `s3_multipeak.png` — stepped I-V and multi-peak P-V.
- `s3_reverse_bias_sweep.png` — GMPP invariant across the swept avalanche range.
