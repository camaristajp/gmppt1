# Phase 1 Verification Log

**Provenance:** pvlib 0.15.2 (pinned) | CEC catalogue 21,535 rows | master seed
20260901 | git 894874c. Regenerated from a clean run of S1 -> S2 -> S3; every
number below is reproduced by `make stage1 stage2`, not hand-transcribed. If the
provenance line printed by a script disagrees with this header, the artefacts are
stale and must be regenerated before they are trusted.

Stages (see WORKFLOW.md): Stage 1 = S1+S2 (env + STC), Stage 2 = S3+S4 (shading
physics + external validation), Stage 3 = S5 (array, standalone/early),
Stage 4 = S6+S7+S8 (pipeline -> Gate A). Invariant: S4 green before any S6-S8.

## S1 - CEC coefficient characterisation (simulator-independent) - PASS

Reads V_mp_ref/V_oc_ref from the CEC database; no device model involved. Two
populations are reported because they play different roles.

**Full catalogue (all technologies)** - the Section 4 headline, reproduced exactly:

| quantity | reproduced | Section 4 target |
|---|---|---|
| N | 21,535 | 21,535 |
| range | 0.6333-0.8741 | 0.633-0.874 |
| mean | 0.80957 | 0.810 |
| s.d. | 0.01727 | 0.017 |
| within +/-0.01 of 0.80 | 40.33% | 40.3% |

**c-Si subset (Mono + Multi)** - the in-scope population (Section 8.2), and the
one saved to `cec_pool.parquet`. Every downstream step draws from this file, so
the technology filter is applied HERE, at pool construction, not at read time:

| quantity | value |
|---|---|
| N | 20,946 |
| range | 0.6977-0.8719 |
| mean | 0.81073 |
| s.d. | 0.01520 |
| within +/-0.01 of 0.80 | 41.00% |

The low tail of the full catalogue (down to 0.633) is thin-film, not outlier
c-Si designs: filtering to c-Si raises the lower bound to 0.698 and tightens the
s.d. from 0.0173 to 0.0152. The premise (0.80 is a population average most
modules miss) survives the filter: 59% of c-Si modules are more than +/-0.01
from 0.80. The frozen c-Si constants live in `config.py` (CSI_POOL_N,
CSI_COEFF_MEAN, CSI_COEFF_SD, CSI_COEFF_RANGE) and S1 asserts the catalogue row
count against CEC_ROWS_EXPECTED so a pvlib/database change cannot pass silently.

## S2 - Single-diode STC verification - PASS (implementation verification at STC)

CEC single-diode model (calcparams_cec -> singlediode) on c-Si modules spanning
the V_mp/V_oc range (both tails + middle), selected deterministically
(percentile-style span, stable sort with alphabetical tie-break).

**What S2 establishes, and what it does not.** The CEC six-parameter set is
extracted so the model passes through the datasheet STC point. Reproducing that
point to 3 sig figs therefore confirms the model is *called correctly* (right
parameters, bandgap defaults, no unit errors) - it is implementation
verification, not physical validation. Physical validation of the shaded/off-STC
regime is S4 (published shading cases) and Phase 8 (measured I-V), per the
invariant.

- **Gated (must match datasheet to 3 sig figs): V_oc, V_mp, I_mp.** All match at
  0.000% relative error across the span. PASS.
- **I_sc - reported, not gated.** Model I_sc sits bracketed between datasheet
  I_sc_ref and I_L_ref (the CEC fit sets I_L_ref >= I_sc_ref; series/shunt
  resistance places the model value inside). Datasheet offset 0.00-1.00% is a
  fit convention, immaterial to a voltage coefficient. Enforced by
  test_isc_bracketed_by_iscref_and_ilref.

### Temperature coefficients - NOT gated (plan Section 9.2 amended)

The original plan text asked for temperature coefficients "to three significant
figures". **This is not achievable under the CEC parameterisation and the gate
was amended** (plan rev: Section 9.2 now gates on the STC operating point, with
the reason recorded here). Only 0.19% of c-Si modules (39 of 20,946) could pass
a 3-sig-fig beta_oc gate, so the criterion was unsatisfiable on any
representative span.

Measured across the S2 span:

| coeff | deviation vs datasheet | note |
|---|---|---|
| alpha_sc | 7.8-14.5% | I_sc temp slope; == \|Adjust\| (see below) |
| beta_oc | 7.7-14.8% | **V_oc temp slope - relevant to the coefficient T-trend** |
| gamma_r | 0.3-0.8% | P_mp temp slope; drives landing-point energy |

