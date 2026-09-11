"""
Interactive PV Partial-Shading Dashboard
========================================

A single-file Streamlit application that simulates a crystalline-silicon PV
module under partial shading and lets the user explore the resulting I-V / P-V
characteristics, the global and local maximum power points (GMPP / LMPPs), and
the spatial shading distribution in real time.

Modelling approach
------------------
The electrical model mirrors the composition used in the project's validated
simulator (single-diode substrings, one bypass diode per substring, composed in
the current domain), but is a *simplified, self-contained* reimplementation so
the app runs natively with no external simulator dependency:

  * Each bypass-diode substring is a single-diode element (five-parameter model),
    solved explicitly by sweeping the internal diode voltage (no implicit solve,
    no Lambert-W, no pvlib needed).
  * Series cells within a substring are current-limited by their most-shaded
    cell (the dominant effect that triggers bypass conduction).
  * A bypass diode clamps each shaded substring to ~-0.7 V; substrings are then
    summed in the current domain to give the module curve.
  * Reverse-bias avalanche (the Bishop term in the full simulator) is NOT
    modelled here; this app is for interactive illustration, not for the
    quantitative figures of record.

Run with:
    pip install streamlit plotly numpy pandas   # (kaleido optional, for PNG export)
    streamlit run app.py
"""

from __future__ import annotations

import io
import json
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

# --------------------------------------------------------------------------- #
# Physical constants and reference (STC) cell parameters
# --------------------------------------------------------------------------- #
Q = 1.602176634e-19          # elementary charge [C]
K = 1.380649e-23             # Boltzmann constant [J/K]
T_REF = 298.15               # reference temperature [K] (25 C)
G_REF = 1000.0               # reference irradiance [W/m^2]

# Reference single-diode parameters for one c-Si cell (typical mono-Si).
CELL_REF = dict(
    I_L_ref=9.5,             # light-generated current [A]
    I_0_ref=1.0e-9,          # diode saturation current [A]
    n=1.10,                  # diode ideality factor
    Rs_cell=0.005,           # series resistance per cell [ohm]
    Rsh_cell=12.0,           # shunt resistance per cell [ohm]
    alpha_isc=0.0045,        # Isc temperature coefficient [A/K]
    Eg=1.121,                # band-gap energy [eV]
)
CELL_AREA_M2 = 0.156 * 0.156     # area of one 156 mm cell [m^2]
V_BYPASS = 0.7                   # bypass-diode forward clamp voltage [V]

# Publication-oriented, colour-blind-safe palette
COL_IV = "#0B5FA5"       # I-V curve (deep blue)
COL_PV = "#C24914"       # P-V curve (burnt orange)
COL_GMPP = "#E8B300"     # global MPP marker (gold)
COL_LMPP = "#6B6B6B"     # local MPP markers (grey)
COL_OP = "#128A5B"       # operating-point marker (green)
GRID = "#D9D9D9"
PLOT_FONT = "Times New Roman, Georgia, serif"

# per-geometry colours used by the Phase-1 gallery
GEOM_COLORS = {"uniform": "#1BAF7A", "whole_substring": "#0B5FA5",
               "sub_substring": "#C24914"}
GEOM_LABEL = {"uniform": "uniform", "whole_substring": "whole-substring",
              "sub_substring": "sub-substring"}


# --------------------------------------------------------------------------- #
# Core physics  (pure NumPy — no Streamlit, independently testable)
# --------------------------------------------------------------------------- #
def element_params(G: float, T_c: float, n_series: int, ref=CELL_REF):
    """Five single-diode parameters for a series element of ``n_series`` cells
    at irradiance ``G`` [W/m^2] and cell temperature ``T_c`` [deg C]."""
    T = T_c + 273.15
    Vt = K * T / Q
    I_L = (G / G_REF) * (ref["I_L_ref"] + ref["alpha_isc"] * (T - T_REF))
    I_L = max(I_L, 0.0)
    I_0 = ref["I_0_ref"] * (T / T_REF) ** 3 * np.exp(
        ref["Eg"] * Q / (ref["n"] * K) * (1.0 / T_REF - 1.0 / T))
    a = ref["n"] * Vt * n_series            # element thermal voltage
    Rs = ref["Rs_cell"] * n_series
    Rsh = ref["Rsh_cell"] * n_series
    return I_L, I_0, a, Rs, Rsh


def element_iv(G: float, T_c: float, n_series: int, npts: int = 500, ref=CELL_REF):
    """Terminal (V, I) curve of one substring element, from short circuit to
    open circuit. Solved explicitly by sweeping the internal diode voltage."""
    I_L, I_0, a, Rs, Rsh = element_params(G, T_c, n_series, ref)
    if I_L <= 1e-6:                          # fully dark: no generation
        V = np.linspace(0.0, 0.01, npts)
        return V, np.zeros_like(V), 0.0, 0.0
    Voc = a * np.log(I_L / I_0 + 1.0)        # open-circuit diode voltage
    Vd = np.linspace(0.0, Voc, npts)
    I = I_L - I_0 * np.expm1(np.clip(Vd / a, -60, 60)) - Vd / Rsh
    V = Vd - I * Rs                          # V ascending, I descending
    Isc = float(np.interp(0.0, V, I))        # current at V = 0
    return V, I, Isc, float(V.max())


