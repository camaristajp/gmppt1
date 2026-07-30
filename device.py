"""
Device model (S3): multi-peak module I-V under partial shading.

A module = `n_substrings` cell groups in series, each with a bypass diode wired
anti-parallel. Each substring is a single-diode model (CEC parameters), extended
into reverse bias by the Bishop (1988) term via pvlib's bishop88, and shunted by
a bypass diode that conducts when the substring is driven negative.

Composition is done in the CURRENT domain:
  * for each substring, compute the terminal I-V of (substring || bypass diode)
    over a fine voltage grid: I_elem(V) = I_substring(V) + I_bypass(V);
  * I_elem(V) is strictly decreasing in V, so invert to V(I) on a common current
    grid shared by all substrings (series elements carry the same current);
  * module voltage V(I) = sum of substring voltages; power P = V * I.

The staircase / multiple peaks arise because as the string current rises past a
shaded substring's short-circuit current, its bypass diode turns on and clamps
that substring near -0.6 V, removing it from the voltage sum.

Reverse-bias (avalanche) parameters are an explicit, cited assumption (a named
limitation of the study). They default to OFF (breakdown_factor=0, i.e. ordinary
ohmic reverse conduction through R_sh) because the bypass diode clamps the
substring long before avalanche; they are exposed here so the sensitivity study
required by the plan can sweep them.
"""
from __future__ import annotations
from dataclasses import dataclass, field
import numpy as np
import pandas as pd
from pvlib import pvsystem, singlediode

from . import config

# Boltzmann * T / q at a reference temperature, for the bypass-diode model
_Q = 1.602176634e-19
_K = 1.380649e-23


# --------------------------------------------------------------------------
# Parameter containers
# --------------------------------------------------------------------------
@dataclass
class ModuleParams:
    """CEC single-diode reference parameters for a whole module."""
    name: str
    N_s: int
    alpha_sc: float
    a_ref: float
    I_L_ref: float
    I_o_ref: float
    R_sh_ref: float
    R_s: float
    Adjust: float

    @classmethod
    def from_cec(cls, name: str) -> "ModuleParams":
        full = pvsystem.retrieve_sam("CECMod").T
        r = full.loc[name]
        num = lambda k: float(pd.to_numeric(r[k]))
        return cls(name=name, N_s=int(num("N_s")), alpha_sc=num("alpha_sc"),
                   a_ref=num("a_ref"), I_L_ref=num("I_L_ref"),
                   I_o_ref=num("I_o_ref"), R_sh_ref=num("R_sh_ref"),
                   R_s=num("R_s"), Adjust=num("Adjust"))


@dataclass
class Breakdown:
    """Reverse-bias avalanche parameters (Bishop term). Default: OFF."""
    factor: float = 0.0          # breakdown_factor (0 => no avalanche)
    voltage: float = -15.0       # breakdown_voltage per substring (V)
    exp: float = 3.28            # breakdown_exp


@dataclass
class Bypass:
    """Anti-parallel bypass diode across each substring."""
    I0: float = 1e-9             # saturation current (A) -> ~0.6 V clamp at ~8 A
    n: float = 1.0               # ideality
    temp_c: float = 25.0         # diode temperature (deg C)

    def current(self, v: np.ndarray) -> np.ndarray:
        """Bypass current vs substring voltage. Conducts (positive) for v<0."""
        vt = self.n * _K * (self.temp_c + 273.15) / _Q
        i = self.I0 * (np.exp(np.clip(-v / vt, -50, 50)) - 1.0)
        return np.maximum(i, 0.0)


# --------------------------------------------------------------------------
# Substring scaling and I-V
# --------------------------------------------------------------------------
def scale_to_substring(mp: ModuleParams, cell_fraction: float) -> dict:
    """Scale module CEC params to a substring holding `cell_fraction` of cells.

    Series-count quantities scale with the number of series cells; current
    quantities do not.
    """
    return dict(
        alpha_sc=mp.alpha_sc,          # A/degC  (current-side, unchanged)
        a_ref=mp.a_ref * cell_fraction,        # n*Ns*k*T/q  (~ Ns)
        I_L_ref=mp.I_L_ref,            # A
        I_o_ref=mp.I_o_ref,            # A
        R_sh_ref=mp.R_sh_ref * cell_fraction,  # ohm (series cells)
        R_s=mp.R_s * cell_fraction,            # ohm (series cells)
        Adjust=mp.Adjust,
    )


