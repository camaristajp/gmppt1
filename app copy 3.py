"""
Interactive PV Partial-Shading Simulator — professional dashboard edition.

Single-file Streamlit app. Four-zone SaaS layout:
  top nav  ·  KPI strip  ·  action/view toolbar  ·  workspace (curves + editable array)

Model: single-diode substrings + per-substring bypass diode, composed in the
current domain (pure NumPy; no external simulator dependency). Datasheet inputs
(Isc, Voc, Imp, Vmp, Ns, temp coeffs, ideality, Rs, Rsh) drive the model and are
fully editable. Consistent with the project's validated simulator in method;
simplified (no Bishop avalanche) — for interactive use, not numbers of record.

Run:  pip install streamlit plotly numpy pandas       # scipy/kaleido optional
      streamlit run app.py
"""
from __future__ import annotations
import io, json, time
from pathlib import Path
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

# --------------------------------------------------------------------------- #
# Constants & palette
# --------------------------------------------------------------------------- #
Q, K, TREF, GREF = 1.602176634e-19, 1.380649e-23, 298.15, 1000.0
V_BYPASS = 0.7
CELL_AREA_M2 = 0.156 * 0.156

# Vibrant marker/line colours chosen to pass contrast on BOTH themes
COL_IV, COL_PV = "#38BDF8", "#FB923C"
COL_GMPP, COL_LMPP, COL_OP = "#FACC15", "#C084FC", "#34D399"
PLOT_FONT = "Inter, Segoe UI, Helvetica, Arial, sans-serif"

# WCAG-checked palettes (text-on-bg contrast >= AA).
THEMES = {
    "Light": dict(bg="#F8FAFC", panel="#FFFFFF", text="#0F172A", muted="#475569",
                  grid="#E2E8F0", axis="#94A3B8", plot_bg="#FFFFFF", paper_bg="#FFFFFF",
                  card="#FFFFFF", card_border="#E2E8F0"),
    "Dark":  dict(bg="#1E293B", panel="#1E293B", text="#F8FAFC", muted="#CBD5E1",
                  grid="#334155", axis="#64748B", plot_bg="#1E293B", paper_bg="#1E293B",
                  card="#223349", card_border="#334155"),
}
TH = THEMES["Dark"]          # reassigned in main() from the theme toggle
GRID = TH["grid"]


def _style(fig):
    """Apply the active theme to any Plotly figure (backgrounds, font, axes)."""
    fig.update_layout(paper_bgcolor=TH["paper_bg"], plot_bgcolor=TH["plot_bg"],
                      font=dict(family=PLOT_FONT, color=TH["text"]))
    fig.update_xaxes(gridcolor=TH["grid"], linecolor=TH["axis"], zeroline=False,
                     mirror=True, ticks="outside", tickcolor=TH["axis"])
    fig.update_yaxes(gridcolor=TH["grid"], linecolor=TH["axis"], zeroline=False,
                     mirror=True, ticks="outside", tickcolor=TH["axis"])
    for ann in fig.layout.annotations:
        if ann.font is None or ann.font.color is None:
            ann.font = dict(family=PLOT_FONT, color=TH["text"])
    return fig


def apply_theme_css(th):
    st.markdown(f"""<style>
        .stApp, [data-testid="stAppViewContainer"] {{ background:{th['bg']}; }}
        [data-testid="stHeader"] {{ background:{th['bg']}; }}
        [data-testid="stSidebar"] {{ background:{th['panel']}; }}
        .stApp, .stMarkdown, p, label, span, li,
        h1,h2,h3,h4,h5 {{ color:{th['text']} !important; }}
        [data-testid="stCaptionContainer"], .st-emotion-cache-caption,
        small {{ color:{th['muted']} !important; }}
        .block-container {{ padding-top:0.8rem; }}
        div[data-testid="stMetric"] {{ background:{th['card']};
            border:1px solid {th['card_border']}; padding:12px 14px; border-radius:12px; }}
        div[data-testid="stMetric"] [data-testid="stMetricValue"] {{
            color:{th['text']} !important; font-size:1.55rem; }}
        div[data-testid="stMetric"] [data-testid="stMetricLabel"] p {{
            color:{th['muted']} !important; }}
        div[data-testid="stMetric"] [data-testid="stMetricDelta"] {{ color:#F87171 !important; }}
        </style>""", unsafe_allow_html=True)
GEOM_COLORS = {"uniform": "#1BAF7A", "whole_substring": "#0B5FA5", "sub_substring": "#C24914"}
GEOM_LABEL = {"uniform": "uniform", "whole_substring": "whole-substring", "sub_substring": "sub-substring"}
TRACE_COLORS = ["#7b61ff", "#00b8a9", "#f6416c", "#3b8beb", "#f9a826"]

# Editable datasheet presets (real-world representative c-Si modules).
MODULE_PRESETS = {
    "Generic 60-cell mono 300 W": dict(tech="monoSi", Isc=9.50, Voc=39.7, Imp=9.00, Vmp=33.3, Ns=60, alpha_isc=0.0048, beta_voc=-0.117, n=1.10, Rs=0.34, Rsh=320.0),
    "Canadian Solar CS6U-310P":   dict(tech="multiSi", Isc=9.45, Voc=44.9, Imp=8.83, Vmp=35.1, Ns=72, alpha_isc=0.0052, beta_voc=-0.135, n=1.20, Rs=0.42, Rsh=300.0),
    "LONGi LR4-60HPH-370M":       dict(tech="monoSi", Isc=11.6, Voc=40.9, Imp=10.9, Vmp=34.0, Ns=60, alpha_isc=0.0058, beta_voc=-0.113, n=1.05, Rs=0.28, Rsh=360.0),
    "JinkoSolar JKM400M-72":      dict(tech="monoSi", Isc=10.4, Voc=49.2, Imp=9.79, Vmp=40.9, Ns=72, alpha_isc=0.0051, beta_voc=-0.142, n=1.12, Rs=0.36, Rsh=340.0),
    "Trina TSM-330PD14 (multi)":  dict(tech="multiSi", Isc=9.16, Voc=46.0, Imp=8.68, Vmp=38.0, Ns=72, alpha_isc=0.0046, beta_voc=-0.138, n=1.22, Rs=0.45, Rsh=290.0),
}
DEFAULT_PRESET = "Generic 60-cell mono 300 W"

DS_FIELDS = ["Isc", "Voc", "Imp", "Vmp", "Ns", "n", "alpha_isc", "beta_voc", "Rs", "Rsh"]
DS_HELP = {
    "Isc": "Short-circuit current — the current when the terminals are shorted (V = 0).",
    "Voc": "Open-circuit voltage — the voltage with no load connected (I = 0).",
    "Imp": "Current at the maximum-power point (the knee of the curve).",
    "Vmp": "Voltage at the maximum-power point.",
    "Ns": "Number of solar cells wired in series inside the module.",
    "n": "Diode ideality factor — how closely the cell follows the ideal diode law (~1–1.5).",
    "alpha_isc": "Temperature coefficient of Isc — how the current changes per °C.",
    "beta_voc": "Temperature coefficient of Voc — how the voltage changes per °C (usually negative).",
    "Rs": "Series resistance — internal resistive loss; higher Rs lowers the fill factor.",
    "Rsh": "Shunt resistance — leakage path across the cell; low Rsh bleeds away power.",
}


def _apply_cec_preset():
    """Dropdown onChange: push the selected module's datasheet into all fields."""
    name = st.session_state.get("ds_pick")
    if name in MODULE_PRESETS:
        for k, v in MODULE_PRESETS[name].items():
            if k != "tech":
                st.session_state[f"p_{k}"] = v
        st.session_state.ds_name = name


def _reset_ds():
    for k, v in MODULE_PRESETS[DEFAULT_PRESET].items():
        if k != "tech":
            st.session_state[f"p_{k}"] = v
    st.session_state.ds_name = DEFAULT_PRESET
    st.session_state["ds_pick"] = DEFAULT_PRESET


def _hide_guide():
    st.session_state.show_guide = False


def _reset_simulation():
    """Restore module, topology, shading, frozen traces and sweep results."""
    _reset_ds()
    st.session_state.sub_irr = None
    st.session_state.frozen = []
    st.session_state.sweep_results = None
    st.session_state["base_pick"] = "1000"
    st.session_state["temp_c"] = 25
    st.session_state["shade_object"] = "Full Sun / No Shading"
    st.session_state["shade_severity"] = "Moderate"
    st.session_state["shade_location"] = "Center"
    st.session_state["shade_custom_zones"] = []
    st.session_state.dataset = None


# --------------------------------------------------------------------------- #
# Model (pure NumPy)
# --------------------------------------------------------------------------- #
def datasheet_to_ref(ds):
    """Map a module datasheet to the per-cell single-diode reference params the
    engine uses. Isc and Voc are matched exactly by construction; Rs/Rsh/n shape
    the MPP (edit them to tune Vmp/Imp)."""
    Vt = K * TREF / Q
    a_cell = ds["n"] * Vt
    voc_cell = ds["Voc"] / ds["Ns"]
    I_L_ref = ds["Isc"]
    I_0_ref = I_L_ref / (np.exp(voc_cell / a_cell) - 1.0)
    ref = dict(I_L_ref=I_L_ref, I_0_ref=I_0_ref, n=ds["n"],
               Rs_cell=ds["Rs"] / ds["Ns"], Rsh_cell=ds["Rsh"] / ds["Ns"],
               alpha_isc=ds["alpha_isc"], Eg=1.121)
    return ref


def element_params(G, T_c, n_series, ref):
    T = T_c + 273.15
    Vt = K * T / Q
    I_L = max((G / GREF) * (ref["I_L_ref"] + ref["alpha_isc"] * (T - TREF)), 0.0)
    I_0 = ref["I_0_ref"] * (T / TREF) ** 3 * np.exp(
        ref["Eg"] * Q / (ref["n"] * K) * (1.0 / TREF - 1.0 / T))
    a = ref["n"] * Vt * n_series
    return I_L, I_0, a, ref["Rs_cell"] * n_series, ref["Rsh_cell"] * n_series


def element_iv(G, T_c, n_series, ref, npts=500):
    I_L, I_0, a, Rs, Rsh = element_params(G, T_c, n_series, ref)
    if I_L <= 1e-6:
        V = np.linspace(0.0, 0.01, npts)
        return V, np.zeros_like(V), 0.0
    Voc = a * np.log(I_L / I_0 + 1.0)
    Vd = np.linspace(0.0, Voc, npts)
    I = I_L - I_0 * np.expm1(np.clip(Vd / a, -60, 60)) - Vd / Rsh
    V = Vd - I * Rs
    Isc = float(np.interp(0.0, V, I))
    return V, I, Isc


