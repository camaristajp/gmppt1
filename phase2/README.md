# Phase 2 -- baselines and test harness

Phase 2 does not build the learned coefficient. It builds the instrument that will
measure it, and the baselines it will be measured against. The thesis reduces to one
comparison: adaptive coefficient vs baselines, same scenarios, power loss vs true GMPP.

## Acceptance criteria (declared before running -- see gmppt/harness.py ACCEPTANCE)

| Quantity | Target (S8) | Tolerance |
|---|---|---|
| Fixed-0.80 mean power loss | 4.1% | +/- 0.3 pt |
| Best constant k | 0.82 | +/- 0.01 |
| Best-constant mean loss | 3.5% | +/- 0.3 pt |
| Costly fraction, sub-substring (>1%) | 77% | +/- 3 pt |
| Region-error rate, sub-substring | 6.7% | +/- 1.0 pt |
| Worst-case absolute loss | 18.3 W | +/- 1.0 W |

A harness that cannot reproduce these on MASTER_SEED is a broken harness, not a new
finding. p1 is the gate on every downstream step.

## Method contract

    fn(ctx) -> float          # returns a landing voltage

ctx exposes v_oc, i_sc, module, geometry, rng, and probe(v) -> power. It does NOT
expose the P-V array or the true GMPP. The ceiling is sealed from the method by
construction, so no result can be contaminated by lookahead.

## Status ledger

| Step | Script | Depends on | Status |
|---|---|---|---|
| P2.1 | gmppt/harness.py | -- | handed over |
| P2.2 | p1_harness_regression.py | P2.1 | not run |
| P2.3 | p2_static_baselines.py | P2.2 pass | not run |
| P2.4 | p3_ahmed_salam.py | P2.2 pass | not written |
| P2.5 | p4_basoglu.py | Month-3 sign-off | GATED |
| P2.6 | p5_timedomain.py | Month-3 sign-off | GATED |
| P2.7 | p6_en50530.py | P2.6 | GATED |

Redirection-independent: P2.1 through P2.4. Safe to build now.
Redirection-dependent: P2.5 onward. Do not start before the Month-3 meeting.

## Outstanding dependency

Full multi-peak magnitude at module scale is deferred to Phase 8 and needs partner
measurement (swept I-V, or one module on loan). This is critical path. Raise it at
the Month-3 meeting.