def module_iv(sub_irradiance, T_c: float, cells_per_sub: int,
              n_grid: int = 800, ref=CELL_REF):
    """Compose substrings in the current domain into the module I-V / P-V curve.

    ``sub_irradiance`` is one irradiance value per substring [W/m^2].
    Returns a dict with the full curve and key operating points.
    """
    elems = [element_iv(G, T_c, cells_per_sub, ref=ref) for G in sub_irradiance]
    isc_list = [e[2] for e in elems]
    i_max = max(isc_list) if isc_list else 0.0
    if i_max <= 1e-6:
        z = np.zeros(n_grid)
        return dict(V=z, I=z, P=z, Voc=0.0, Isc=0.0,
                    gmpp=(0.0, 0.0, 0.0), lmpps=[], sub_irr=list(sub_irradiance),
                    bypassed=[True] * len(sub_irradiance))

    Igrid = np.linspace(0.0, i_max, n_grid)
    Vmod = np.zeros_like(Igrid)
    for V, I, Isc, _ in elems:
        I_asc = I[::-1]                       # current ascending 0 -> I_L
        V_asc = V[::-1]                       # matching substring voltage
        v_sub = np.interp(Igrid, I_asc, V_asc)
        v_sub = np.where(Igrid <= Isc, v_sub, -V_BYPASS)
        Vmod += v_sub

    Pmod = Vmod * Igrid
    # operating branch (non-negative module voltage)
    mask = Vmod >= 0.0
    Vop, Iop, Pop = Vmod[mask], Igrid[mask], Pmod[mask]
    order = np.argsort(Vop)
    Vop, Iop, Pop = Vop[order], Iop[order], Pop[order]

    Voc = float(Vop.max()) if Vop.size else 0.0
    Isc = float(np.interp(0.0, Vop, Iop)) if Vop.size else 0.0

    peaks = _find_peaks(Vop, Pop)
    if not peaks:
        k = int(np.argmax(Pop)) if Pop.size else 0
        peaks = [(float(Vop[k]), float(Iop[k]), float(Pop[k]))]
    peaks.sort(key=lambda t: t[2], reverse=True)
    gmpp = peaks[0]
    lmpps = peaks[1:]

    # which substrings are bypassed at the GMPP current
    bypassed = [gmpp[1] > isc + 1e-9 for isc in isc_list]

    return dict(V=Vop, I=Iop, P=Pop, Voc=Voc, Isc=Isc,
                gmpp=gmpp, lmpps=lmpps, sub_irr=list(sub_irradiance),
                bypassed=bypassed)


def _find_peaks(V, P, prom_frac: float = 0.01, min_sep_v: float = 2.0):
    """Local maxima of P(V) with a prominence floor and a minimum V separation,
    so grid jitter and near-ties do not register as spurious peaks."""
    if P.size < 3:
        return []
    pmax = float(P.max())
    cand = []
    for i in range(1, len(P) - 1):
        if P[i] >= P[i - 1] and P[i] > P[i + 1]:
            left = P[:i].min()
            right = P[i:].min()
            prom = P[i] - max(left, right)
            if prom >= prom_frac * pmax:
                cand.append((float(V[i]), float(P[i]), i))
    # enforce minimum separation, keep the stronger peak
    cand.sort(key=lambda t: t[1], reverse=True)
    kept = []
    for v, p, i in cand:
        if all(abs(v - kv) > min_sep_v for kv, _, _ in kept):
            kept.append((v, p, i))
    return [(V[i], _current_at(V, P, i), P[i]) for _v, _p, i in kept]


def _current_at(V, P, i):
    """Recover current at index i from P = V*I (guards V -> 0)."""
    return float(P[i] / V[i]) if V[i] > 1e-9 else 0.0


def metrics(res: dict, incident_power_w: float) -> dict:
    """Summary electrical metrics from a composed curve."""
    Vmpp, Impp, Pmax = res["gmpp"]
    Voc, Isc = res["Voc"], res["Isc"]
    ff = Pmax / (Voc * Isc) if (Voc > 0 and Isc > 0) else 0.0
    eff = 100.0 * Pmax / incident_power_w if incident_power_w > 0 else 0.0
    return dict(Pmax=Pmax, Vmpp=Vmpp, Impp=Impp, Voc=Voc, Isc=Isc,
                FF=ff, efficiency=eff)