def module_iv(sub_irradiance, T_c, cells_per_sub, ref, n_grid=800):
    elems = [element_iv(G, T_c, cells_per_sub, ref) for G in sub_irradiance]
    isc_list = [e[2] for e in elems]
    i_max = max(isc_list) if isc_list else 0.0
    if i_max <= 1e-6:
        z = np.zeros(n_grid)
        return dict(V=z, I=z, P=z, Voc=0.0, Isc=0.0, gmpp=(0.0, 0.0, 0.0),
                    lmpps=[], bypassed=[True] * len(sub_irradiance),
                    sub_curves=[])
    Igrid = np.linspace(0.0, i_max, n_grid)
    Vmod = np.zeros_like(Igrid)
    sub_curves = []
    for V, I, Isc in elems:
        v_sub = np.where(Igrid <= Isc, np.interp(Igrid, I[::-1], V[::-1]), -V_BYPASS)
        Vmod += v_sub
        sub_curves.append((v_sub, Igrid.copy()))
    Pmod = Vmod * Igrid
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
    bypassed = [peaks[0][1] > isc + 1e-9 for isc in isc_list]
    return dict(V=Vop, I=Iop, P=Pop, Voc=Voc, Isc=Isc, gmpp=peaks[0],
                lmpps=peaks[1:], bypassed=bypassed, sub_curves=sub_curves)


def _find_peaks(V, P, prom_frac=0.01, min_sep_v=2.0):
    if P.size < 3:
        return []
    pmax = float(P.max())
    cand = []
    for i in range(1, len(P) - 1):
        if P[i] >= P[i - 1] and P[i] > P[i + 1]:
            prom = P[i] - max(P[:i].min(), P[i:].min())
            if prom >= prom_frac * pmax:
                cand.append((float(V[i]), float(P[i]), i))
    cand.sort(key=lambda t: t[1], reverse=True)
    kept = []
    for v, p, i in cand:
        if all(abs(v - kv) > min_sep_v for kv, _, _ in kept):
            kept.append((v, p, i))
    return [(V[i], float(P[i] / V[i]) if V[i] > 1e-9 else 0.0, P[i]) for _v, _p, i in kept]


def compute_metrics(res, ds, topo):
    """Array-level metrics from a module result + topology."""
    Vmpp, Impp, Pmax = res["gmpp"]
    Voc, Isc = res["Voc"], res["Isc"]
    ff = Pmax / (Voc * Isc) if (Voc > 0 and Isc > 0) else 0.0
    m_str, p_str = topo["modules_per_string"], topo["parallel_strings"]
    p_array_w = Pmax * m_str * p_str
    return dict(Pmax_W=Pmax, Vmpp=Vmpp, Impp=Impp, Voc=Voc, Isc=Isc, FF=ff,
                P_array_kW=p_array_w / 1000.0, n_lmpp=len(res["lmpps"]),
                V_string=Voc * m_str, I_array=Isc * p_str)


def topology_ok(Ns, n_sub):
    return int(Ns) % int(n_sub) == 0


def _divisors(n):
    return [d for d in range(1, 9) if n % d == 0]


def validate_datasheet(ds, n_sub):
    """Non-silent, user-facing checks for physically inconsistent inputs."""
    w = []
    if ds["Imp"] > ds["Isc"]:
        w.append("Imp should normally be ≤ Isc.")
    if ds["Vmp"] > ds["Voc"]:
        w.append("Vmp should normally be ≤ Voc.")
    if ds["Voc"] > 0 and ds["Isc"] > 0 and (ds["Vmp"] * ds["Imp"]) > (ds["Voc"] * ds["Isc"]):
        w.append("Vmp × Imp exceeds Voc × Isc, which implies a fill factor above 1 (impossible).")
    if ds["beta_voc"] > 0:
        w.append("β_Voc is normally negative (open-circuit voltage falls as temperature rises).")
    if ds["alpha_isc"] < 0:
        w.append("α_Isc is normally positive (short-circuit current rises slightly with temperature).")
    return w


def what_happened(res, sub_irr):
    """Plain-English interpretation generated from the actual result state."""
    hi = max(sub_irr) if sub_irr else 0.0
    spread = (hi - min(sub_irr)) / hi if hi > 0 else 0.0
    n_lmpp = len(res["lmpps"])
    byp = [i + 1 for i, b in enumerate(res["bypassed"]) if b]
    if spread < 0.02:
        return ("All substrings receive essentially the same irradiance, so the module behaves "
                "as an approximately uniform PV source and produces a single dominant P–V peak.")
    parts = ["Uneven irradiance creates a current mismatch between substrings."]
    if byp:
        s = "substring " + ", ".join(f"S{i}" for i in byp)
        parts.append(f"At the global maximum-power point, {s} is bypassed: its bypass-diode path "
                     "carries the string current instead, which protects the shaded cells but "
                     "removes that substring's voltage contribution.")
    if n_lmpp:
        parts.append(f"The mismatch adds {n_lmpp} local power peak{'s' if n_lmpp > 1 else ''}, "
                     "so more than one operating point is possible.")
    else:
        parts.append("The curve stays single-peaked here, but the shaded substring still lowers "
                     "the available power.")
    return " ".join(parts)


def fullsun_bar(p_full_kw, p_cur_kw):
    fig = go.Figure(go.Bar(x=["Full sun", "Current scenario"],
                           y=[p_full_kw, p_cur_kw],
                           marker_color=[COL_GMPP, COL_PV],
                           text=[f"{p_full_kw:.3f} kW", f"{p_cur_kw:.3f} kW"],
                           textposition="outside"))
    fig.update_layout(height=220, yaxis_title="Maximum power [kW]",
                      margin=dict(l=50, r=10, t=10, b=30), showlegend=False)
    return _style(fig)


def simulation_config(ds, topo, base_G, T_c, sub_irr, scen_name, res):
    return {
        "scenario_name": scen_name or st.session_state.ds_name,
        "module": st.session_state.ds_name,
        "datasheet": {k: ds[k] for k in DS_FIELDS},
        "temperature_C": T_c,
        "base_irradiance_Wm2": base_G,
        "shading": {"object": st.session_state.get("shade_object"),
                    "severity": st.session_state.get("shade_severity"),
                    "location": st.session_state.get("shade_location")},
        "substring_irradiance_Wm2": [float(x) for x in sub_irr],
        "topology": {"substring_zones": topo["bypass"],
                     "modules_per_string": topo["modules_per_string"],
                     "parallel_strings": topo["parallel_strings"]},
        "results": {"Vmpp_V": round(res["gmpp"][0], 3), "Impp_A": round(res["gmpp"][1], 3),
                    "Pmax_W": round(res["gmpp"][2], 3), "n_local_peaks": len(res["lmpps"])},
        "model": {"type": "single-diode + per-substring bypass (simplified)",
                  "note": "Vmp/Imp are datasheet reference values; the simplified model does not "
                          "force the calculated MPP to reproduce them exactly."},
    }


# --------------------------------------------------------------------------- #
# Shading presets & maps
# --------------------------------------------------------------------------- #
def preset_sub_irradiance(preset, base_G, shade_frac, n_sub):
    if preset == "Uniform":
        return [base_G] * n_sub
    if preset == "One substring shaded":
        v = [base_G] * n_sub
        v[-1] = base_G * shade_frac
        return v
    if preset == "Graded":
        return list(np.linspace(base_G, base_G * shade_frac, n_sub))
    if preset == "Heavy partial":
        v = [base_G] * n_sub
        v[0] = base_G * shade_frac
        if n_sub > 2:
            v[-1] = base_G * (shade_frac + (1 - shade_frac) * 0.5)
        return v
    return [base_G] * n_sub


# Real-world shading scenarios -> per-substring irradiance (fractions of base G).
SHADING_OBJECTS = ["Full Sun / No Shading", "Cloud", "Tree", "Pole", "Building",
                   "Soil / Ground Shadow", "Soiling", "Custom"]
SHADING_ICON = {"Full Sun / No Shading": "☀️", "Cloud": "☁️", "Tree": "🌳",
                "Pole": "🏗️", "Building": "🏢", "Soil / Ground Shadow": "🟫",
                "Soiling": "🌫️", "Custom": "✏️"}
SEVERITY_REDUCTION = {"Light": 0.25, "Moderate": 0.55, "Severe": 0.80, "Custom": None}
OBJECT_HELP = {
    "Full Sun / No Shading": "Uniform full irradiance across all substrings.",
    "Cloud": "Soft, graded irradiance reduction across the whole module.",
    "Tree": "Dappled shade on the selected zone(s).",
    "Pole": "A narrow hard shadow on a single substring.",
    "Building": "A larger hard shadow across the selected zone(s).",
    "Soil / Ground Shadow": "Ground/edge shadow reducing the selected zone(s).",
    "Soiling": "Uneven dirt/soiling reducing all substrings unevenly.",
    "Custom": "Type exact per-substring irradiance values under the steppers.",
}


