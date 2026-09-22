"""
gmppt_app.py — new entry point for the GMPPT Bench dashboard.

Wraps your existing app.py (kept unchanged, imported as `sim`) in the new
four-section navigation and the gmppt_ui design system.

    Run:  streamlit run gmppt_app.py
    Needs: streamlit >= 1.40, plotly, numpy, pandas — plus app.py and gmppt_ui.py
           in the same folder.

Sections (see DESIGN.md §2):
    Home
    Explore     The panels · Inside a panel · Whole system
    Simulator   Set up a panel · Saved scenarios · Make a dataset   <- your existing app
    Testing     Watch one run · Compare methods · Dynamic irradiance
    The data    The dataset · Where it comes from

Pages marked "coming" are shown as labelled placeholders on purpose — the
design rule is that planned features are visible, never hidden and never faked.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import app as sim          # your existing simulator — physics, presets, pages
import gmppt_ui as ui
from gmppt import config as _gcfg, device as _eng, scenarios as _scen

st.set_page_config(page_title="GMPPT Bench", layout="wide", initial_sidebar_state="collapsed")
sim.init_state()
st.session_state.setdefault("gm_theme", "Light")
st.session_state.setdefault("gm_lang", "EN")

# Theme: the existing figures read sim.TH, so keep it in step with the new tokens.
ui.setup(st.session_state.gm_theme)
sim.TH = sim.THEMES["Dark" if st.session_state.gm_theme == "Dark" else "Light"]
sim.GRID = sim.TH["grid"]

P: dict[str, st.Page] = {}   # filled below; page functions look pages up here at run time


def go_to(key: str) -> None:
    """Replaces the old `st.session_state.section = ...; st.rerun()` pattern."""
    st.switch_page(P[key])


# --------------------------------------------------------------------------- #
# Home  (landing — matches the design mockup exactly)
# --------------------------------------------------------------------------- #
# Illustration and card icons extracted verbatim from the design mockup
# (minified to a single line so Streamlit Markdown renders them as HTML, not code).
_HERO_SVG = r'''<svg viewBox="0 0 620 360" style="width:100%;height:auto;display:block;" role="img" aria-label="The same panel side by side: unshaded with one smooth power peak, and shaded with three peaks of which only one is the true maximum"><rect x="6" y="6" width="298" height="348" rx="10" fill="#F7F6F1"></rect><rect x="316" y="6" width="298" height="348" rx="10" fill="#FBF4EC"></rect><text x="22" y="30" font-family="IBM Plex Mono, monospace" font-size="12" fill="#16616B">UNSHADED</text><text x="332" y="30" font-family="IBM Plex Mono, monospace" font-size="12" fill="#9A5314">SHADOW ACROSS THE STRIPS</text><rect x="70" y="44" width="170" height="84" fill="#DCE8E8" stroke="#A8C0C1"></rect><line x1="127" y1="44" x2="127" y2="128" stroke="#A8C0C1"></line><line x1="184" y1="44" x2="184" y2="128" stroke="#A8C0C1"></line><rect x="380" y="44" width="170" height="84" fill="#DCE8E8" stroke="#A8C0C1"></rect><line x1="437" y1="44" x2="437" y2="128" stroke="#A8C0C1"></line><line x1="494" y1="44" x2="494" y2="128" stroke="#A8C0C1"></line><rect x="380" y="102" width="170" height="26" fill="#B5641A" opacity="0.5"></rect><line x1="20" y1="298" x2="292" y2="298" stroke="#D6D2C7"></line><line x1="330" y1="298" x2="602" y2="298" stroke="#D6D2C7"></line><polyline points="20,298 50,272 80,246 110,222 140,200 165,186 185,180 205,181 225,192 245,214 265,250 285,298" fill="none" stroke="#16616B" stroke-width="2.5" stroke-linejoin="round"></polyline><circle cx="192" cy="180" r="6" fill="#B5641A"></circle><polyline points="330,298 349,273 369,250 388,234 403,228 415,235 425,249 437,231 452,207 466,189 478,182 491,186 503,200 515,218 527,210 539,202 553,196 563,206 576,233 588,266 600,298" fill="none" stroke="#16616B" stroke-width="2.5" stroke-linejoin="round"></polyline><circle cx="478" cy="182" r="6" fill="#B5641A"></circle><circle cx="403" cy="228" r="4" fill="none" stroke="#8A9098" stroke-width="1.5"></circle><circle cx="553" cy="196" r="4" fill="none" stroke="#8A9098" stroke-width="1.5"></circle><text x="22" y="322" font-family="IBM Plex Sans, sans-serif" font-size="13" fill="#2B3238">One peak. Any tracker finds it.</text><text x="332" y="322" font-family="IBM Plex Sans, sans-serif" font-size="13" fill="#2B3238">Three peaks. Only one is the real maximum.</text><text x="22" y="342" font-family="IBM Plex Mono, monospace" font-size="11" fill="#6A7177">power against voltage</text><text x="332" y="342" font-family="IBM Plex Mono, monospace" font-size="11" fill="#6A7177">the other two are traps</text><line x1="310" y1="6" x2="310" y2="354" stroke="#FFFFFF" stroke-width="3"></line></svg>'''
_CARD_ICONS = [r'''<svg width="17" height="17" viewBox="0 0 18 18" aria-hidden="true"><rect x="2" y="2" width="14" height="14" rx="1.5" fill="none" stroke="#16616B" stroke-width="1.4"></rect><path d="M6.7 2v14M11.3 2v14" stroke="#16616B" stroke-width="1.4"></path></svg>''', r'''<svg width="17" height="17" viewBox="0 0 18 18" aria-hidden="true"><rect x="2" y="2" width="14" height="14" rx="1.5" fill="none" stroke="#16616B" stroke-width="1.4"></rect><path d="M2 11l7-7M5 15l10-10M10 16l6-6" stroke="#B5641A" stroke-width="1.3"></path></svg>''', r'''<svg width="17" height="17" viewBox="0 0 18 18" aria-hidden="true"><path d="M2 15c3 0 3-9 6.5-9S12 13 16 3" fill="none" stroke="#16616B" stroke-width="1.5" stroke-linecap="round"></path></svg>''', r'''<svg width="17" height="17" viewBox="0 0 18 18" aria-hidden="true"><path d="M4 3l8 6-8 6z" fill="none" stroke="#16616B" stroke-width="1.4" stroke-linejoin="round"></path></svg>''', r'''<svg width="17" height="17" viewBox="0 0 18 18" aria-hidden="true"><path d="M3 15V9M8 15V4M13 15v-4" stroke="#16616B" stroke-width="1.6" stroke-linecap="round"></path></svg>''']
_CARD_TEXT = [
    ("Build the panel",
     "Pick a 60- or 72-cell module, set the sunlight and the cell temperature, "
     "and start from a clean unshaded curve."),
    ("Place the shadow",
     "Drag a band along the cell strips or across them, choose how dark it is, "
     "and watch which bypass diodes switch on."),
    ("Read the curve",
     "The current and power curves redraw as you go, with the step, every peak, "
     "and the true maximum marked."),
    ("Run the trackers",
     "Send your scenario to the classic algorithms and to the model, and watch each "
     "one search the same curve step by step."),
    ("Compare and export",
     "See how much power each method actually captured, how long it took, and take "
     "the table and figures away as files."),
]
# The page each card opens, in the order of _CARD_TEXT.
_CARD_LINKS = ["sim_setup", "panels", "inside", "run", "compare"]


def _home_css(c):
    st.markdown(
        ("<style>"
         ".st-key-hero-primary a{height:52px;padding:0 26px;background:%(teal)s;"
         "color:#fff!important;border:1px solid %(teal)s;border-radius:10px;font-size:15px;"
         "font-weight:600;display:flex;align-items:center;justify-content:center;gap:10px;"
         "text-decoration:none;}"
         ".st-key-hero-primary a:hover{background:%(teal_dark)s;border-color:%(teal_dark)s;}"
         ".st-key-hero-primary a p{color:#fff!important;margin:0;font-weight:600;}"
         ".st-key-hero-secondary a{height:52px;padding:0 22px;background:%(surface)s;"
         "color:%(text)s!important;border:1px solid %(border_strong)s;border-radius:10px;"
         "font-size:15px;font-weight:500;display:flex;align-items:center;justify-content:center;"
         "gap:10px;text-decoration:none;}"
         ".st-key-hero-secondary a p{color:%(text)s!important;margin:0;}"
         ".st-key-hero-primary a>svg,.st-key-hero-secondary a>svg{display:none;}"
         ".st-key-gmcards{margin-top:18px;}"
         # Each card is one HTML block, so the card's own flex column decides where the
         # Open button sits. Stretching the wrappers only equalises the row's heights —
         # if a selector ever stops matching, cards just size to their own content.
         ".st-key-gmcards div[data-testid=\"stColumn\"]{display:flex;flex-direction:column;}"
         ".st-key-gmcards div[data-testid=\"stColumn\"]>div,"
         ".st-key-gmcards div[data-testid=\"stElementContainer\"],"
         ".st-key-gmcards div[data-testid=\"stMarkdown\"],"
         ".st-key-gmcards div[data-testid=\"stMarkdownContainer\"]{width:100%%;height:100%%;}"
         ".gm-card{box-sizing:border-box;display:flex;flex-direction:column;height:100%%;"
         "min-height:210px;background:%(surface)s;border:1px solid %(border)s;"
         "border-radius:14px;padding:18px;"
         "transition:border-color .12s ease,box-shadow .12s ease;}"
         ".gm-card:hover{border-color:%(border_strong)s;"
         "box-shadow:0 2px 12px rgba(16,24,32,.07);}"
         ".gm-card .gm-ico{width:34px;height:34px;display:flex;align-items:center;"
         "justify-content:center;border:1px solid %(border)s;border-radius:9px;}"
         ".gm-card .gm-title{margin-top:12px;font-size:15px;font-weight:600;color:%(text)s;}"
         ".gm-card .gm-desc{margin:6px 0 0 0;font-size:13px;line-height:1.5;"
         "color:%(text_body)s;}"
         # margin-top:auto pins the button to the bottom; padding-top keeps a gap from
         # the description even when the text fills the card.
         ".gm-card .gm-open{display:inline-flex;align-items:center;justify-content:center;"
         "height:36px;padding:0 16px;border-radius:8px;background:%(teal)s;"
         "color:#fff!important;font-weight:600;font-size:13px;text-decoration:none!important;}"
         ".gm-card .gm-open:hover{background:%(teal_dark)s;}"
         ".gm-card .gm-openwrap{margin-top:auto;padding-top:16px;}"
         "</style>") % {"teal": c["teal"], "teal_dark": c["teal_dark"],
                        "surface": c["surface"], "text": c["text"],
                        "text_body": c["text_body"],
                        "border": c["border"], "border_strong": c["border_strong"]},
        unsafe_allow_html=True)


def page_home():
    c = ui.T()
    disp, mono = ui.FONTS["display"], ui.FONTS["mono"]
    _home_css(c)

    left, right = st.columns([0.46, 0.54], gap="large", vertical_alignment="center")
    with left:
        st.markdown(
            f'<span style="display:inline-flex;align-items:center;gap:8px;padding:7px 14px;'
            f'border:1px solid {c["amber_border"]};border-radius:999px;background:{c["amber_tint"]};'
            f'font-family:{mono};font-size:11px;letter-spacing:.07em;text-transform:uppercase;'
            f'color:{c["amber_text"]};"><svg width="10" height="10" viewBox="0 0 10 10">'
            f'<circle cx="5" cy="5" r="4" fill="{c["amber"]}"></circle></svg>'
            f'AI Lab \u00b7 Jeju National University \u00d7 Nanum Energy</span>'
            f'<h1 style="margin:16px 0 0 0;font-family:{disp};font-size:54px;font-weight:800;'
            f'line-height:1.04;letter-spacing:-.035em;color:{c["text"]};">Welcome to the<br>'
            f'<span style="color:{c["teal"]};">GMPPT</span> '
            f'<span style="color:{c["amber"]};">Bench</span><br>Dashboard</h1>'
            f'<p style="margin:16px 0 0 0;font-size:17px;line-height:1.55;color:{c["text_body"]};'
            f'max-width:520px;">Put a shadow anywhere on a solar panel, watch the power curve '
            f'change shape, and see which tracking algorithm still finds the true peak.</p>',
            unsafe_allow_html=True)
        b1, b2 = st.columns([1, 1.25])
        with b1:
            with st.container(key="hero-primary"):
                st.page_link(P["panels"], label="Start exploring  \u2192")
        with b2:
            with st.container(key="hero-secondary"):
                st.page_link(P["run"], label="\u25b6  Watch a worked example")
        st.markdown(
            f'<p style="margin:14px 0 0 0;font-size:13px;line-height:1.5;color:{c["text_muted"]};'
            f'max-width:520px;">No account and no setup. Every panel here is simulated on a model '
            f'matched to within about one per cent of 616 laboratory flash tests.</p>',
            unsafe_allow_html=True)
    with right:
        st.markdown(
            f'<div style="background:{c["surface"]};border:1px solid {c["border"]};'
            f'border-radius:16px;padding:18px 20px 12px 20px;">{_HERO_SVG}'
            f'<p style="margin:6px 0 0 0;text-align:center;font-size:12.5px;color:{c["text_muted"]};">'
            f'The same panel on the same afternoon — compared with and without partial shading.'
            f'</p></div>', unsafe_allow_html=True)

    st.markdown(
        f'<div style="margin-top:28px;text-align:center;font-family:{mono};font-size:12px;'
        f'letter-spacing:.14em;text-transform:uppercase;color:{c["text_muted"]};">'
        f'What you can do here</div>', unsafe_allow_html=True)
    with st.container(key="gmcards"):
        cols = st.columns(5, gap="small")
        for i, ((title, desc), icon, target) in enumerate(
                zip(_CARD_TEXT, _CARD_ICONS, _CARD_LINKS)):
            with cols[i]:
                # One markdown block per card: the button is a plain link inside the
                # card's own flex column, like the footer link, so nothing can slide
                # under the text the way a nested st.page_link container did.
                st.markdown(
                    f'<div class="gm-card">'
                    f'<span class="gm-ico">{icon}</span>'
                    f'<div class="gm-title">{title}</div>'
                    f'<p class="gm-desc">{desc}</p>'
                    f'<div class="gm-openwrap">'
                    f'<a class="gm-open" href="{P[target].url_path}" target="_self">'
                    f'Open →</a></div></div>', unsafe_allow_html=True)

    st.markdown(
        f'<div style="margin-top:28px;display:flex;align-items:center;gap:16px;padding-top:18px;'
        f'border-top:1px solid {c["border"]};font-size:12.5px;color:{c["text_muted"]};">'
        f'<span>Simulated modules only \u2014 no field measurements behind these figures yet.</span>'
        f'<a href="sources" target="_self" style="text-decoration:none;font-weight:600;'
        f'color:{c["teal"]};">Where the numbers come from \u2192</a>'
        f'<span style="margin-left:auto;font-family:{mono};">Dept. of Computer Engineering, '
        f'Jeju National University</span></div>', unsafe_allow_html=True)


# =========================================================================== #
# Explore
# =========================================================================== #
# =========================================================================== #
# Explore · The panels  — wired to the VALIDATED engine (gmppt.device) and the
# held-out VALIDATION modules (gmppt.scenarios.split_modules).
# =========================================================================== #
@st.cache_resource(show_spinner=False)
def _cec_table():
    from pvlib import pvsystem
    return pvsystem.retrieve_sam("CECMod").T


@st.cache_data(show_spinner=False)
def _pool():
    return pd.read_parquet(_gcfg.CEC_POOL)


@st.cache_data(show_spinner=False)
def _validation_modules():
    """A curated few held-out (validation) modules for the panel dropdown."""
    pool = _pool()
    _, heldout = _scen.split_modules(pool)
    h = pool.loc[list(heldout)].copy()
    h["P"] = h["V_mp_ref"] * h["I_mp_ref"]
    wanted = [(72, 330, 350, "72-cell c-Si · 3 bypass diodes · ~340 W"),
              (60, 270, 290, "60-cell c-Si · 3 bypass diodes · ~280 W"),
              (72, 300, 330, "72-cell c-Si · 3 bypass diodes · ~315 W")]
    out, seen = [], set()
    for nc, lo, hi, lab in wanted:
        s = h[(h["N_s"] == nc) & (h["P"].between(lo, hi))].sort_values("P")
        if len(s):
            nm = str(s.index[len(s) // 2])
            if nm not in seen:
                out.append((lab, nm)); seen.add(nm)
    return out


@st.cache_data(show_spinner=False)
def _mparams(name):
    r = _cec_table().loc[name]
    num = lambda k: float(pd.to_numeric(r[k]))
    return _eng.ModuleParams(name=name, N_s=int(num("N_s")), alpha_sc=num("alpha_sc"),
                             a_ref=num("a_ref"), I_L_ref=num("I_L_ref"),
                             I_o_ref=num("I_o_ref"), R_sh_ref=num("R_sh_ref"),
                             R_s=num("R_s"), Adjust=num("Adjust"))


def _key(irr):
    """Hashable cache key for an irradiance pattern (scalars or per-group lists)."""
    return tuple(tuple(float(x) for x in e) if isinstance(e, (list, tuple)) else float(e)
                 for e in irr)


@st.cache_data(show_spinner=False)
def _sim(name, irr_key, T):
    """Validated module curve + peak analysis, restricted to V>=0 and V-ascending."""
    mp = _mparams(name)
    irr = [list(e) if isinstance(e, tuple) else float(e) for e in irr_key]
    c = _eng.module_iv(mp, irr, T, bd=_gcfg.breakdown())
    a = _eng.analyse(c)
    V, I, P = c["V"], c["I"], c["P"]
    m = V >= 0
    V, I, P = V[m], I[m], P[m]
    o = np.argsort(V)
    return dict(V=V[o], I=I[o], P=P[o], gmpp=a["gmpp"], peaks=a["peaks"],
                n_peaks=a["n_peaks"], voc=float(V.max()))


def _substring_voltages(name, irr, T, at_current):
    """Per-substring terminal voltage at a given string current — for the bypass
    table and the operating-point view. Recomputed only for the inspected panel."""
    mp = _mparams(name); bd = _gcfg.breakdown(); bp = _eng.Bypass(temp_c=T)
    n_sub = _gcfg.N_SUBSTRINGS
    base = mp.N_s // n_sub
    counts = [base] * n_sub
    for k in range(mp.N_s - base * n_sub):
        counts[k] += 1
    out = []
    for entry, cnt in zip(irr, counts):
        sub = _eng.scale_to_substring(mp, cnt / mp.N_s)
        if np.isscalar(entry):
            v, ie = _eng.substring_element_iv(sub, float(entry), T, bd, bp)
        else:
            v, ie = _eng.substring_element_iv_subshaded(sub, list(entry), T, bd, bp)
        vk = float(np.interp(at_current, ie[::-1], v[::-1]))
        out.append(vk)
    return out, bp.clamp_voltage


def _event_pattern(obj, depth, width, runs, edge, base_G,
                   n_sub=_gcfg.N_SUBSTRINGS, n_groups=3):
    """Map the shadow controls to a per-substring irradiance argument for the
    validated engine. 'across' -> sub-substring on every strip (deepest multi-
    peak); 'along' -> whole strips shaded; 'diagonally' -> a staircase; cloud /
    soiling -> a graded blanket over the whole module."""
    lvl = float(depth)
    if edge.startswith("soft"):
        lvl = (lvl + base_G) / 2.0

    def grp(n_shaded):
        g = [float(base_G)] * n_groups
        for k in range(int(min(n_shaded, n_groups))):
            g[k] = lvl if not (edge.startswith("dappled") and k % 2) else (lvl + base_G) / 2.0
        return g

    if obj in ("Cloud", "Soiling"):
        return [max(lvl, base_G * f) for f in (0.55, 0.70, 0.85)][:n_sub]
    if runs.startswith("along"):
        ns = max(1, min(n_sub - 1, round(width * n_sub)))
        return [lvl if s < ns else float(base_G) for s in range(n_sub)]
    if runs.startswith("diag"):
        return [grp(max(1, round(width * (s + 1)))) for s in range(n_sub)]
    ns = max(1, min(n_groups, round(width * n_groups)))
    return [grp(ns) for _ in range(n_sub)]


def _set_scenario(module, temp, irr, label):
    """Shared scenario store — the single source of truth that flows between tabs.
    Kept in session (memory) and mirrored to results/current_scenario.json."""
    sc = {"module": str(module), "temp": float(temp), "label": str(label),
          "irr": [list(e) if isinstance(e, (list, tuple)) else float(e) for e in irr]}
    st.session_state["scenario"] = sc
    try:
        import json
        (_gcfg.RESULTS_DIR / "current_scenario.json").write_text(json.dumps(sc, indent=2))
    except Exception:
        pass


def _dfmt(p, unit):
    return f"{p:g}{unit}"


def _dual_sel(key, presets, unit):
    sel = st.session_state[f"{key}_sel"]
    if sel != "Custom\u2026":
        labels = [_dfmt(p, unit) for p in presets]
        v = float(presets[labels.index(sel)])
        st.session_state[f"{key}_num"] = v
        st.session_state[key] = v


def _dual_num(key, presets, unit):
    v = float(st.session_state[f"{key}_num"])
    st.session_state[key] = v
    labels = [_dfmt(p, unit) for p in presets]
    st.session_state[f"{key}_sel"] = labels[presets.index(v)] if v in presets else "Custom\u2026"


def _dual(label, key, presets, unit, step, vmin, vmax, default, help=None):
    """A single dropdown of presets (the extra editable box was removed per request)."""
    st.session_state.setdefault(key, float(default))
    cur = st.session_state[key]
    if cur not in presets:
        cur = min(presets, key=lambda p: abs(float(p) - float(cur)))
        st.session_state[key] = float(cur)
    labels = [_dfmt(p, unit) for p in presets]
    st.caption(label)
    sel = st.selectbox(label, labels, index=presets.index(cur), key=f"{key}_pick",
                       label_visibility="collapsed", help=help)
    v = float(presets[labels.index(sel)])
    st.session_state[key] = v
    return v


def _array_svg(rows, per, shaded_idx, sel_idx, obj_color, c, sel_id=""):
    lm, gap, pw, ph, top = 66, 12, 96, 62, 22
    W = lm + per * (pw + gap)
    H = top + rows * (ph + gap) + 4
    p = [f'<svg viewBox="0 0 {W} {H}" style="width:100%;height:auto;">',
         f'<rect x="0" y="0" width="{W}" height="{H}" rx="12" fill="{c["muted_fill"]}"/>']
    # a soft pole-shadow band across the shaded block
    if shaded_idx:
        xs = [lm + (i % per) * (pw + gap) for i in shaded_idx]
        ys = [top + (i // per) * (ph + gap) for i in shaded_idx]
        x0, x1 = min(xs) - 6, max(xs) + pw + 6
        y0, y1 = min(ys) - 4, max(ys) + ph + 4
        p.append(f'<polygon points="{x0+28:.0f},{y0:.0f} {x1:.0f},{y0:.0f} '
                 f'{x1-28:.0f},{y1:.0f} {x0:.0f},{y1:.0f}" fill="#2B3238" opacity="0.16"/>')
    for r in range(rows):
        y = top + r * (ph + gap)
        p.append(f'<text x="6" y="{y+ph/2+4:.0f}" font-family="IBM Plex Mono,monospace" '
                 f'font-size="10" fill="{c["text_muted"]}">STRING {chr(65+r)}</text>')
        for col in range(per):
            i = r * per + col
            x = lm + col * (pw + gap)
            p.append(f'<rect x="{x}" y="{y}" width="{pw}" height="{ph}" rx="4" fill="{c["panel"]}"/>')
            p.append(f'<path d="M{x+pw/3:.0f} {y}v{ph}M{x+2*pw/3:.0f} {y}v{ph}'
                     f'M{x} {y+ph/2:.0f}h{pw}" stroke="#33566B" stroke-width="1"/>')
            if i in shaded_idx:
                p.append(f'<rect x="{x}" y="{y}" width="{pw}" height="{ph}" rx="4" '
                         f'fill="{obj_color}" opacity="0.5"/>')
            if i == sel_idx:
                p.append(f'<rect x="{x-2}" y="{y-2}" width="{pw+4}" height="{ph+4}" rx="6" '
                         f'fill="none" stroke="{c["amber"]}" stroke-width="3"/>')
                p.append(f'<rect x="{x}" y="{y-17}" width="90" height="16" rx="4" '
                         f'fill="{c["amber"]}"/>')
                p.append(f'<text x="{x+6}" y="{y-5}" font-family="IBM Plex Mono,monospace" '
                         f'font-size="10" fill="#ffffff">{sel_id} selected</text>')
    p.append('</svg>')
    return "".join(p)


def _daytimeline_svg(c):
    W, H, lm = 1120, 168, 140
    x0, x1 = lm, W - 10
    lanes = [("Inter-row shading", "#AFC9E3", [(0.05, 0.20)]),
             ("Pole or vent shadow", "#F0C68A", [(0.27, 0.55)]),
             ("Cloud passes", "#AFC9E3", [(0.80, 0.98)]),
             ("Soiling", "#E9A08C", [(0.02, 0.98)])]
    X = lambda f: x0 + f * (x1 - x0)
    lh, ly0 = 26, 8
    p = [f"<svg viewBox='0 0 {W} {H}' style='width:100%;height:168px;margin-top:10px'>"]
    for k, (name, col, blocks) in enumerate(lanes):
        y = ly0 + k * (lh + 8)
        p.append(f"<text x='0' y='{y+lh/2+4:.0f}' font-family='IBM Plex Sans,sans-serif' "
                 f"font-size='11.5' fill='{c['text_muted']}'>{name}</text>")
        p.append(f"<rect x='{x0}' y='{y}' width='{x1-x0}' height='{lh}' rx='5' "
                 f"fill='{c['muted_fill']}'/>")
        for a, b in blocks:
            p.append(f"<rect x='{X(a):.0f}' y='{y+3}' width='{X(b)-X(a):.0f}' "
                     f"height='{lh-6}' rx='4' fill='{col}'/>")
    yp = ly0 + 1 * (lh + 8)
    p.append(f"<rect x='{X(0.27):.0f}' y='{yp+3}' width='{X(0.55)-X(0.27):.0f}' height='{lh-6}' "
             f"rx='4' fill='none' stroke='{c['amber']}' stroke-width='2'/>")
    p.append(f"<text x='{X(0.285):.0f}' y='{yp+lh/2+4:.0f}' font-family='IBM Plex Mono,monospace' "
             f"font-size='10' fill='#7A5A1E'>selected</text>")
    ay = ly0 + len(lanes) * (lh + 8) + 4
    for f, lab in [(0, "06:00"), (0.25, "09:00"), (0.5, "12:00"), (0.75, "15:00"), (1, "18:00")]:
        p.append(f"<text x='{X(f)-14:.0f}' y='{ay+12}' font-family='IBM Plex Mono,monospace' "
                 f"font-size='10' fill='{c['text_muted']}'>{lab}</text>")
    phx = X(0.78)
    p.append(f"<line x1='{phx:.0f}' y1='4' x2='{phx:.0f}' y2='{ay+2}' stroke='{c['amber']}' "
             f"stroke-width='1.5'/><circle cx='{phx:.0f}' cy='4' r='5' fill='{c['amber']}'/>")
    p.append("</svg>")
    return "".join(p)


def _module_face_svg(irr, base_G, c):
    W, H = 150, 104
    sw = (W - 12) / 3.0
    p = [f'<svg viewBox="0 0 {W} {H}" style="width:150px;height:104px;">',
         f'<rect x="6" y="6" width="{W-12}" height="{H-24}" fill="{c["panel"]}"/>']
    for s in range(3):
        x = 6 + s * sw
        if s > 0:
            p.append(f'<line x1="{x:.0f}" y1="6" x2="{x:.0f}" y2="{H-18}" '
                     f'stroke="#7FA5A8" stroke-width="1.5"/>')
        entry = irr[s] if s < len(irr) else base_G
        groups = list(entry) if isinstance(entry, (list, tuple)) else [entry, entry, entry]
        gh = (H - 24) / len(groups)
        for gi, gv in enumerate(groups):
            if gv < base_G - 1:
                op = 0.62 * (1 - gv / max(base_G, 1)) + 0.15
                p.append(f'<rect x="{x:.0f}" y="{6 + gi*gh:.0f}" width="{sw:.0f}" '
                         f'height="{gh:.0f}" fill="#101A20" opacity="{op:.2f}"/>')
        p.append(f'<text x="{x + sw/2 - 6:.0f}" y="{H-4}" font-family="IBM Plex Mono,monospace" '
                 f'font-size="10" fill="{c["text_muted"]}">S{s+1}</text>')
    p.append('</svg>')
    return "".join(p)


# --- event-based day: model + runner (functional; drag replaced by timing sliders) ---
# kind -> (target substring index or "all", light left as a fraction of the sun level)
_KIND_MAP = {
    "Row in front": (0, 0.35), "Building edge": (0, 0.40),
    "Pole or vent": (1, 0.28), "Tree branch": (1, 0.45), "Snow band": ("all", 0.55),
    "Paint your own": (1, 0.40),
    "Cloud": ("all", 0.55),
    "Soiling": ("all", 0.80), "Bird dropping": (2, 0.20), "Leaf": (2, 0.30),
}
_KIND_LANE = {"Row in front": 0, "Building edge": 0,
              "Pole or vent": 1, "Tree branch": 1, "Snow band": 1, "Paint your own": 1,
              "Cloud": 2, "Soiling": 3, "Bird dropping": 3, "Leaf": 3}
_DAY_LANES = ["Inter-row shading", "Pole or vent shadow", "Cloud passes", "Soiling"]
_DAY_COL = {0: "#AFC9E3", 1: "#F0C68A", 2: "#AFC9E3", 3: "#E9A08C"}


_DAY_MOTIONS = ["fixed in place", "drifts across the strips", "grows through the event"]


def _day_motions_for(kind):
    """Whole-module events (cloud, soiling, snow) have no single strip to drift across."""
    sub = _KIND_MAP.get(kind, (1, 0.4))[0]
    return [m for m in _DAY_MOTIONS if not (sub == "all" and m.startswith("drifts"))]


def _day_add(kind):
    st.session_state.setdefault("day_events", [])
    st.session_state["day_events"].append({"kind": kind, "t0": 0.28, "t1": 0.55,
                                           "motion": "fixed in place"})


def _day_timeline_svg(events, playhead, c):
    W, H, lm = 1120, 168, 140
    x0, x1 = lm, W - 10
    X = lambda f: x0 + f * (x1 - x0)
    lh, ly0 = 26, 8
    p = [f"<svg viewBox='0 0 {W} {H}' style='width:100%;height:168px;margin-top:8px'>"]
    for k, name in enumerate(_DAY_LANES):
        y = ly0 + k * (lh + 8)
        p.append(f"<text x='0' y='{y+lh/2+4:.0f}' font-family='IBM Plex Sans,sans-serif' "
                 f"font-size='11.5' fill='{c['text_muted']}'>{name}</text>")
        p.append(f"<rect x='{x0}' y='{y}' width='{x1-x0}' height='{lh}' rx='5' "
                 f"fill='{c['muted_fill']}'/>")
    for ev in events:
        lane = _KIND_LANE.get(ev["kind"], 1)
        y = ly0 + lane * (lh + 8)
        a, b = X(max(0, ev["t0"])), X(min(1, ev["t1"]))
        p.append(f"<rect x='{a:.0f}' y='{y+3}' width='{max(6,b-a):.0f}' height='{lh-6}' rx='4' "
                 f"fill='{_DAY_COL[lane]}'/>")
        p.append(f"<text x='{a+6:.0f}' y='{y+lh/2+4:.0f}' font-family='IBM Plex Mono,monospace' "
                 f"font-size='10' fill='#2B2A20'>{ev['kind']}</text>")
    ay = ly0 + len(_DAY_LANES) * (lh + 8) + 4
    for f, lab in [(0, "06:00"), (0.25, "09:00"), (0.5, "12:00"), (0.75, "15:00"), (1, "18:00")]:
        p.append(f"<text x='{X(f)-14:.0f}' y='{ay+12}' font-family='IBM Plex Mono,monospace' "
                 f"font-size='10' fill='{c['text_muted']}'>{lab}</text>")
    phx = X(max(0, min(1, playhead)))
    p.append(f"<line x1='{phx:.0f}' y1='4' x2='{phx:.0f}' y2='{ay+2}' stroke='{c['amber']}' "
             f"stroke-width='1.5'/><circle cx='{phx:.0f}' cy='4' r='5' fill='{c['amber']}'/>")
    p.append("</svg>")
    return "".join(p)


@st.cache_data(show_spinner=True)
def _day_run(module, temp, base_G, events_key):
    import numpy as np
    from gmppt import dynamic as dyn, tracking as trk, pso, config as gc, device
    from gmppt.device import ModuleParams
    mp = ModuleParams.from_cec(module)
    slices, SPS = 48, 8
    times = np.linspace(6.0, 18.0, slices)
    sun = float(base_G) * np.clip(np.sin(np.pi * (times - 6) / 12), 0, None)

    def curve_at(irr):
        c = device.module_iv(mp, irr, float(temp), bd=gc.breakdown())
        a = device.analyse(c)
        V = np.asarray(c["V"], float); P = np.asarray(c["P"], float)
        o = np.argsort(V)
        return (V[o], P[o], float(a["gmpp"]["V"]), float(a["gmpp"]["P"]))

    curves, unshaded = [], []
    for ti, g in zip(times, sun):
        irr = [float(g)] * 3
        for kind, t0, t1, motion in events_key:
            frac = (ti - 6) / 12
            if not (t0 <= frac <= t1):
                continue
            sub, depth = _KIND_MAP.get(kind, (1, 0.4))
            # f = how far through its own window this event is, 0 at the start, 1 at the end
            f = min(1.0, max(0.0, (frac - t0) / max(t1 - t0, 1e-6)))
            if motion == "grows through the event":
                depth = 1.0 - (1.0 - depth) * f        # light at first, full depth by the end
            elif motion == "drifts across the strips" and sub != "all":
                sub = min(2, int(f * 3))               # the shadow walks S1 -> S2 -> S3
            if sub == "all":
                irr = [min(x, g * depth) for x in irr]
            else:
                irr[int(sub)] = min(irr[int(sub)], g * depth)
        curves.append(curve_at([max(1.0, v) for v in irr]))
        unshaded.append(curve_at([max(1.0, float(g))] * 3)[3])

    bs = np.array([SPS] * slices); scored = np.ones(slices, bool)
    mk = lambda: dyn.DynamicTrajectory(curves=curves, block_steps=bs, scored=scored,
                                       module=module)
    out = {"t": [float(x) for x in np.repeat(times, SPS)],
           "unshaded": [float(x) for x in np.repeat(unshaded, SPS)], "methods": {}}

    def run(name, fn, **kw):
        tj = mk(); fn(tj, n_steps=int(bs.sum()), **kw)
        out["methods"][name] = [float(x) for x in tj.p_hist]
        out["avail"] = [float(x) for x in tj.avail_hist]

    run("P&O", trk.perturb_and_observe)
    run("PSO", pso.particle_swarm)
    model = _c3_model()
    if model is not None:
        from gmppt import hybrid as hyb
        run("Hybrid", hyb.make_hybrid(model), temp_c=float(temp))
    av = np.array(out["avail"])
    out["energy"] = {m: 100 * float(np.sum(ph)) / max(1e-9, float(np.sum(av)))
                     for m, ph in out["methods"].items()}
    return out


def page_panels():
    ui.page_intro("Your panels",
                  "Put a shadow on a panel and see what it does to the power it can make.",
                  "Explore · The panels")
    c = ui.T()
    try:
        val_mods = _validation_modules()
        assert val_mods
    except Exception as e:
        ui.callout(f"Could not load the validation-module pool ({e}). Make sure the "
                   "`gmppt/` package and `results/cec_pool.parquet` sit beside "
                   "`gmppt_app.py`.", "Engine not connected", "limit")
        return

    label_to_name = dict(val_mods)
    ctrl, mid, right = st.columns([0.92, 1.5, 1.18], gap="large")

    # ------------------------------------------------------------------ controls
    with ctrl:
        with st.expander("1 · The panel", expanded=True):
            labels = [l for l, _ in val_mods] + ["Nanum target panel — [awaiting spec]"]
            pick = st.selectbox("Panel model (validation set)", labels, key="gm_panel")
            awaiting = pick.startswith("Nanum")
            name = val_mods[0][1] if awaiting else label_to_name[pick]
            if awaiting:
                ui.callout("Nanum's target spec is awaited — showing a held-out "
                           "validation module in the meantime.", "", "info")
            rows = int(_dual("Rows (strings)", "gm_rows", [1, 2, 3, 4, 6], "", 1, 1, 6, 3))
            per = int(_dual("Per row", "gm_per", [1, 2, 3, 4, 5, 6, 8], "", 1, 1, 8, 5))
            mount = st.segmented_control("Mounting", ["Portrait", "Landscape"],
                                         default="Portrait", key="gm_mount") or "Portrait"
            st.caption("Orientation decides what a shadow does: across the cell "
                       "strips, or along them.")
        n_panels = rows * per
        ids = [f"{chr(65 + i // per)}-{i % per + 1:02d}" for i in range(n_panels)]

        with st.expander("2 · The shadow", expanded=True):
            objs = ["Pole or vent", "Row in front", "Tree branch", "Cloud",
                    "Soiling", "Bird dropping", "Leaf"]
            obj = st.selectbox("What casts it", objs, key="gm_obj2")
            depth = _dual("Shadow depth — W/m² under it", "gm_depth2",
                          [0, 100, 200, 240, 300, 400, 600, 900], " W/m²", 10, 0, 900, 240,
                          help="Irradiance left under the shadow. Lower = darker.")
            width = _dual("Width across the panel", "gm_width",
                          [0.25, 0.4, 0.5, 0.55, 0.75, 1.0], "", 0.05, 0.0, 1.0, 0.55)
            rc1, rc2 = st.columns(2)
            default_runs = 0 if mount == "Portrait" else 1
            runs = rc1.selectbox("Runs", ["across the strips", "along the strips",
                                          "diagonally"], index=default_runs, key="gm_runs")
            edge = rc2.selectbox("Edge", ["hard", "soft (penumbra)", "dappled"], key="gm_edge")
            covers_all = obj in ("Cloud", "Soiling")
            if covers_all:
                shaded_ids = list(ids)
                st.caption("Cloud and soiling cover the whole array.")
            else:
                if "gm_shaded_ids" not in st.session_state:
                    s0 = max(0, (n_panels - min(3, n_panels)) // 2)
                    st.session_state["gm_shaded_ids"] = ids[s0:s0 + min(3, n_panels)]
                st.session_state["gm_shaded_ids"] = [i for i in
                    st.session_state["gm_shaded_ids"] if i in ids] or ids[:min(3, n_panels)]
                shaded_ids = st.multiselect("Shade which panels", ids, key="gm_shaded_ids",
                                            help="Pick exactly which panels the shadow covers.")
            n_shaded = len(shaded_ids)
            st.caption("These controls set one single moment. How the shadow moves "
                       "through the day is set on the day timeline below.")

        with st.expander("3 · Conditions", expanded=False):
            base_G = int(_dual("Sunlight (W/m²)", "gm_G2",
                               [200, 400, 600, 800, 910, 1000, 1100], " W/m²", 10, 200, 1100, 910))
            T = int(_dual("Cell temperature (°C)", "gm_T2",
                          [10, 25, 43, 55, 70], " °C", 1, 10, 70, 43,
                          help="Cell (not air) temperature."))
        # The page recomputes on every control change, so this is a re-render nudge,
        # not a compute trigger — labelled and styled so it does not claim otherwise.
        st.button("Refresh analysis", key="sim-panels", use_container_width=True,
                  help="The curves above recompute as soon as you change a control. "
                       "Use this only to redraw the page.")

    # ------------------------------------------------------------------ compute
    pattern = _event_pattern(obj, depth, width, runs, edge, base_G)
    uniform = [float(base_G)] * _gcfg.N_SUBSTRINGS
    shaded_idx = {ids.index(x) for x in shaded_ids}

    sh = _sim(name, _key(pattern), T)
    uns = _sim(name, _key(uniform), T)
    array_now = len(shaded_idx) * sh["gmpp"]["P"] + (n_panels - len(shaded_idx)) * uns["gmpp"]["P"]
    array_uns = n_panels * uns["gmpp"]["P"]
    shadow_type = ("Across the strips" if runs.startswith("across")
                   else "Along the strips" if runs.startswith("along") else "Diagonal")

    # ------------------------------------------------------------------ center
    with mid:
        th = st.columns([5, 0.6, 0.6, 0.6], vertical_alignment="center")
        th[0].markdown(
            f"<div class='bh'>Your panels</div>"
            f"<div style='font-size:13.5px;color:{c['text_muted']}'>{n_panels} panels in "
            f"{rows} string{'s' if rows > 1 else ''} — pick one to inspect it.</div>",
            unsafe_allow_html=True)
        th[1].button("⤢", key="tool_drag", disabled=True, use_container_width=True,
                     help="Drag the shadow — unavailable: requires an interactive custom "
                          "component. Use the shadow controls on the left instead.")
        th[2].button("▦", key="tool_paint", disabled=True, use_container_width=True,
                     help="Paint cells — unavailable: requires an interactive custom "
                          "component. Use the shadow controls on the left instead.")
        if th[3].button("✕", key="tool_clear", use_container_width=True,
                        help="Reset the inspected panel"):
            st.session_state.pop("gm_sel", None); st.rerun()
        default_id = shaded_ids[0] if shaded_ids else ids[0]
        sel_id = st.selectbox("Inspect panel", ids, index=ids.index(default_id), key="gm_sel")
        sel_idx = ids.index(sel_id)
        st.markdown(_array_svg(rows, per, shaded_idx, sel_idx,
                               ui.EVENT_COLORS.get(obj, "#C2BFB6"), c, sel_id),
                    unsafe_allow_html=True)
        ui.kpi_row([
            ("All panels, right now", f"{array_now/1000:.2f} kW",
             f"of {array_uns/1000:.2f} kW unshaded", "hero"),
            ("Shaded panels", str(len(shaded_idx)),
             "covering everything" if covers_all else f"under the {obj.lower()}"),
            ("Shadow type", shadow_type, runs),
        ], weights=[1.3, 1, 1])
        ui.engine_badge("validated")

    # selected-panel data (real engine)
    sel_shaded = sel_idx in shaded_idx
    sel_irr = pattern if sel_shaded else uniform
    det = sh if sel_shaded else uns
    vsub, clamp = _substring_voltages(name, sel_irr, T, det["gmpp"]["I"])

    # ------------------------------------------------------------------ right rail
    with right:
        with st.container(border=True):
            st.markdown(
                f"<div style='display:flex;align-items:baseline;gap:10px;'>"
                f"<span class='bh'>Panel {sel_id}</span>"
                f"<span class='bmono' style='font-size:12px;color:{c['text_muted']}'>"
                f"{'the one under the shadow' if sel_shaded else 'in full sun'}</span></div>",
                unsafe_allow_html=True)
            fc, ft = st.columns([1, 1.1], vertical_alignment="center")
            fc.markdown(_module_face_svg(sel_irr, base_G, c), unsafe_allow_html=True)
            with ft:
                def _state(vk):
                    return ("on" if vk <= clamp + 0.2 else
                            "partial" if vk < -0.05 else "off")
                lines = "".join(
                    f"<div style='display:flex;justify-content:space-between'>"
                    f"<span style='color:{c['text_muted']}'>bypass D{i+1}</span>"
                    f"<span style='color:{c['amber_text'] if _state(vk)!='off' else c['text']}'>"
                    f"{_state(vk)}</span></div>" for i, vk in enumerate(vsub))
                st.markdown(
                    f"<div class='bmono' style='font-size:12.5px;"
                    f"display:flex;flex-direction:column;gap:7px'>{lines}"
                    f"<div style='display:flex;justify-content:space-between'>"
                    f"<span style='color:{c['text_muted']}'>V_oc</span>"
                    f"<span>{det['voc']:.1f} V</span></div>"
                    f"<div style='display:flex;justify-content:space-between'>"
                    f"<span style='color:{c['text_muted']}'>peaks</span>"
                    f"<span>{det['n_peaks']}</span></div></div>", unsafe_allow_html=True)

            v1, v2 = st.columns(2)
            show = v1.segmented_control("view", ["P–V", "I–V"], default="P–V",
                                        key="gm_pv", label_visibility="collapsed") or "P–V"
            show_uns = v2.toggle("Show unshaded", key="gm_showuns")

            fig = go.Figure()
            if show == "P–V":
                if show_uns and sel_shaded:
                    fig.add_trace(go.Scatter(x=uns["V"], y=uns["P"], name="unshaded",
                                             line=dict(color=ui.REF_COLORS["unshaded"],
                                                       width=2, dash="dot")))
                fig.add_trace(go.Scatter(x=det["V"], y=det["P"], name="with shadow",
                                         line=dict(color=c["teal"], width=3)))
                ui.mark_gmpp(fig, det["gmpp"]["V"], det["gmpp"]["P"])
                ui.mark_local_peaks(fig, [(v, i, pw) for (v, i, pw) in det["peaks"]
                                          if abs(pw - det["gmpp"]["P"]) > 1e-6])
                ui.style_fig(fig, height=230, x_title="Voltage (V)", y_title="Power (W)")
            else:
                fig.add_trace(go.Scatter(x=det["V"], y=det["I"], name="I–V",
                                         line=dict(color="#2C7FA0", width=3)))
                ui.style_fig(fig, height=230, x_title="Voltage (V)", y_title="Current (A)")
            fig.update_layout(showlegend=False, margin=dict(l=48, r=10, t=10, b=40))
            st.plotly_chart(fig, width="stretch")

            with st.container(key="next-panelsend"):
                if st.button("Send this panel to the trackers  →", key="send_trackers",
                             type="primary", use_container_width=True):
                    _set_scenario(name, T, sel_irr, f"Panel {sel_id} · {obj}")
                    st.switch_page(P["run"])

        ui.callout("Not this page. The optimizer behind this panel measures its own "
                   "voltage and current, one point at a time, plus one temperature. "
                   "This view is for you.", "What the algorithm gets to see", "caveat")

    # remember for the 'Inside a panel' page
    st.session_state["gm_last"] = dict(name=name, pattern=_key(sel_irr), T=T, sel_id=sel_id)

    # ------------------------------------------------------------------ day timeline (functional)
    st.session_state.setdefault("day_events", [{"kind": "Pole or vent", "t0": 0.28,
                                                "t1": 0.55, "motion": "fixed in place"}])
    with st.container(border=True):
        hd = st.columns([4, 1.6], vertical_alignment="center")
        hd[0].markdown(
            f"<span class='bh' style='font-size:17px'>Shading events over the day</span>"
            f"<span style='font-size:13px;color:{c['text_muted']};margin-left:10px'>"
            f"add events, set their timing and motion, then run the whole day</span>",
            unsafe_allow_html=True)
        run_day = hd[1].button("Run the whole day through the trackers", key="day_run_btn",
                               type="primary", use_container_width=True)
        st.markdown(f"<span style='font-size:11.5px;font-weight:600;letter-spacing:.05em;"
                    f"text-transform:uppercase;color:{c['text_muted']}'>Add an event</span>",
                    unsafe_allow_html=True)
        _kinds = ["Row in front", "Pole or vent", "Tree branch", "Cloud", "Soiling",
                  "Bird dropping", "Leaf", "Snow band", "Building edge", "Paint your own"]
        cc = st.columns(len(_kinds))
        for _k, _kind in enumerate(_kinds):
            cc[_k].button(_kind, key=f"day_add_{_k}", on_click=_day_add, args=(_kind,),
                          use_container_width=True)
        ph_t = st.slider("Time of day", 6.0, 18.0, 15.33, 0.25, key="day_time", format="%.2f")
        st.markdown(_day_timeline_svg(st.session_state["day_events"], (ph_t - 6) / 12, c),
                    unsafe_allow_html=True)
        with st.expander("Day behaviour \u2014 timing and motion of each event", expanded=False):
            st.caption("Motion belongs to the day timeline: it decides how an event "
                       "changes while it passes, not what the single-moment curve above "
                       "looks like.")
            _rm = None
            for _i, _ev in enumerate(st.session_state["day_events"]):
                _ev.setdefault("motion", "fixed in place")
                ec = st.columns([1.5, 2.5, 1.8, 0.5], vertical_alignment="center")
                ec[0].markdown(f"**{_ev['kind']}**")
                _w = ec[1].slider(f"window {_i}", 6.0, 18.0,
                                  (6 + _ev["t0"] * 12, 6 + _ev["t1"] * 12), 0.25,
                                  key=f"day_win_{_i}", label_visibility="collapsed")
                _ev["t0"], _ev["t1"] = (_w[0] - 6) / 12, (_w[1] - 6) / 12
                _opts = _day_motions_for(_ev["kind"])
                if _ev["motion"] not in _opts:
                    _ev["motion"] = _opts[0]
                _ev["motion"] = ec[2].selectbox(
                    f"motion {_i}", _opts, index=_opts.index(_ev["motion"]),
                    key=f"day_mot_{_i}", label_visibility="collapsed",
                    help="Day-event motion \u2014 how the shadow changes across its own window.")
                if ec[3].button("\u2715", key=f"day_rm_{_i}"):
                    _rm = _i
            if _rm is not None:
                st.session_state["day_events"].pop(_rm); st.rerun()
            if st.button("Clear all events", key="day_clear"):
                st.session_state["day_events"] = []; st.rerun()
        if run_day:
            st.session_state["day_ran"] = True
        if st.session_state.get("day_ran") and st.session_state["day_events"]:
            _evkey = tuple((e["kind"], round(e["t0"], 3), round(e["t1"], 3),
                            e.get("motion", "fixed in place"))
                           for e in st.session_state["day_events"])
            day = _day_run(name, T, base_G, _evkey)
            import numpy as np
            _t = np.array(day["t"])
            figd = go.Figure()
            figd.add_trace(go.Scatter(x=_t, y=day["unshaded"], name="unshaded potential",
                           line=dict(color="#B5641A", dash="dot", width=2)))
            figd.add_trace(go.Scatter(x=_t, y=day["avail"], name="available at true peak",
                           line=dict(color="#2B3238", width=2.5)))
            for _m, _ph in day["methods"].items():
                figd.add_trace(go.Scatter(x=_t, y=_ph, name=_m,
                               line=dict(color=_RUN_COLORS.get(_m, c["teal"]), width=2)))
            figd.add_vline(x=st.session_state["day_time"],
                           line=dict(color=c["amber"], width=1.5, dash="dot"))
            ui.style_fig(figd, height=300, x_title="time of day (h)", y_title="power (W)")
            figd.update_layout(legend=dict(orientation="h", y=1.1, x=0))
            st.plotly_chart(figd, width="stretch")
            _cells = "".join(f"<span style='font-weight:500'>{_m}</span>"
                             f"<span>{_v:.2f}%</span>" for _m, _v in day["energy"].items())
            st.markdown(f"<div class='bmono' style='display:grid;"
                        f"grid-template-columns:1fr .7fr;gap:6px 14px;max-width:340px;"
                        f"font-size:13px'><span style='color:{c['text_muted']}'>method</span>"
                        f"<span style='color:{c['text_muted']}'>energy captured</span>"
                        f"{_cells}</div>", unsafe_allow_html=True)
            ui.callout("Real day run: a sun-arc irradiance profile with your events, stepped "
                       "through the trackers on this panel. Dragging events and animated play "
                       "need a custom component; the timing sliders are the functional "
                       "stand-in.", "Day run — computed", "info")
        else:
            ui.callout("Add events with the chips, set their timing, then press \u201cRun the "
                       "whole day through the trackers.\u201d", "Ready to run", "info")
    ui.next_step("You have seen the curve grow extra peaks. Now look at why.",
                 P["inside"], "Look inside the panel →", key="panels")


def page_inside():
    ui.page_intro("Inside a panel",
                  "Move the operating point and watch each bypass diode switch on or off.",
                  "Explore · Inside a panel")
    last = st.session_state.get("gm_last")
    if not last:
        ui.callout("Set up a shadow on the panels page first — this page explains "
                   "that result.", "Nothing to show yet", "info")
        st.page_link(P["panels"], label="Go to the panels →")
        return
    name, irr_key, T = last["name"], last["pattern"], last["T"]
    irr = [list(e) if isinstance(e, tuple) else float(e) for e in irr_key]
    det = _sim(name, irr_key, T)
    voc = det["voc"] or 1.0
    v_op = st.slider("Terminal voltage (V)", 0.0, round(voc, 1),
                     round(float(det["gmpp"]["V"]), 1), 0.1, key="gm_vop")
    i_op = float(np.interp(v_op, det["V"], det["I"]))
    vsub, clamp = _substring_voltages(name, irr, T, i_op)

    rows = []
    for k, (entry, vk) in enumerate(zip(irr, vsub)):
        light = (sum(entry) / len(entry)) if isinstance(entry, (list, tuple)) else entry
        on = vk <= clamp + 0.2
        rows.append({"Strip": f"S{k+1}", "Light (W/m²)": round(light),
                     "Bypass diode": "on — current goes around" if on else
                     ("partial" if vk < -0.05 else "off"),
                     "Volts it adds": round(vk, 2)})

    left, right = st.columns([1, 1.3], gap="large")
    with left:
        ui.kpi_row([("Current", f"{i_op:.2f} A"), ("Power", f"{v_op * i_op:.1f} W")])
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
        ui.callout("A bypass diode is a switch, not a dimmer. When a shaded strip "
                   "cannot carry the current its neighbours want, the diode turns on "
                   "and the strip drops out of the voltage sum. That switch is what "
                   "puts the steps in the curve. A strip is one substring — the group of "
                   "cells that shares a bypass diode; the Simulator calls it a substring.",
                   "Why the curve has steps", "info")
    with right:
        fig = go.Figure(go.Scatter(x=det["V"], y=det["I"], name="Current",
                                   line=dict(color="#2C7FA0", width=3)))
        fig.add_vline(x=v_op, line=dict(color=ui.PEAK_COLORS["operating"], width=2, dash="dash"))
        ui.style_fig(fig, height=360, x_title="Voltage (V)", y_title="Current (A)")
        fig.update_layout(showlegend=False)
        st.plotly_chart(fig, width="stretch")
        ui.engine_badge("validated")

    ui.next_step("You know why the curve has several peaks. Now watch each method "
                 "try to find the tallest.", P["run"], "Run the trackers →", key="inside")


def page_system():
    ui.page_intro("Whole system",
                  "Planned extension: electrical interaction across several modules, "
                  "strings and array configurations.", "Explore · Whole system")
    ui.not_built("Whole-system array analysis",
                 "Every other page models one module and, in the Simulator, scales its power "
                 "to an array. This page will solve the array itself — series/parallel "
                 "mismatch between modules and strings, then DC/DC and inverter losses — "
                 "and separate what shading cost from what tracking cost. It needs a string "
                 "and inverter model that does not exist yet, so nothing is shown rather "
                 "than an estimate.")
    ui.callout("Nothing on this page is computed yet. The array figures you can see today "
               "are on the Simulator, where array power is the module result multiplied by "
               "the array scaling.", "Why this page is empty", "info")
    ui.next_step("The tracking result these figures would rest on is measured under Testing.",
                 P["compare"], "Open the comparison →", key="system")


# =========================================================================== #
# Simulator — your existing app, unchanged
# =========================================================================== #
# =========================================================================== #
# Simulator · Set up a panel  (the "Bench") — the SIMPLIFIED engine (app.py),
# with an editable datasheet.  Matches the Bench mockup; sized to the 1440 grid.
# =========================================================================== #
def _bench_apply_preset():
    p = sim.MODULE_PRESETS.get(st.session_state.get("bench_preset"))
    if not p:
        return
    for f in sim.DS_FIELDS:
        st.session_state[f"bench_{f}"] = int(p[f]) if f == "Ns" else float(p[f])


def _bench_init():
    st.session_state.setdefault("bench_preset", sim.DEFAULT_PRESET)
    if "bench_Isc" not in st.session_state:
        _bench_apply_preset()
    st.session_state.setdefault("bench_nsub", 3)
    st.session_state.setdefault("bench_mstr", 5)
    st.session_state.setdefault("bench_pstr", 3)
    st.session_state.setdefault("bench_obj", "Custom")
    st.session_state.setdefault("bench_baseG", 910)
    st.session_state.setdefault("bench_T", 43)


def _bench_pill(obj):
    n = int(st.session_state.bench_nsub)
    g = float(st.session_state.bench_baseG)
    st.session_state.bench_obj = obj
    if obj == "Pole":
        vals = [g] * n
        vals[min(1, n - 1)] = 240.0
    elif obj == "Cloud":
        vals = [g * f for f in (0.9, 0.7, 0.5, 0.45, 0.4, 0.35)][:n]
    elif obj == "Soiling":
        vals = [g * 0.7] * n
    else:
        return
    for i, v in enumerate(vals):
        st.session_state[f"bench_s{i}"] = float(round(v))


def _bench_obj_change():
    obj = st.session_state.bench_obj
    n = int(st.session_state.bench_nsub)
    g = float(st.session_state.bench_baseG)
    if obj == "Pole":
        vals = [g] * n
        vals[min(1, n - 1)] = 240.0
    elif obj == "Cloud":
        vals = [g * f for f in (0.9, 0.7, 0.5, 0.45, 0.4, 0.35)][:n]
    elif obj == "Soiling":
        vals = [g * 0.7] * n
    else:
        return
    for i, v in enumerate(vals):
        st.session_state[f"bench_s{i}"] = float(round(v))


@st.cache_data(show_spinner=False)
def _bench_sim(ds_key, T, sub_key):
    ds = dict(ds_key); ds["Ns"] = int(ds["Ns"])
    ref = sim.datasheet_to_ref(ds)
    cps = ds["Ns"] // len(sub_key)
    return sim.module_iv(list(sub_key), float(T), cps, ref)


def _bench_record(label, ds, n_sub, m_str, p_str, base_G, T, sub_irr, res):
    """One saved scenario, in the same shape app.py's Saved-scenarios page reads.
    The extra `bench` block is what Load needs to put every control back."""
    return dict(
        label=label,
        V=[float(x) for x in res["V"]], I=[float(x) for x in res["I"]],
        P=[float(x) for x in res["P"]], gmpp=[float(x) for x in res["gmpp"]],
        config={
            "scenario_name": label,
            "module": st.session_state.get("bench_preset", "—"),
            "datasheet": {k: ds[k] for k in sim.DS_FIELDS},
            "temperature_C": int(T),
            "base_irradiance_Wm2": int(base_G),
            "substring_irradiance_Wm2": [float(x) for x in sub_irr],
            "topology": {"substring_zones": int(n_sub),
                         "modules_per_string": int(m_str),
                         "parallel_strings": int(p_str)},
            "results": {"Vmpp_V": round(float(res["gmpp"][0]), 3),
                        "Impp_A": round(float(res["gmpp"][1]), 3),
                        "Pmax_W": round(float(res["gmpp"][2]), 3),
                        "n_local_peaks": len(res["lmpps"])},
            "model": {"type": "interactive simulator — single-diode + per-substring bypass",
                      "note": "Exploratory engine. Not the validated engine behind the "
                              "benchmark figures."},
            "bench": {"preset": st.session_state.get("bench_preset"),
                      "obj": st.session_state.get("bench_obj", "Custom"),
                      "ds": {k: ds[k] for k in sim.DS_FIELDS},
                      "nsub": int(n_sub), "mstr": int(m_str), "pstr": int(p_str),
                      "baseG": int(base_G), "T": int(T),
                      "sub_irr": [float(x) for x in sub_irr]},
        })


def _bench_label():
    """Whatever the user typed, else something that identifies the scenario."""
    name = (st.session_state.get("bench_scen_name") or "").strip()
    if name:
        return name
    preset = str(st.session_state.get("bench_preset", "module")).split(" (")[0]
    return f"{preset} · {st.session_state.get('bench_obj', 'Custom')}"


def _bench_to_dataset(ds, n_sub, m_str, p_str, base_G, T):
    """Make a dataset reads app.py's own state keys — copy this bench setup into them
    so 'generate a dataset from this module' is true rather than a label."""
    for f, v in ds.items():
        st.session_state[f"p_{f}"] = int(v) if f == "Ns" else float(v)
    st.session_state["ds_name"] = str(st.session_state.get("bench_preset", "Bench module"))
    st.session_state["topo_nsub"] = int(n_sub)
    st.session_state["topo_mstr"] = int(m_str)
    st.session_state["topo_pstr"] = int(p_str)
    st.session_state["base_val"] = int(base_G)
    st.session_state["temp_c"] = int(T)


def _bench_save(label, ds, n_sub, m_str, p_str, base_G, T, sub_irr, res):
    """Append to the one shared scenario list (`frozen`) that Saved scenarios reads."""
    st.session_state.setdefault("frozen", [])
    st.session_state.frozen.append(
        _bench_record(label, ds, n_sub, m_str, p_str, base_G, T, sub_irr, res))
    st.session_state.frozen = st.session_state.frozen[-12:]


def _bench_load(rec):
    """Put a saved scenario's controls back on Set up a panel, and mark it as run."""
    b = (rec.get("config") or {}).get("bench")
    if not b:
        return False
    for f, v in b["ds"].items():
        st.session_state[f"bench_{f}"] = int(v) if f == "Ns" else float(v)
    if b.get("preset"):
        st.session_state["bench_preset"] = b["preset"]
    st.session_state["bench_obj"] = b.get("obj", "Custom")
    st.session_state["bench_scen_name"] = rec.get("label", "")
    st.session_state["bench_nsub"] = int(b["nsub"])
    st.session_state["bench_mstr"] = int(b["mstr"])
    st.session_state["bench_pstr"] = int(b["pstr"])
    st.session_state["bench_baseG"] = int(b["baseG"])
    st.session_state["bench_T"] = int(b["T"])
    for i, g in enumerate(b["sub_irr"]):
        st.session_state[f"bench_s{i}"] = float(g)
    ds_key = tuple(sorted({k: (int(v) if k == "Ns" else float(v))
                           for k, v in b["ds"].items()}.items()))
    st.session_state["bench_ran"] = (ds_key, int(b["T"]),
                                     tuple(float(x) for x in b["sub_irr"]), int(b["nsub"]))
    return True