# --------------------------------------------------------------------------- #
# Shading scenarios  ->  per-cell irradiance grid
# --------------------------------------------------------------------------- #
def make_irradiance_grid(preset: str, rows: int, cols: int,
                         base_G: float, shade_frac: float,
                         manual_sub=None, n_sub: int = 3) -> np.ndarray:
    """Return an (rows x cols) irradiance map [W/m^2] for the chosen preset.

    ``shade_frac`` is the fraction of base irradiance the *shaded* cells keep
    (0.2 => shaded cells at 20 % of base). ``manual_sub`` (list of per-substring
    irradiance) overrides the preset when preset == 'Custom (per-substring)'.
    """
    G = np.full((rows, cols), base_G, dtype=float)
    shaded = base_G * shade_frac
    bands = np.array_split(np.arange(rows), n_sub)   # substring = group of rows

    if preset == "Uniform irradiance":
        pass

    elif preset == "Diagonal shading":
        # graded diagonal band: lighter at top-left, darker toward bottom-right,
        # so the three row-band substrings receive distinct effective irradiance
        for r in range(rows):
            for c in range(cols):
                if abs(r / max(rows - 1, 1) - c / max(cols - 1, 1)) < 0.28:
                    depth = shade_frac + (1 - shade_frac) * (
                        1 - (r + c) / ((rows - 1) + (cols - 1)))
                    G[r, c] = base_G * depth

    elif preset == "Row-by-row shading":
        # progressively darker towards the bottom rows
        for r in range(rows):
            frac = 1.0 - (1.0 - shade_frac) * (r / max(rows - 1, 1))
            G[r, :] = base_G * frac

    elif preset == "Heavy partial shading":
        # one whole substring band heavily shaded + a shaded corner block
        G[bands[-1], :] = shaded
        G[: max(1, rows // 3), : max(1, cols // 3)] = shaded * 0.6

    elif preset == "Custom (per-substring)" and manual_sub is not None:
        for b, gval in zip(bands, manual_sub):
            G[b, :] = gval

    return np.clip(G, 0.0, 1500.0)


def substring_irradiance(Ggrid: np.ndarray, n_sub: int = 3):
    """Effective per-substring irradiance = the most-shaded (minimum) cell in
    the substring's rows (series current limiting)."""
    bands = np.array_split(np.arange(Ggrid.shape[0]), n_sub)
    return [float(Ggrid[b, :].min()) for b in bands]


def thermal_stress_grid(Ggrid, base_G, bypassed, n_sub=3):
    """Illustrative per-cell thermal-stress proxy: shaded cells inside an
    active (non-bypassed) substring are forced to carry current and dissipate."""
    bands = np.array_split(np.arange(Ggrid.shape[0]), n_sub)
    stress = np.zeros_like(Ggrid)
    for b, byp in zip(bands, bypassed):
        shade = 1.0 - Ggrid[b, :] / max(base_G, 1e-9)      # 0 = full sun
        stress[b, :] = shade * (0.35 if byp else 1.0)      # bypassed => relieved
    return np.clip(stress, 0.0, 1.0)


# --------------------------------------------------------------------------- #
# Plotly figures (publication styling)
# --------------------------------------------------------------------------- #
def _base_layout(fig, title, xlab, ylab):
    fig.update_layout(
        title=dict(text=title, x=0.5, xanchor="center",
                   font=dict(size=18, family=PLOT_FONT, color="#111")),
        font=dict(family=PLOT_FONT, size=14, color="#111"),
        plot_bgcolor="white", paper_bgcolor="white",
        xaxis=dict(title=xlab, showgrid=True, gridcolor=GRID, zeroline=False,
                   linecolor="#111", mirror=True, ticks="outside"),
        yaxis=dict(title=ylab, showgrid=True, gridcolor=GRID, zeroline=False,
                   linecolor="#111", mirror=True, ticks="outside"),
        legend=dict(bgcolor="rgba(255,255,255,0.75)", bordercolor="#BBB",
                    borderwidth=1, x=0.99, y=0.99, xanchor="right", yanchor="top"),
        margin=dict(l=70, r=30, t=55, b=60),
    )
    return fig


def iv_figure(res, v_op=None):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=res["V"], y=res["I"], mode="lines",
                             line=dict(color=COL_IV, width=3.2), name="I–V"))
    Vm, Im, _ = res["gmpp"]
    fig.add_trace(go.Scatter(x=[Vm], y=[Im], mode="markers", name="GMPP",
                             marker=dict(color=COL_GMPP, size=13, symbol="star",
                                         line=dict(color="#111", width=1))))
    # annotate bypass steps (where dI/dV is steep)
    _annotate_steps(fig, res, axis="I")
    if v_op is not None:
        i_op = float(np.interp(v_op, res["V"], res["I"]))
        fig.add_trace(go.Scatter(x=[v_op], y=[i_op], mode="markers",
                                 name="operating pt",
                                 marker=dict(color=COL_OP, size=12,
                                             symbol="diamond",
                                             line=dict(color="#111", width=1))))
    return _base_layout(fig, "I–V Characteristic", "Voltage  V  [V]",
                        "Current  I  [A]")


def pv_figure(res, v_op=None):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=res["V"], y=res["P"], mode="lines",
                             line=dict(color=COL_PV, width=3.2), name="P–V"))
    Vm, _, Pm = res["gmpp"]
    fig.add_trace(go.Scatter(x=[Vm], y=[Pm], mode="markers", name="GMPP",
                             marker=dict(color=COL_GMPP, size=15, symbol="star",
                                         line=dict(color="#111", width=1))))
    fig.add_annotation(x=Vm, y=Pm, text=f"GMPP<br>{Pm:.1f} W", showarrow=True,
                       arrowhead=2, ax=0, ay=-40, font=dict(size=12))
    if res["lmpps"]:
        fig.add_trace(go.Scatter(
            x=[v for v, _, _ in res["lmpps"]],
            y=[p for _, _, p in res["lmpps"]], mode="markers", name="LMPP",
            marker=dict(color=COL_LMPP, size=10, symbol="circle",
                        line=dict(color="#111", width=1))))
    if v_op is not None:
        p_op = float(np.interp(v_op, res["V"], res["P"]))
        fig.add_trace(go.Scatter(x=[v_op], y=[p_op], mode="markers",
                                 name="operating pt",
                                 marker=dict(color=COL_OP, size=12,
                                             symbol="diamond",
                                             line=dict(color="#111", width=1))))
    return _base_layout(fig, "P–V Characteristic", "Voltage  V  [V]",
                        "Power  P  [W]")


def _annotate_steps(fig, res, axis="I"):
    """Mark voltages where a bypass diode switches (large local |dI/dV|)."""
    V, I = res["V"], res["I"]
    if V.size < 5:
        return
    dIdV = np.gradient(I, V)
    thr = np.percentile(np.abs(dIdV), 98)
    marked = []
    for i in range(1, len(V) - 1):
        if abs(dIdV[i]) >= thr and all(abs(V[i] - m) > 3 for m in marked):
            marked.append(V[i])
            fig.add_vline(x=V[i], line=dict(color="#AAAAAA", width=1, dash="dot"))