def zones_from_location(location, n_sub, custom_zones=None):
    if location == "All":
        return list(range(n_sub))
    if location == "Left":
        return [0]
    if location == "Right":
        return [n_sub - 1]
    if location == "Center":
        return [n_sub // 2]
    if custom_zones:
        return [int(z[1:]) - 1 for z in custom_zones if z[1:].isdigit()]
    return [n_sub // 2]


def object_to_sub_irr(obj, reduction, zones_idx, base_G, n_sub):
    """Convert a shading object + severity + location into per-substring irradiance."""
    base = [float(base_G)] * n_sub
    if obj.startswith("Full Sun") or reduction <= 0:
        return base
    if obj == "Cloud":
        f = np.linspace(1 - 0.4 * reduction, 1 - reduction, n_sub)
        return [round(base_G * x, 1) for x in f]
    if obj == "Soiling":
        f = 1 - reduction * np.linspace(0.5, 1.0, n_sub)
        return [round(base_G * x, 1) for x in f]
    v = base[:]
    for i in zones_idx:
        if 0 <= i < n_sub:
            v[i] = round(base_G * (1 - reduction), 1)
    return v


REALWORLD_PRESETS = ["Full Sun", "Passing Cloud", "Overhead Pole Shadow",
                     "Severe Soiling", "Custom shading"]
REALWORLD_HELP = {
    "Full Sun": "Uniform irradiance across all substrings — a single dominant P–V peak.",
    "Passing Cloud": "Gradual irradiance reduction across the module (soft, non-uniform cloud shadow).",
    "Overhead Pole Shadow": "One substring receives substantially lower irradiance (narrow hard shadow).",
    "Severe Soiling": "Uneven irradiance reduction across the module (non-uniform soiling).",
    "Custom shading": "Type exact per-substring irradiance values with the steppers below.",
}


def realworld_sub(preset, base_G, n_sub):
    """Map a real-world scenario name to a per-substring irradiance list [W/m^2]."""
    if preset == "Full Sun":
        return [float(base_G)] * n_sub
    if preset == "Passing Cloud":
        return list(np.round(base_G * np.linspace(0.90, 0.55, n_sub), 0))
    if preset == "Overhead Pole Shadow":
        v = [float(base_G)] * n_sub
        v[-1] = round(base_G * 0.22, 0)          # one zone hard-shadowed
        return v
    if preset == "Severe Soiling":
        return list(np.round(base_G * np.linspace(0.72, 0.40, n_sub), 0))
    return [float(base_G)] * n_sub               # Custom handled by the editor


def module_graphic(sub_irr):
    """Interactive 2D module graphic: substring bands colour-coded by irradiance
    (100 W/m^2 dark-gray -> 1000 W/m^2 yellow)."""
    n = len(sub_irr)
    z = np.array(sub_irr).reshape(n, 1)[::-1]     # S1 at top
    labels = [[f"S{n-i}<br>{int(sub_irr[n-1-i])} W/m²"] for i in range(n)]
    fig = go.Figure(go.Heatmap(
        z=z, text=labels, texttemplate="%{text}",
        textfont=dict(size=13, color="#0F172A", family=PLOT_FONT),
        colorscale=[[0.0, "#334155"], [0.35, "#7C6F52"], [0.7, "#CA8A04"], [1.0, "#FACC15"]],
        zmin=0, zmax=1200, showscale=True,
        colorbar=dict(title="W/m²", thickness=12),
        hovertemplate="%{text}<extra></extra>", xgap=3, ygap=3))
    fig.update_layout(height=150 + 26 * n, title=dict(text="Solar module — substring irradiance",
                      font=dict(size=13, family=PLOT_FONT)),
                      margin=dict(l=10, r=10, t=40, b=10))
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    return _style(fig)


def build_cell_grid(sub_irr, cells_per_sub):
    """A per-cell irradiance grid for the heatmap: each substring is a row band."""
    n_sub = len(sub_irr)
    cols = max(1, int(round(np.sqrt(cells_per_sub * n_sub) )))
    rows_per = max(1, cells_per_sub // cols) or 1
    grid = np.vstack([np.full((max(1, rows_per), cols), g) for g in sub_irr])
    return grid


def thermal_stress_grid(grid, base_G, bypassed, n_sub):
    bands = np.array_split(np.arange(grid.shape[0]), n_sub)
    stress = np.zeros_like(grid)
    for b, byp in zip(bands, bypassed):
        shade = 1.0 - grid[b, :] / max(base_G, 1e-9)
        stress[b, :] = shade * (0.35 if byp else 1.0)
    return np.clip(stress, 0.0, 1.0)


# --------------------------------------------------------------------------- #
# Figures
# --------------------------------------------------------------------------- #
def _axes(fig):
    fig.update_xaxes(showgrid=True, gridcolor=TH["grid"], zeroline=False,
                     linecolor=TH["axis"], mirror=True, ticks="outside")
    fig.update_yaxes(showgrid=True, gridcolor=TH["grid"], zeroline=False,
                     linecolor=TH["axis"], mirror=True, ticks="outside")


def combined_figure(res, frozen):
    fig = make_subplots(rows=1, cols=2, subplot_titles=("I–V Characteristic",
                                                        "P–V Characteristic"),
                        horizontal_spacing=0.08)
    # frozen comparison traces (behind)
    for k, fr in enumerate(frozen):
        c = TRACE_COLORS[k % len(TRACE_COLORS)]
        fig.add_trace(go.Scatter(x=fr["V"], y=fr["I"], mode="lines",
                                 line=dict(color=c, width=1.5, dash="dot"),
                                 name=fr["label"], legendgroup=fr["label"],
                                 hovertemplate="%{x:.1f} V, %{y:.2f} A<extra></extra>"),
                      row=1, col=1)
        fig.add_trace(go.Scatter(x=fr["V"], y=fr["P"], mode="lines",
                                 line=dict(color=c, width=1.5, dash="dot"),
                                 name=fr["label"], legendgroup=fr["label"],
                                 showlegend=False,
                                 hovertemplate="%{x:.1f} V, %{y:.1f} W<extra></extra>"),
                      row=1, col=2)
    # active traces
    fig.add_trace(go.Scatter(x=res["V"], y=res["I"], mode="lines",
                             line=dict(color=COL_IV, width=3), name="current",
                             hovertemplate="%{x:.1f} V, %{y:.2f} A<extra></extra>"),
                  row=1, col=1)
    fig.add_trace(go.Scatter(x=res["V"], y=res["P"], mode="lines",
                             line=dict(color=COL_PV, width=3), name="current",
                             showlegend=False,
                             hovertemplate="%{x:.1f} V, %{y:.1f} W<extra></extra>"),
                  row=1, col=2)
    Vm, Im, Pm = res["gmpp"]
    # GMPP "target" badge (outer ring + star) on BOTH curves
    def _gmpp(col, y, unit, val):
        fig.add_trace(go.Scatter(x=[Vm], y=[y], mode="markers", showlegend=(col == 1),
                                 name="GMPP",
                                 marker=dict(color="rgba(0,0,0,0)", size=24, symbol="circle",
                                             line=dict(color=COL_GMPP, width=2.5)),
                                 hoverinfo="skip"), row=1, col=col)
        fig.add_trace(go.Scatter(x=[Vm], y=[y], mode="markers", showlegend=False,
                                 marker=dict(color=COL_GMPP, size=12, symbol="star",
                                             line=dict(color="#1c1300", width=1)),
                                 hovertemplate=f"GMPP<br>{Vm:.1f} V, {val:.2f} {unit}<extra></extra>"),
                      row=1, col=col)
    _gmpp(1, Im, "A", Im)
    _gmpp(2, Pm, "W", Pm)
    fig.add_annotation(x=Vm, y=Pm, text=f"<b>GMPP</b> {Pm:.0f} W", showarrow=True,
                       arrowhead=2, ax=0, ay=-40, row=1, col=2,
                       font=dict(size=12, color=TH["text"]),
                       bgcolor="rgba(250,204,21,0.18)", bordercolor=COL_GMPP)
    # LMPP diamond badges on BOTH curves
    if res["lmpps"]:
        lv = [v for v, _, _ in res["lmpps"]]
        li = [i for _, i, _ in res["lmpps"]]
        lp = [p for _, _, p in res["lmpps"]]
        txt = [f"LMPP {p:.0f} W (−{(Pm-p)/Pm*100:.0f}% vs GMPP)" for p in lp]
        fig.add_trace(go.Scatter(x=lv, y=li, mode="markers", name="LMPP",
                                 marker=dict(color=COL_LMPP, size=10, symbol="diamond",
                                             line=dict(color="#2b1a4a", width=1)),
                                 text=txt, hovertemplate="%{text}<extra></extra>"),
                      row=1, col=1)
        fig.add_trace(go.Scatter(x=lv, y=lp, mode="markers", name="LMPP", showlegend=False,
                                 marker=dict(color=COL_LMPP, size=11, symbol="diamond",
                                             line=dict(color="#2b1a4a", width=1)),
                                 text=txt, hovertemplate="%{text}<extra></extra>"),
                      row=1, col=2)
    fig.update_xaxes(title_text="Voltage  V  [V]", row=1, col=1)
    fig.update_xaxes(title_text="Voltage  V  [V]", row=1, col=2)
    fig.update_yaxes(title_text="Current  I  [A]", row=1, col=1)
    fig.update_yaxes(title_text="Power  P  [W]", row=1, col=2)
    fig.update_layout(height=440, margin=dict(l=60, r=20, t=54, b=55),
                      hovermode="x unified",
                      legend=dict(orientation="h", y=1.16, x=1, xanchor="right"))
    # synchronized-hover spikelines (vertical guide follows the cursor on each plot)
    fig.update_xaxes(showspikes=True, spikemode="across", spikesnap="cursor",
                     spikethickness=1, spikedash="dot", spikecolor=TH["muted"])
    return _style(fig)


def string_breakdown_figure(res, ds):
    fig = go.Figure()
    for k, (Vs, Ig) in enumerate(res["sub_curves"], 1):
        m = Vs >= 0
        fig.add_trace(go.Scatter(x=Vs[m], y=(Vs * Ig)[m], mode="lines",
                                 name=f"substring {k}",
                                 line=dict(width=2)))
    fig.add_trace(go.Scatter(x=res["V"], y=res["P"], mode="lines",
                             name="module", line=dict(color="#111", width=3)))
    fig.update_layout(height=430, plot_bgcolor="white", paper_bgcolor="white",
                      font=dict(family=PLOT_FONT, size=13),
                      title="Per-substring vs module P–V",
                      xaxis_title="Voltage [V]", yaxis_title="Power [W]",
                      margin=dict(l=60, r=20, t=50, b=55))
    return _style(fig)


def heatmap_figure(grid, title, colorscale, zmax):
    fig = go.Figure(go.Heatmap(z=grid, colorscale=colorscale, zmin=0, zmax=zmax,
                               colorbar=dict(title="")))
    fig.update_layout(height=250, title=dict(text=title, font=dict(size=13, family=PLOT_FONT)),
                      plot_bgcolor="white", paper_bgcolor="white",
                      font=dict(family=PLOT_FONT),
                      yaxis=dict(autorange="reversed", title="row", scaleanchor="x"),
                      xaxis=dict(title="col"), margin=dict(l=40, r=10, t=40, b=30))
    return _style(fig)


PLOTLY_CFG_SVG = {"displaylogo": False,
                  "toImageButtonOptions": {"format": "svg", "filename": "pv_curves", "scale": 1},
                  "modeBarButtonsToAdd": ["toImage"]}


# --------------------------------------------------------------------------- #
# Exports
# --------------------------------------------------------------------------- #
def curve_csv(res):
    return pd.DataFrame({"V_[V]": res["V"], "I_[A]": res["I"], "P_[W]": res["P"]}).to_csv(index=False)


def matlab_bytes(res, meta):
    try:
        from scipy.io import savemat
    except Exception:
        return None
    buf = io.BytesIO()
    savemat(buf, {"V": np.asarray(res["V"]), "I": np.asarray(res["I"]),
                  "P": np.asarray(res["P"]),
                  "gmpp": np.asarray(res["gmpp"], float),
                  "lmpps": np.asarray(res["lmpps"], float) if res["lmpps"] else np.zeros((0, 3)),
                  "meta": meta})
    return buf.getvalue()


def svg_bytes(fig):
    try:
        return fig.to_image(format="svg")
    except Exception:
        return None


def peaks_rows(res):
    Pm = res["gmpp"][2]
    rows = [{"Peak Type": "🎯 Global Max Peak", "Voltage (V)": round(res["gmpp"][0], 2),
             "Current (A)": round(res["gmpp"][1], 2), "Power (W)": round(Pm, 1),
             "Power Loss vs. Max Peak (%)": "—"}]
    for v, i, pp in res.get("lmpps", []):
        rows.append({"Peak Type": "◆ Local Peak", "Voltage (V)": round(v, 2),
                     "Current (A)": round(i, 2), "Power (W)": round(pp, 1),
                     "Power Loss vs. Max Peak (%)": f"−{(Pm-pp)/Pm*100:.1f}"})
    return rows


def res_from_frozen(f):
    return dict(V=np.array(f["V"]), I=np.array(f["I"]), P=np.array(f["P"]),
                gmpp=tuple(f["gmpp"]), lmpps=[])


def simple_pv_figure(res, title):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=res["V"], y=res["P"], mode="lines",
                             line=dict(color=COL_PV, width=3)))
    Vm, _, Pm = res["gmpp"]
    fig.add_trace(go.Scatter(x=[Vm], y=[Pm], mode="markers",
                             marker=dict(color=COL_GMPP, size=13, symbol="star",
                                         line=dict(color="#1c1300", width=1))))
    fig.update_layout(height=360, title=title, xaxis_title="Voltage [V]",
                      yaxis_title="Power [W]", showlegend=False)
    return _style(fig)


SWEEP_COLORS = ["#38BDF8", "#FB923C", "#34D399", "#C084FC", "#F472B6", "#FBBF24",
                "#60A5FA", "#A3E635", "#F87171", "#22D3EE", "#E879F9", "#4ADE80"]


@st.cache_data(show_spinner=False)
def run_sweep(modules, temps, irrs, n_sub, max_perms=120):
    """Solve module_iv for every (module × temperature × irradiance) permutation."""
    traces = []
    for name in modules:
        ds_p = MODULE_PRESETS[name]
        ref = datasheet_to_ref(ds_p)
        cps = max(1, ds_p["Ns"] // n_sub)
        short = name.split()[0]
        for T in temps:
            for G in irrs:
                if len(traces) >= max_perms:
                    return traces
                r = module_iv([float(G)] * n_sub, float(T), cps, ref)
                traces.append(dict(label=f"{short} · {int(T)}°C · {int(G)} W/m²",
                                   V=r["V"].tolist(), I=r["I"].tolist(),
                                   P=r["P"].tolist(), gmpp=list(r["gmpp"])))
    return traces


def sweep_figure(traces):
    fig = go.Figure()
    for k, t in enumerate(traces):
        c = SWEEP_COLORS[k % len(SWEEP_COLORS)]
        fig.add_trace(go.Scatter(x=t["V"], y=t["P"], mode="lines", name=t["label"],
                                 line=dict(color=c, width=2),
                                 hovertemplate=t["label"] + "<br>%{x:.1f} V, %{y:.1f} W<extra></extra>"))
        Vm, _, Pm = t["gmpp"]
        fig.add_trace(go.Scatter(x=[Vm], y=[Pm], mode="markers", showlegend=False,
                                 marker=dict(color=c, size=7, symbol="star",
                                             line=dict(color="#1c1300", width=0.5))))
    fig.update_layout(height=520, title="Parametric sweep — layered P–V overlay",
                      xaxis_title="Voltage [V]", yaxis_title="Power [W]",
                      legend=dict(font=dict(size=10), orientation="v", x=1.02, y=1))
    return _style(fig)


# --------------------------------------------------------------------------- #
# Bulk dataset generator (runs the REAL model N times)
# --------------------------------------------------------------------------- #
def _resample_curve(res, L=256):
    V = np.asarray(res["V"], float)
    if V.size < 2:
        z = np.zeros(L); return z, z, z
    grid = np.linspace(0.0, max(float(V.max()), 1e-6), L)
    return grid, np.interp(grid, V, res["I"]), np.interp(grid, V, res["P"])


def _sample_scenario(rng, cfg, n_sub):
    obj = str(rng.choice(cfg["objects"]))
    if obj.startswith("Full Sun"):
        reduction = 0.0
    elif cfg["rand_severity"]:
        reduction = float(rng.uniform(0.15, 0.90))
    else:
        reduction = SEVERITY_REDUCTION.get(cfg["severity"], 0.55) or 0.55
    if obj in ("Cloud", "Soiling"):
        zones = list(range(n_sub))
    elif cfg["rand_location"]:
        k = int(rng.integers(1, n_sub + 1))
        zones = sorted(int(z) for z in rng.choice(n_sub, size=k, replace=False))
    else:
        zones = zones_from_location(cfg["location"], n_sub)
    base_G = float(rng.uniform(cfg["G_min"], cfg["G_max"])) if cfg["rand_base"] else cfg["base_G"]
    T = float(rng.uniform(cfg["T_min"], cfg["T_max"])) if cfg["rand_temp"] else cfg["T"]
    return obj, reduction, zones, base_G, T


def generate_dataset(ds, n_sub, cfg, progress=None):
    cells_per_sub = ds["Ns"] // n_sub
    ref = datasheet_to_ref(ds)
    rng = np.random.default_rng(cfg["seed"])
    rows, Vs, Is, Ps = [], [], [], []
    fails = 0
    N = cfg["n"]
    for i in range(N):
        obj, reduction, zones, base_G, T = _sample_scenario(rng, cfg, n_sub)
        sub_irr = object_to_sub_irr(obj, reduction, zones, base_G, n_sub)
        try:
            res = module_iv(sub_irr, T, cells_per_sub, ref, n_grid=400)
            uns = module_iv([max(sub_irr)] * n_sub, T, cells_per_sub, ref, n_grid=400)
            Pmax, Pfull = res["gmpp"][2], uns["gmpp"][2]
            if Pmax <= 0:
                fails += 1
            else:
                V, I, P = _resample_curve(res)
                row = {"scenario_id": f"S{i+1:05d}", "shading_object": obj,
                       "reduction_percent": round(reduction * 100, 1),
                       "affected_zones": ("-" if obj.startswith("Full Sun")
                                          else "|".join(f"S{z+1}" for z in zones)),
                       "temperature_C": round(T, 1),
                       "base_irradiance_Wm2": round(base_G, 1)}
                for z in range(n_sub):
                    row[f"substring_irradiance_{z+1}"] = round(sub_irr[z], 1)
                row.update({"gmpp_voltage_V": round(res["gmpp"][0], 3),
                            "gmpp_current_A": round(res["gmpp"][1], 3),
                            "gmpp_power_W": round(Pmax, 3),
                            "power_loss_W": round(Pfull - Pmax, 3),
                            "power_loss_percent": round((Pfull - Pmax) / Pfull * 100, 2)
                            if Pfull > 0 else 0.0,
                            "local_peak_count": 1 + len(res["lmpps"])})
                for z in range(n_sub):
                    row[f"bypass_state_{z+1}"] = "Active" if res["bypassed"][z] else "Not active"
                rows.append(row); Vs.append(V); Is.append(I); Ps.append(P)
        except Exception:
            fails += 1
        if progress and (i % 25 == 0 or i == N - 1):
            progress(i + 1, N)
    df = pd.DataFrame(rows)
    curves = {"scenario_id": (df["scenario_id"].to_numpy() if len(df) else np.array([])),
              "V": np.array(Vs), "I": np.array(Is), "P": np.array(Ps)}
    byp = df.filter(like="bypass_state_").eq("Active").any(axis=1) if len(df) else pd.Series([], dtype=bool)
    stats = {"requested": N, "successful": len(df), "failed": fails,
             "multi_peak": int((df["local_peak_count"] > 1).sum()) if len(df) else 0,
             "bypass_active": int(byp.sum()) if len(df) else 0,
             "gmpp_min_W": round(float(df["gmpp_power_W"].min()), 1) if len(df) else 0,
             "gmpp_max_W": round(float(df["gmpp_power_W"].max()), 1) if len(df) else 0,
             "loss_min_pct": round(float(df["power_loss_percent"].min()), 1) if len(df) else 0,
             "loss_max_pct": round(float(df["power_loss_percent"].max()), 1) if len(df) else 0}
    return df, curves, stats


def dataset_readme(cfg, stats, ds):
    import datetime
    return (
        "PV Partial-Shading Simulation Dataset\n"
        f"Generated: {datetime.datetime.now().isoformat(timespec='seconds')}\n\n"
        f"Scenarios requested: {cfg['n']}   successful: {stats['successful']}   "
        f"failed: {stats['failed']}\n"
        f"Module: {cfg['module']}  (Ns={ds['Ns']}, {cfg['n_sub']} substring zones)\n"
        f"Array: {cfg['topology']['modules_per_string']} modules/string x "
        f"{cfg['topology']['parallel_strings']} parallel\n"
        f"Shading objects: {', '.join(cfg['objects'])}\n"
        f"Base irradiance: {cfg['G_min']}-{cfg['G_max']} W/m^2 (randomized={cfg['rand_base']})\n"
        f"Temperature: {cfg['T_min']}-{cfg['T_max']} C (randomized={cfg['rand_temp']})\n"
        f"Random seed: {cfg['seed']}   Model version: {cfg.get('version','1.0')}\n\n"
        "FILES\n"
        "  scenarios.csv        one row per scenario (shading + GMPP + loss + bypass)\n"
        f"  curves.npz           arrays V,I,P each shape (N,{cfg.get('L',256)}); scenario_id index\n"
        "  configuration.json   full generation configuration (reproducible with the seed)\n\n"
        "DEFINITIONS\n"
        "  GMPP         global maximum power point on the P-V curve\n"
        "  local peaks  additional local P-V maxima caused by partial shading\n"
        "  bypass state whether a substring's bypass diode conducts at the GMPP\n"
        "  units: irradiance W/m^2, temperature C, voltage V, current A, power W\n\n"
        "LIMITATIONS\n"
        "  Simplified single-diode + per-substring bypass model for interactive/research\n"
        "  use; not a substitute for measured I-V characterization. Static shading only.\n")


def build_dataset_zip(df, curves, cfg, stats, ds):
    import zipfile
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("pv_partial_shading_dataset/scenarios.csv", df.to_csv(index=False))
        npz = io.BytesIO()
        np.savez_compressed(npz, scenario_id=curves["scenario_id"], V=curves["V"],
                            I=curves["I"], P=curves["P"])
        z.writestr("pv_partial_shading_dataset/curves.npz", npz.getvalue())
        z.writestr("pv_partial_shading_dataset/configuration.json",
                   json.dumps({**cfg, "datasheet": {k: ds[k] for k in DS_FIELDS},
                               "stats": stats}, indent=2, default=str))
        z.writestr("pv_partial_shading_dataset/README.txt", dataset_readme(cfg, stats, ds))
    return buf.getvalue()


def build_export_zip(scenarios, types, configs=None):
    import zipfile
    configs = configs or {}
    buf = io.BytesIO()
    notes = []
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name, res_s in scenarios:
            safe = name.replace(" ", "_").replace("/", "-").replace("·", "-")
            if types.get("csv"):
                z.writestr(f"{safe}_curve.csv", curve_csv(res_s))
            if types.get("peaks"):
                z.writestr(f"{safe}_peaks.csv",
                           pd.DataFrame(peaks_rows(res_s)).to_csv(index=False))
            if types.get("mat"):
                mb = matlab_bytes(res_s, name)
                if mb:
                    z.writestr(f"{safe}.mat", mb)
                else:
                    notes.append("MATLAB export needs SciPy (pip install scipy).")
            if types.get("svg"):
                sv = svg_bytes(simple_pv_figure(res_s, name))
                if sv:
                    z.writestr(f"{safe}_PV.svg", sv)
                else:
                    notes.append("SVG export needs kaleido+Chrome; "
                                 "use the chart 📷 icon (exports SVG client-side).")
            if types.get("json"):
                cfg = configs.get(name) or {"scenario_name": name,
                    "results": {"Vmpp_V": round(res_s["gmpp"][0], 3),
                                "Impp_A": round(res_s["gmpp"][1], 3),
                                "Pmax_W": round(res_s["gmpp"][2], 3)}}
                z.writestr(f"{safe}_config.json", json.dumps(cfg, indent=2))
        if notes:
            z.writestr("README.txt", "\n".join(sorted(set(notes))))
    return buf.getvalue()


def render_export_popover(res, frozen, current_cfg=None):
    opts = ["Current Scenario Only", "Active Comparison Traces",
            "All Session Scenarios", "Custom Selection"]
    sweep = st.session_state.get("sweep_results")
    if sweep:
        opts.append("Parametric Sweep Results")
    scope = st.radio("Export scope", opts, key="exp_scope")
    cur = [("current", res)]
    froz = [(f["label"], res_from_frozen(f)) for f in frozen]
    if scope == "Current Scenario Only":
        chosen = cur
    elif scope == "Parametric Sweep Results":
        chosen = [(t["label"], res_from_frozen(t)) for t in (sweep or [])]
    elif scope in ("Active Comparison Traces", "All Session Scenarios"):
        chosen = cur + froz
    else:
        labels = ["current"] + [f["label"] for f in frozen]
        allmap = {"current": res}
        for f in frozen:
            allmap[f["label"]] = res_from_frozen(f)
        picks = st.multiselect("Scenarios", labels, default=["current"], key="exp_custom")
        chosen = [(nm, allmap[nm]) for nm in picks if nm in allmap]
    st.markdown("**Data types**")
    types = dict(csv=st.checkbox("Curve Raw Data (.csv)", True, key="exp_csv"),
                 peaks=st.checkbox("Peak Metrics (.csv)", True, key="exp_peaks"),
                 mat=st.checkbox("MATLAB Struct (.mat)", False, key="exp_mat"),
                 svg=st.checkbox("Chart Vector (.svg)", False, key="exp_svg"),
                 json=st.checkbox("Simulation Config (.json)", True, key="exp_json",
                                  help="All inputs needed to reproduce the run."))
    configs = {"current": current_cfg}
    for f in frozen:
        configs[f["label"]] = f.get("config")
    if not chosen or not any(types.values()):
        st.caption("Pick at least one scenario and one data type.")
    else:
        st.download_button("⬇️ Prepare & download (.zip)",
                           build_export_zip(chosen, types, configs), "pv_export.zip",
                           "application/zip", use_container_width=True)


# --------------------------------------------------------------------------- #
# Assets for Gallery / Validation (bundled)
# --------------------------------------------------------------------------- #
ASSETS = Path(__file__).parent / "assets"


@st.cache_data(show_spinner=False)
def load_curve_bank():
    p = ASSETS / "phase1_curves.json"
    return json.loads(p.read_text()) if p.exists() else None


@st.cache_data(show_spinner=False)
def load_slim_dataset():
    p = ASSETS / "phase1_dataset.csv"
    return pd.read_csv(p) if p.exists() else None


VALIDATION_GATES = [
    {"Gate": "S1 · premise", "Type": "Independent", "Independent source": "CEC database, directly",
     "Result": "20,946 c-Si · mean 0.811 · 41% within ±0.01 of 0.80"},
    {"Gate": "S2 · STC point", "Type": "Independent", "Independent source": "Manufacturer datasheets (3 s.f.)",
     "Result": "PASS — worst error 0.000%"},
    {"Gate": "S3 · composition", "Type": "Self-consistency", "Independent source": "Direct single-diode (self-consistency)",
     "Result": "PASS — 3 peaks present"},
    {"Gate": "S4 · off-STC", "Type": "Independent", "Independent source": "Sandia measurement model, 108 twins",
     "Result": "PASS — P_mp 2.1% @STC, 2.5% @55 °C"},
    {"Gate": "S4 · structure", "Type": "Qualitative", "Independent source": "Başoğlu (2019), IEEE TIA",
     "Result": "PASS (qualitative)"},
    {"Gate": "S4 · magnitude", "Type": "Deferred", "Independent source": "Measured shaded I–V (partner)",
     "Result": "Deferred → Phase 8"},
    {"Gate": "S5 · array", "Type": "Self-consistency", "Independent source": "Module model (self-consistency)", "Result": "PASS"},
    {"Gate": "Gate A · dataset", "Type": "Self-consistency", "Independent source": "2,000-scenario characterisation",
     "Result": "6.1% raw region error (≈ plan 6.7%)"},
]
MEASURED_LAYERS = {
    "C1 — coefficient (flash-test DB)": "v_c1_measured.csv",
    "L2 — measured I-V vs model": "v_l2_curves.csv",
    "L3 — IEC 61853 off-STC": "v_l3_offstc.csv",
    "L4 — breakdown sensitivity": "v_l4_breakdown_sensitivity.csv",
}


# --------------------------------------------------------------------------- #
# Session-state helpers
# --------------------------------------------------------------------------- #
def init_state():
    st.session_state.setdefault("ds_name", DEFAULT_PRESET)
    st.session_state.setdefault("ds_pick", DEFAULT_PRESET)
    for k, v in MODULE_PRESETS[DEFAULT_PRESET].items():
        if k != "tech":
            st.session_state.setdefault(f"p_{k}", v)
    st.session_state.setdefault("frozen", [])
    st.session_state.setdefault("sub_irr", None)
    st.session_state.setdefault("sweep_results", None)
    st.session_state.setdefault("show_guide", True)
    st.session_state.setdefault("scen_pick", "Full Sun")
    st.session_state.setdefault("base_pick", "1000")
    st.session_state.setdefault("temp_c", 25)
    st.session_state.setdefault("shade_object", "Full Sun / No Shading")
    st.session_state.setdefault("shade_severity", "Moderate")
    st.session_state.setdefault("shade_location", "Center")
    st.session_state.setdefault("shade_custom_zones", [])
    st.session_state.setdefault("shade_custom_pct", 70)
    st.session_state.setdefault("shade_label", "Full Sun")
    st.session_state.setdefault("dataset", None)


# --------------------------------------------------------------------------- #
# Sidebar (inputs, datasheet, topology, solver status)
# --------------------------------------------------------------------------- #
def render_sidebar():
    sb = st.sidebar
    sb.markdown("### ☀️ PV Simulator")
    sb.caption("Edit inputs here → results appear on the right")

    # 1) ---- Module & Datasheet ----
    sb.markdown("#### 1 · 📇 Module & Datasheet")
    names = list(MODULE_PRESETS) + ["Custom / uploaded"]
    dcol, ucol = sb.columns([3, 1])
    with dcol:
        st.selectbox("CEC datasheet", names, key="ds_pick",
                     on_change=_apply_cec_preset, label_visibility="collapsed")
    with ucol:
        with st.popover("⬆", use_container_width=True, help="Upload CSV/JSON datasheet"):
            up = st.file_uploader("Datasheet file", type=["csv", "json"],
                                  label_visibility="collapsed")
            if up is not None:
                try:
                    d = json.load(up) if up.name.endswith("json") else \
                        pd.read_csv(up).iloc[0].to_dict()
                    for k in DS_FIELDS:
                        if k in d:
                            st.session_state[f"p_{k}"] = int(float(d[k])) if k == "Ns" \
                                else float(d[k])
                    st.session_state.ds_name = "Custom / uploaded"; st.success("Loaded.")
                except Exception as e:
                    st.error(f"Parse error: {e}")
    ds = {k: st.session_state[f"p_{k}"] for k in DS_FIELDS}
    ds["Ns"] = int(ds["Ns"])

    # 2) ---- Array Topology ----
    with sb.expander("2 · 🔲 Array Topology", expanded=True):
        n_sub = int(st.number_input(
            "Substring / bypass-diode zones", 1, 8, 3, 1,
            help="Number of series-connected cell substrings in the module model. "
                 "Each substring has its own bypass-diode path."))
        m_str = int(st.number_input("Modules per string", 1, 40, 1, 1))
        p_str = int(st.number_input("Parallel strings", 1, 40, 1, 1))
        st.caption("Array power assumes identical modules sharing the same substring "
                   "irradiance pattern and parameters.")
    topo = dict(bypass=n_sub, modules_per_string=m_str, parallel_strings=p_str)

    # 3) ---- Array Shading & Scenarios ----
    with sb.expander("3 · 🌓 Array Shading & Scenarios", expanded=True):
        obj = st.selectbox("Shading object", SHADING_OBJECTS, key="shade_object",
                           format_func=lambda o: f"{SHADING_ICON[o]} {o}")
        st.caption(OBJECT_HELP.get(obj, ""))

        st.selectbox("Base irradiance [W/m²]",
                     ["1000", "800", "650", "500", "300", "Custom…"], key="base_pick",
                     help="Full sunlight before shading is applied.")
        base_G = st.number_input("Custom base [W/m²]", 100, 1200, 800, 25) \
            if st.session_state.base_pick == "Custom…" else int(st.session_state.base_pick)
        T_c = st.number_input("Cell temperature [°C]", -10, 70, key="temp_c", step=1,
                              help="Cell temperature, not ambient air temperature.")
        st.caption("STC reference: 1000 W/m² and 25 °C cell temperature.")

        reduction, zones = 0.0, list(range(n_sub))
        is_full = obj.startswith("Full Sun")
        is_custom = (obj == "Custom")
        if not is_full and not is_custom:
            sev = st.selectbox("Shading severity",
                               ["Light", "Moderate", "Severe", "Custom"], key="shade_severity")
            if sev == "Custom":
                reduction = st.slider("Shading reduction [%]", 0, 95,
                                      int(st.session_state.shade_custom_pct),
                                      key="shade_custom_pct") / 100.0
            else:
                reduction = SEVERITY_REDUCTION[sev]
            if obj in ("Tree", "Pole", "Building", "Soil / Ground Shadow"):
                loc = st.selectbox("Shading location",
                                   ["Center", "Left", "Right", "All", "Custom zones"],
                                   key="shade_location")
                cz = None
                if loc == "Custom zones":
                    cz = st.multiselect("Affected substrings",
                                        [f"S{i+1}" for i in range(n_sub)],
                                        key="shade_custom_zones")
                zones = zones_from_location(loc, n_sub, cz)

        if (st.session_state.sub_irr is None) or (len(st.session_state.sub_irr) != n_sub):
            st.session_state.sub_irr = [float(base_G)] * n_sub
        if is_custom:
            st.markdown("**Custom substring irradiance [W/m²]**")
            new = [st.number_input(f"S{i+1}", 0.0, 1200.0,
                                   float(st.session_state.sub_irr[i]), 25.0,
                                   key=f"sub_step_{i}_{n_sub}") for i in range(n_sub)]
            st.session_state.sub_irr = [float(x) for x in new]
        else:
            st.session_state.sub_irr = object_to_sub_irr(obj, reduction, zones, base_G, n_sub)

        st.caption(f"Base **{int(base_G)}** W/m²  ·  reduction **{int(reduction*100)}%** "
                   f"on affected zones")
        st.caption("Resulting: " + " · ".join(f"S{i+1}={int(g)}"
                                              for i, g in enumerate(st.session_state.sub_irr))
                   + " W/m²")
        st.session_state.shade_label = ("Full Sun" if is_full else
                                        ("Custom shading" if is_custom else
                                         f"{obj} · {int(reduction*100)}%"))

        with st.expander("🧪 Parametric Sweep Generator", expanded=False):
            mods = st.multiselect("Modules to compare", list(MODULE_PRESETS),
                                  default=[st.session_state.ds_name
                                           if st.session_state.ds_name in MODULE_PRESETS
                                           else DEFAULT_PRESET])
            st.caption("Temperature sweep (°C)")
            tc = st.columns(3)
            t_start = int(tc[0].number_input("T start", -10, 90, 15, 5))
            t_end = int(tc[1].number_input("T end", -10, 90, 75, 5))
            t_step = int(tc[2].number_input("T step", 1, 50, 15, 1))
            st.caption("Irradiance sweep (W/m²)")
            gc = st.columns(3)
            g_start = int(gc[0].number_input("G start", 100, 1200, 200, 50))
            g_end = int(gc[1].number_input("G end", 100, 1200, 1000, 50))
            g_step = int(gc[2].number_input("G step", 25, 500, 200, 25))
            temps = list(range(t_start, t_end + 1, max(t_step, 1)))
            irrs = list(range(g_start, g_end + 1, max(g_step, 1)))
            n_perm = len(mods) * len(temps) * len(irrs)
            msg = f"{len(mods)} module(s) × {len(temps)} T × {len(irrs)} G = **{n_perm}** curves"
            if n_perm <= 12:
                st.caption(msg + " · small")
            elif n_perm <= 48:
                st.info(msg + " · moderate — a few seconds.")
            else:
                st.warning(msg + " · large — may take a while (capped at 120).")
            r1, r2 = st.columns([2, 1])
            if r1.button("▶ Run Parametric Sweep", use_container_width=True):
                if not mods:
                    st.warning("Select at least one module.")
                else:
                    st.session_state.sweep_results = run_sweep(
                        tuple(mods), tuple(temps), tuple(irrs), n_sub)
            if r2.button("Clear", use_container_width=True):
                st.session_state.sweep_results = None

        st.plotly_chart(module_graphic(st.session_state.sub_irr),
                        use_container_width=True, config={"displaylogo": False})
    sub_irr = st.session_state.sub_irr

    # 4) ---- Advanced Diode & Physics (research / calibration) ----
    with sb.expander("4 · 🔬 Advanced Diode & Physics Parameters", expanded=False):
        st.caption("**Research / calibration controls.** These change the underlying "
                   "electrical model; use them to calibrate against measured data or "
                   "study model sensitivity. Auto-fills when you pick a module above.")
        c1, c2 = st.columns(2)
        c1.number_input("Isc — Short-circuit current [A]", 0.1, 40.0, step=0.01,
                        key="p_Isc", help=DS_HELP["Isc"])
        c2.number_input("Voc — Open-circuit voltage [V]", 1.0, 150.0, step=0.1,
                        key="p_Voc", help=DS_HELP["Voc"])
        c1.number_input("Imp — Current at max power [A]", 0.1, 40.0, step=0.01,
                        key="p_Imp", help=DS_HELP["Imp"])
        c2.number_input("Vmp — Voltage at max power [V]", 1.0, 150.0, step=0.1,
                        key="p_Vmp", help=DS_HELP["Vmp"])
        c1.number_input("Ns — Cells in series", 12, 200, step=1,
                        key="p_Ns", help=DS_HELP["Ns"])
        c2.number_input("n — Diode ideality factor", 0.8, 2.0, step=0.01,
                        key="p_n", help=DS_HELP["n"])
        c1.number_input("α_Isc — Isc temp. coeff. [A/°C]", -0.05, 0.05, step=0.0001,
                        format="%.4f", key="p_alpha_isc", help=DS_HELP["alpha_isc"])
        c2.number_input("β_Voc — Voc temp. coeff. [V/°C]", -0.5, 0.0, step=0.001,
                        format="%.3f", key="p_beta_voc", help=DS_HELP["beta_voc"])
        c1.number_input("Rs — Series resistance [Ω]", 0.0, 5.0, step=0.01,
                        key="p_Rs", help=DS_HELP["Rs"])
        c2.number_input("Rsh — Shunt resistance [Ω]", 10.0, 3000.0, step=5.0,
                        key="p_Rsh", help=DS_HELP["Rsh"])
        st.caption("ℹ️ Vmp and Imp are datasheet **reference** values. The simplified "
                   "single-diode model does not force its calculated MPP to reproduce "
                   "them exactly — tune Rs / Rsh / n to shape the knee.")
        st.button("↺ Reset module parameters", use_container_width=True, on_click=_reset_ds)

    sb.divider()
    sb.caption(f"🟢 Python solver: Ready · single-diode + bypass · "
               f"{ds['Ns']} cells · {n_sub} substrings")
    with sb.popover("↻ Reset simulation", use_container_width=True):
        st.warning("This clears the module, shading, frozen scenarios and sweep results.")
        st.button("Yes, reset everything", type="primary",
                  use_container_width=True, on_click=_reset_simulation)
    return ds, topo, base_G, T_c, sub_irr


# --------------------------------------------------------------------------- #
# Simulator page
# --------------------------------------------------------------------------- #
def page_simulator(ds, topo, base_G, T_c, sub_irr):
    n_sub = topo["bypass"]

    # ---- Getting Started (dismissible) ----
    if st.session_state.show_guide:
        with st.container(border=True):
            st.markdown("**🔆 Start a simulation**  —  1. Choose a module → "
                        "2. Set array configuration → 3. Choose irradiance/shading → "
                        "4. Read the P–V curve")
            st.caption("Explore how uneven irradiance affects PV current, voltage, "
                       "bypass-diode behavior, and available power.")
            st.button("Hide this guide", on_click=_hide_guide)

    st.markdown(f"**Current scenario:** {st.session_state.ds_name} · "
                f"{int(T_c)} °C · base {int(base_G)} W/m² · {st.session_state.scen_pick}")

    # ---- input validation (warn, don't silently fix) ----
    for w in validate_datasheet(ds, n_sub):
        st.warning("⚠️ Check datasheet values: " + w)
    if not topology_ok(ds["Ns"], n_sub):
        st.error(f"⚠️ Cell/zone configuration: {ds['Ns']} cells cannot be evenly divided "
                 f"into {n_sub} substring zones. Choose a zone count from "
                 f"{_divisors(ds['Ns'])}. The model was not run, to avoid silently "
                 f"discarding cells.")
        return

    cells_per_sub = ds["Ns"] // n_sub          # guaranteed divisible here
    ref = datasheet_to_ref(ds)
    res = module_iv(sub_irr, T_c, cells_per_sub, ref)
    res_unshaded = module_iv([max(sub_irr)] * n_sub, T_c, cells_per_sub, ref)
    m = compute_metrics(res, ds, topo)
    m_str, p_str = topo["modules_per_string"], topo["parallel_strings"]
    p_full = res_unshaded["gmpp"][2] * m_str * p_str / 1000.0
    p_cur = res["gmpp"][2] * m_str * p_str / 1000.0
    abs_loss = p_full - p_cur
    mismatch = (abs_loss / p_full * 100) if p_full > 0 else 0.0
    auto_name = (f"{st.session_state.ds_name.split()[0]} · {st.session_state.shade_label}"
                 f" · {int(T_c)}°C")
    current_cfg = simulation_config(ds, topo, base_G, T_c, sub_irr,
                                    st.session_state.get("scenario_name") or auto_name, res)

    # ---- unified top action bar ----
    t1, t2, t3, t4 = st.columns([2.8, 1.1, 1.0, 1.5])
    with t1:
        view = st.radio("View", ["Combined I-V/P-V", "Per-substring breakdown",
                                 "Cell irradiance map"], horizontal=True,
                        label_visibility="collapsed", key="view_mode")
    with t2:
        with st.popover("📌 Freeze", use_container_width=True):
            nm = st.text_input("Scenario name (optional)", key="scenario_name",
                               placeholder=auto_name)
            if st.button("Freeze this scenario", use_container_width=True):
                st.session_state.frozen.append(dict(
                    label=(nm.strip() or auto_name), V=res["V"].tolist(),
                    I=res["I"].tolist(), P=res["P"].tolist(),
                    gmpp=list(res["gmpp"]), config=current_cfg))
                st.session_state.frozen = st.session_state.frozen[-8:]
    if t3.button("🧹 Clear", use_container_width=True):
        st.session_state.frozen = []
    with t4:
        with st.popover("⬇ Export Data ⌄", use_container_width=True):
            render_export_popover(res, st.session_state.frozen, current_cfg)

    # ---- KPI strip ----
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Maximum Power", f"{p_cur:.3f} kW",
              help=f"Array Pmax at the global maximum-power point (full sun: {p_full:.3f} kW).")
    k2.metric("Shading Power Loss", f"{mismatch:.1f} %",
              delta=f"−{abs_loss:.3f} kW vs full sun", delta_color="inverse",
              help="Power lost to partial shading vs. the same array fully lit.")
    k3.metric("Fill Factor (FF)", f"{m['FF']*100:.1f} %",
              help="FF = Pmax / (Voc × Isc) — the 'squareness' of the curve. "
                   "This is NOT module conversion efficiency.")
    k4.metric("Local Power Peaks", f"{m['n_lmpp']}",
              help="Secondary local maxima in the P–V curve. Partial shading can create "
                   "multiple possible operating points.")

    # ---- Effect of shading ----
    st.markdown("#### ☀️ Effect of shading")
    e1, e2 = st.columns([1.25, 1.0])
    with e1:
        st.dataframe(pd.DataFrame({
            "Condition": ["Full sun", "Current scenario", "Power lost", "Relative loss"],
            "Maximum Power": [f"{p_full:.3f} kW", f"{p_cur:.3f} kW",
                              f"{abs_loss:.3f} kW", f"{mismatch:.1f} %"]}),
            hide_index=True, use_container_width=True)
        st.caption("Full-sun comparison uses the same module, temperature and array "
                   "configuration, with all substrings set to the maximum irradiance in "
                   "the current scenario.")
    with e2:
        st.plotly_chart(fullsun_bar(p_full, p_cur), use_container_width=True,
                        config={"displaylogo": False})

    # ---- graphs ----
    if view == "Combined I-V/P-V":
        st.plotly_chart(combined_figure(res, st.session_state.frozen),
                        use_container_width=True, config=PLOTLY_CFG_SVG)
    elif view == "Per-substring breakdown":
        st.plotly_chart(string_breakdown_figure(res, ds),
                        use_container_width=True, config=PLOTLY_CFG_SVG)
    else:
        grid = build_cell_grid(sub_irr, cells_per_sub)
        st.plotly_chart(heatmap_figure(grid, "Irradiance per cell", "Cividis", 1200),
                        use_container_width=True, config=PLOTLY_CFG_SVG)
    st.caption("I–V: electrical current available at each voltage.  P–V: calculated "
               "power available at each voltage.  ★ = GMPP; ◆ = local maxima.")
    st.markdown("★ **GMPP** — Global Maximum Power Point (highest calculated power)  ·  "
                "◆ **LMPP** — Local Maximum Power Point (secondary maximum)  ·  "
                "⋯ **Frozen** — a saved curve kept for comparison")

    # ---- What happened? ----
    st.markdown("#### 🔎 What happened?")
    st.info(what_happened(res, sub_irr))

    # ---- Substring & bypass behavior ----
    st.markdown("#### Substring & bypass behavior")
    brows = [{"Substring": f"S{i+1}", "Irradiance": f"{int(g)} W/m²",
              "Bypass state at GMPP": "Active at GMPP" if b else "Not active",
              "Interpretation": "Shaded zone bypassed" if b else "Normal contribution"}
             for i, (g, b) in enumerate(zip(sub_irr, res["bypassed"]))]
    st.dataframe(pd.DataFrame(brows), hide_index=True, use_container_width=True)
    with st.expander("What is a bypass diode?"):
        st.markdown("A bypass diode provides an alternate current path around a shaded "
                    "substring when that substring can no longer support the required "
                    "operating current. It protects the shaded cells from reverse-bias "
                    "stress, at the cost of that substring's voltage contribution. Bypass "
                    "state depends on the operating point — here it is reported **at the "
                    "GMPP**.")

    # ---- Detected peaks ----
    st.markdown("#### Detected Peaks")
    st.dataframe(pd.DataFrame(peaks_rows(res)), hide_index=True, use_container_width=True)

    # ---- Model scope ----
    with st.expander("⚠️ Model scope & limitations"):
        st.markdown("This simulator uses a **simplified single-diode PV model with "
                    "per-substring bypass behavior**, intended for interactive "
                    "exploration, comparison and research development — **not** a "
                    "substitute for measured I–V characterization or certified "
                    "PV-system design.")
        ms1, ms2 = st.columns(2)
        ms1.markdown("**Included**\n\n- irradiance effects\n- temperature effects\n"
                     "- series / shunt resistance\n- substring mismatch\n"
                     "- bypass-diode behavior\n- multiple P–V peaks")
        ms2.markdown("**Simplified / not modeled in full**\n\n- detailed avalanche / "
                     "breakdown physics\n- detailed thermal dynamics\n- measurement "
                     "noise\n- manufacturing variability\n- full MPPT controller dynamics")
        st.caption("Array power assumes identical modules with the same simulated "
                   "substring irradiance pattern and module parameters.")

    # ---- Parametric sweep overlay ----
    sweep = st.session_state.sweep_results
    if sweep:
        st.markdown("### 🧪 Parametric Sweep — Multi-Trace Overlay")
        st.success(f"{len(sweep)} simulations completed.")
        fdim = st.radio("Filter overlay", ["All", "By module", "By temperature",
                                           "By irradiance"], horizontal=True, key="sweep_filter")
        traces = sweep
        if fdim != "All":
            idx = {"By module": 0, "By temperature": 1, "By irradiance": 2}[fdim]
            vals = sorted({t["label"].split(" · ")[idx] for t in sweep})
            pickv = st.selectbox("Show", vals, key="sweep_filter_val")
            traces = [t for t in sweep if t["label"].split(" · ")[idx] == pickv]
        st.plotly_chart(sweep_figure(traces), use_container_width=True,
                        config=PLOTLY_CFG_SVG)
        st.caption("Export all sweep curves via **Export Data ▾ → Parametric Sweep Results**.")

# --------------------------------------------------------------------------- #
# Other pages
# --------------------------------------------------------------------------- #
def page_static_efficiency():
    st.subheader("📊 Static Efficiency · Planned")
    st.info("**Planned module (not yet available).** It will reuse the current "
            "module, datasheet and shading inputs, sweep operating conditions, and "
            "report a static-efficiency curve plus an η_static KPI. The Simulator, "
            "Gallery and Validation pages are fully functional in the meantime.")


def page_dynamic_efficiency():
    st.subheader("🌀 Dynamic Efficiency · Planned")
    st.info("**Planned module (not yet available).** It will add a time-domain "
            "irradiance trace (e.g. EN 50530) and report tracking efficiency and "
            "re-convergence over time. Use the Simulator page for steady-state "
            "partial-shading analysis today.")


def page_history():
    st.subheader("🗂️ Scenario History")
    frozen = st.session_state.frozen
    if not frozen:
        st.info("No frozen scenarios yet. On the Simulator, open **📌 Freeze**, "
                "optionally name the scenario, and save it to compare here.")
        return
    rows = []
    for f in frozen:
        c = f.get("config", {})
        tp = c.get("topology", {})
        rows.append({"Name": f["label"], "Module": c.get("module", "—"),
                     "T (°C)": c.get("temperature_C", "—"),
                     "Base G (W/m²)": c.get("base_irradiance_Wm2", "—"),
                     "Zones": tp.get("substring_zones", "—"),
                     "Modules/str": tp.get("modules_per_string", "—"),
                     "Pmax (W)": round(f["gmpp"][2], 1)})
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
    fig = go.Figure()
    for k, f in enumerate(frozen):
        fig.add_trace(go.Scatter(x=f["V"], y=f["P"], mode="lines", name=f["label"],
                                 line=dict(color=SWEEP_COLORS[k % len(SWEEP_COLORS)], width=2)))
    fig.update_layout(height=430, title="Frozen scenarios — P–V overlay",
                      xaxis_title="Voltage [V]", yaxis_title="Power [W]")
    _style(fig)
    st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CFG_SVG)
    with st.expander("Full configuration of each frozen scenario"):
        for f in frozen:
            st.markdown(f"**{f['label']}**")
            st.json(f.get("config", {}), expanded=False)
    if st.button("🧹 Clear all frozen scenarios"):
        st.session_state.frozen = []
        st.rerun()