**The beta_oc deviation is not noise - it equals \|Adjust\|.** Verified
database-wide (400 random c-Si, max residual 3.6e-4, correlation 0.99999981):

    beta_oc(model) / beta_oc(datasheet) - 1  ==  Adjust / 100

`Adjust` is the CEC parameter that reconciles the fit's alpha_sc to the
datasheet; the same fit produces a beta_oc that misses the datasheet by exactly
that ratio. So the ~10% is a documented, per-module-computable property of the
parameterisation, printed inline in the S2 output as a check. Consequences:

- gamma_r (power) is faithful, so landing-point *energy* vs temperature is
  trustworthy;
- beta_oc (voltage) carries a bounded bias: across all c-Si, the implied
  \|V_oc error\| at 60 C is median 0.465 V, p90 0.844 V, p99 1.421 V; as a
  candidate-placement error (x0.8) that is median 0.372 V, and **31.5% of c-Si
  modules exceed the 0.47 V Task 3 MAE target from this source alone**;
- therefore Task 1 reports the T-trend in normalised as well as absolute terms
  (already planned), the absolute slope is treated as indicative, and the trend
  is cross-checked against partner measured I-V at temperature in Phase 8 before
  any temperature-as-a-feature claim is made load-bearing. Held-out modules are
  stratified by \|Adjust\| so instrument bias is separable from the physical
  trend.

## S3 - reverse-bias (Bishop) + bypass diodes - PASS

Canonical module **Canadian_Solar_Inc__CS6U_310P** (72-cell, 310.1 W,
V_mp/V_oc = 0.8107 == the c-Si population mean to four decimals - a median
design, pinned in config.CANONICAL_DEMO_MODULE and selected on coefficient
proximity to the mean, not power). Module = 3 substrings in series, each a
cell-fraction-scaled single-diode model (a_ref, R_s, R_sh_ref scaled by 1/3;
I_L_ref, I_o_ref, alpha_sc unchanged), extended into reverse bias by pvlib
bishop88, shunted by an anti-parallel bypass diode (I0=1e-9 A, n=1). Composed in
the current domain: I_elem(V) = I_substring(V) + I_bypass(V), inverted to V(I),
summed across substrings.

Four checkpoints, all enforced by tests (test_s3_device.py):

1. **UNSHADED CONSISTENCY** - three uniform substrings reproduce the direct
   single-diode module: P_mp exact (0.0000%), V_oc/I_sc exact, V_mp/I_mp to
   0.017%. Proves the scaling + composition are correct. (Note: with three
   identical substrings this exercises the series sum but not the bypass path;
   the shaded-path validation is S4.)
2. **MULTI-PEAK** - substrings at 1000/600/300 W/m^2 give 3 peaks at
   11.06 / 25.06 / 39.81 V, separated by ~14 V (not grid artefacts). GMPP =
   131.61 W at 25.06 V (region 2, two substrings active), vs 105.66 W at the
   rightmost peak the fixed-0.8 model targets. Substring Isc ratios 9.08 / 5.451
   / 2.726 = 1.000 / 0.600 / 0.300, confirming linear photocurrent scaling. The
   peak detector now applies a prominence (1% of GMPP) and separation (1 V)
   criterion so near-threshold flattening cannot inflate the count at S6/S7.
3. **BYPASS ACTIVATION** - a 200 W/m^2 substring forced to the bright Isc clamps
   at -0.583 V, as expected for a ~0.6 V bypass diode. (Algebraic by
   construction with I0=1e-9, n=1; confirms wiring, not cell physics. I0 is a
   stated assumption exposed for the S6 sweep; the partner's actual bypass part
   number is on the Month-1 data request.)
4. **REVERSE-BIAS SWEEP - scope corrected.** Swept 6x4 = 24 avalanche
   combinations (breakdown_factor 0..5e-2, breakdown_voltage -10..-30 V); base
   GMPP 131.611 W, max deviation 0.020%. **This confirms the avalanche
   parameters CANNOT ACT in this regime; it does NOT measure their influence.**
   Diagnostic: the deepest substring voltage at the GMPP current is -0.556 V
   (bypass clamp), 54x shallower than the -30 V knee, so the avalanche term is
   sampled only in its far tail. The substring voltage grid floor is now
   adaptive (reaches ~95% of the knee when avalanche is on, vs a fixed -2.0 V
   that clipped the knee off-grid and made the sweep vacuous), and module_iv
   asserts the operating region stays finite. The regime where these parameters
   DO act - sub-substring shading, a single unshaded-group cell driven deep into
   reverse bias with no bypass path - is not represented by the current
   one-irradiance-per-substring module_iv and is deferred to S6.