def module_heatmaps(Ggrid, stress):
    fig = go.Figure(data=go.Heatmap(
        z=Ggrid, colorscale="Cividis", zmin=0, zmax=1000,
        colorbar=dict(title="G [W/m²]"), hovertemplate="G=%{z:.0f} W/m²<extra></extra>"))
    fig.update_layout(
        title=dict(text="Irradiance map (per cell)", x=0.5, font=dict(
            size=16, family=PLOT_FONT)),
        font=dict(family=PLOT_FONT), plot_bgcolor="white", paper_bgcolor="white",
        yaxis=dict(autorange="reversed", title="cell row", scaleanchor="x"),
        xaxis=dict(title="cell column"), margin=dict(l=50, r=20, t=50, b=40))

    fig2 = go.Figure(data=go.Heatmap(
        z=stress, colorscale="Reds", zmin=0, zmax=1,
        colorbar=dict(title="stress"),
        hovertemplate="stress=%{z:.2f}<extra></extra>"))
    fig2.update_layout(
        title=dict(text="Relative thermal stress (illustrative)", x=0.5,
                   font=dict(size=16, family=PLOT_FONT)),
        font=dict(family=PLOT_FONT), plot_bgcolor="white", paper_bgcolor="white",
        yaxis=dict(autorange="reversed", title="cell row", scaleanchor="x"),
        xaxis=dict(title="cell column"), margin=dict(l=50, r=20, t=50, b=40))
    return fig, fig2


# --------------------------------------------------------------------------- #
# Caching wrapper
# --------------------------------------------------------------------------- #
@st.cache_data(show_spinner=False)
def simulate(sub_irr_tuple, T_c, cells_per_sub):
    return module_iv(list(sub_irr_tuple), T_c, cells_per_sub)


# --------------------------------------------------------------------------- #
# Export helpers
# --------------------------------------------------------------------------- #
def png_bytes(fig, scale=4):
    """High-resolution PNG via kaleido; returns None if kaleido is absent."""
    try:
        return fig.to_image(format="png", scale=scale)
    except Exception:
        return None


def plotly_config(name):
    return {"displaylogo": False,
            "toImageButtonOptions": {"format": "png", "filename": name,
                                     "scale": 4}}


# --------------------------------------------------------------------------- #
# Bundled assets (real Phase-1 outputs) and static validation record
# --------------------------------------------------------------------------- #
ASSETS = Path(__file__).parent / "assets"


@st.cache_data(show_spinner=False)
def load_curve_bank():
    p = ASSETS / "phase1_curves.json"
    if not p.exists():
        return None
    return json.loads(p.read_text())


@st.cache_data(show_spinner=False)
def load_slim_dataset():
    p = ASSETS / "phase1_dataset.csv"
    if not p.exists():
        return None
    return pd.read_csv(p)


# Validation gates, as re-run on the pinned toolchain (pvlib 0.15.2, seed
# 20260901). These are results of record from the verification harness (S1–S8).
VALIDATION_GATES = [
    {"Gate": "S1 · premise", "Checks": "CEC V_mp/V_oc spread (no model run)",
     "Independent source": "CEC module database, directly",
     "Result": "20,946 c-Si modules · mean 0.811 · 41% within ±0.01 of 0.80"},
    {"Gate": "S2 · STC point", "Checks": "Single-diode reproduces datasheet "
     "V_oc, V_mp, I_mp", "Independent source": "Manufacturer datasheets (3 s.f.)",
     "Result": "PASS — worst error 0.000%"},
    {"Gate": "S3 · composition", "Checks": "Composed substrings = direct module; "
     "multi-peak appears", "Independent source": "Direct single-diode model "
     "(self-consistency)", "Result": "PASS — 3 peaks present"},
    {"Gate": "S4 · off-STC physics", "Checks": "Single-diode vs measurement, "
     "25–55 °C", "Independent source": "Sandia measurement model, 108 c-Si twins",
     "Result": "PASS — P_mp error 2.1% @STC, 2.5% @55 °C"},
    {"Gate": "S4 · structure", "Checks": "Multi-peak structure of published "
     "shading cases", "Independent source": "Başoğlu (2019), IEEE TIA",
     "Result": "PASS (qualitative / structural)"},
    {"Gate": "S4 · magnitude", "Checks": "Quantitative multi-peak magnitude",
     "Independent source": "Measured shaded I–V (partner)",
     "Result": "Deferred → Phase 8 (no public dataset exists)"},
    {"Gate": "S5 · array", "Checks": "N=1 string = module; series scaling",
     "Independent source": "Module model (self-consistency)", "Result": "PASS"},
    {"Gate": "S6/S7 · integrity", "Checks": "Reproducibility, convergence, "
     "label resolution-independence", "Independent source": "Seed + sweep-grid "
     "invariance", "Result": "PASS"},
    {"Gate": "Gate A · dataset", "Checks": "Fixed-0.80 region error, sub-substring",
     "Independent source": "2,000-scenario characterisation",
     "Result": "6.1% raw region error (≈ plan's 6.7%)"},
]