def _coeff_hist(slim):
    fig = go.Figure()
    for g in ["uniform", "whole_substring", "sub_substring"]:
        c = slim[slim.geometry == g]["coeff_Vmp_Voc"]
        fig.add_trace(go.Histogram(x=c, name=GEOM_LABEL[g], opacity=0.6,
                                   marker_color=GEOM_COLORS[g], nbinsx=45))
    fig.add_vline(x=0.80, line=dict(color=TH["muted"], dash="dash"))
    fig.update_layout(barmode="overlay", height=360,
                      xaxis_title="V_gmpp / V_oc", yaxis_title="scenarios",
                      legend=dict(x=0.01, y=0.99))
    return _style(fig)


def _gallery_dataset():
    dstate = st.session_state.dataset
    if not dstate:
        st.info("No generated dataset yet. Create one in **🧪 Dataset Generator**.")
        return
    df = dstate["df"]; curves = dstate["curves"]
    st.caption(f"{len(df):,} scenarios in the current dataset.")
    f1, f2, f3 = st.columns(3)
    objs = f1.multiselect("Shading object", sorted(df["shading_object"].unique()))
    peakmin = f2.selectbox("Min local peaks", [1, 2, 3, 4], index=0)
    byp = f3.selectbox("Bypass", ["Any", "Active", "None active"])
    hi = float(max(df["power_loss_percent"].max(), 1.0))
    lossr = st.slider("Power-loss range [%]", 0.0, hi, (0.0, hi))
    fdf = df.copy()
    if objs:
        fdf = fdf[fdf["shading_object"].isin(objs)]
    fdf = fdf[fdf["local_peak_count"] >= peakmin]
    fdf = fdf[(fdf["power_loss_percent"] >= lossr[0]) & (fdf["power_loss_percent"] <= lossr[1])]
    active_any = fdf.filter(like="bypass_state_").eq("Active").any(axis=1)
    if byp == "Active":
        fdf = fdf[active_any]
    elif byp == "None active":
        fdf = fdf[~active_any]
    st.caption(f"{len(fdf):,} of {len(df):,} match the filters (showing up to 200).")
    st.dataframe(fdf.head(200), hide_index=True, use_container_width=True)
    if len(fdf):
        pick = st.selectbox("Inspect scenario", fdf["scenario_id"].tolist())
        ids = list(curves["scenario_id"])
        if pick in ids:
            k = ids.index(pick)
            row = df[df["scenario_id"] == pick].iloc[0]
            fig = make_subplots(rows=1, cols=2, subplot_titles=("I–V", "P–V"),
                                horizontal_spacing=0.09)
            fig.add_trace(go.Scatter(x=curves["V"][k], y=curves["I"][k], mode="lines",
                                     line=dict(color=COL_IV, width=2), showlegend=False), 1, 1)
            fig.add_trace(go.Scatter(x=curves["V"][k], y=curves["P"][k], mode="lines",
                                     line=dict(color=COL_PV, width=2), showlegend=False), 1, 2)
            fig.add_trace(go.Scatter(x=[row["gmpp_voltage_V"]], y=[row["gmpp_power_W"]],
                                     mode="markers", showlegend=False,
                                     marker=dict(color=COL_GMPP, size=13, symbol="star")), 1, 2)
            fig.update_layout(height=360, margin=dict(l=50, r=20, t=40, b=45))
            fig.update_xaxes(title_text="Voltage [V]")
            _style(fig)
            st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CFG_SVG)
            st.markdown(f"**{pick}** · {row['shading_object']} · loss "
                        f"{row['power_loss_percent']}% · {row['local_peak_count']} peak(s) · "
                        f"GMPP {row['gmpp_power_W']} W")