def _bench_css(c):
    st.markdown(("<style>"
        # section-title + mono helpers
        ".bh{font-family:%(disp)s;font-weight:700;font-size:16px;color:%(text)s;}"
        ".bmono,.bmono *{font-family:%(mono)s;}"
        # cards: warm-paper, 1px border, 14px radius (matches the mockup)
        "div.st-key-benchroot div[data-testid=\"stVerticalBlockBorderWrapper\"]{"
        "border:1px solid %(border)s!important;border-radius:14px!important;"
        "background:%(surface)s!important;}"
        # inputs: clean mono, faint fill, NO +/- steppers
        "div.st-key-benchroot [data-testid=\"stNumberInput\"] button{display:none!important;}"
        "div.st-key-benchroot input{background:%(surface)s!important;"
        "border-color:%(border_strong)s!important;font-family:%(mono)s!important;font-size:13px!important;}"
        "div.st-key-benchroot [data-testid=\"stWidgetLabel\"] p{font-family:%(mono)s!important;"
        "font-size:11.5px!important;color:%(muted)s!important;}"
        # results tab bar: underline the active tab, drop the pill chrome
        "div.st-key-benchroot [data-baseweb=\"tab-list\"]{gap:2px;border-bottom:1px solid %(border)s;}"
        "div.st-key-benchroot [data-baseweb=\"tab\"]{font-size:13.5px;padding:9px 13px;color:%(muted)s;}"
        "div.st-key-benchroot [data-baseweb=\"tab\"][aria-selected=\"true\"]{color:%(teal)s;}"
        "div.st-key-benchroot [data-baseweb=\"tab-highlight\"]{background:%(teal)s;}"
        # inline dark Run button
        "div.st-key-benchrun button{background:%(text)s!important;color:#fff!important;"
        "border:none!important;height:44px;font-weight:600;}"
        "div.st-key-benchrun button p{color:#fff!important;}"
        # pill-shaped shading-object buttons
        "div.st-key-benchpills button{border-radius:999px!important;height:34px;}"
        # sub-tab row links
        "div.st-key-benchtabs a{padding:10px 14px;border-radius:0;font-size:14px;"
        "color:%(text_body)s!important;text-decoration:none;border-bottom:3px solid transparent;}"
        "div.st-key-benchtabs a p{margin:0;}"
        "</style>") % {"disp": ui.FONTS["display"], "mono": ui.FONTS["mono"],
                       "text": c["text"], "text_body": c["text_body"], "muted": c["text_muted"],
                       "border": c["border"], "border_strong": c["border_strong"],
                       "surface": c["surface"], "teal": c["teal"]},
        unsafe_allow_html=True)