REFERENCES_MD = """
- **Bu, C. et al. (2025).** *Cross-validation-assisted hybrid dataset
  construction for low-cost and accurate prediction of PV GMPP under partial
  shading.* Energy Reports **14**, 2732–2754. — same domain (ANN GMPP
  *prediction*); its hybrid-dataset method is borrowed, and it is distinguished
  from this *tracking* work.
- **Başoğlu, M. E. (2019).** Multi-peak partial-shading case studies, IEEE
  Trans. Ind. Appl. **55(2)** — structural validation reference (Leg 1).
- **King, D. L. et al.** *Sandia Array Performance Model* — measurement-derived
  model used for the off-STC quantitative validation (Leg 2).
- **Holmgren, W. F. et al.** *pvlib-python* — single-diode / CEC model and the
  CEC module database (parameter source), pinned at 0.15.2.
- **NN-seed-then-P&O prior art:** Messalti et al. (2017); Li et al. (2013);
  Khanaki et al. (2016) — establish that "ML predicts the GMPP region" is not by
  itself novel; the contribution is cost/worst-case/dynamic re-seed.
"""


# --------------------------------------------------------------------------- #
# Streamlit UI
# --------------------------------------------------------------------------- #
def main():
    st.set_page_config(page_title="PV Partial-Shading Dashboard",
                       layout="wide", initial_sidebar_state="expanded")

    st.markdown("""
        <style>
        .block-container {padding-top: 1.5rem;}
        /* Metric cards: light card with explicitly dark text, so they stay
           readable under BOTH light and dark Streamlit themes. */
        div[data-testid="stMetric"] {background:#F5F7FA; border:1px solid #E3E7EE;
            padding:12px 14px; border-radius:10px;}
        div[data-testid="stMetric"] [data-testid="stMetricValue"] {
            color:#0F1B2D !important;}
        div[data-testid="stMetric"] [data-testid="stMetricLabel"],
        div[data-testid="stMetric"] [data-testid="stMetricLabel"] p {
            color:#3A4552 !important;}
        div[data-testid="stMetric"] [data-testid="stMetricDelta"] {
            color:#B23A2E !important;}
        </style>""", unsafe_allow_html=True)

    page = st.sidebar.radio(
        "Page", ["Dashboard", "Multi-peak showcase",
                 "Phase-1 gallery", "Validation & literature"], index=0)
    st.sidebar.divider()
    if page == "Dashboard":
        render_dashboard()
    elif page == "Multi-peak showcase":
        render_showcase()
    elif page == "Phase-1 gallery":
        render_gallery()
    else:
        render_validation()