def _gallery_frozen():
    frozen = st.session_state.frozen
    if not frozen:
        st.info("No frozen scenarios yet — save some from the Simulator (📌 Freeze).")
        return
    pick = st.selectbox("Frozen scenario", [f["label"] for f in frozen])
    f = next(x for x in frozen if x["label"] == pick)
    fig = make_subplots(rows=1, cols=2, subplot_titles=("I–V", "P–V"), horizontal_spacing=0.09)
    fig.add_trace(go.Scatter(x=f["V"], y=f["I"], mode="lines",
                             line=dict(color=COL_IV, width=2), showlegend=False), 1, 1)
    fig.add_trace(go.Scatter(x=f["V"], y=f["P"], mode="lines",
                             line=dict(color=COL_PV, width=2), showlegend=False), 1, 2)
    fig.add_trace(go.Scatter(x=[f["gmpp"][0]], y=[f["gmpp"][2]], mode="markers", showlegend=False,
                             marker=dict(color=COL_GMPP, size=13, symbol="star")), 1, 2)
    fig.update_layout(height=360, margin=dict(l=50, r=20, t=40, b=45))
    _style(fig)
    st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CFG_SVG)
    with st.expander("Configuration"):
        st.json(f.get("config", {}), expanded=False)


def page_gallery():
    st.subheader("🖼️ Simulation Gallery")
    src = st.radio("Source", ["Generated dataset", "Frozen scenarios", "Phase-1 research set"],
                   horizontal=True, key="gallery_src")
    if src == "Generated dataset":
        _gallery_dataset(); return
    if src == "Frozen scenarios":
        _gallery_frozen(); return
    st.markdown("#### Phase-1 research set")
    bank = load_curve_bank()
    if bank is None:
        st.info("Place **assets/phase1_curves.json** next to app.py to enable this page.")
        return
    curves = bank["curves"]
    geos = st.multiselect("Geometries", list(GEOM_LABEL), default=list(GEOM_LABEL),
                          format_func=lambda g: GEOM_LABEL[g])
    pool = [c for c in curves if c["geometry"] in geos]
    if not pool:
        st.warning("Select at least one geometry."); return
    n_show = st.slider("Curves to show", 6, len(pool), min(24, len(pool)), 6)
    sel = sorted(pool, key=lambda d: (d["geometry"], d["n_peaks"]))[:n_show]
    ncol = 6
    nrow = int(np.ceil(len(sel) / ncol))
    titles = [f"#{c['id']} {GEOM_LABEL[c['geometry']][:5]} {c['n_peaks']}pk" for c in sel]
    fig = make_subplots(rows=nrow, cols=ncol, subplot_titles=titles,
                        horizontal_spacing=0.028, vertical_spacing=0.1)
    for k, c in enumerate(sel):
        r, col = k // ncol + 1, k % ncol + 1
        fig.add_trace(go.Scatter(x=c["V"], y=c["P"], mode="lines",
                                 line=dict(color=GEOM_COLORS[c["geometry"]], width=1.7),
                                 showlegend=False), row=r, col=col)
        fig.add_trace(go.Scatter(x=[c["gmpp_V"]], y=[c["gmpp_P"]], mode="markers",
                                 marker=dict(color=COL_GMPP, size=6, symbol="star"),
                                 showlegend=False), row=r, col=col)
    fig.update_layout(height=200 * nrow, plot_bgcolor="white", paper_bgcolor="white",
                      font=dict(family=PLOT_FONT, size=9), margin=dict(l=25, r=10, t=45, b=20))
    fig.update_xaxes(showgrid=True, gridcolor=GRID, tickfont=dict(size=7))
    fig.update_yaxes(showgrid=True, gridcolor=GRID, tickfont=dict(size=7))
    for ann in fig.layout.annotations:
        ann.font = dict(size=8, family=PLOT_FONT, color=TH["text"])
    _style(fig)
    st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CFG_SVG)
    slim = load_slim_dataset()
    if slim is not None:
        st.plotly_chart(_coeff_hist(slim), use_container_width=True, config=PLOTLY_CFG_SVG)