**Per-region deviation of the fixed-0.8 model (canonical module, this scenario).**
Fixed candidates n*0.8*Voc/3 (Voc=44.90) vs the true peaks:

| region (active substrings) | fixed | true | error | implied coeff | bypass-corrected coeff |
|---|---|---|---|---|---|
| 1 (brightest only) | 11.97 | 11.06 | -0.91 | 0.739 | 0.817 |
| 2 (GMPP) | 23.95 | 25.06 | +1.11 | 0.837 | 0.857 |
| 3 (all three) | 35.92 | 39.81 | +3.89 | 0.887 | 0.887 |

Three findings for the research, all measured not asserted:
- **The GMPP error is +1.11 V, not the "11 V" a single-candidate 0.8*Voc reading
  suggests** - the fixed model selects the correct region here (consistent with
  Section 4's 153/153). Recording the module-level error as ~1 V, not ~11 V,
  keeps C2's honest baseline honest.
- **The region-1 error is negative** while regions 2-3 are positive. Section 4's
  "always positive" holds for the GMPP but not per region, and deep two-substring
  shading puts the GMPP in region 1 - so Task 1 must report error by region
  before C1 asserts a directional prior.
- **Part of the error is deterministic and free to remove.** Adding back the
  (3-n) bypass drops tightens the implied coefficient spread from 0.739-0.887 to
  0.817-0.887. C2's baseline is therefore "recalibrated alpha + closed-form
  bypass correction", which raises the bar Gate A(ii) must clear. The residual
  0.817/0.857/0.887 spread within one curve is the sharp argument for C3: no
  scalar alpha serves all three regions, which is why the ordered scan
  trajectory carries information a single irradiance-keyed lookup discards.
- Flank asymmetry at the GMPP peak: ~2.5 W/V below vs ~5.6 W/V above, so
  overshoot costs ~2x undershoot -> Phase 3 fitting loss and Phase 4 quantile
  interval should be asymmetric.

## Status

S1, S2, S3 PASS (15 tests, no leaked warnings under -W error::RuntimeWarning).
Simulator produces the multi-peak characteristic and the canonical module is
pinned and reproducible across machines.

**Not yet done:** S4 (published-shading reproduction = verification step 2), S5
(array generalisation), S6-S8. Gate A cannot be evaluated until S6-S8 complete,
and S4 must be green before any S6-S8 step runs (invariant).

**Open items carried to later phases** (recorded so they are not silently
dropped): (a) sub-substring cell-group composition inside module_iv, required
for Gate A(i)'s region-error-rate-under-sub-substring-geometry test - blocks S6;
(b) temperature-dependent bypass I0 and its addition to the S6 sweep; (c) the
plan-text amendment to Section 9.2 (temperature-coefficient gate) and Section 4
(c-Si vs full-catalogue figures, "outlier designs" wording).

## S4 - external validation of the simulator - PASS

S3 proved self-consistency (composed == direct model); that is not validation,
because a sign error reproduces perfectly. S4 checks the simulator against
sources it was NOT built to reproduce, in three legs of deliberately different
strength. No PySAM required for the gated leg.

**Leg 1 - structural, vs Basoglu (2019).** Fitted his Table II submodule, composed
three in series, ran his two published shading cases. Peak STRUCTURE reproduces:
Case-1 gives 3 peaks (GMPP in the middle region), Case-2 gives 2 peaks, both
correct; voltage ordering correct. The GMPP *magnitude* differs by ~9% from his
numbers - but this is expected and not our error: his module is a lab PV-emulator
part specified by only 4 datasheet points, and his Table IV "theoretical" column
is itself a 0.8-model prediction (its GMPP current 3.34 A implies a limiting
substring at ~570 W/m^2, which does not exist in his 100/500/1000 case - i.e. it
is not a device-simulation result). Reproducing it exactly would be a red flag.
Leg 1 is therefore QUALITATIVE (structure), PASS.

**Leg 2 - single-diode physics vs Sandia MEASUREMENT model - the gated quantitative
check.** The CEC and Sandia libraries do not share modules by identity, but 108
c-Si modules are electrical twins (V_oc/I_sc/V_mp/I_mp/N_s matched to tight
tolerance). Sandia coefficients are fit from outdoor MEASUREMENTS; CEC gives the
single-diode parameters our simulator uses. Running both across irradiance and
temperature (no fit, no PySAM):

| condition | Voc | Vmp | Pmp |
|---|---|---|---|
| 25 C, G=600/300 (near-STC) | 1.0% mean | 1.5% mean | 2.1% mean (max 7.3) |
| 55 C, G=600/300 (operating heat) | 1.3% mean | 2.0% mean | 2.5% mean (max 11.9) |

The single-substring physics agrees with a measurement-derived model to ~2% near
STC and ~2.5% at operating heat. Three consequences:
- this is the off-STC error bar every temperature-dependent result (S8, Phase 3)
  must carry, now measured against measurement rather than assumed;
- it CORROBORATES the S2 beta_oc/Adjust finding from an independent, measurement-
  based route - two methods, same magnitude of off-STC temperature uncertainty;
- it validates the SINGLE-SUBSTRING layer only, not the multi-peak composition.
Pass criterion: Pmp mean < 3% near STC and < 6% at 55 C. Both met. PASS.
Artefact: results/s4_sandia_crosscheck.csv;
figure results/figures/s4_sandia_crosscheck.png (error bars per quantity
25C vs 55C, plus the Pmp error distribution over all pairs).

**Leg 3 - quantitative multi-peak - DEFERRED to Phase 8, recorded as a finding.**
No public dataset of measured, partial-shaded, multi-peak I-V curves on
three-substring c-Si modules with full parameters exists. Confirmed by evaluating
three candidates: Basoglu (under-specified, emulator, 0.8-model "theoretical"
values); a Mendeley outdoor mismatch-fault set (real curves but single small
~20-90 W panels, mostly single-peak - wrong module class); and a targeted
literature search (returns only MATLAB/Simulink simulation output, or measured
curves locked inside papers as figures, never as reusable data). The multi-peak
COMPOSITION layer is therefore validated against the partner's measured I-V in
Phase 8. This confirms plan Section 9.11's premise by exhausting the alternatives
rather than asserting it.

**What S4 secures, and what it does not.** The simulator is a stack: single-diode
substring -> bypass/series composition -> multi-peak module -> extracted
coefficient. S4 validates the BOTTOM layer against measurement (leg 2) and the
STRUCTURE of the composition against published work (leg 1). It does NOT validate
the composition's magnitude - that is Phase 8's job, now the load-bearing
validation for C1's distribution and C3's learned model. The ~2-2.5% off-STC band
travels with every temperature-dependent claim downstream.

Status: 18 tests pass. S4 green -> the S6-S8 block is unblocked (invariant met).

## S5 - array generalisation (Stage 3, standalone) - PASS

Generalises the S3 module-level composition one level up: a module is substrings
in series (current-domain, sum voltages, bypass across each substring); a string
is modules in series composed the SAME way, with a bypass diode across each
module. The array-capable simulator is the same code applied recursively.

Three checkpoints on the canonical module (Canadian_Solar_Inc__CS6U_310P):

1. **N=1 reduction.** A string of one module reproduces module_iv exactly
   (GMPP 310.128 W at 36.394 V, identical to 1e-6). The generalisation does not
   change the base case.
2. **Series scaling.** Three identical unshaded modules give 3x voltage
   (36.39 -> 109.18 V) and 3x power (310.1 -> 930.4 W) at the same current
   (8.52 A) - correct series composition.
3. **String-level multi-peak.** Three modules at 1000/700/400 W/m^2 produce a
   3-peak string curve (module Isc 9.08/6.36/3.63 A, ratios 1.00/0.70/0.40),
   GMPP 461.9 W at 75.4 V. A shaded string is multi-peak by the same
   module-level-bypass mechanism S3 demonstrated for substrings.

Figure: results/figures/s5_string_multipeak.png (stepped I-V and multi-peak P-V
at string scale).

**Why this matters (insurance).** Gate A(ii) may find that a recalibrated
constant already solves the module-level problem, in which case the study
redirects to string level. S5 ensures that redirect costs 2-3 weeks, not two
months, because the string simulator already exists and is verified. Kept a
standalone checkpoint so it cannot be quietly dropped, but scheduled immediately
after Stage 2 while the S3 composition code is fresh.

Status: 21 tests pass. Phase 1 Stages 1-3 complete; Stage 4 (S6-S8 -> Gate A) is
the remaining work.