def render_dashboard():
    st.title("☀️ Interactive PV Partial-Shading Dashboard")
    st.caption("Single-diode substrings · bypass-diode composition · "
               "Global & Local MPP tracking — for interactive illustration "
               "alongside the validated simulator.")

    # ----------------------------- Sidebar -------------------------------- #
    sb = st.sidebar
    sb.header("⚙️ Controls")

    with sb.expander("Module geometry", expanded=False):
        rows = st.number_input("Cell rows", 3, 12, 6, step=1)
        cols = st.number_input("Cell columns", 3, 16, 10, step=1)
        n_sub = 3
        st.caption(f"{rows}×{cols} = {rows*cols} cells, {n_sub} bypass-diode "
                   f"substrings (row bands).")
    cells_per_sub = (rows * cols) // n_sub

    sb.subheader("🌤️ Environment")
    base_G = sb.slider("Base irradiance  G  [W/m²]", 200, 1000, 1000, step=50)
    T_c = sb.slider("Cell temperature  T  [°C]", -10, 70, 25, step=1)

    sb.subheader("🌓 Shading")
    preset = sb.selectbox("Preset scenario", [
        "Uniform irradiance", "Diagonal shading", "Row-by-row shading",
        "Heavy partial shading", "Custom (per-substring)"])
    shade_frac = sb.slider("Shaded-cell irradiance (fraction of base)",
                           0.0, 1.0, 0.25, step=0.05,
                           help="0.25 → shaded cells receive 25 % of base G.")
    manual_sub = None
    if preset == "Custom (per-substring)":
        manual_sub = [sb.slider(f"Substring {i+1}  G  [W/m²]", 0, 1000,
                                int(base_G if i == 0 else base_G*0.6),
                                step=25, key=f"sub{i}") for i in range(n_sub)]

    # ----------------------------- Simulation ----------------------------- #
    Ggrid = make_irradiance_grid(preset, rows, cols, base_G, shade_frac,
                                 manual_sub, n_sub)
    sub_irr = substring_irradiance(Ggrid, n_sub)
    res = simulate(tuple(round(g, 2) for g in sub_irr), T_c, cells_per_sub)

    sb.subheader("🎯 Operating point")
    v_op = sb.slider("Operating voltage  V  [V]", 0.0,
                     float(max(res["Voc"], 1.0)),
                     float(round(res["gmpp"][0], 1)), step=0.5)
    i_op = float(np.interp(v_op, res["V"], res["I"])) if res["V"].size else 0.0
    p_op = float(np.interp(v_op, res["V"], res["P"])) if res["V"].size else 0.0

    incident = float(Ggrid.sum()) * CELL_AREA_M2      # incident optical power [W]
    m = metrics(res, incident)

    # --------------------------- Metric cards ----------------------------- #
    st.subheader("Summary metrics")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("P_max (GMPP)", f"{m['Pmax']:.1f} W")
    c2.metric("V_mpp", f"{m['Vmpp']:.2f} V")
    c3.metric("I_mpp", f"{m['Impp']:.2f} A")
    c4.metric("Fill Factor", f"{m['FF']*100:.1f} %")
    c5.metric("Efficiency", f"{m['efficiency']:.2f} %")

    c6, c7, c8, c9 = st.columns(4)
    c6.metric("V_oc", f"{m['Voc']:.2f} V")
    c7.metric("I_sc", f"{m['Isc']:.2f} A")
    c8.metric("# P–V peaks", f"{1 + len(res['lmpps'])}")
    c9.metric("P at operating V", f"{p_op:.1f} W",
              delta=f"{p_op - m['Pmax']:.1f} W vs GMPP")

    st.divider()

    # ----------------------------- Heatmaps ------------------------------- #
    st.subheader("Spatial shading distribution")
    stress = thermal_stress_grid(Ggrid, base_G, res["bypassed"], n_sub)
    h1, h2 = module_heatmaps(Ggrid, stress)
    hc1, hc2 = st.columns(2)
    hc1.plotly_chart(h1, width='stretch',
                     config=plotly_config("irradiance_map"))
    hc2.plotly_chart(h2, width='stretch',
                     config=plotly_config("thermal_stress"))
    st.caption("Substring effective irradiance (min-cell, current-limiting): "
               + " · ".join(f"S{i+1}={g:.0f} W/m²"
                            for i, g in enumerate(sub_irr))
               + "  |  bypassed at GMPP: "
               + ", ".join(f"S{i+1}" for i, b in enumerate(res["bypassed"]) if b)
               + (" — none" if not any(res["bypassed"]) else ""))

    st.divider()

    # ------------------------------ Curves -------------------------------- #
    st.subheader("Electrical characteristics")
    fig_iv = iv_figure(res, v_op)
    fig_pv = pv_figure(res, v_op)
    g1, g2 = st.columns(2)
    g1.plotly_chart(fig_iv, width='stretch',
                    config=plotly_config("IV_curve"))
    g2.plotly_chart(fig_pv, width='stretch',
                    config=plotly_config("PV_curve"))
    st.caption("Dotted vertical lines mark bypass-diode switching steps. "
               "Use the camera icon on each chart for a high-resolution PNG.")

    # ------------------------------ Exports ------------------------------- #
    st.divider()
    st.subheader("Export for publication")
    e1, e2, e3, e4 = st.columns(4)

    df = pd.DataFrame({"V_[V]": res["V"], "I_[A]": res["I"], "P_[W]": res["P"]})
    e1.download_button("⬇️ Curve data (CSV)", df.to_csv(index=False),
                       "pv_curve.csv", "text/csv", width='stretch')

    for col, fig, label, fname in [
            (e2, fig_iv, "I–V", "IV_curve"),
            (e3, fig_pv, "P–V", "PV_curve")]:
        data = png_bytes(fig)
        if data:
            col.download_button(f"⬇️ {label} PNG (300+ dpi)", data,
                                f"{fname}.png", "image/png",
                                width='stretch')
        else:
            col.download_button(f"⬇️ {label} (HTML)",
                                fig.to_html(include_plotlyjs="cdn"),
                                f"{fname}.html", "text/html",
                                width='stretch')

    summary = pd.DataFrame([{
        "preset": preset, "base_G_Wm2": base_G, "T_C": T_c,
        "shade_frac": shade_frac,
        **{f"sub{i+1}_G": g for i, g in enumerate(sub_irr)},
        "Pmax_W": m["Pmax"], "Vmpp_V": m["Vmpp"], "Impp_A": m["Impp"],
        "Voc_V": m["Voc"], "Isc_A": m["Isc"], "FF": m["FF"],
        "efficiency_pct": m["efficiency"], "n_peaks": 1 + len(res["lmpps"])}])
    e4.download_button("⬇️ Metrics (CSV)", summary.to_csv(index=False),
                       "pv_metrics.csv", "text/csv", width='stretch')

    if png_bytes(fig_iv) is None:
        st.info("Install `kaleido` (`pip install kaleido`) to enable direct "
                "PNG download buttons; HTML export and the chart camera icon "
                "work without it.")

    # ------------------------------ About --------------------------------- #
    with st.expander("ℹ️ About the model (read before citing)"):
        st.markdown(
            "- **Consistency.** The composition here (single-diode substrings "
            "→ per-substring bypass diode → current-domain sum → peak search) "
            "matches the project's validated simulator.\n"
            "- **Simplifications.** This standalone app omits the Bishop "
            "reverse-bias avalanche term and treats sub-substring shading by "
            "current-limiting each substring to its most-shaded cell. It is "
            "intended for **interactive illustration**.\n"
            "- **Numbers of record** for the paper should come from the "
            "validated `device.py` / pvlib pipeline, which is externally "
            "validated (datasheet STC, Sandia measurement model) and carries "
            "the quantitative multi-peak validation to the measured-data phase.")