def page_validation():
    st.subheader("✅ Validation & Literature")
    with st.expander("ℹ️ How to read validation", expanded=False):
        st.markdown(
            "Validation compares the simulator against independent measurements, "
            "published models, or internal self-consistency checks. A **PASS** means "
            "the stated criterion was satisfied for *that gate only* — it does not "
            "imply universal accuracy. Gate **Type**:\n"
            "- **Independent** — checked against measurement or an external database.\n"
            "- **Self-consistency** — internal (a coherent model, not external proof).\n"
            "- **Qualitative** — matches the *shape* reported in the literature.\n"
            "- **Deferred** — planned, not yet performed.")
    t1, t2, t3 = st.tabs(["Simulator gates", "Measured layers", "Literature"])
    with t1:
        st.dataframe(pd.DataFrame(VALIDATION_GATES), hide_index=True, use_container_width=True)
        st.markdown("- **Leg 2 (Sandia):** single-diode vs measurement, 2.1% @STC / "
                    "2.5% @55 °C over 108 c-Si twins.\n"
                    "- **Leg 3:** quantitative multi-peak magnitude deferred to Phase 8 "
                    "(no public dataset).")
    with t2:
        any_found = False
        for label, fname in MEASURED_LAYERS.items():
            for base in (Path(__file__).parent / "results", ASSETS):
                p = base / fname
                if p.exists():
                    any_found = True
                    st.markdown(f"**{label}**  ·  `{p.name}`")
                    st.dataframe(pd.read_csv(p), hide_index=True, use_container_width=True)
                    break
        if not any_found:
            st.info("Run `run_validation.py` and keep `results/v_*.csv` next to app.py "
                    "(or copy them into `assets/`) to display the measured layers here.")
    with t3:
        st.markdown(
            "- **Bu et al. (2025)**, Energy Reports 14, 2732–2754 — ANN GMPP prediction; "
            "hybrid-dataset method borrowed, distinguished from tracking.\n"
            "- **Başoğlu (2019)**, IEEE TIA — structural validation cases.\n"
            "- **Sandia Array Performance Model** — off-STC measurement reference.\n"
            "- **pvlib** — single-diode / CEC model, pinned 0.15.2.\n"
            "- NN-seed prior art: Messalti (2017), Li (2013), Khanaki (2016).")