def substring_operating_params(sub: dict, G: float, T: float):
    """(IL, I0, Rs, Rsh, nNsVth) for a substring at irradiance G, temp T."""
    return pvsystem.calcparams_cec(
        effective_irradiance=G, temp_cell=T,
        alpha_sc=sub["alpha_sc"], a_ref=sub["a_ref"], I_L_ref=sub["I_L_ref"],
        I_o_ref=sub["I_o_ref"], R_sh_ref=sub["R_sh_ref"], R_s=sub["R_s"],
        Adjust=sub["Adjust"], EgRef=config.EG_REF, dEgdT=config.DEG_DT)


def substring_element_iv(sub, G, T, bd: Breakdown, bp: Bypass, n_v=4000):
    """Terminal I-V of (substring || bypass) over a fine voltage grid.

    Returns (v, i_elem) with v ascending and i_elem strictly decreasing.
    """
    IL, I0, Rs, Rsh, nNsVth = substring_operating_params(sub, G, T)
    # forward open-circuit voltage sets the upper end of the grid
    fwd = pvsystem.singlediode(IL, I0, Rs, Rsh, nNsVth)
    v_oc = float(fwd["v_oc"])
    v = np.linspace(-2.0, v_oc * 1.02, n_v)
    i_sub = singlediode.bishop88_i_from_v(
        v, IL, I0, Rs, Rsh, nNsVth,
        breakdown_factor=bd.factor, breakdown_voltage=bd.voltage,
        breakdown_exp=bd.exp)
    i_elem = np.asarray(i_sub) + bp.current(v)
    return v, i_elem


# --------------------------------------------------------------------------
# Module I-V
# --------------------------------------------------------------------------
def module_iv(mp: ModuleParams, irradiances, T,
              n_substrings=config.N_SUBSTRINGS,
              bd: Breakdown | None = None, bp: Bypass | None = None,
              n_points=4000):
    """Compose the module I-V from per-substring irradiances.

    `irradiances` is a length-`n_substrings` sequence (W/m^2). Returns a dict
    with arrays I, V, P and the per-substring short-circuit currents.
    """
    bd = bd or Breakdown()
    bp = bp or Bypass(temp_c=T)
    irr = np.asarray(irradiances, dtype=float)
    assert len(irr) == n_substrings

    # split cells across substrings (handle non-divisible counts)
    base = mp.N_s // n_substrings
    counts = [base] * n_substrings
    for k in range(mp.N_s - base * n_substrings):
        counts[k] += 1
    fracs = [c / mp.N_s for c in counts]

    # per-substring element I-V and short-circuit current
    elems, isc = [], []
    for G, frac in zip(irr, fracs):
        sub = scale_to_substring(mp, frac)
        v, i_elem = substring_element_iv(sub, G, T, bd, bp)
        elems.append((v, i_elem))
        isc.append(float(np.interp(0.0, v, i_elem)))  # v ascending -> i at v=0
    isc = np.array(isc)

    # common current grid up to the brightest substring's Isc (inclusive, so the
    # V=0 point is representable for consistency checks)
    i_max = isc.max()
    I = np.linspace(0.0, i_max, n_points)

    # invert each substring's element I-V to V(I) and sum
    V = np.zeros_like(I)
    for (v, i_elem) in elems:
        # i_elem strictly decreasing in v -> ascending when reversed
        i_asc = i_elem[::-1]
        v_asc = v[::-1]
        V += np.interp(I, i_asc, v_asc)

    P = V * I
    return dict(I=I, V=V, P=P, isc_substrings=isc, cell_counts=counts)


# --------------------------------------------------------------------------
# Curve analysis
# --------------------------------------------------------------------------
def analyse(curve: dict):
    """Global peak and local maxima of a module P-V/P-I curve."""
    I, V, P = curve["I"], curve["V"], curve["P"]
    # restrict to the physical operating region (V >= 0)
    mask = V >= 0
    Im, Vm, Pm = I[mask], V[mask], P[mask]
    g = int(np.argmax(Pm))
    # local maxima in P vs V (V decreasing as I increases, so scan P)
    peaks = []
    for j in range(1, len(Pm) - 1):
        if Pm[j] >= Pm[j - 1] and Pm[j] > Pm[j + 1]:
            peaks.append((float(Vm[j]), float(Im[j]), float(Pm[j])))
    return dict(
        gmpp=dict(V=float(Vm[g]), I=float(Im[g]), P=float(Pm[g])),
        n_peaks=len(peaks),
        peaks=sorted(peaks, key=lambda t: -t[2]),
    )