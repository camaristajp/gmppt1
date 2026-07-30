# Phase 1 Verification Log

Toolchain: Python 3.12, pvlib 0.15.2, CEC database (21,535 modules).
Everything seeded; scripts in `src/`, outputs in `results/`.

## S1 - CEC coefficient characterisation (simulator-independent) - PASS
Reads V_mp_ref/V_oc_ref from the CEC database; no device model involved.

| quantity | reproduced | Section 4 target |
|---|---|---|
| N | 21,535 | 21,535 |
| range | 0.633-0.874 | 0.633-0.874 |
| mean | 0.8096 | 0.810 |
| s.d. | 0.01727 | 0.017 |
| within +/-0.01 of 0.80 | 40.33% | 40.3% |

Reproduces the preliminary premise exactly. C1's population claim stands on
data independent of the simulator.

## S2 - Single-diode STC verification (3 sig figs) - PASS
CEC single-diode model (calcparams_cec -> singlediode), c-Si modules spanning
the V_mp/V_oc range (both tails + middle).

- **Gated (must match datasheet to 3 sig figs):** V_oc, V_mp, I_mp.
  All match at 0.000% relative error across the span. PASS.
- **I_sc - reported, not gated on datasheet:** model I_sc sits bracketed
  between datasheet I_sc_ref and I_L_ref. The CEC database sets I_L_ref 0-5.6%
  above I_sc_ref (median 0.14%, upper quartile >0.5%); series/shunt resistance
  places the model value inside that bracket (at the low end for high-Rs / low
  V_mp/V_oc modules, near I_L_ref for others). The datasheet offset is therefore
  explained by the CEC parameterisation, not a simulator error, and is
  immaterial to a voltage-based coefficient. Root cause verified against the
  database directly, not assumed; enforced by test_isc_bracketed_by_iscref_and_ilref.

### OPEN CAVEAT - temperature coefficients do NOT reach 3 sig figs
The plan asks for temperature coefficients "to three significant figures".
Under the standard CEC model this is not achievable, because beta_oc and
gamma_r are not inputs - they are emergent from the bandgap model and the fit:

| coeff | model vs datasheet | note |
|---|---|---|
| alpha_sc | ~5-15% off | used indirectly; I_sc temp slope |
| beta_oc | ~5-15% off | V_oc temp slope - **relevant to the coefficient's T-trend** |
| gamma_r | <1.5% off | P_mp temp slope - drives landing-point energy |

Consequence: gamma_r (power) is faithful, so landing-point energy vs
temperature is trustworthy. beta_oc being ~10% off means the *absolute*
temperature trend of V_mp/V_oc (Finding 1) carries a modelling bias, so:
  (a) Task 1 reports the T-trend in normalised as well as absolute terms
      (already planned - this is the cheap test), and treats the absolute
      slope as indicative, not exact;
  (b) the T-trend is cross-checked against the partner's measured I-V at
      temperature in Phase 8 before any temperature-as-a-feature claim is
      made load-bearing.
DECISION NEEDED (see chat): accept emergent temp coeffs + document, or fit
EgRef/dEgdT per module to tighten beta_oc. Recommendation: accept + document;
the study's coefficient question is answered in normalised terms regardless.

## Status
S1, S2 PASS. Simulator verification step 1 (STC) complete for the operating-point
quantities the study uses. Not yet done: S3 (reverse-bias + bypass), S4
(published-shading reproduction = verification step 2). Gate A cannot be
evaluated until S3, S4, S6, S7, S8 are complete.