# --------------------------------------------------------------------------- #
# Main — top navigation
# --------------------------------------------------------------------------- #
def page_dataset_generator(ds, topo, base_G, T_c):
    st.subheader("🧪 Scenario Dataset Generator")
    st.caption("Run the real PV model over many randomized static-shading scenarios "
               "and download a reproducible numerical dataset (CSV + NPZ + config).")
    n_sub = topo["bypass"]
    if not topology_ok(ds["Ns"], n_sub):
        st.error(f"{ds['Ns']} cells cannot be divided into {n_sub} substring zones — "
                 "fix the array topology first.")
        return

    c1, c2 = st.columns(2)
    with c1:
        nchoice = st.selectbox("Number of scenarios",
                               ["10", "100", "500", "1000", "2000", "5000", "Custom"], index=1)
        N = int(st.number_input("Custom count", 1, 20000, 200, 10)) if nchoice == "Custom"             else int(nchoice)
        seed = int(st.number_input("Random seed", 0, 1_000_000_000, 42, 1))
    with c2:
        objs = st.multiselect("Shading objects to sample",
                              [o for o in SHADING_OBJECTS if o != "Custom"],
                              default=["Cloud", "Tree", "Pole", "Building",
                                       "Soil / Ground Shadow", "Soiling"])
    st.markdown("**Randomize**")
    rr = st.columns(4)
    rand_sev = rr[0].checkbox("Severity", True)
    rand_loc = rr[1].checkbox("Location", True)
    rand_base = rr[2].checkbox("Base irradiance", True)
    rand_temp = rr[3].checkbox("Temperature", True)
    gg = st.columns(2)
    G_min = int(gg[0].number_input("Base G min [W/m²]", 100, 1200, 600, 25))
    G_max = int(gg[1].number_input("Base G max [W/m²]", 100, 1200, 1000, 25))
    tt = st.columns(2)
    T_min = int(tt[0].number_input("Temp min [°C]", -10, 70, 15, 1))
    T_max = int(tt[1].number_input("Temp max [°C]", -10, 70, 55, 1))
    if N > 5000:
        st.warning(f"{N:,} scenarios is large — generation may take several minutes.")
    if not objs:
        st.info("Select at least one shading object to sample.")

    if st.button("▶ Generate dataset", type="primary", disabled=not objs):
        cfg = dict(n=N, seed=seed, objects=objs, rand_severity=rand_sev,
                   rand_location=rand_loc, rand_base=rand_base, rand_temp=rand_temp,
                   severity="Moderate", location="Center", base_G=int(base_G), T=int(T_c),
                   G_min=G_min, G_max=G_max, T_min=T_min, T_max=T_max, n_sub=n_sub,
                   module=st.session_state.ds_name,
                   topology=dict(modules_per_string=topo["modules_per_string"],
                                 parallel_strings=topo["parallel_strings"]),
                   version="1.0", L=256)
        bar = st.progress(0.0)
        status = st.empty()
        t0 = time.time()

        def prog(done, total):
            bar.progress(done / total)
            status.write(f"Generating scenarios… {done:,} / {total:,}  ·  "
                         f"{time.time() - t0:.0f}s")

        df, curves, stats = generate_dataset(ds, n_sub, cfg, progress=prog)
        bar.progress(1.0)
        status.write(f"✓ {stats['successful']:,} scenarios generated in "
                     f"{time.time() - t0:.0f}s")
        st.session_state.dataset = dict(df=df, curves=curves, cfg=cfg, stats=stats,
                                        ds={k: ds[k] for k in DS_FIELDS})

    dstate = st.session_state.dataset
    if dstate:
        stt = dstate["stats"]
        st.success(f"Dataset ready: {stt['successful']:,} scenarios  ·  failed "
                   f"{stt['failed']}  ·  multi-peak {stt['multi_peak']}  ·  "
                   f"bypass-active {stt['bypass_active']}.")
        mm = st.columns(4)
        mm[0].metric("GMPP min", f"{stt['gmpp_min_W']} W")
        mm[1].metric("GMPP max", f"{stt['gmpp_max_W']} W")
        mm[2].metric("Loss min", f"{stt['loss_min_pct']} %")
        mm[3].metric("Loss max", f"{stt['loss_max_pct']} %")
        st.dataframe(dstate["df"].head(50), hide_index=True, use_container_width=True)
        st.download_button("⬇️ Download dataset (.zip)",
                           build_dataset_zip(dstate["df"], dstate["curves"], dstate["cfg"],
                                             stt, ds),
                           "pv_partial_shading_dataset.zip", "application/zip")
        st.caption("Browse individual scenarios under **🖼️ Gallery → Generated dataset**.")