def render_showcase():
    """A dedicated wide-format page: a long series of graded-irradiance
    substrings composed into a single continuous P-V curve with many peaks."""
    st.title("🔬 Multi-peak Showcase")
    st.caption("A long series of substrings at graded irradiance, composed in "
               "the current domain into one wide, continuous P–V landscape — "
               "to illustrate why global tracking is hard when many local peaks "
               "compete. This is a simulator view; numbers are model output.")

    sb = st.sidebar
    sb.header("🔬 Showcase controls")
    n_elem = sb.slider("Series substrings (up to this many peaks)", 4, 16, 12)
    cells_per_elem = sb.slider("Cells per substring", 8, 24, 20, step=2)
    grange = sb.slider("Irradiance range  G  [W/m²]", 100, 1000, (200, 1000),
                       step=50)
    T_c = sb.slider("Cell temperature  T  [°C]", -10, 70, 25, step=1)
    pattern = sb.selectbox("Irradiance pattern",
                           ["Graded (linear)", "Random", "Alternating hi/lo"])
    seed = int(sb.number_input("Random seed", 0, 9999, 42, step=1))

    gmax, gmin = float(max(grange)), float(min(grange))
    if pattern == "Graded (linear)":
        irrs = np.linspace(gmax, gmin, n_elem)
    elif pattern == "Random":
        irrs = np.random.default_rng(seed).uniform(gmin, gmax, n_elem)
    else:
        irrs = np.array([gmax if i % 2 == 0 else gmin for i in range(n_elem)])

    # high resolution -> smooth, continuous curve
    res = module_iv([float(g) for g in irrs], T_c, cells_per_elem, n_grid=1800)
    # relaxed peak detection so a busy landscape reveals its many local peaks
    peaks = _find_peaks(res["V"], res["P"], prom_frac=0.004, min_sep_v=1.0)
    if not peaks:
        k = int(np.argmax(res["P"])) if res["P"].size else 0
        peaks = [(float(res["V"][k]), _current_at(res["V"], res["P"], k),
                  float(res["P"][k]))]
    peaks.sort(key=lambda t: t[2], reverse=True)
    res = dict(res, gmpp=peaks[0], lmpps=peaks[1:])

    Vm, Im, Pm = res["gmpp"]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("P_max (GMPP)", f"{Pm:.1f} W")
    c2.metric("V at GMPP", f"{Vm:.1f} V")
    c3.metric("Local peaks found", f"{len(peaks)}")
    c4.metric("Voltage span", f"0 – {res['Voc']:.0f} V")

    st.divider()
    fig = pv_figure(res)
    fig.update_layout(height=560)
    st.plotly_chart(fig, width='stretch', config=plotly_config("multipeak_PV"))

    with st.expander("Show the matching I–V curve"):
        fig_iv = iv_figure(res)
        fig_iv.update_layout(height=460)
        st.plotly_chart(fig_iv, width='stretch',
                        config=plotly_config("multipeak_IV"))

    st.caption("Per-substring irradiance [W/m²]: "
               + ", ".join(f"{g:.0f}" for g in irrs))

    # ------------------------------ Exports ------------------------------- #
    e1, e2, e3 = st.columns(3)
    df = pd.DataFrame({"V_[V]": res["V"], "I_[A]": res["I"], "P_[W]": res["P"]})
    e1.download_button("⬇️ Curve data (CSV)", df.to_csv(index=False),
                       "multipeak_curve.csv", "text/csv", width='stretch')
    data = png_bytes(fig)
    if data:
        e2.download_button("⬇️ P–V PNG (hi-res)", data, "multipeak_PV.png",
                           "image/png", width='stretch')
    else:
        e2.download_button("⬇️ P–V (HTML)", fig.to_html(include_plotlyjs="cdn"),
                           "multipeak_PV.html", "text/html", width='stretch')
    peaks_df = pd.DataFrame(peaks, columns=["V_[V]", "I_[A]", "P_[W]"]
                            ).sort_values("V_[V]").reset_index(drop=True)
    e3.download_button("⬇️ Peak table (CSV)", peaks_df.to_csv(index=False),
                       "multipeak_peaks.csv", "text/csv", width='stretch')


def render_gallery():
    """Grid of real Phase-1 P-V curves — evidence that every scenario differs."""
    st.title("🗂️ Phase-1 Scenario Gallery")
    st.caption("A sample of the 2,000 seeded partial-shading scenarios built in "
               "Phase 1 by the **validated** simulator (pvlib single-diode + "
               "bypass, breakdown ON). Each panel is a different scenario's P–V "
               "curve — the point is that no two are alike.")

    bank = load_curve_bank()
    if bank is None:
        st.info("Curve bank not found. Place **assets/phase1_curves.json** in an "
                "`assets/` folder next to `app.py`.")
        return
    curves = bank["curves"]

    sb = st.sidebar
    sb.header("🗂️ Gallery controls")
    geos = sb.multiselect("Shading geometries",
                          ["uniform", "whole_substring", "sub_substring"],
                          default=["uniform", "whole_substring", "sub_substring"],
                          format_func=lambda g: GEOM_LABEL[g])
    pool = [c for c in curves if c["geometry"] in geos]
    if not pool:
        st.warning("Select at least one geometry.")
        return
    n_show = sb.slider("Curves to show", 6, len(pool),
                       min(24, len(pool)), step=6)
    if sb.button("🔀 Reshuffle sample"):
        st.session_state["gal_seed"] = int(np.random.randint(1_000_000))
    seed = st.session_state.get("gal_seed", 0)

    rng = np.random.default_rng(seed)
    sel = list(pool)
    rng.shuffle(sel)
    sel = sel[:n_show]
    order = {"uniform": 0, "whole_substring": 1, "sub_substring": 2}
    sel.sort(key=lambda d: (order[d["geometry"]], d["n_peaks"], d["id"]))

    ncol = 6
    nrow = int(np.ceil(len(sel) / ncol))
    titles = [f"#{c['id']} · {GEOM_LABEL[c['geometry']][:5]} · {c['n_peaks']}pk"
              for c in sel]
    fig = make_subplots(rows=nrow, cols=ncol, subplot_titles=titles,
                        horizontal_spacing=0.028, vertical_spacing=0.10)
    for k, c in enumerate(sel):
        r, col = k // ncol + 1, k % ncol + 1
        fig.add_trace(go.Scatter(x=c["V"], y=c["P"], mode="lines",
                                 line=dict(color=GEOM_COLORS[c["geometry"]],
                                           width=1.8), showlegend=False),
                      row=r, col=col)
        fig.add_trace(go.Scatter(x=[c["gmpp_V"]], y=[c["gmpp_P"]], mode="markers",
                                 marker=dict(color=COL_GMPP, size=6, symbol="star",
                                             line=dict(color="#111", width=0.4)),
                                 showlegend=False), row=r, col=col)
    fig.update_layout(
        height=205 * nrow, plot_bgcolor="white", paper_bgcolor="white",
        font=dict(family=PLOT_FONT, size=10), margin=dict(l=30, r=12, t=52, b=24),
        title=dict(text="Phase-1 P–V curves (validated simulator) — "
                        "every scenario differs", x=0.5,
                   font=dict(size=18, family=PLOT_FONT, color="#111")))
    fig.update_xaxes(showgrid=True, gridcolor=GRID, linecolor="#ccc",
                     tickfont=dict(size=8))
    fig.update_yaxes(showgrid=True, gridcolor=GRID, linecolor="#ccc",
                     tickfont=dict(size=8))
    for ann in fig.layout.annotations:
        ann.font = dict(size=9, family=PLOT_FONT, color="#333")
    st.plotly_chart(fig, width='stretch', config=plotly_config("phase1_gallery"))

    st.caption("Gold star = GMPP.  Colours: "
               "🟢 uniform · 🔵 whole-substring · 🟠 sub-substring.  "
               f"Provenance: {bank.get('provenance', 'n/a')}")

    slim = load_slim_dataset()
    if slim is not None:
        st.subheader("Why they differ — the label distribution over all 2,000")
        st.plotly_chart(_coeff_hist(slim), width='stretch',
                        config=plotly_config("coeff_distribution"))


