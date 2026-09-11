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
import io, json
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
REALWORLD_PRESETS = ["Full Sun", "Passing Cloud", "Overhead Pole Shadow",
                     "Severe Soiling", "Custom Entry"]
REALWORLD_HELP = {
    "Full Sun": "Uniform full irradiance across all substrings — a single P–V peak.",
    "Passing Cloud": "A soft irradiance gradient as a cloud drifts over the module.",
    "Overhead Pole Shadow": "A hard narrow shadow fully shading one bypass zone.",
    "Severe Soiling": "Heavy, uneven dirt/soiling reducing all substrings unevenly.",
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
        zmin=100, zmax=1000, showscale=True,
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
    rows = [dict(peak="🎯 GMPP", V=round(res["gmpp"][0], 2), I=round(res["gmpp"][1], 2),
                 P_W=round(Pm, 1), dP_vs_GMPP="—")]
    for v, i, pp in res.get("lmpps", []):
        rows.append(dict(peak="◆ LMPP", V=round(v, 2), I=round(i, 2), P_W=round(pp, 1),
                         dP_vs_GMPP=f"−{(Pm-pp)/Pm*100:.1f}%"))
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


def build_export_zip(scenarios, types):
    import zipfile
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
        if notes:
            z.writestr("README.txt", "\n".join(sorted(set(notes))))
    return buf.getvalue()


def render_export_popover(res, frozen):
    scope = st.radio("Export scope", ["Current Scenario Only", "Active Comparison Traces",
                                      "All Session Scenarios", "Custom Selection"])
    cur = [("current", res)]
    froz = [(f["label"], res_from_frozen(f)) for f in frozen]
    if scope == "Current Scenario Only":
        chosen = cur
    elif scope in ("Active Comparison Traces", "All Session Scenarios"):
        chosen = cur + froz
    else:
        labels = ["current"] + [f["label"] for f in frozen]
        allmap = {"current": res}
        for f in frozen:
            allmap[f["label"]] = res_from_frozen(f)
        picks = st.multiselect("Scenarios", labels, default=["current"])
        chosen = [(nm, allmap[nm]) for nm in picks if nm in allmap]
    st.markdown("**Data types**")
    types = dict(csv=st.checkbox("Curve Raw Data (.csv)", True),
                 peaks=st.checkbox("Peak Metrics (.csv)", True),
                 mat=st.checkbox("MATLAB Struct (.mat)", False),
                 svg=st.checkbox("Chart Vector (.svg)", False))
    if not chosen or not any(types.values()):
        st.caption("Pick at least one scenario and one data type.")
    else:
        st.download_button("⬇️ Prepare & download (.zip)",
                           build_export_zip(chosen, types), "pv_export.zip",
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
    {"Gate": "S1 · premise", "Independent source": "CEC database, directly",
     "Result": "20,946 c-Si · mean 0.811 · 41% within ±0.01 of 0.80"},
    {"Gate": "S2 · STC point", "Independent source": "Manufacturer datasheets (3 s.f.)",
     "Result": "PASS — worst error 0.000%"},
    {"Gate": "S3 · composition", "Independent source": "Direct single-diode (self-consistency)",
     "Result": "PASS — 3 peaks present"},
    {"Gate": "S4 · off-STC", "Independent source": "Sandia measurement model, 108 twins",
     "Result": "PASS — P_mp 2.1% @STC, 2.5% @55 °C"},
    {"Gate": "S4 · structure", "Independent source": "Başoğlu (2019), IEEE TIA",
     "Result": "PASS (qualitative)"},
    {"Gate": "S4 · magnitude", "Independent source": "Measured shaded I–V (partner)",
     "Result": "Deferred → Phase 8"},
    {"Gate": "S5 · array", "Independent source": "Module model (self-consistency)", "Result": "PASS"},
    {"Gate": "Gate A · dataset", "Independent source": "2,000-scenario characterisation",
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
    if "ds" not in st.session_state:
        st.session_state.ds = dict(MODULE_PRESETS[DEFAULT_PRESET])
        st.session_state.ds_name = DEFAULT_PRESET
    if "frozen" not in st.session_state:
        st.session_state.frozen = []
    if "sub_irr" not in st.session_state:
        st.session_state.sub_irr = None


# --------------------------------------------------------------------------- #
# Sidebar (inputs, datasheet, topology, solver status)
# --------------------------------------------------------------------------- #
def render_sidebar():
    sb = st.sidebar
    sb.markdown("### ☀️ PV Simulator")
    sb.caption("Continuous top-to-bottom input workflow")

    # 1) ---- Module & Datasheet (dropdown + compact upload icon) ----
    sb.markdown("#### 1 · 📇 Module & Datasheet")
    names = list(MODULE_PRESETS) + ["Custom / uploaded"]
    dcol, ucol = sb.columns([3, 1])
    with dcol:
        pick = st.selectbox("CEC datasheet", names,
                            index=names.index(st.session_state.ds_name)
                            if st.session_state.ds_name in names else 0,
                            label_visibility="collapsed")
    with ucol:
        with st.popover("⬆", use_container_width=True, help="Upload CSV/JSON datasheet"):
            up = st.file_uploader("Datasheet file", type=["csv", "json"],
                                  label_visibility="collapsed")
            if up is not None:
                try:
                    d = json.load(up) if up.name.endswith("json") else \
                        pd.read_csv(up).iloc[0].to_dict()
                    st.session_state.ds.update({k: float(v) for k, v in d.items()
                                                if k in st.session_state.ds and k != "tech"})
                    st.session_state.ds_name = "Custom / uploaded"; st.success("Loaded.")
                except Exception as e:
                    st.error(f"Parse error: {e}")
    if pick != "Custom / uploaded" and pick != st.session_state.ds_name:
        st.session_state.ds = dict(MODULE_PRESETS[pick]); st.session_state.ds_name = pick
    ds = st.session_state.ds

    # 2) ---- Array Topology ----
    with sb.expander("2 · 🔲 Array Topology", expanded=True):
        n_sub = int(st.number_input("Bypass diodes / module", 1, 6, 3, 1))
        m_str = int(st.number_input("Modules per string", 1, 40, 1, 1))
        p_str = int(st.number_input("Parallel strings", 1, 40, 1, 1))
    topo = dict(bypass=n_sub, modules_per_string=m_str, parallel_strings=p_str)

    # 3) ---- Array Shading & Scenarios ----
    with sb.expander("3 · 🌓 Array Shading & Scenarios", expanded=True):
        scen = st.selectbox("Real-world scenario", REALWORLD_PRESETS, index=0,
                            help="One click applies a realistic non-uniform pattern.")
        if scen in REALWORLD_HELP:
            st.caption(REALWORLD_HELP[scen])

        # Base / standard irradiance quick-adjust (scales all substrings)
        qopts = ["1000", "800", "650", "500", "300", "Custom…"]
        bpick = st.selectbox("Base irradiance [W/m²]", qopts, index=0,
                             help="Scales baseline sunlight across all substrings.")
        base_G = st.number_input("Custom base [W/m²]", 100, 1200, 800, 25) \
            if bpick == "Custom…" else int(bpick)
        T_c = st.number_input("Cell temperature [°C]", -10, 70, 25, 1)

        # keep session vector sized to n_sub; presets set it, Custom edits it
        if (st.session_state.sub_irr is None) or (len(st.session_state.sub_irr) != n_sub):
            st.session_state.sub_irr = [float(base_G)] * n_sub
        if scen != "Custom Entry":
            st.session_state.sub_irr = realworld_sub(scen, base_G, n_sub)

        st.markdown("**Substring irradiance [W/m²]**")
        custom = (scen == "Custom Entry")
        new = []
        for i in range(n_sub):
            new.append(st.number_input(f"S{i+1}", 0.0, 1200.0,
                                       float(st.session_state.sub_irr[i]), 25.0,
                                       disabled=not custom, key=f"sub_step_{i}_{n_sub}"))
        if custom:
            st.session_state.sub_irr = [float(x) for x in new]
        else:
            st.caption("Switch to **Custom Entry** to fine-tune S₁…Sₙ with the steppers.")

        # Interactive 2D substring heatmap
        st.plotly_chart(module_graphic(st.session_state.sub_irr),
                        use_container_width=True, config={"displaylogo": False})
    sub_irr = st.session_state.sub_irr

    # 4) ---- Advanced Diode & Physics Parameters (bottom, collapsed) ----
    with sb.expander("4 · 🔬 Advanced Diode & Physics Parameters", expanded=False):
        st.caption("Editable for researchers; auto-filled from the datasheet.")
        c1, c2 = st.columns(2)
        ds["Isc"] = c1.number_input("Isc [A]", 0.1, 30.0, float(ds["Isc"]), 0.01)
        ds["Voc"] = c2.number_input("Voc [V]", 1.0, 120.0, float(ds["Voc"]), 0.1)
        ds["Imp"] = c1.number_input("Imp [A]", 0.1, 30.0, float(ds["Imp"]), 0.01)
        ds["Vmp"] = c2.number_input("Vmp [V]", 1.0, 120.0, float(ds["Vmp"]), 0.1)
        ds["Ns"] = int(c1.number_input("Cells Ns", 12, 200, int(ds["Ns"]), 1))
        ds["n"] = c2.number_input("Ideality n", 0.8, 2.0, float(ds["n"]), 0.01)
        ds["alpha_isc"] = c1.number_input("α_Isc [A/°C]", -0.05, 0.05, float(ds["alpha_isc"]), 0.0001, format="%.4f")
        ds["beta_voc"] = c2.number_input("β_Voc [V/°C]", -0.5, 0.0, float(ds["beta_voc"]), 0.001, format="%.3f")
        ds["Rs"] = c1.number_input("Rs [Ω]", 0.0, 5.0, float(ds["Rs"]), 0.01)
        ds["Rsh"] = c2.number_input("Rsh [Ω]", 10.0, 2000.0, float(ds["Rsh"]), 5.0)
        if st.button("↺ Reset to standard", use_container_width=True):
            st.session_state.ds = dict(MODULE_PRESETS[DEFAULT_PRESET])
            st.session_state.ds_name = DEFAULT_PRESET; st.rerun()

    sb.divider()
    sb.caption(f"🟢 Python solver: Ready · single-diode + bypass · "
               f"{ds['Ns']} cells · {n_sub} substrings")
    return ds, topo, base_G, T_c, sub_irr


# --------------------------------------------------------------------------- #
# Simulator page
# --------------------------------------------------------------------------- #
def page_simulator(ds, topo, base_G, T_c, sub_irr):
    n_sub = topo["bypass"]
    cells_per_sub = max(1, ds["Ns"] // n_sub)
    ref = datasheet_to_ref(ds)

    res = module_iv(sub_irr, T_c, cells_per_sub, ref)
    res_unshaded = module_iv([max(sub_irr)] * n_sub, T_c, cells_per_sub, ref)
    m = compute_metrics(res, ds, topo)
    mismatch = 0.0
    if res_unshaded["gmpp"][2] > 0:
        mismatch = (res_unshaded["gmpp"][2] - res["gmpp"][2]) / res_unshaded["gmpp"][2] * 100

    # ---- unified top action bar: view pills + Freeze / Clear / Export ----
    t1, t2, t3, t4 = st.columns([2.8, 1.0, 1.0, 1.5])
    with t1:
        view = st.radio("View", ["Combined I-V/P-V", "String breakdown",
                                 "Bypass diode states"], horizontal=True,
                        label_visibility="collapsed")
    freeze = t2.button("📌 Freeze", use_container_width=True)
    clr = t3.button("🧹 Clear", use_container_width=True)
    with t4:
        with st.popover("⬇ Export Data ⌄", use_container_width=True):
            render_export_popover(res, st.session_state.frozen)

    if freeze:
        lbl = f"{st.session_state.ds_name.split()[0]} · {int(min(sub_irr))}–{int(max(sub_irr))}"
        st.session_state.frozen.append(dict(label=lbl, V=res["V"].tolist(),
                                            I=res["I"].tolist(), P=res["P"].tolist(),
                                            gmpp=list(res["gmpp"])))
        st.session_state.frozen = st.session_state.frozen[-5:]
    if clr:
        st.session_state.frozen = []

    # ---- KPI strip ----
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Global Max Power  P_GMPP", f"{m['P_array_kW']:.3f} kW",
              help="Array-aggregated over topology")
    k2.metric("Mismatch loss", f"{mismatch:.1f} %", help="vs unshaded (brightest substring)")
    k3.metric("Array Fill Factor", f"{m['FF']*100:.1f} %")
    k4.metric("Local peaks (LMPP)", f"{m['n_lmpp']}")

    # ---- clean canvas: graphs only (hover crosshairs, no slider) ----
    if view == "Combined I-V/P-V":
        st.plotly_chart(combined_figure(res, st.session_state.frozen),
                        use_container_width=True, config=PLOTLY_CFG_SVG)
        st.caption("Hover either curve — the vertical crosshair tracks the operating "
                   "voltage on both plots.")
    elif view == "String breakdown":
        st.plotly_chart(string_breakdown_figure(res, ds),
                        use_container_width=True, config=PLOTLY_CFG_SVG)
    else:
        grid = build_cell_grid(sub_irr, cells_per_sub)
        st.plotly_chart(heatmap_figure(grid, "Irradiance per cell", "Cividis", 1000),
                        use_container_width=True, config=PLOTLY_CFG_SVG)
        states = pd.DataFrame({"substring": [f"S{i+1}" for i in range(n_sub)],
                               "irradiance_Wm2": [round(g, 0) for g in sub_irr],
                               "bypass_active": ["● yes" if b else "○ no"
                                                 for b in res["bypassed"]]})
        st.dataframe(states, hide_index=True, use_container_width=True)

    # ---- peak table (GMPP vs LMPP) ----
    st.markdown("**Detected peaks**")
    st.dataframe(pd.DataFrame(peaks_rows(res)), hide_index=True, use_container_width=True)

    if st.session_state.frozen:
        st.caption("Frozen traces: " + ", ".join(f["label"] for f in st.session_state.frozen)
                   + " — shown dotted on the curves. Export them via **Export Data ▾**.")

# --------------------------------------------------------------------------- #
# Other pages
# --------------------------------------------------------------------------- #
def page_static_efficiency():
    st.subheader("📊 Static Efficiency")
    st.info("**Coming soon.** This module will reuse the same module, datasheet "
            "and shading inputs from the sidebar, sweep operating conditions, and "
            "report a static-efficiency curve plus an η_static KPI. Reserved here "
            "so adding it changes no navigation.")


def page_dynamic_efficiency():
    st.subheader("🌀 Dynamic Efficiency")
    st.info("**Coming soon.** This module will add a time-domain irradiance trace "
            "(e.g. EN 50530) as its only new input, and report tracking efficiency "
            "and re-convergence over time on the same workspace canvas.")


def page_history():
    st.subheader("🗂️ Scenario History")
    frozen = st.session_state.get("frozen", [])
    if not frozen:
        st.info("No frozen traces yet. On the Simulator, set up a scenario and "
                "press **📌 Freeze** to pin it here for comparison.")
        return
    df = pd.DataFrame([{"label": f["label"], "V_gmpp": round(f["gmpp"][0], 2),
                        "I_gmpp": round(f["gmpp"][1], 2), "P_gmpp_W": round(f["gmpp"][2], 1)}
                       for f in frozen])
    st.dataframe(df, hide_index=True, use_container_width=True)
    fig = go.Figure()
    for k, f in enumerate(frozen):
        fig.add_trace(go.Scatter(x=f["V"], y=f["P"], mode="lines",
                                 name=f["label"],
                                 line=dict(color=TRACE_COLORS[k % len(TRACE_COLORS)], width=2)))
    fig.update_layout(height=420, plot_bgcolor="white", paper_bgcolor="white",
                      font=dict(family=PLOT_FONT), title="Frozen P–V traces",
                      xaxis_title="Voltage [V]", yaxis_title="Power [W]")
    _style(fig)
    st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CFG_SVG)
    if st.button("🧹 Clear all frozen traces"):
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


def page_gallery():
    st.subheader("🗂️ Phase-1 Scenario Gallery")
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

    nav = st.radio("nav", ["🔆 Partial-Shading Simulator", "📊 Static Efficiency",
                           "🌀 Dynamic Efficiency", "🗂️ Scenario History",
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
    elif nav.startswith("🖼️"):
        page_gallery()
    else:
        page_validation()


if __name__ == "__main__":
    main()