def main():
    st.set_page_config(page_title="PV Partial-Shading Simulator", layout="wide",
                       initial_sidebar_state="expanded")
    init_state()
    if "theme" not in st.session_state:
        st.session_state.theme = "Dark"
    global TH
    top = st.columns([6, 1.7])
    top[0].markdown("#### 🔆 PV Partial-Shading Simulator")
    with top[1]:
        choice = st.radio("Theme", ["🌞 Light", "🌙 Dark"],
                          index=0 if st.session_state.theme == "Light" else 1,
                          horizontal=True, label_visibility="collapsed")
        st.session_state.theme = "Light" if choice.startswith("🌞") else "Dark"
    TH = THEMES[st.session_state.theme]
    apply_theme_css(TH)

    nav = st.radio("nav", ["🔆 Partial-Shading Simulator", "📊 Static Efficiency · Planned",
                           "🌀 Dynamic Efficiency · Planned", "🗂️ Scenario History", "🧪 Dataset Generator",
                           "🖼️ Gallery", "✅ Validation"],
                   horizontal=True, label_visibility="collapsed")
    st.divider()
    ds, topo, base_G, T_c, sub_irr = render_sidebar()
    if nav.startswith("🔆"):
        page_simulator(ds, topo, base_G, T_c, sub_irr)
    elif nav.startswith("📊"):
        page_static_efficiency()
    elif nav.startswith("🌀"):
        page_dynamic_efficiency()
    elif nav.startswith("🗂️"):
        page_history()
    elif nav.startswith("🧪"):
        page_dataset_generator(ds, topo, base_G, T_c)
    elif nav.startswith("🖼️"):
        page_gallery()
    else:
        page_validation()


if __name__ == "__main__":
    main()