def _coeff_hist(slim):
    fig = go.Figure()
    for g in ["uniform", "whole_substring", "sub_substring"]:
        c = slim[slim.geometry == g]["coeff_Vmp_Voc"]
        fig.add_trace(go.Histogram(x=c, name=GEOM_LABEL[g], opacity=0.6,
                                   marker_color=GEOM_COLORS[g], nbinsx=45))
    fig.add_vline(x=0.80, line=dict(color="#555", dash="dash", width=1.5),
                  annotation_text="fixed 0.80")
    fig.update_layout(barmode="overlay", plot_bgcolor="white",
                      paper_bgcolor="white", font=dict(family=PLOT_FONT, size=13),
                      title=dict(text="GMPP coefficient V_gmpp / V_oc across "
                                      "2,000 scenarios", x=0.5),
                      xaxis=dict(title="V_gmpp / V_oc", gridcolor=GRID),
                      yaxis=dict(title="scenarios", gridcolor=GRID),
                      legend=dict(x=0.01, y=0.99), margin=dict(t=50, b=50))
    return fig


def render_validation():
    """How the simulator was validated, with the actual results and references."""
    st.title("✅ Validation & Literature")
    st.markdown(
        "The simulator is validated in **layers**, from an independent premise "
        "through datasheet and measurement checks to a deliberately-deferred "
        "quantitative multi-peak step. Self-consistency alone is *not* treated "
        "as validation (a sign error reproduces itself perfectly), so the middle "
        "layers test the model against sources it was never built to reproduce.")

    st.subheader("Validation gates (re-run on pvlib 0.15.2, seed 20260901)")
    st.dataframe(pd.DataFrame(VALIDATION_GATES), hide_index=True,
                 width='stretch')

    st.subheader("External validation — the three legs of S4")
    st.markdown(
        "- **Leg 1 — structural (Başoğlu 2019).** Reproduces the *shape* of "
        "published shading cases (peak count, ordering). Qualitative by design: "
        "the source module is under-specified, so an exact magnitude match would "
        "be a red flag, not a success.\n"
        "- **Leg 2 — quantitative vs measurement (Sandia).** 108 c-Si modules "
        "present in both the CEC and Sandia libraries as electrical twins; the "
        "single-diode layer agrees with the outdoor-measurement-derived Sandia "
        "model to **2.1% (P_mp) near STC and 2.5% at 55 °C** — the off-STC error "
        "bar every temperature-dependent result carries.\n"
        "- **Leg 3 — quantitative multi-peak (deferred).** No public dataset of "
        "measured, partial-shaded, multi-peak I–V curves on three-substring c-Si "
        "modules exists, so the composed-magnitude check is carried to Phase 8 "
        "with the partner's measured curves. Recorded as a finding, not a gap.")

    slim = load_slim_dataset()
    if slim is not None:
        st.subheader("The founding premise (S1) and the label it produces")
        st.plotly_chart(_coeff_hist(slim), width='stretch',
                        config=plotly_config("coeff_distribution_val"))
        summary = (slim.groupby("geometry")
                   .agg(n=("coeff_Vmp_Voc", "size"),
                        coeff_mean=("coeff_Vmp_Voc", "mean"),
                        coeff_sd=("coeff_Vmp_Voc", "std"),
                        mean_peaks=("n_peaks", "mean"),
                        costly_region_err=("region_error_costly", "mean"),
                        mean_power_loss=("power_lost_frac", "mean"))
                   .round(3).reset_index())
        summary["geometry"] = summary["geometry"].map(GEOM_LABEL)
        summary["costly_region_err"] = (summary["costly_region_err"] * 100).round(1)
        summary["mean_power_loss"] = (summary["mean_power_loss"] * 100).round(2)
        st.subheader("Dataset summary by geometry")
        st.dataframe(summary, hide_index=True, width='stretch')

    st.subheader("Literature & references")
    st.markdown(REFERENCES_MD)

    st.info("**One-line claim for the paper:** the single-diode layer and its "
            "series composition are validated to the fullest extent possible "
            "without measured shaded curves — STC and single-substring physics "
            "quantitatively, multi-peak structure qualitatively — with the "
            "quantitative multi-peak validation deferred to Phase 8. "
            "*'Fully validated' would overstate it.*")


if __name__ == "__main__":
    main()