def _bh(title):
    return f"<span class='bh'>{title}</span>"


def page_sim_setup():
    _bench_init()
    c = ui.T()
    _bench_css(c)

    with st.container(key="benchroot"):
        # ---- header sub-tabs (Saved / Make a dataset shown as coming) ----
        with st.container(key="benchtabs"):
            tt = st.columns([1.3, 1.7, 1.7, 5], vertical_alignment="center")
            tt[0].markdown(f"<span style='padding:10px 14px;font-size:14px;font-weight:600;"
                           f"border-bottom:3px solid {c['teal']};color:{c['text']}'>Set up a panel"
                           f"</span>", unsafe_allow_html=True)
            tt[1].page_link(P["sim_saved"], label="Saved scenarios")
            tt[2].page_link(P["sim_dataset"], label="Make a dataset")

        # ---- bench-mode banner ----
        with st.container(border=True):
            bb = st.columns([0.85, 5, 1.7], vertical_alignment="center")
            bb[0].markdown(
                f"<span class='bmono' style='padding:5px 10px;border-radius:999px;"
                f"background:{c['teal_tint']};color:{c['teal']};font-size:11px;"
                f"letter-spacing:.06em;text-transform:uppercase'>Interactive simulator</span>",
                unsafe_allow_html=True)
            bb[1].markdown(f"<span style='font-size:13.5px;color:{c['text_body']}'>Every number "
                           f"shown and editable, on a datasheet module you type in yourself. "
                           f"This is a <b>different engine</b> from Explore and Testing, which "
                           f"run the validated engine on CEC modules — the two do not share a "
                           f"scenario.</span>", unsafe_allow_html=True)
            with bb[2]:
                st.page_link(P["panels"], label="The panels (validated) →")

        left, mid, right = st.columns([0.92, 1.55, 1.05], gap="medium")

        # ============================================================= LEFT
        with left:
            with st.container(border=True):
                hd = st.columns([3, 1], vertical_alignment="center")
                hd[0].markdown(_bh("Datasheet"), unsafe_allow_html=True)
                hd[1].button("Reset", key="bench_reset", on_click=_bench_apply_preset,
                             use_container_width=True)
                st.selectbox("Module preset",
                             list(sim.MODULE_PRESETS) + ["Nanum target module — [AWAITING SPEC]"],
                             key="bench_preset", on_change=_bench_apply_preset,
                             label_visibility="collapsed")
                with st.expander("View module details", expanded=False):
                    fields = [("Isc", "Isc  A"), ("Voc", "Voc  V"), ("Imp", "Imp  A"),
                              ("Vmp", "Vmp  V"), ("Ns", "Ns  cells"), ("n", "n  ideality"),
                              ("alpha_isc", "α_Isc  A/K"), ("beta_voc", "β_Voc  V/K"),
                              ("Rs", "Rs  Ω"), ("Rsh", "Rsh  Ω")]
                    for a, b in zip(fields[0::2], fields[1::2]):
                        g1, g2 = st.columns(2)
                        for col, (f, lab) in ((g1, a), (g2, b)):
                            if f == "Ns":
                                col.number_input(lab, 1, 200, key="bench_Ns", step=1)
                            else:
                                col.number_input(lab, key=f"bench_{f}",
                                                 format="%.4g" if f == "alpha_isc" else "%g")
                    _dsx = {f: st.session_state[f"bench_{f}"] for f in sim.DS_FIELDS}
                    _dsx["Ns"] = int(_dsx["Ns"])
                    warns = sim.validate_datasheet(_dsx, int(st.session_state.bench_nsub))
                    if warns:
                        st.markdown(f"<div style='padding:9px 11px;background:{c['amber_tint']};"
                                    f"border-radius:8px;font-size:12px;line-height:1.45;"
                                    f"color:{c['amber_text']}'>{' '.join(warns)}</div>",
                                    unsafe_allow_html=True)
                    else:
                        st.markdown(f"<div style='padding:9px 11px;background:{c['amber_tint']};"
                                    f"border-radius:8px;font-size:12px;line-height:1.45;"
                                    f"color:{c['amber_text']}'>Checks run as you type: Imp ≤ Isc, "
                                    f"Vmp ≤ Voc, fill factor under 1, β negative.</div>",
                                    unsafe_allow_html=True)
                ds = {f: st.session_state[f"bench_{f}"] for f in sim.DS_FIELDS}
                ds["Ns"] = int(ds["Ns"])

            with st.container(border=True):
                st.markdown(_bh("Module configuration"), unsafe_allow_html=True)
                n_sub = int(st.number_input("substrings (bypass zones)", 1, 12,
                                            key="bench_nsub", step=1))
                divides = ds["Ns"] % n_sub == 0
                if divides:
                    st.markdown(f"<div class='bmono' style='font-size:12px;color:{c['teal']}'>"
                                f"{ds['Ns'] // n_sub} cells per substring · divides cleanly ✓"
                                f"</div>", unsafe_allow_html=True)
                else:
                    st.markdown(f"<div class='bmono' style='font-size:12px;color:{c['red']}'>"
                                f"{ds['Ns']} ÷ {n_sub} does not divide — pick a divisor of "
                                f"{ds['Ns']}.</div>", unsafe_allow_html=True)
                st.markdown(f"<div style='font-size:12px;line-height:1.45;color:{c['text_muted']}'>"
                            f"The cell count must divide by the substring count, so only the "
                            f"divisors that work are valid. This is what the simulated "
                            f"curve is computed for.</div>", unsafe_allow_html=True)

            with st.container(border=True):
                st.markdown(_bh("Array scaling"), unsafe_allow_html=True)
                a1, a2 = st.columns(2)
                m_str = int(a1.number_input("modules per string", 1, 40,
                                            key="bench_mstr", step=1))
                p_str = int(a2.number_input("parallel strings", 1, 40,
                                            key="bench_pstr", step=1))
                st.markdown(f"<div style='font-size:12px;line-height:1.45;"
                            f"color:{c['text_muted']}'>Array scaling multiplies the reported "
                            f"array power by {m_str * p_str} modules. It does not change the "
                            f"P–V curve: this simulator models one module and scales, it "
                            f"does not solve series/parallel mismatch across an array."
                            f"</div>", unsafe_allow_html=True)

        for i in range(n_sub):
            st.session_state.setdefault(f"bench_s{i}", float(st.session_state.bench_baseG))

        # ============================================================= CENTER
        with mid:
            with st.container(border=True):
                ir = st.columns([2.2, 2.8], vertical_alignment="center")
                ir[0].markdown(_bh("Irradiance per substring") +
                               f"<span style='font-size:12.5px;color:{c['text_muted']};"
                               f"margin-left:8px'>type exact values, or drop a shading object "
                               f"on it</span>", unsafe_allow_html=True)
                with ir[1]:
                    st.segmented_control("Shading object",
                                         ["Pole", "Cloud", "Soiling", "Custom"],
                                         key="bench_obj", on_change=_bench_obj_change,
                                         label_visibility="collapsed")
                # one inline row: S inputs · spacer · base G · T · Run
                row = st.columns([1] * n_sub + [1.1, 1, 0.9, 2.4],
                                 vertical_alignment="bottom")
                sub_irr = []
                for i in range(n_sub):
                    v = row[i].number_input(f"S{i+1} W/m²", 0, 1200, key=f"bench_s{i}", step=10)
                    sub_irr.append(float(v))
                base_G = int(row[n_sub + 1].number_input("base G", 100, 1200,
                                                         key="bench_baseG", step=10))
                T = int(row[n_sub + 2].number_input("T °C", -10, 80, key="bench_T", step=1))
                with row[n_sub + 3]:
                    with st.container(key="benchrun"):
                        run_clicked = st.button("Run simulation", key="bench_run_btn",
                                                use_container_width=True)
                # coloured substring bands
                bw = 104
                bands = [f"<svg viewBox='0 0 {bw*n_sub} 56' style='width:100%;height:56px;"
                         f"margin-top:10px'>"]
                for i, g in enumerate(sub_irr):
                    t = max(0.0, min(1.0, g / max(base_G, 1)))
                    col = f"rgb({int(74+160*t)},{int(69+107*t)},{int(53-5*t)})"
                    bands.append(f"<rect x='{i*bw}' y='6' width='{bw-4}' height='44' fill='{col}'/>")
                    bands.append(f"<text x='{i*bw+12}' y='34' font-family='IBM Plex Mono,monospace' "
                                 f"font-size='12' fill='{'#2B2A20' if t>0.5 else '#F0EDE4'}'>"
                                 f"S{i+1} {int(g)}</text>")
                bands.append("</svg>")
                st.markdown("".join(bands), unsafe_allow_html=True)

            # The Run button owns the simulation. `bench_ran` holds the inputs of the
            # last run, and everything below is drawn from those — never from inputs
            # the user has changed but not yet run.
            ds_key = tuple(sorted(ds.items()))
            cur_sig = (ds_key, int(T), tuple(float(x) for x in sub_irr), int(n_sub))
            if run_clicked and divides:
                st.session_state["bench_ran"] = cur_sig
            ran = st.session_state.get("bench_ran")

            if not divides:
                with st.container(border=True):
                    ui.callout("Fix the module configuration (cell count must divide by "
                               "the substring count) and run again.", "Topology error", "limit")
                res = None
            elif ran is None:
                with st.container(border=True):
                    ui.callout("Set the datasheet, module configuration and irradiance, "
                               "then press “Run simulation” to compute the curve.",
                               "No result yet", "info")
                res = None
            else:
                r_ds_key, r_T, r_sub, r_nsub = ran
                r_ds = dict(r_ds_key); r_ds["Ns"] = int(r_ds["Ns"])
                res = _bench_sim(r_ds_key, r_T, r_sub)
                if ran != cur_sig:
                    ui.callout("The inputs above have changed since this result was "
                               "computed. Press “Run simulation” to update it.",
                               "Showing the last run", "caveat")
                with st.container(border=True):
                    tabs = st.tabs(["I–V / P–V", "Substrings", "Peaks", "Cell map",
                                    "Parametric sweep"])
                    with tabs[0]:
                        st.caption("800-point current grid · 256-point export")
                        Vm, Im, Pm = res["gmpp"]
                        fig = go.Figure()
                        fig.add_trace(go.Scatter(x=res["V"], y=res["I"], name="I–V",
                                                 line=dict(color="#2C7FA0", width=2.5)))
                        fig.add_trace(go.Scatter(x=res["V"], y=res["P"], name="P–V", yaxis="y2",
                                                 line=dict(color=c["amber"], width=2.5)))
                        fig.add_trace(go.Scatter(x=[Vm], y=[Pm], mode="markers+text", name="GMPP",
                                                 yaxis="y2", text=["GMPP"], textposition="top center",
                                                 marker=dict(color=c["amber"], size=11)))
                        if res["lmpps"]:
                            fig.add_trace(go.Scatter(
                                x=[v for v, i, p in res["lmpps"]],
                                y=[p for v, i, p in res["lmpps"]], mode="markers", name="LMPP",
                                yaxis="y2", marker=dict(color="rgba(0,0,0,0)", size=10,
                                                        line=dict(color="#8A9098", width=2))))
                        ui.style_fig(fig, height=330, x_title="terminal voltage  V")
                        fig.update_layout(yaxis=dict(title="I  A"),
                                          yaxis2=dict(title="P  W", overlaying="y", side="right",
                                                      showgrid=False))
                        st.plotly_chart(fig, width="stretch")

                        e = st.columns(5)
                        if e[0].button("Freeze this curve", key="bench_freeze",
                                       use_container_width=True,
                                       help="Save it to Saved scenarios for comparison"):
                            _bench_save(_bench_label(), r_ds, r_nsub, m_str, p_str,
                                        base_G, r_T, r_sub, res)
                            st.toast("Saved to Saved scenarios.")
                        csv = "V,I,P\n" + "\n".join(
                            f"{v:.5g},{i:.5g},{p:.5g}"
                            for v, i, p in zip(res["V"], res["I"], res["P"]))
                        e[1].download_button("Curve CSV", csv, "curve.csv", "text/csv",
                                             use_container_width=True)
                        import json
                        cfg = json.dumps(dict(datasheet=r_ds, module_configuration=dict(
                            substrings=r_nsub), array_scaling=dict(
                            modules_per_string=m_str, parallel_strings=p_str),
                            sub_irradiance=list(r_sub), base_G=base_G, T_C=r_T,
                            engine="interactive simulator — single-diode + per-substring "
                                   "bypass (not the validated engine)"), indent=2)
                        e[2].download_button("Config JSON", cfg, "config.json",
                                             "application/json", use_container_width=True)
                        try:
                            import io
                            from scipy.io import savemat
                            buf = io.BytesIO()
                            savemat(buf, {"V": np.asarray(res["V"]), "I": np.asarray(res["I"]),
                                          "P": np.asarray(res["P"]),
                                          "gmpp": np.asarray(res["gmpp"], float)})
                            e[3].download_button(".mat", buf.getvalue(), "curve.mat",
                                                 use_container_width=True)
                        except Exception:
                            e[3].button(".mat", disabled=True, use_container_width=True,
                                        help="scipy not available")
                        e[4].button("Figure SVG", disabled=True, use_container_width=True,
                                    help="Server-side SVG export needs kaleido + Chrome")

                    with tabs[1]:
                        rows = [{"Substring": f"S{i+1}", "Irradiance (W/m²)": int(g),
                                 "Bypass at GMPP": "active" if res["bypassed"][i] else "off"}
                                for i, g in enumerate(r_sub)]
                        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
                        ui.legend_note("A substring is bypassed when the GMPP current exceeds "
                                       "its own short-circuit current.")

                    with tabs[2]:
                        peaks = [("GMPP",) + tuple(res["gmpp"])] + \
                                [(f"LMPP {i+1}",) + tuple(pk) for i, pk in enumerate(res["lmpps"])]
                        st.dataframe(pd.DataFrame(
                            [{"Peak": nm, "V": round(v, 2), "I": round(i, 2), "P (W)": round(p, 1)}
                             for nm, v, i, p in peaks]), hide_index=True, width="stretch")

                    with tabs[3]:
                        grid = sim.build_cell_grid(list(r_sub), r_ds["Ns"] // r_nsub)
                        hm = go.Figure(go.Heatmap(z=grid, colorscale="YlOrBr", showscale=True,
                                                  colorbar=dict(title="W/m²")))
                        ui.style_fig(hm, height=300)
                        hm.update_yaxes(autorange="reversed")
                        st.plotly_chart(hm, width="stretch")
                        ui.legend_note("Each substring is a row band (this engine holds one "
                                       "irradiance per strip).")

                    with tabs[4]:
                        ui.not_built("Parametric sweep",
                                     "Sweep a module across a temperature × irradiance matrix "
                                     "and overlay the curves. The Analysis sweep can be moved "
                                     "here — flagged so it is not faked.")

        # ============================================================= RIGHT
        with right:
            if res is not None:
                Vm, Im, Pm = res["gmpp"]
                Voc, Isc = res["Voc"], res["Isc"]
                ff = Pm / (Voc * Isc) if Voc * Isc > 0 else 0.0
                allkw = Pm * m_str * p_str / 1000.0
                with st.container(border=True):
                    st.markdown(_bh("Result"), unsafe_allow_html=True)
                    grid_items = [("Pmax", f"{Pm:.1f} W"), ("Vmpp", f"{Vm:.1f} V"),
                                  ("Impp", f"{Im:.2f} A"), ("Voc", f"{Voc:.1f} V"),
                                  ("Isc", f"{Isc:.2f} A"), ("fill factor", f"{ff:.2f}"),
                                  ("local peaks", str(len(res["lmpps"]))),
                                  ("array (scaled)", f"{allkw:.2f} kW")]
                    cells = "".join(
                        f"<span style='color:{c['text_muted']}'>{k}</span>"
                        f"<span style='font-weight:500;color:{c['text']}'>{v}</span>"
                        for k, v in grid_items)
                    st.markdown(f"<div class='bmono' style='margin-top:10px;display:grid;"
                                f"grid-template-columns:repeat(2,minmax(0,1fr));gap:8px 12px;"
                                f"font-size:13px'>{cells}</div>", unsafe_allow_html=True)
                    chips = "".join(
                        f"<span style='padding:4px 9px;border-radius:6px;"
                        f"background:{c['amber_tint'] if res['bypassed'][i] else c['muted_fill']};"
                        f"color:{c['amber_text'] if res['bypassed'][i] else c['text']}'>"
                        f"D{i+1} {'active' if res['bypassed'][i] else 'off'}</span>"
                        for i in range(r_nsub))
                    st.markdown(f"<div class='bmono' style='margin-top:10px;padding-top:10px;"
                                f"border-top:1px solid {c['border']};display:flex;gap:8px;"
                                f"flex-wrap:wrap;font-size:12.5px'>{chips}</div>",
                                unsafe_allow_html=True)
                    st.markdown(f"<div style='margin-top:10px;font-size:12px;line-height:1.45;"
                                f"color:{c['text_muted']}'>Pmax, Vmpp, Impp, Voc and Isc are "
                                f"for one module. <b>Array (scaled)</b> is that module power "
                                f"multiplied by {m_str} modules × {p_str} strings — "
                                f"array scaling does not change the curve.</div>",
                                unsafe_allow_html=True)

                with st.container(border=True):
                    st.markdown(_bh("What happened"), unsafe_allow_html=True)
                    st.markdown(f"<p style='margin:8px 0 0 0;font-size:13px;line-height:1.55;"
                                f"color:{c['text_body']}'>{sim.what_happened(res, list(r_sub))}</p>",
                                unsafe_allow_html=True)
                    st.markdown(f"<div class='bmono' style='margin-top:8px;font-size:11px;"
                                f"color:{c['text_faint']}'>written from the result state, "
                                f"not a stored template</div>", unsafe_allow_html=True)

                with st.container(border=True):
                    st.markdown(_bh("Do something with it"), unsafe_allow_html=True)
                    st.text_input("Scenario name", key="bench_scen_name",
                                  placeholder="e.g. 60-cell · pole at noon")
                    with st.container(key="next-benchsend"):
                        if st.button("Save to Saved scenarios", key="bench_save",
                                     type="primary", use_container_width=True):
                            _bench_save(_bench_label(), r_ds, r_nsub, m_str, p_str,
                                        base_G, r_T, r_sub, res)
                            st.switch_page(P["sim_saved"])
                    if st.button("Use this module for a dataset", key="bench_to_dataset",
                                 use_container_width=True,
                                 help="Copies this datasheet, substring count and "
                                      "conditions into Make a dataset"):
                        _bench_to_dataset(r_ds, r_nsub, m_str, p_str, base_G, r_T)
                        st.switch_page(P["sim_dataset"])
                    st.page_link(P["sim_saved"], label="Saved scenarios")
                    # The trackers run the validated engine on a CEC module; this bench
                    # runs the interactive engine on a datasheet. Say so rather than
                    # offering a "send" that cannot carry anything across.
                    st.markdown(
                        f"<div style='margin-top:10px;padding-top:10px;border-top:1px solid "
                        f"{c['border']};font-size:12px;line-height:1.5;color:{c['text_muted']}'>"
                        f"Scenarios for the trackers come from <b>Explore · The panels</b>, "
                        f"which runs the validated engine on a CEC module. A bench curve "
                        f"cannot be sent there — the two engines take different module "
                        f"definitions.</div>", unsafe_allow_html=True)
                    st.page_link(P["panels"], label="Build a scenario for the trackers →")

            # engine badge — the exact red "which model drew this" card
            st.markdown(
                "<div style='background:#FBEFEE;border:1px solid #E0A9A4;border-radius:14px;"
                "padding:14px 18px'>"
                "<div style='font-size:11.5px;font-weight:600;letter-spacing:.05em;"
                "text-transform:uppercase;color:#7A2019'>Interactive simulator — not the "
                "validated engine</div>"
                "<p style='margin:7px 0 0 0;font-size:12.5px;line-height:1.5;color:#2B3238'>"
                "This tab is for exploratory configuration and visualisation. The "
                "benchmark figures under Testing come from the validated engine.</p>"
                "<div class='bmono' style='margin-top:8px;display:flex;flex-direction:column;"
                "gap:5px;font-size:11.5px;color:#2B3238'>"
                "<span>engine: single-diode + per-substring bypass (simplified)</span>"
                "<span>reverse-bias avalanche: not modelled</span>"
                "<span>shading detail: one value per strip</span>"
                "<span style='color:#7A2019'>part-of-a-strip shading: this engine cannot show "
                "it</span></div>"
                "<p style='margin:8px 0 0 0;font-size:12.5px;line-height:1.5;color:#2B3238'>"
                "Every page states which engine drew its curve. Nothing from this tab may be "
                "quoted as a benchmark result unless it was produced by the validated engine."
                "</p></div>", unsafe_allow_html=True)


def page_sim_saved():
    ui.page_intro("Saved scenarios",
                  "Load a saved scenario back onto Set up a panel, or compare the ones "
                  "you have kept.", "Simulator")
    saved = st.session_state.get("frozen") or []
    if not saved:
        ui.callout("Nothing saved yet. On Set up a panel, run a simulation and press "
                   "“Freeze this curve” or “Save to Saved scenarios”.",
                   "No saved scenarios", "info")
        st.page_link(P["sim_setup"], label="Go to Set up a panel →")
        return

    with st.container(border=True):
        st.markdown(_bh("Load a scenario"), unsafe_allow_html=True)
        idx = list(range(len(saved) - 1, -1, -1))          # newest first
        pick = st.selectbox("Scenario", idx, key="saved_pick",
                            format_func=lambda i: f"{saved[i]['label']}  ·  "
                                                  f"{saved[i]['gmpp'][2]:.1f} W")
        rec = saved[pick]
        loadable = bool((rec.get("config") or {}).get("bench"))
        bc = st.columns([1.4, 1.4, 4])
        if bc[0].button("Load onto Set up a panel", key="saved_load", type="primary",
                        disabled=not loadable, use_container_width=True,
                        help=None if loadable else
                        "This scenario was saved without the Set-up-a-panel controls, "
                        "so it can be compared but not reloaded."):
            if _bench_load(rec):
                st.switch_page(P["sim_setup"])
        if bc[1].button("Delete this scenario", key="saved_del", use_container_width=True):
            st.session_state.frozen = [f for k, f in enumerate(saved) if k != pick]
            st.session_state.pop("saved_pick", None)
            st.rerun()
        if loadable:
            b = rec["config"]["bench"]
            st.caption(f"Restores: {b['preset']} · {b['nsub']} substrings · "
                       f"{[int(g) for g in b['sub_irr']]} W/m² · {b['T']} °C · "
                       f"{b['mstr']}×{b['pstr']} array scaling.")
        with st.expander("Full configuration", expanded=False):
            st.json(rec.get("config", {}), expanded=False)

    sim.render_scenarios_section()


def page_sim_dataset():
    ui.page_intro("Make a dataset",
                  "Generate thousands of scenarios with a fixed seed and download them.",
                  "Simulator")
    _ds = sim.current_ds()
    st.caption(f"Generating from: {st.session_state.get('ds_name', '—')} · "
               f"{_ds['Ns']} cells · {st.session_state.get('topo_nsub', '—')} substrings. "
               f"Use “Use this module for a dataset” on Set up a panel to change it.")
    sim.render_dataset_section()
    ui.callout("These scenarios are produced by the interactive simulator, not by the "
               "validated engine behind the Testing benchmarks.",
               "Which engine made this dataset", "caveat")
    ui.next_step("Generated scenarios are summarised on the data pages.",
                 P["dataset"], "Open The dataset →", key="simdataset")


# =========================================================================== #
# Testing
# =========================================================================== #
# =========================================================================== #
# Testing · Watch one run  — real trackers on a real curve (device.py), and the
# trained C3 learned seed. No numbers are typed in; everything is computed.
# =========================================================================== #
_RUN_METHODS = ["P&O", "InC", "PSO", "Model only", "Hybrid", "Perfect tracker"]
_RUN_COLORS = {"P&O": "#A32B24", "InC": "#C07D30", "PSO": "#2C7FA0",
               "Model only": "#6A7177", "Hybrid": "#16616B",
               "Perfect tracker": "#2F8F63"}
_RUN_READINGS = {"P&O": 0, "InC": 0, "Perfect tracker": 0,
                 "Model only": 6, "Hybrid": 6, "PSO": 100}
# demo scenario: a held-out validation module under a three-region shadow
_RUN_DEMO = dict(module="LG_Electronics_Inc__LG375N2K_G4", temp=43.0,
                 irr=(910.0, 300.0, 600.0))


@st.cache_resource(show_spinner=False)
def _c3_model():
    """Load the trained two-stage seed. None if sklearn / the .pkl is missing."""
    try:
        from gmppt.model import TwoStageModel
        return TwoStageModel.load("c3_two_stage_full")
    except Exception:
        return None


def _score_traj(t):
    import numpy as np
    p = np.asarray(t.p_hist, float)
    pg = float(t.p_gmpp)
    steady = p[-max(1, len(p) // 4):]
    lost = max(0.0, pg - float(steady.mean()))
    reached = lost < 0.01 * pg
    pf = float(steady.mean())
    band = max(0.01 * abs(pf), 1e-9)
    below = np.nonzero(np.abs(p - pf) > band)[0]
    steps = int(below[-1] + 1) if len(below) and below[-1] < len(p) - 1 else 0
    return dict(reached=bool(reached), steps=int(steps), lost=float(lost),
                v_hist=[float(x) for x in t.v_hist],
                p_hist=[float(x) for x in t.p_hist])


@st.cache_data(show_spinner=True)
def _run_scenario(module, temp, irr_key):
    import numpy as np
    from gmppt import tracking as trk, trackers as trkx, pso as pso
    from gmppt.scenarios import Scenario
    irr = [list(e) if isinstance(e, tuple) else float(e) for e in irr_key]
    sc = Scenario(module, float(temp), "whole_substring", irr, False)
    base = trk.trajectory_for(sc)
    out = dict(V=[float(x) for x in base.V], P=[float(x) for x in base.P],
               v_oc=float(base.v_oc), v_gmpp=float(base.v_gmpp),
               p_gmpp=float(base.p_gmpp), n_peaks=int(base.n_peaks), methods={})

    def run(name, fn, **kw):
        t = trk.trajectory_for(sc); fn(t, **kw); out["methods"][name] = _score_traj(t)

    run("P&O", trk.perturb_and_observe)
    run("InC", trkx.incremental_conductance)
    run("PSO", pso.particle_swarm)
    run("Perfect tracker", trk.parked_at_gmpp)

    model = _c3_model()
    out["has_model"] = model is not None
    out["seed"] = None
    if model is not None:
        from gmppt import hybrid as hyb
        from gmppt.features import extract_features, PROBE_FRACTIONS
        ts = trk.trajectory_for(sc)
        v_seed, region = hyb.seed_voltage(ts, model, float(temp))
        xs = extract_features(trk.trajectory_for(sc).step, base.v_oc,
                              module, float(temp)).reshape(1, -1)
        proba = [float(p) for p in model.classifier.predict_proba(xs)[0]]
        out["seed"] = dict(v_seed=float(v_seed), region=int(region), proba=proba,
                           probes=[float(f) * base.v_oc for f in PROBE_FRACTIONS])
        run("Model only", hyb.make_seed_only(model), temp_c=float(temp))
        run("Hybrid", hyb.make_hybrid(model), temp_c=float(temp))
    return out


def page_run():
    import numpy as np
    c = ui.T()
    disp, mono = ui.FONTS["display"], ui.FONTS["mono"]
    st.markdown(f"<style>.bh{{font-family:{disp};font-weight:700;color:{c['text']};}}"
                f".bmono,.bmono *{{font-family:{mono};}}"
                f"div.st-key-runtabs a{{padding:10px 14px;font-size:14px;"
                f"color:{c['text_body']}!important;text-decoration:none;}}"
                f"div.st-key-runtabs a p{{margin:0;}}"
                f"div.st-key-seeall a{{height:44px;display:flex;align-items:center;"
                f"justify-content:center;border-radius:8px;background:{c['teal']};"
                f"color:#fff!important;font-weight:600;text-decoration:none;}}"
                f"div.st-key-seeall a p{{margin:0;color:#fff!important;}}"
                f"</style>", unsafe_allow_html=True)

    # ---- sub-tabs ----
    with st.container(key="runtabs"):
        tt = st.columns([1.3, 1.5, 1.4, 5], vertical_alignment="center")
        tt[0].markdown(f"<span style='padding:10px 14px;font-size:14px;font-weight:600;"
                       f"border-bottom:3px solid {c['teal']};color:{c['text']}'>Watch one run"
                       f"</span>", unsafe_allow_html=True)
        tt[1].page_link(P["compare"], label="Compare methods")
        tt[2].page_link(P["moving"], label="Dynamic irradiance")

    _sc = st.session_state.get("scenario")
    if _sc:
        _irrkey = tuple(tuple(float(x) for x in e) if isinstance(e, list) else float(e)
                        for e in _sc["irr"])
        d = _run_scenario(_sc["module"], _sc["temp"], _irrkey)
        scc = st.columns([5, 1.3], vertical_alignment="center")
        scc[0].caption(f"Scenario sent from Explore: {_sc.get('label', 'your panel')}  ·  "
                       f"{_sc['module']}  ·  {_sc['temp']:.0f} °C  ·  "
                       f"{[int(g) if not isinstance(g, list) else [int(x) for x in g] for g in _sc['irr']]} W/m²")
        if scc[1].button("Use the example instead", key="run_use_example",
                         use_container_width=True):
            st.session_state.pop("scenario", None); st.rerun()
    else:
        d = _run_scenario(_RUN_DEMO["module"], _RUN_DEMO["temp"], _RUN_DEMO["irr"])
        # Say plainly that this is not the user's scenario.
        ui.callout("No scenario has been sent from Explore, so this is the built-in example "
                   "(a held-out validation module under a three-region shadow). Build your "
                   "own on Explore · The panels and press “Send this panel to the trackers”.",
                   "Showing the example scenario", "info")
        st.page_link(P["panels"], label="Build your own scenario →")
    avail = [m for m in _RUN_METHODS if m in d["methods"]]

    # ---- overlay chooser ----
    oc = st.columns([0.7, 6], vertical_alignment="center")
    oc[0].markdown(f"<span style='font-size:12px;font-weight:600;letter-spacing:.05em;"
                   f"text-transform:uppercase;color:{c['text_muted']}'>Overlay</span>",
                   unsafe_allow_html=True)
    default = [m for m in ("P&O", "Hybrid") if m in avail] or avail[:1]
    sel = oc[1].segmented_control("overlay", avail, selection_mode="multi",
                                  default=default, key="run_overlay",
                                  label_visibility="collapsed") or default

    left, right = st.columns([1.55, 0.95], gap="large")

    # ============================================================= main chart
    with left:
        with st.container(border=True):
            st.markdown(_bh_run("What each method does on this curve") +
                        f"<span style='font-size:13px;color:{c['text_muted']};"
                        f"margin-left:10px'>where each method starts, what it measures, "
                        f"where it stops</span>", unsafe_allow_html=True)
            V, Pw = np.array(d["V"]), np.array(d["P"])
            fig = go.Figure()
            seed = d["seed"]
            show_seed = seed and any(m in sel for m in ("Hybrid", "Model only"))
            if show_seed:
                w = d["v_oc"] / 3.0
                r = seed["region"]
                fig.add_vrect(x0=r * w, x1=(r + 1) * w, fillcolor=c["teal"],
                              opacity=0.08, line_width=0,
                              annotation_text="predicted region",
                              annotation_position="top left",
                              annotation_font_size=11)
            fig.add_trace(go.Scatter(x=V, y=Pw, name="P–V",
                                     line=dict(color=c["teal"], width=2.5)))
            fig.add_trace(go.Scatter(x=[d["v_gmpp"]], y=[d["p_gmpp"]], mode="markers",
                                     name="GMPP", marker=dict(symbol="star", size=15,
                                     color="#F5B301", line=dict(color="#1c1300", width=.6))))
            if show_seed:
                px = seed["probes"]
                py = [float(np.interp(v, V, Pw)) for v in px]
                fig.add_trace(go.Scatter(x=px, y=py, mode="markers+text",
                              text=[f"p{i+1}" for i in range(len(px))],
                              textposition="bottom center", name="6 readings",
                              marker=dict(color=c["teal"], size=7),
                              textfont=dict(size=9, color=c["teal"])))
            for m in sel:
                r = d["methods"].get(m)
                if not r:
                    continue
                vh, ph = np.array(r["v_hist"]), np.array(r["p_hist"])
                col = _RUN_COLORS[m]
                if m in ("P&O", "InC"):
                    fig.add_trace(go.Scatter(x=vh[::6], y=ph[::6], mode="lines",
                                  line=dict(color=col, width=1.4, dash="dot"),
                                  name=m, opacity=0.7))
                    fig.add_trace(go.Scatter(x=[vh[0]], y=[ph[0]], mode="markers",
                                  marker=dict(color=col, size=8, symbol="circle-open",
                                  line=dict(width=2)), showlegend=False))
                fig.add_trace(go.Scatter(x=[vh[-1]], y=[ph[-1]], mode="markers",
                              marker=dict(color=col, size=12), name=m,
                              showlegend=m not in ("P&O", "InC")))
                lab = ("stops · %.0f W · −%.1f W" % (ph[-1], r["lost"])) if not r["reached"] \
                    else ("settles · %d steps" % r["steps"])
                fig.add_annotation(x=vh[-1], y=ph[-1], text=lab, showarrow=True,
                                   arrowhead=0, ax=0, ay=-24, font=dict(size=10, color=col))
            ui.style_fig(fig, height=400, x_title="terminal voltage  V",
                         y_title="power  W")
            fig.update_layout(legend=dict(orientation="h", y=1.06, x=0))
            st.plotly_chart(fig, width="stretch")
            ui.callout("On the uniform single-peak curve P&O reaches 99.98%. The failure "
                       "here is trapping, not a defective algorithm.", "Control", "info")

    # ============================================================= right aside
    with right:
        with st.container(border=True):
            st.markdown(_bh_run("How the model picks a starting point", 15),
                        unsafe_allow_html=True)
            if seed:
                pr = seed["proba"]
                r = seed["region"]
                bars = ""
                for i, pv in enumerate(pr):
                    fill = c["teal"] if i == r else c["text_muted"]
                    bars += (f"<div style='display:flex;align-items:center;gap:8px;"
                             f"font-family:{mono};font-size:12px'><span style='width:26px'>"
                             f"S{i+1}</span><span style='flex-grow:1;height:8px;"
                             f"background:{c['muted_fill']};border-radius:4px'>"
                             f"<span style='display:block;width:{pv*100:.0f}%;height:8px;"
                             f"background:{fill};border-radius:4px'></span></span>"
                             f"<span>{pv:.2f}</span></div>")
                st.markdown(
                    f"<div style='margin-top:8px;font-size:13px;line-height:1.5;"
                    f"color:{c['text_body']}'><b>1 · Take six readings</b> at fixed "
                    f"voltages across the curve — each costs a little output.<br>"
                    f"<b>2 · Pick a strip</b> — the model chooses which cell strip holds "
                    f"the tallest peak, instead of guessing a voltage.</div>"
                    f"<div style='margin-top:8px;padding:10px 12px;background:"
                    f"{c['muted_fill']};border-radius:8px'>{bars}</div>"
                    f"<div style='margin-top:8px;font-size:13px;line-height:1.5;"
                    f"color:{c['text_body']}'><b>3 · Place the start</b> inside strip "
                    f"S{r+1}, at {seed['v_seed']:.1f} V.<br>"
                    f"<b>4 · Hand to P&amp;O</b> — the ordinary hill-climber, unchanged; "
                    f"it just starts in the right place.<br>"
                    f"<b>5 · Safety check</b> — a bounded backup scan runs only when the "
                    f"seed is not confident.</div>", unsafe_allow_html=True)
            else:
                ui.callout("The learned seed needs the trained model "
                           "(`results/phase3/c3_two_stage.pkl`) and scikit-learn. The "
                           "classical trackers below are running on real data.",
                           "Learned seed unavailable", "limit")

        with st.container(border=True):
            st.markdown(_bh_run("This scenario, side by side", 15), unsafe_allow_html=True)
            order = [m for m in ("Hybrid", "Model only", "PSO", "P&O", "InC")
                     if m in d["methods"]]
            head = ("<span style='color:%s'></span><span style='color:%s'>found it</span>"
                    "<span style='color:%s'>steps</span><span style='color:%s'>readings"
                    "</span><span style='color:%s'>lost</span>" % ((c["text_muted"],) * 5))
            rowshtml = ""
            for m in order:
                r = d["methods"][m]
                found = ("<span style='color:%s'>yes</span>" % c["teal"]) if r["reached"] \
                    else ("<span style='color:%s'>no</span>" % c["red"])
                rowshtml += (f"<span style='font-weight:500'>{m}</span>{found}"
                             f"<span>{r['steps']}</span><span>{_RUN_READINGS.get(m,0)}</span>"
                             f"<span>{r['lost']:.1f} W</span>")
            st.markdown(f"<div class='bmono' style='margin-top:8px;display:grid;"
                        f"grid-template-columns:1.2fr .8fr .7fr .9fr .9fr;gap:6px 8px;"
                        f"font-size:12px'>{head}{rowshtml}</div>", unsafe_allow_html=True)
            with st.container(key="seeall"):
                st.page_link(P["compare"], label="One scenario proves nothing — see all 632 →")

    # ============================================================= change shading mid-run
    import math
    reloc = _load_json("phase2/relocation_comparison_pole.json")
    with st.container(border=True):
        st.markdown(_bh_run("Change the shading mid-run") +
                    f"<span style='font-size:13px;color:{c['text_muted']};margin-left:10px'>"
                    f"the tallest peak jumps to another strip — who notices?</span>",
                    unsafe_allow_html=True)
        # Only the pole single-jump experiment has been run. These are the state of the
        # experiment set, not controls — nothing here selects between results.
        ec1, ec2 = st.columns([1.5, 3])
        with ec1:
            st.markdown(
                f"<div style='font-size:11.5px;font-weight:600;letter-spacing:.05em;"
                f"text-transform:uppercase;color:{c['text_muted']}'>Available experiment</div>"
                f"<div style='margin-top:6px;font-size:13.5px;color:{c['text']}'>"
                f"<span style='color:{c['teal']}'>●</span> One shift at step 40"
                f"{'' if reloc else ' <span style=\"color:#A8AEB4\">(export missing)</span>'}"
                f"</div>", unsafe_allow_html=True)
        with ec2:
            st.markdown(
                f"<div style='font-size:11.5px;font-weight:600;letter-spacing:.05em;"
                f"text-transform:uppercase;color:{c['text_muted']}'>Planned experiments — "
                f"not run</div>"
                f"<div style='margin-top:6px;font-size:13.5px;color:#A8AEB4;display:flex;"
                f"gap:18px;flex-wrap:wrap'>"
                f"<span>○ No change</span><span>○ Pole drifts all run</span>"
                f"<span>○ Cloud passes</span></div>", unsafe_allow_html=True)
        head = ("<span style='color:%s'>method</span><span style='color:%s'>followed the peak"
                "</span><span style='color:%s'>steps to recover</span>"
                "<span style='color:%s'>energy lost in transit</span>" % ((c["text_muted"],)*4))
        if reloc:
            S = reloc["stats"]
            rows = [("Hybrid · triggered reseed", "hybrid, triggered reseed"),
                    ("Hybrid · never reseed", "hybrid, never reseed"),
                    ("Model only (seed)", "seed only"),
                    ("PSO", "PSO"), ("PSO · triggered reseed", "PSO, triggered reseed"),
                    ("P&O / InC", "P&O")]
            body = ""
            for label, key in rows:
                sm = S.get(key)
                if not sm:
                    continue
                follow = sm.get("reconv_frac", 0) >= 0.5
                med = sm.get("median")
                steps = ("—" if med is None or (isinstance(med, float) and math.isnan(med))
                         else f"{med:.0f}")
                fol = (f"<span style='color:{c['teal']}'>yes</span>" if follow
                       else f"<span style='color:{c['red']}'>no</span>")
                body += (f"<span style='font-weight:500'>{label}</span>{fol}"
                         f"<span>{steps}</span><span>{sm['energy_loss_pct']:.1f}%</span>")
            st.markdown(f"<div class='bmono' style='display:grid;"
                        f"grid-template-columns:1.7fr 1fr 1fr 1.4fr;gap:6px 10px;"
                        f"font-size:12.5px'>{head}{body}</div>", unsafe_allow_html=True)
            ht = S.get("hybrid, triggered reseed", {})
            ui.callout(
                f"Pole single-jump · {reloc['n_windows']} relocation windows, all data-validation "
                f"gates passed. Only a **triggered re-seed** follows the peak: the hybrid "
                f"recovers in ~{ht.get('median', 0):.0f} steps losing "
                f"{ht.get('energy_loss_pct', 0):.1f}%, while every stateless method — P&O, InC, "
                f"PSO, seed-only and the never-reseed hybrid — stays on the old peak (~64% lost in "
                f"transit). The drift and cloud families have not been run yet.",
                "Pole relocation — measured", "info")
        else:
            empty = "".join(f"<span style='font-weight:500'>{m}</span>"
                            f"<span style='color:{c['text_muted']}'>—</span>"
                            f"<span style='color:{c['text_muted']}'>—</span>"
                            f"<span style='color:{c['text_muted']}'>—</span>"
                            for m in ("Hybrid", "Model only", "PSO", "P&O / InC"))
            st.markdown(f"<div class='bmono' style='display:grid;"
                        f"grid-template-columns:1.2fr 1fr 1fr 1.3fr;gap:6px 10px;font-size:12.5px'>"
                        f"{head}{empty}</div>", unsafe_allow_html=True)
            ui.callout("The pattern-transition experiment has not been run. Produce "
                       "`results/phase2/relocation_comparison_pole.json` "
                       "(`phase2/p12_relocation_comparison.py`) and it appears here.",
                       "Not run yet", "caveat")
    ui.next_step("One curve proves nothing on its own. See every method on every shaded case.",
                 P["compare"], "Compare methods →", key="run")


def _bh_run(title, size=17):
    return f"<span class='bh' style='font-size:{size}px'>{title}</span>"


# Snapshot from the validation report (p7 static n=632, p9 convergence). Replace with the
# harness export once --emit exists; never compute these numbers inside the dashboard.
_SNAPSHOT = pd.DataFrame([
    ("Hybrid", 99.88, 98.6, 5, 6, 6.4),
    ("PSO", 99.9, 97.8, 62, 120, None),
    ("Model only", 99.76, 94.5, 0, 6, 6.3),
    ("P&O", 79.51, 46.2, 18, 3, 185.4),
    ("InC", 79.51, 46.2, 18, 3, 185.4),
], columns=["Method", "Energy captured (%)", "Found true peak (%)", "Steps", "Readings", "Worst case (W)"])


def _load_json(rel):
    import json
    p = _gcfg.RESULTS_DIR / rel
    try:
        return json.loads(p.read_text())
    except Exception:
        return None


def page_compare():
    import pandas as pd
    c = ui.T()
    ui.page_intro("Compare methods", "Every method on the same 632 shaded curves.", "Testing")
    tc = _load_json("phase2/tracker_comparison_val.json")
    pso = _load_json("phase2/pso_comparison_val.json")

    if not tc:
        ui.callout("Run `phase2/p7_tracker_comparison.py --split val` to produce "
                   "`results/phase2/tracker_comparison_val.json`; showing the recorded "
                   "snapshot meanwhile.", "Live export not found", "caveat")
        st.dataframe(_SNAPSHOT, hide_index=True, width="stretch")
        ui.next_step("Now see whether it holds while the irradiance changes.", P["moving"],
                     "Open dynamic irradiance →", key="compare")
        return

    R = tc["results"]
    sub = "multi_peak"           # the 632 shaded curves

    def g(m):
        b = R[m][sub]
        return dict(energy=b["steady_eff_pct"], found=b["reached_pct"],
                    steps=b["median_conv_steps"], worst=b["worst_energy_lost_w"])

    hyb, mod, po, inc = g("hybrid, bounded"), g("seed only"), g("P&O"), g("InC")
    pso_row, pso_read = None, 120
    if pso and pso.get("pso_sweep"):
        best = max(pso["pso_sweep"], key=lambda e: e["all_reached_pct"])
        pso_row = dict(energy=best["all_steady_eff_pct"], found=best["all_reached_pct"],
                       steps=None, worst=best["all_worst_energy_lost_w"])
        pso_read = int(best["sequential_steps"])

    d_pt = hyb["energy"] - po["energy"]
    x_read = pso_read / 6.0
    ui.kpi_row([
        ("Highest energy captured", f"Hybrid · {hyb['energy']:.2f}%",
         "power captured relative to available power", "hero"),
        ("Energy captured vs P&O", f"+{d_pt:.1f} pt", "same scenarios, same conditions"),
        ("Readings per cycle vs PSO", f"{x_read:.0f}× fewer",
         f"{pso_read} readings against 6"),
    ], weights=[1.4, 1, 1])

    left, right = st.columns([1.5, 1], gap="large")
    with left:
        tbl = [("Hybrid", hyb, 6), ("Model only", mod, 6)]
        if pso_row:
            tbl.append(("PSO", pso_row, pso_read))
        tbl += [("P&O", po, 3), ("InC", inc, 3)]
        df = pd.DataFrame([{
            "Method": n, "Energy captured (%)": r["energy"],
            "Found true peak (%)": round(r["found"], 1),
            "Steps": ("—" if r["steps"] is None else int(r["steps"])),
            "Readings": rd, "Worst case (W)": round(r["worst"], 1)} for n, r, rd in tbl])
        st.dataframe(df, hide_index=True, width="stretch",
                     column_config={"Energy captured (%)": st.column_config.ProgressColumn(
                         "Energy captured (%)", min_value=78, max_value=100, format="%.2f")})
        ui.legend_note(f"Multi-peak subset, n={R['P&O'][sub]['n']} validation scenarios. "
                       "Bars start at 78% so the top methods are separable.")
    with right:
        fig = go.Figure()
        pts = [("P&O", 3, 100 - po["energy"]), ("Model only", 6, 100 - mod["energy"]),
               ("Hybrid", 6, 100 - hyb["energy"])]
        if pso_row:
            pts.append(("PSO", pso_read, 100 - pso_row["energy"]))
        for m, x, y in pts:
            col = ui.METHOD_COLORS.get(m, c["teal"]) if hasattr(ui, "METHOD_COLORS") else c["teal"]
            fig.add_trace(go.Scatter(x=[x], y=[max(y, 0.01)], mode="markers+text", name=m,
                                     text=[m], textposition="middle right",
                                     marker=dict(size=13, color=col)))
        fig.update_xaxes(type="log", title_text="readings per cycle")
        fig.update_yaxes(type="log", title_text="energy lost (%)")
        ui.style_fig(fig, height=340)
        fig.update_layout(showlegend=False,
                          title="Energy lost against readings per cycle")
        st.plotly_chart(fig, width="stretch")

    ui.callout(f"Hybrid and PSO record the same energy captured; they differ in readings "
               f"per cycle. Validation modules, held back, {R['P&O'][sub]['n']} multi-peak "
               f"scenarios, validated engine. Nothing measured in the field yet.",
               "Read these alongside", "caveat")
    ui.next_step("Now see whether it holds while the irradiance changes.", P["moving"],
                 "Open dynamic irradiance →", key="compare")


_MV_COLORS = {"Hybrid": "#16616B", "P&O": "#A32B24", "PSO": "#7FA5A8",
              "Model only": "#9BBDBF", "InC": "#8A9098"}
_MV_DEMO = dict(module="LG_Electronics_Inc__LG375N2K_G4", temp=43.0,
                shaded=(910.0, 300.0, 600.0))


@st.cache_data(show_spinner=True)
def _dynamic_day(sequence, shaded):
    """One EN 50530 ramp profile stepped by every tracker — real per-step power."""
    import numpy as np
    from gmppt import dynamic as dyn, tracking as trk, trackers as trkx, pso
    from gmppt.scenarios import Scenario
    slopes = [r[1] for r in dyn.SEQUENCES[sequence][1]]
    prof = dyn.make_profile(sequence, slopes[len(slopes) // 2], max_cycles=1)
    m, tp = _MV_DEMO["module"], _MV_DEMO["temp"]
    if shaded:
        sc = Scenario(m, tp, "whole_substring", list(_MV_DEMO["shaded"]), False)
    else:
        sc = Scenario(m, tp, "uniform", [1000.0, 1000.0, 1000.0], False)
    uni = Scenario(m, tp, "uniform", [1000.0, 1000.0, 1000.0], False)

    def avail_line(scn):
        tj = dyn.dynamic_trajectory_for(scn, prof)
        pg = np.array([cc[3] for cc in tj.curves])
        return np.repeat(pg, tj.block_steps).astype(float)

    shaded_av = avail_line(sc)
    unshaded_av = avail_line(uni)
    traces = {}

    def run(name, fn, **kw):
        tj = dyn.dynamic_trajectory_for(sc, prof)
        fn(tj, n_steps=tj.n_steps, **kw)
        traces[name] = [float(x) for x in tj.p_hist]

    run("P&O", trk.perturb_and_observe)
    run("InC", trkx.incremental_conductance)
    run("PSO", pso.particle_swarm)
    model = _c3_model()
    if model is not None:
        from gmppt import hybrid as hyb
        run("Hybrid", hyb.make_hybrid(model), temp_c=tp)
        run("Model only", hyb.make_seed_only(model), temp_c=tp)
    return dict(avail=[float(x) for x in shaded_av],
                unshaded=[float(x) for x in unshaded_av],
                traces=traces, t0=20)


def page_moving():
    import numpy as np
    c = ui.T()
    disp, mono = ui.FONTS["display"], ui.FONTS["mono"]
    st.markdown(f"<style>.bh{{font-family:{disp};font-weight:700;color:{c['text']};}}"
                f"div.st-key-mvtabs a{{padding:10px 14px;font-size:14px;"
                f"color:{c['text_body']}!important;text-decoration:none;}}"
                f"div.st-key-mvtabs a p{{margin:0;}}</style>", unsafe_allow_html=True)
    with st.container(key="mvtabs"):
        tt = st.columns([1.3, 1.5, 1.3, 5], vertical_alignment="center")
        tt[0].page_link(P["run"], label="Watch one run")
        tt[1].page_link(P["compare"], label="Compare methods")
        tt[2].markdown(f"<span style='padding:10px 14px;font-size:14px;font-weight:600;"
                       f"border-bottom:3px solid {c['teal']};color:{c['text']}'>Dynamic irradiance"
                       f"</span>", unsafe_allow_html=True)

    ui.page_intro("Dynamic irradiance",
                  "How each tracking method responds while the irradiance changes, on the "
                  "EN 50530 ramp profile.", "Testing · Dynamic irradiance")
    # ---- irradiance profile + KPIs from the aggregate export ----
    scen = st.segmented_control("Irradiance profile",
                                ["EN 50530 · Seq 30-100", "EN 50530 · Seq 10-50",
                                 "Unshaded control"],
                                default="EN 50530 · Seq 30-100", key="mv_scen") \
        or "EN 50530 · Seq 30-100"
    st.caption("EN 50530 irradiance ramp, stepped on a control-step axis. This is a "
               "standard ramp profile, not a time-of-day sun path.")
    seq = "10-50" if "10-50" in scen else "30-100"
    shaded = "Unshaded" not in scen

    dyj = _load_json(f"phase2/dynamic_comparison_{seq}_val.json")
    if dyj:
        sh = dyj["results"]["shaded" if shaded else "uniform"]
        def agg(m): return sh[m]["aggregate_pct"] if m in sh else None
        hyb, pso, po = agg("hybrid, no reseed"), agg("PSO"), agg("P&O")
        se = sh.get("hybrid, no reseed", {}).get("scenario_se_pct", 0.0)
        kp = [("Dynamic efficiency", f"{hyb:.3f}%",
               f"hybrid · ±{se:.3f} · EN 50530 Seq {dyj['sequence']}", "hero")]
        if pso is not None:
            kp.append(("Against PSO", f"+{hyb - pso:.2f} pt", "aggregate over the set"))
        if po is not None:
            kp.append(("Against P&O", f"+{hyb - po:.1f} pt", "inherited from static trapping"))
        ui.kpi_row(kp)

    # ---- live per-step day traces ----
    try:
        day = _dynamic_day(seq, shaded)
    except Exception as e:
        ui.callout(f"Could not compute the dynamic trajectory ({e}).", "Trace unavailable", "limit")
        ui.next_step("Every number so far rests on a dataset. See what is in it.",
                     P["dataset"], "Where these numbers come from →", key="moving")
        return

    avail = np.array(day["avail"]); unshaded = np.array(day["unshaded"])
    t0 = day["t0"]
    x = np.arange(len(avail))
    all_methods = [m for m in ("Hybrid", "P&O", "PSO", "Model only", "InC")
                   if m in day["traces"]]
    default = [m for m in ("Hybrid", "P&O") if m in all_methods] or all_methods[:1]
    sel = st.segmented_control("Show", all_methods, selection_mode="multi",
                               default=default, key="mv_show") or default
    mode = st.segmented_control("mode", ["Power", "Efficiency %"], default="Power",
                                key="mv_mode", label_visibility="collapsed") or "Power"

    def trim(a):
        return a[t0:]
    xs = trim(x)

    with st.container(border=True):
        st.markdown(f"<span class='bh' style='font-size:17px'>Power through the profile</span>"
                    f"<span style='font-size:13px;color:{c['text_muted']};margin-left:10px'>"
                    f"the gap to the dotted line is shading; the gap to the dark line is "
                    f"tracking — only the second one is ours</span>", unsafe_allow_html=True)
        fig = go.Figure()
        if mode == "Power":
            fig.add_trace(go.Scatter(x=xs, y=trim(unshaded), name="unshaded potential",
                          line=dict(color="#B5641A", width=2, dash="dot")))
            fig.add_trace(go.Scatter(x=xs, y=trim(avail), name="available at true peak",
                          line=dict(color="#2B3238", width=2.5)))
            for m in sel:
                fig.add_trace(go.Scatter(x=xs, y=trim(np.array(day["traces"][m])), name=m,
                              line=dict(color=_MV_COLORS[m], width=2)))
            ui.style_fig(fig, height=320, x_title="EN 50530 profile (control steps)",
                         y_title="power (W)")
        else:
            eff = lambda a: np.where(avail > 1e-9, 100 * a / avail, 100.0)
            fig.add_trace(go.Scatter(x=xs, y=trim(np.full_like(avail, 100.0)),
                          name="available", line=dict(color="#2B3238", width=2)))
            for m in sel:
                fig.add_trace(go.Scatter(x=xs, y=trim(eff(np.array(day["traces"][m]))), name=m,
                              line=dict(color=_MV_COLORS[m], width=2)))
            ui.style_fig(fig, height=320, x_title="EN 50530 profile (control steps)",
                         y_title="tracking efficiency (%)")
            fig.update_yaxes(range=[60, 101])
        fig.update_layout(legend=dict(orientation="h", y=1.08, x=0))
        st.plotly_chart(fig, width="stretch")

    with st.container(border=True):
        st.markdown(f"<span class='bh' style='font-size:17px'>Power lost to tracking</span>"
                    f"<span style='font-size:13px;color:{c['text_muted']};margin-left:10px'>"
                    f"the distance from the dark line above — shading excluded, the tracker's "
                    f"own fault only</span>", unsafe_allow_html=True)
        fig2 = go.Figure()
        for m in sel:
            loss = np.maximum(0.0, avail - np.array(day["traces"][m]))
            fig2.add_trace(go.Scatter(x=xs, y=trim(loss), name=m,
                           line=dict(color=_MV_COLORS[m], width=2)))
        ui.style_fig(fig2, height=170, x_title="EN 50530 profile (control steps)",
                     y_title="power lost (W)")
        fig2.update_layout(legend=dict(orientation="h", y=1.15, x=0))
        st.plotly_chart(fig2, width="stretch")

    ui.callout("The x-axis is the EN 50530 ramp profile (control steps), not a clock. The "
               "standard ramps irradiance but barely moves the peak location, so the margin "
               "over P&O is largely static trapping carried into a changing scene.",
               "Read this beside the traces", "caveat")
    ui.not_built("Day-long event simulation",
                 "Future extension for time-varying shading events across a 06:00–18:00 sun "
                 "arc, with a live playhead. It is not what the EN 50530 profile above "
                 "shows. The event-based day that does run today is on Explore · The "
                 "panels, under “Shading events over the day”.")
    st.page_link(P["panels"], label="Open the day-event run on The panels →")
    ui.next_step("Every number so far rests on a dataset. See what is in it.",
                 P["dataset"], "Where these numbers come from →", key="moving")


# =========================================================================== #
# The data
# =========================================================================== #
def page_dataset():
    ui.page_intro("The dataset", "What is in the scenario set, and where the error concentrates.", "The data")
    st.page_link(P["sources"], label="Where it comes from →")
    d = st.session_state.get("dataset")
    if not d or d.get("df") is None or len(d["df"]) == 0:
        ui.callout("No dataset has been generated in this session, so there is nothing to "
                   "show here. Generate one on Simulator → Make a dataset and it appears "
                   "on this page.", "No dataset yet", "info")
        st.page_link(P["sim_dataset"], label="Make a dataset →")
        return
    df = d["df"]
    _cfg = d.get("cfg", {})
    ui.kpi_row([("Scenarios", f"{len(df):,}"),
                ("With more than one peak", f"{int((df['local_peak_count'] > 1).sum()):,}"),
                ("Largest loss to shade", f"{df['power_loss_percent'].max():.1f}%")])
    hd = st.columns([4, 1.4], vertical_alignment="center")
    hd[0].caption(f"Module {_cfg.get('module', '—')} · {_cfg.get('n_sub', '—')} substrings · "
                  f"seed {_cfg.get('seed', '—')} · objects sampled: "
                  f"{', '.join(_cfg.get('objects', [])) or '—'}")
    try:
        hd[1].download_button("Download (.zip)",
                              sim.build_dataset_zip(df, d["curves"], _cfg, d["stats"],
                                                    d.get("ds") or sim.current_ds()),
                              "pv_partial_shading_dataset.zip", "application/zip",
                              key="dl_dataset_datapage", use_container_width=True)
    except Exception as _e:
        hd[1].button("Download (.zip)", disabled=True, use_container_width=True,
                     help=f"Export unavailable: {_e}")
    a, b = st.columns(2, gap="large")
    with a:
        fig = go.Figure(go.Histogram(x=df["gmpp_voltage_V"], nbinsx=40,
                                     marker_color=ui.METHOD_COLORS["Model only"]))
        ui.style_fig(fig, 320, "Scenarios", "Voltage of the true peak (V)")
        fig.update_layout(title="Where the tallest peak sits")
        st.plotly_chart(fig, width="stretch")
        ui.legend_note("Clusters, not one bump: the peak sits near a strip boundary.")
    with b:
        fig = go.Figure()
        for objname, g in df.groupby("shading_object"):
            fig.add_trace(go.Scatter(x=g["reduction_percent"], y=g["power_loss_percent"],
                                     mode="markers", name=objname, marker=dict(size=6, opacity=0.7)))
        ui.style_fig(fig, 320, "Power lost to shade (%)", "Light blocked (%)")
        fig.update_layout(title="Loss against how dark the shadow is")
        st.plotly_chart(fig, width="stretch")
    ui.engine_badge("simplified")


def page_sources():
    c = ui.T()
    ui.page_intro("Where it comes from",
                  "From a laboratory measurement to the figure on screen — and what the numbers cannot tell you.",
                  "The data")
    st.page_link(P["dataset"], label="← The dataset")

    # Which page is drawn by which engine, and where each input comes from.
    with st.container(border=True):
        st.markdown(_bh("The two engines"), unsafe_allow_html=True)
        rows = [
            ("Validated engine", "gmppt.device + pvlib CEC parameters",
             "Explore · The panels, Inside a panel; all of Testing",
             "Research and benchmark analysis. Matched to ~1% against 616 laboratory "
             "flash tests."),
            ("Interactive simulator", "app.py single-diode + per-substring bypass",
             "Simulator · Set up a panel, Make a dataset, The dataset",
             "Exploratory configuration and visualisation. Not a benchmark result; "
             "reverse-bias avalanche is not modelled."),
        ]
        cells = "".join(
            f"<span style='font-weight:600;color:{c['text']}'>{n}</span>"
            f"<span class='bmono' style='font-size:11.5px'>{code}</span>"
            f"<span style='font-size:12.5px'>{where}</span>"
            f"<span style='font-size:12.5px;color:{c['text_muted']}'>{why}</span>"
            for n, code, where, why in rows)
        st.markdown(
            f"<div style='margin-top:10px;display:grid;"
            f"grid-template-columns:1fr 1.2fr 1.3fr 1.8fr;gap:10px 14px;font-size:13px'>"
            f"<span style='color:{c['text_muted']};font-size:11.5px'>engine</span>"
            f"<span style='color:{c['text_muted']};font-size:11.5px'>code</span>"
            f"<span style='color:{c['text_muted']};font-size:11.5px'>used on</span>"
            f"<span style='color:{c['text_muted']};font-size:11.5px'>what it is for</span>"
            f"{cells}</div>", unsafe_allow_html=True)

    with st.container(border=True):
        st.markdown(_bh("Where each input comes from"), unsafe_allow_html=True)
        st.markdown(
            "- **Module parameters** — the CEC module database via `pvlib` "
            "(`retrieve_sam(\"CECMod\")`), pooled into `results/cec_pool.parquet`.\n"
            "- **Validation modules** — the held-out half of that pool "
            "(`gmppt.scenarios.split_modules`). The panel dropdown on Explore only offers "
            "held-out modules, so nothing on screen was used to fit the model.\n"
            "- **Datasheet modules** — the Simulator's own presets and any numbers you type "
            "there. These are not CEC modules and are not used for any benchmark.\n"
            "- **Tracking methods** — P&O (`gmppt.tracking`), incremental conductance "
            "(`gmppt.trackers`), PSO (`gmppt.pso`), and the learned seed / hybrid "
            "(`gmppt.model`, `gmppt.hybrid`) loaded from the trained two-stage model.\n"
            "- **Benchmark profiles** — EN 50530 irradiance ramp sequences "
            "(`gmppt.dynamic.SEQUENCES`). These are standard ramps, not a sun path.\n"
            "- **Comparison figures** — the exported runs under `results/phase2/`. When an "
            "export is missing the page says so rather than substituting an estimate.")

    sim.page_validation()


# --------------------------------------------------------------------------- #
# Custom top header (always rendered in the page body — matches the mockup and
# does not depend on Streamlit's built-in navigation bar)
# --------------------------------------------------------------------------- #
_LOGO_SVG = r'''<svg width="26" height="26" viewBox="0 0 30 30" aria-hidden="true"><circle cx="10" cy="10" r="5" fill="#B5641A"></circle><path d="M2 25 C 8 25, 9 13, 15 13 C 21 13, 20 21, 28 21" fill="none" stroke="#16616B" stroke-width="2.4" stroke-linecap="round"></path></svg>'''


def _header_css(c, disp):
    st.markdown(
        ("<style>"
         "div.st-key-gmhdr{background:%(surface)s;border:1px solid %(border)s;"
         "border-radius:12px;padding:6px 14px;margin-bottom:18px;}"
         "div.st-key-gmhdr a{display:inline-flex;align-items:center;justify-content:center;"
         "padding:8px 12px;border-radius:8px;font-size:14px;font-weight:500;"
         "color:%(text_body)s!important;text-decoration:none;}"
         "div.st-key-gmhdr a:hover{background:%(muted_fill)s;}"
         "div.st-key-gmhdr a p{margin:0;color:%(text_body)s!important;font-weight:500;}"
         "div.st-key-gmhdr a>svg{display:none;}"
         "div.st-key-gmbrand div[data-testid=\"stHorizontalBlock\"]{gap:10px!important;"
         "flex-wrap:nowrap!important;align-items:center!important;}"
         "div.st-key-gmbrand div[data-testid=\"stColumn\"]{width:auto!important;flex:0 0 auto!important;"
         "min-width:0!important;}"
         "div.st-key-gmbrandlink a,div.st-key-gmbrandlink a:hover,"
         "div.st-key-gmbrandlink a[aria-current]{background:transparent!important;"
         "padding:0!important;margin:0!important;border-radius:0!important;}"
         "div.st-key-gmbrandlink a p{font-family:%(display)s!important;font-weight:700!important;"
         "font-size:18px!important;letter-spacing:-.01em;color:%(text)s!important;"
         "white-space:nowrap;transition:opacity .12s ease;}"
         "div.st-key-gmbrandlink a:hover p{opacity:.66;}"
         ".bh{font-family:%(display)s;font-weight:700;font-size:16px;color:%(text)s;}"
         ".bmono,.bmono *{font-family:%(mono)s;}"
         "</style>") % {"surface": c["surface"], "border": c["border"],
                        "text_body": c["text_body"], "muted_fill": c["muted_fill"],
                        "text": c["text"], "display": disp, "mono": ui.FONTS["mono"]},
        unsafe_allow_html=True)


def render_header():
    c = ui.T(); disp = ui.FONTS["display"]
    _header_css(c, disp)
    with st.container(key="gmhdr"):
        L, M, R = st.columns([1.15, 2.6, 1.35], vertical_alignment="center")
        with L:
            with st.container(key="gmbrand"):
                mark, word = st.columns([1, 4], vertical_alignment="center")
                mark.markdown(f'<div style="line-height:0;">{_LOGO_SVG}</div>',
                              unsafe_allow_html=True)
                with word:
                    with st.container(key="gmbrandlink"):
                        st.page_link(P["home"], label="GMPPT Bench")
        with M:
            t = st.columns(4)
            t[0].page_link(P["panels"], label="Explore")
            t[1].page_link(P["sim_setup"], label="Simulator")
            t[2].page_link(P["run"], label="Testing")
            t[3].page_link(P["dataset"], label="The data")
        with R:
            r1, r2 = st.columns([1.1, 1])
            r1.segmented_control("Language", ["EN", "KO"], key="gm_lang",
                                 label_visibility="collapsed")
            r2.segmented_control("Theme", ["Light", "Dark"], key="gm_theme",
                                 label_visibility="collapsed")


# =========================================================================== #
# Navigation
# =========================================================================== #
P.update(
    home=st.Page(page_home, title="Home", url_path="home", default=True),
    panels=st.Page(page_panels, title="The panels", url_path="panels"),
    inside=st.Page(page_inside, title="Inside a panel", url_path="panel"),
    system=st.Page(page_system, title="Whole system", url_path="system"),
    sim_setup=st.Page(page_sim_setup, title="Set up a panel", url_path="simulator"),
    sim_saved=st.Page(page_sim_saved, title="Saved scenarios", url_path="saved"),
    sim_dataset=st.Page(page_sim_dataset, title="Make a dataset", url_path="make-dataset"),
    run=st.Page(page_run, title="Watch one run", url_path="run"),
    compare=st.Page(page_compare, title="Compare methods", url_path="compare"),
    moving=st.Page(page_moving, title="Dynamic irradiance", url_path="dynamic-irradiance"),
    dataset=st.Page(page_dataset, title="The dataset", url_path="data"),
    sources=st.Page(page_sources, title="Where it comes from", url_path="sources"),
)
SECTIONS = {
    "": [P["home"]],
    "Explore": [P["panels"], P["inside"], P["system"]],
    "Simulator": [P["sim_setup"], P["sim_saved"], P["sim_dataset"]],
    "Testing": [P["run"], P["compare"], P["moving"]],
    "The data": [P["dataset"], P["sources"]],
}

# Built-in nav hidden — we render our own always-visible header above every page.
nav = st.navigation(SECTIONS, position="hidden")
render_header()
nav.run()