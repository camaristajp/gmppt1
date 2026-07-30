# Phase 1 Verification Log

Toolchain: Python 3.12, pvlib 0.15.2, matplotlib 3.11.1, CEC database
(21,535 modules). Everything seeded; scripts in `phase1/`, outputs and figures
in `results/`.

Stages (see WORKFLOW.md): Stage 1 = S1+S2 (env + STC), Stage 2 = S3+S4 (shading
physics + external validation), Stage 3 = S5 (array, standalone/early),
Stage 4 = S6+S7+S8 (pipeline -> Gate A). Invariant: S4 green before any S6-S8.

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
S1, S2, S3 PASS (12 tests). Simulator now produces the multi-peak characteristic.
Not yet done: S4 (published-shading reproduction = verification step 2), S5
(array generalisation), S6-S8. Gate A cannot be evaluated until S6-S8 complete.

## S3 - reverse-bias (Bishop) + bypass diodes - PASS
Module = 3 substrings in series, each a cell-fraction-scaled single-diode model
(a_ref, R_s, R_sh_ref scaled by 1/3; I_L_ref, I_o_ref, alpha_sc unchanged),
extended into reverse bias by pvlib bishop88, shunted by an anti-parallel bypass
diode (I0=1e-9 A, n=1). Composed in the current domain: I_elem(V) = I_substring(V)
+ I_bypass(V), inverted to V(I), summed across substrings.

Four checkpoints, all enforced by tests (test_s3_device.py):
1. UNSHADED CONSISTENCY - 3 uniform substrings reproduce the direct single-diode
   module to 3 sig figs: P_mp exact (0.0000%), V_oc/I_sc/V_mp/I_mp all OK. This
   proves the scaling + composition are correct.
2. MULTI-PEAK - substrings at 1000/600/300 W/m^2 give 3 peaks; GMPP = 125.5 W at
   25.1 V (mid-curve), vs 100.8 W at the rightmost peak the fixed-0.8 model
   targets. Staircase confirmed (bypass switching at ~40->28 V and ~24->13 V).
3. BYPASS ACTIVATION - a 200 W/m^2 substring forced to the bright Isc clamps at
   -0.582 V, as expected for a ~0.6 V bypass diode.
4. REVERSE-BIAS INSENSITIVITY - turning avalanche on (factor 2e-3) vs off moves
   GMPP by 0.000%. The bypass clamps long before avalanche, so the uncertain
   reverse-bias parameters (a named limitation) are inert in normal multi-peak
   operation and matter only near-threshold / under sub-substring shading (S6).
   Default is breakdown_factor=0; the parameters are exposed for the S6 sweep.

Reverse-bias parameters are documented as an explicit assumption, not fitted.
Bypass diode I0/n are stated parameters, exposed for sensitivity.
