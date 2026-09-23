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

Only genuinely unimplemented features are labelled as planned/not built. Implemented
pages are navigable and must not be presented as "coming".
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import app as sim          # your existing simulator — physics, presets, pages
import gmppt_ui as ui
from gmppt import config as _gcfg, dataset as _ds, device as _eng, scenarios as _scen
from gmppt.hybrid import SEED_PROBE_COST

st.set_page_config(page_title="GMPPT Bench", layout="wide", initial_sidebar_state="collapsed")
sim.init_state()
st.session_state.setdefault("gm_theme", "Light")
st.session_state.setdefault("gm_anim", "On")     # §6 — global animation switch

# Theme: the existing figures read sim.TH, so keep it in step with the new tokens.
ui.setup(st.session_state.gm_theme)
sim.TH = sim.THEMES["Dark" if st.session_state.gm_theme == "Dark" else "Light"]
sim.GRID = sim.TH["grid"]

P: dict[str, st.Page] = {}   # filled below; page functions look pages up here at run time
_e = ui._e                   # HTML-escape, so export strings cannot break the markup


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
    ("Build a scenario",
     "Pick a validation module, choose a shading object and which panels it covers, "
     "and set the sunlight and cell temperature."),
    ("Read the curve",
     "The power and current curves for that scenario, with every local peak and the "
     "true maximum marked, and each bypass diode's state as you move the "
     "operating point."),
    ("Run the trackers",
     "Send your scenario to the classic algorithms and to the model, and watch each "
     "one search the same curve step by step."),
    ("Compare methods",
     "Every method on the same validation scenarios: arrival rate, worst case, "
     "steps, and what the accuracy costs in readings."),
    ("Results vs targets",
     "The funded targets beside what was measured, with the caveats that belong to "
     "each number."),
]
# The page each card opens, in the order of _CARD_TEXT — the real journey:
# build a scenario, look inside it, run the trackers, compare, read the verdict.
_CARD_LINKS = ["panels", "inside", "run", "compare", "results"]

_SANDBOX_CARD_ICONS = [_CARD_ICONS[0]]
_SANDBOX_CARD_TEXT = [
    ("Sandbox — set up a panel",
     "Type a datasheet in yourself and watch the curve. A separate, simplified "
     "engine: exploratory only, never a benchmark result."),
]
_SANDBOX_CARD_LINKS = ["sim_setup"]


def _home_steps():
    """The journey as stepper rows — one per stage, landing on its first page.

    Every link goes through st.page_link, never a raw href: a full browser
    navigation would start a new session and drop the scenario. (R1)
    """
    rows = []
    for stage, keys in STAGES:
        k = keys[0]
        rows.append((k, P.get(k), stage, _PAGE_PURPOSE.get(k, "")))
    return rows


def _tutorial_steps():
    """The onboarding tour (§6–7): each step points at a REAL control on Home.

    The targets are the hero's primary action and the stepper rows, which are
    the same links the reader will use once the tour is over. No stand-ins.
    """
    first = STAGES[0][1][0]
    row = lambda k: f".st-key-gm-step-{k}"
    return [
        {"target": ".st-key-hero-primary a", "title": "Start here",
         "body": "Build the validation scenario you want to inspect. This button "
                 "takes you to the first step."},
        {"target": row("panels"), "title": "Choose your scenario",
         "body": "Select the validation module, the shading object, the sunlight "
                 "and the cell temperature. The power curve redraws as you go."},
        {"target": row("inside"), "title": "Inspect the panel",
         "body": "Move the operating point and see how the curve and each "
                 "bypass diode respond."},
        {"target": row("run"), "title": "Watch the search",
         "body": "Send the scenario to the tracking methods and watch how each "
                 "one searches the same curve."},
        {"target": row("compare"), "title": "Compare methods",
         "body": "Compare the tracking methods on the same validation "
                 "scenarios — every method, every shaded case."},
        {"target": row("moving"), "title": "Explore changing conditions",
         "body": "Dynamic irradiance and shading relocation show how changing "
                 "conditions affect tracking."},
        {"target": row("results"), "title": "Review the results",
         "body": "Read the measured results beside the documented targets, and "
                 "see where every number came from."},
    ] if first == "panels" else []


def _session_io():
    """Download / restore everything the user has built in this session."""
    import json
    with st.expander("Save or restore your session", expanded=False):
        st.caption("Scenarios, saved curves and day events live in this browser "
                   "session only. Download them to carry them to another machine.")
        a, b = st.columns(2)
        with a:
            st.download_button("Download session (JSON)", _session_blob(),
                               "gmppt_session.json", "application/json",
                               use_container_width=True, key="session_dl")
        with b:
            up = st.file_uploader("Load session (JSON)", type=["json"],
                                  key="session_up", label_visibility="collapsed")
            if up is not None and st.button("Restore this session", key="session_restore",
                                            use_container_width=True):
                try:
                    blob = json.loads(up.getvalue().decode("utf-8"))
                except Exception as e:
                    st.error(f"Not a session file: {e}")
                else:
                    for k in ("scenario_draft", "scenario_sent", "frozen", "day_events"):
                        if k in blob:
                            st.session_state[k] = blob[k]
                    st.toast("Session restored.")
                    st.rerun()


def _session_blob() -> str:
    """The session, plus which exports were on disk when it was saved."""
    import json
    exports = {}
    for rel in _EXPORT_SCRIPT:
        p = _export_path(rel)
        try:
            if p.exists():
                d = json.loads(p.read_text())
                exports[rel] = {"mtime": p.stat().st_mtime,
                                "split": d.get("split"),
                                "version": d.get("version"),
                                "n_scenarios": d.get("n_scenarios")}
        except Exception:
            exports[rel] = {"unreadable": True}
    return json.dumps({
        "scenario_draft": st.session_state.get("scenario_draft"),
        "scenario_sent": st.session_state.get("scenario_sent"),
        "frozen": st.session_state.get("frozen", []),
        "day_events": st.session_state.get("day_events", []),
        "exports": exports,
    }, indent=2, default=str)


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
         # ---- A8 --------------------------------------------------------- #
         # The hero curves draw themselves once, from the polyline coordinates
         # already in the mockup's SVG. Nothing is computed and no number is
         # introduced: this is the stroke being revealed along its own path.
         # The animation runs only under .on (Animations: On) and is disabled
         # outright under prefers-reduced-motion, where the finished drawing is
         # what a reader sees.
         "@keyframes gm-draw{to{stroke-dashoffset:0;}}"
         "@keyframes gm-pop{from{opacity:0;transform:scale(.4);}"
         "to{opacity:1;transform:scale(1);}}"
         ".gm-hero.on polyline{stroke-dasharray:900;stroke-dashoffset:900;"
         "animation:gm-draw 1.7s cubic-bezier(.22,.61,.36,1) forwards;}"
         ".gm-hero.on polyline:nth-of-type(2){animation-delay:.45s;}"
         ".gm-hero.on circle{opacity:0;transform-box:fill-box;"
         "transform-origin:center;animation:gm-pop .45s ease-out 1.9s forwards;}"
         "@media (prefers-reduced-motion: reduce){"
         ".gm-hero.on polyline{stroke-dasharray:none;stroke-dashoffset:0;"
         "animation:none;}"
         ".gm-hero.on circle{opacity:1;animation:none;transform:none;}}"
         "div[class*=\"st-key-gmcards\"]{margin-top:18px;}"
         # The card body is HTML; the action is a real st.page_link so it cannot
         # reload the session. The keyed container is the card, and its last child
         # (the link) is pushed to the bottom so the rows line up.
         "div[class*=\"st-key-gmcards\"] div[data-testid=\"stColumn\"]{display:flex;"
         "flex-direction:column;}"
         "div[class*=\"st-key-gmcards\"] div[data-testid=\"stColumn\"]>div{width:100%%;"
         "height:100%%;}"
         "div[class*=\"-card-\"]{box-sizing:border-box;display:flex;flex-direction:column;"
         "height:100%%;min-height:212px;gap:0!important;background:%(surface)s;"
         "border:1px solid %(border)s;border-radius:14px;padding:18px;"
         "transition:border-color .12s ease,box-shadow .12s ease;}"
         "div[class*=\"-card-\"]>div{flex:0 0 auto;width:100%%;min-height:0;}"
         "div[class*=\"-card-\"]:hover{border-color:%(border_strong)s;"
         "box-shadow:0 2px 12px rgba(16,24,32,.07);}"
         ".gm-ico{width:34px;height:34px;display:flex;align-items:center;"
         "justify-content:center;border:1px solid %(border)s;border-radius:9px;}"
         ".gm-title{margin-top:12px;font-size:15px;font-weight:600;color:%(text)s;}"
         ".gm-desc{margin:6px 0 0 0;font-size:13px;line-height:1.5;color:%(text_body)s;}"
         "div[class*=\"-go-\"]{margin-top:auto!important;padding-top:16px;}"
         "div[class*=\"-go-\"] a{display:inline-flex;align-items:center;"
         "justify-content:center;height:36px;padding:0 16px;border-radius:8px;"
         "background:%(teal)s;color:#fff!important;font-weight:600;font-size:13px;"
         "text-decoration:none;}"
         "div[class*=\"-go-\"] a:hover{background:%(teal_dark)s;}"
         "div[class*=\"-go-\"] a p{margin:0;color:#fff!important;font-weight:600;}"
         "div[class*=\"-go-\"] a>svg{display:none;}"
         ".st-key-home-sources a{color:%(teal)s!important;font-weight:600;"
         "text-decoration:none;}"
         ".st-key-home-sources a p{margin:0;font-weight:600;}"
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
        # A8: the illustration draws itself. CSS only, on the coordinates the
        # mockup already carries — no numbers are introduced for the hero.
        cls = "gm-hero on" if ui.anim_on() else "gm-hero"
        st.markdown(
            f'<div class="{cls}" style="background:{c["surface"]};'
            f'border:1px solid {c["border"]};'
            f'border-radius:16px;padding:18px 20px 12px 20px;">{_HERO_SVG}'
            f'<p style="margin:6px 0 0 0;text-align:center;font-size:12.5px;color:{c["text_muted"]};">'
            f'The same panel on the same afternoon — compared with and without partial shading.'
            f'</p></div>', unsafe_allow_html=True)
        ui.anim_badge("schematic", "the illustration from the design mockup")

    # The journey, as a stepper rather than five peer cards: one strong "start
    # here", the rest quiet, and the stages already visited ticked (§13–14).
    st.space(size="medium")
    ui.section_head("The workflow", "six stages, in order — start at the top")
    ui.stepper(_home_steps(), current=None,
               done=st.session_state.get("gm_visited", []))

    st.space(size="small")
    with st.container(key="gm-sandbox-link"):
        st.page_link(P["sim_setup"], label="Sandbox — a separate, simplified engine "
                                           "for trying your own datasheet →",
                     help=ui.GLOSSARY["Sandbox"])

    if st.session_state.get("gm_tut_done"):
        if st.button("Show tutorial again", key="gm_tut_reopen",
                     help="Reopen the six-step walkthrough."):
            st.session_state["gm_tut_done"] = False
            st.session_state["gm_tut_step"] = 0
            st.rerun()

    _session_io()

    st.markdown(
        f'<div style="margin-top:28px;display:flex;align-items:center;gap:16px;padding-top:18px;'
        f'border-top:1px solid {c["border"]};font-size:12.5px;color:{c["text_muted"]};">'
        f'<span>Simulated modules only \u2014 no field measurements behind these figures yet.</span>'
        f'<span style="margin-left:auto;font-family:{mono};">Dept. of Computer Engineering, '
        f'Jeju National University</span></div>', unsafe_allow_html=True)
    with st.container(key="home-sources"):
        st.page_link(P["sources"], label="Where the numbers come from \u2192")


# =========================================================================== #
# Explore
# =========================================================================== #
# =========================================================================== #
# Explore · The panels  — wired to the VALIDATED engine (gmppt.device) and to the
# SAME module set `phase2/p7_tracker_comparison.py --split val` runs on.
#
# That is `dataset.module_split().val`, NOT `scenarios.split_modules(pool)[1]`.
# The latter is the 20% held-out TEST set, which dataset.py reserves for a single
# ledgered opening through p3_final_comparison.py --confirm-test; p7's docstring
# says so explicitly. An earlier revision of this dashboard drew its dropdown
# from that set and called it "validation", which spent the one set whose
# independence the project protects. SPLIT_NAME travels with every figure.
# =========================================================================== #
SPLIT_NAME = "val"


@st.cache_resource(show_spinner=False)
def _cec_table():
    from pvlib import pvsystem
    return pvsystem.retrieve_sam("CECMod").T


@st.cache_data(show_spinner=False)
def _pool():
    return pd.read_parquet(_gcfg.CEC_POOL)


# The parameters the nearest-training-module distance is measured in. z-scored
# over the FULL pool so no single column (N_s, in the hundreds) dominates.
_DIST_COLS = ("V_mp_ref", "I_mp_ref", "V_oc_ref", "I_sc_ref", "N_s")
# The demo scenario's module is picked from this band, deterministically. (U1)
_DEMO_NS, _DEMO_P_MIN, _DEMO_P_MAX = 72, 340.0, 380.0


@st.cache_data(show_spinner=False)
def _val_module_names() -> frozenset:
    """The validation module set, resolved through the same call p7 --split val
    makes. Imported, never re-derived."""
    return frozenset(str(m) for m in _ds.module_split().val)


@st.cache_data(show_spinner=False)
def _train_module_names() -> frozenset:
    """The training set — needed to answer "was this module fitted on?" live."""
    return frozenset(str(m) for m in _ds.module_split().train)


@st.cache_data(show_spinner=False)
def _split_counts() -> dict:
    s = _ds.module_split()
    return {"train": len(s.train), "val": len(s.val), "test": len(s.test)}


def _in_val(name: str) -> bool:
    return str(name) in _val_module_names()


@st.cache_data(show_spinner=False)
def _zmatrix():
    """Pool parameters, z-scored over the whole pool. Index-aligned to _pool()."""
    pool = _pool()
    X = pool[list(_DIST_COLS)].astype(float)
    sd = X.std(ddof=0).replace(0.0, 1.0)
    return (X - X.mean()) / sd


@st.cache_data(show_spinner=False)
def _nearest_train(name: str):
    """(nearest training module, z-scored distance) for one module.

    Computed live against `dataset.module_split().train`, not against anything
    stored in the model file — the model does not record its training list. The
    note beside the check on screen says so. (U1.8)
    """
    Z = _zmatrix()
    name = str(name)
    train = [m for m in _train_module_names() if m in Z.index]
    if name not in Z.index or not train:
        return None, float("nan")
    d = np.linalg.norm(Z.loc[train].to_numpy() - Z.loc[name].to_numpy(), axis=1)
    i = int(np.argmin(d))
    return str(train[i]), float(d[i])


@st.cache_data(show_spinner=False)
def _demo_module() -> tuple:
    """The demo module for Watch one run and Dynamic irradiance. (U1.2)

    Deterministic: among validation modules with N_s == 72 and P in
    [340, 380] W, take the one whose NEAREST TRAINING module is farthest away in
    z-scored parameter space. Picking the most distant candidate is the point —
    a demo is meant to show the method working on something the model was not
    fitted near, and the split is by module name, so near-identical siblings can
    land on opposite sides of it.

    Returns (name, distance, nearest training module, note).
    """
    pool = _pool()
    Z = _zmatrix()
    val = [n for n in _val_module_names() if n in pool.index]
    h = pool.loc[val].copy()
    h["P"] = h["V_mp_ref"] * h["I_mp_ref"]
    cand = h[(h["N_s"] == _DEMO_NS) & (h["P"].between(_DEMO_P_MIN, _DEMO_P_MAX))]
    note = ""
    if not len(cand):
        cand = h[h["N_s"] == _DEMO_NS] if len(h[h["N_s"] == _DEMO_NS]) else h
        note = (f"No validation module matched N_s={_DEMO_NS} and "
                f"{_DEMO_P_MIN:.0f}–{_DEMO_P_MAX:.0f} W, so the band was widened.")
    names = [n for n in cand.index if n in Z.index]
    train = [m for m in _train_module_names() if m in Z.index]
    if not names or not train:
        return ("—", float("nan"), None, "No validation module could be resolved.")
    C = Z.loc[names].to_numpy()
    T = Z.loc[train].to_numpy()
    # nearest training neighbour for every candidate, in chunks so the pairwise
    # matrix never gets large
    best_d = np.full(len(names), np.inf)
    best_i = np.zeros(len(names), dtype=int)
    for s in range(0, len(train), 4000):
        blk = T[s:s + 4000]
        d = np.linalg.norm(C[:, None, :] - blk[None, :, :], axis=2)
        j = d.argmin(axis=1)
        dm = d[np.arange(len(names)), j]
        upd = dm < best_d
        best_i[upd] = s + j[upd]
        best_d[upd] = dm[upd]
    k = int(np.argmax(best_d))
    return (str(names[k]), float(best_d[k]), str(train[best_i[k]]), note)


def _demo_startup_log():
    """Log the chosen demo module and its distance once per session. (U1.2)"""
    if st.session_state.get("_demo_logged"):
        return
    name, dist, near, _ = _demo_module()
    print(f"[gmppt_app] demo module: {name} (validation) · nearest training module "
          f"{near} at z-distance {dist:.3f} · split "
          f"{_split_counts()}", flush=True)
    st.session_state["_demo_logged"] = True


def assert_val_modules(names, what="this page") -> bool:
    """Every module on screen must be a validation module. (U1.3)

    A module that has slipped into train or test invalidates the page it is on,
    so the page renders no results rather than a figure that cannot be quoted.
    """
    val, train = _val_module_names(), _train_module_names()
    bad = []
    for n in names:
        n = str(n)
        if n in train:
            bad.append((n, "training"))
        elif n not in val:
            bad.append((n, "not in the validation split (test, or absent)"))
    if not bad:
        return True
    ui.unavailable(
        "Wrong data set",
        f"{what} would have shown a panel that is not validation data, so nothing "
        f"is drawn. Only validation panels can be compared with the benchmark, and "
        f"the held-out test panels are never opened here.",
        "- " + "\n- ".join(f"`{n}` is in the {w} set" for n, w in bad[:4]) + "\n"
        "- Membership is resolved through `gmppt.dataset.module_split().val`, the "
        "same set `p7_tracker_comparison.py --split val` runs on.",
        kind="limit")
    return False


# U1.6 asked for one consistent wording wherever the dashboard describes the
# modules it shows — "held-out" and "never seen" belong to the TEST set and are
# never used for these. That wording now lives in ui.data_chip("Validation data",
# …) via _unseen_check(), so every page says it the same way and says it once.


@st.cache_data(show_spinner=False)
def _validation_modules():
    """A curated few VALIDATION modules for the panel dropdown."""
    pool = _pool()
    names = [n for n in _val_module_names() if n in pool.index]
    h = pool.loc[names].copy()
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


def geometry_of(irr) -> str:
    """The `scenarios.Scenario.geometry` tag implied by an irradiance argument.

    Derived from the pattern itself so a scenario can never be filed under a
    geometry it does not have. Matches scenarios.py's own definitions:
      uniform          every substring the same scalar
      sub_substring    at least one substring carries a per-cell-group list
      whole_substring  substrings uniform but differing
    """
    entries = list(irr)
    if any(isinstance(e, (list, tuple)) for e in entries):
        return "sub_substring"
    vals = [float(e) for e in entries]
    return "uniform" if max(vals) - min(vals) < 1e-9 else "whole_substring"


def geometry_label(irr) -> str:
    """The geometry tag as shown to a reader.

    scenarios.py's sub_substring shades ONE cell group in ONE substring. The
    shadow controls here can shade a cell group on every substring at once, which
    is the same geometry class but a different case, so it is named as such
    rather than passed off as the harness's."""
    g = geometry_of(irr)
    if g == "sub_substring" and all(isinstance(e, (list, tuple)) for e in irr):
        return "sub-substring (all strips)"
    return g.replace("_", "-")


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


@st.cache_data(show_spinner=False)
def _substring_curves(name, irr_key, T):
    """Each substring's element I–V from the validated engine, computed once.

    The bypass table used to build these curves on every call. A3 needs a
    substring voltage at sixty different currents, so building them once and
    interpolating along them keeps the animation inside the engine-evaluation
    budget — and the interpolation is the same one the table always did.
    """
    irr = [list(e) if isinstance(e, tuple) else float(e) for e in irr_key]
    mp = _mparams(name); bd = _gcfg.breakdown(); bp = _eng.Bypass(temp_c=T)
    n_sub = _gcfg.N_SUBSTRINGS
    base = mp.N_s // n_sub
    counts = [base] * n_sub
    for k in range(mp.N_s - base * n_sub):
        counts[k] += 1
    curves = []
    for entry, cnt in zip(irr, counts):
        sub = _eng.scale_to_substring(mp, cnt / mp.N_s)
        if np.isscalar(entry):
            v, ie = _eng.substring_element_iv(sub, float(entry), T, bd, bp)
        else:
            v, ie = _eng.substring_element_iv_subshaded(sub, list(entry), T, bd, bp)
        curves.append(([float(x) for x in v], [float(x) for x in ie]))
    return curves, float(bp.clamp_voltage)


def _substring_voltages(name, irr, T, at_current):
    """Per-substring terminal voltage at a given string current — for the bypass
    table and the operating-point view."""
    curves, clamp = _substring_curves(name, _key(irr), float(T))
    out = [float(np.interp(at_current, ie[::-1], v[::-1])) for v, ie in curves]
    return out, clamp


# The one bypass rule. The table, the operating-point view and A3 all read the
# diode state through this, so an animation cannot come to disagree with the
# table printed beside it. (§10)
def _diode_state(vk, clamp):
    if vk <= clamp + 0.2:
        return "on"
    return "partial" if vk < -0.05 else "off"


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


# --------------------------------------------------------------------------- #
# The scenario store. Two states, one shape (R3).
#
#   scenario_draft  what The panels is showing right now — rewritten every render
#   scenario_sent   what Testing is running — written only by "Send to trackers"
#
# Keeping them apart is what lets the banner say "edited since sent" instead of
# letting an edit on Explore silently change the curve a Testing page already
# drew. `hash` is what the two are compared on.
# --------------------------------------------------------------------------- #
def _scenario(module, temp, irr, label) -> dict:
    import datetime as _d
    irr_l = [list(e) if isinstance(e, (list, tuple)) else float(e) for e in irr]
    return {"module": str(module), "temp": float(temp), "label": str(label),
            "irr": irr_l,
            "geometry": geometry_of(irr_l),
            "geometry_label": geometry_label(irr_l),
            "pattern": " / ".join(
                ("[" + ",".join(f"{float(x):.0f}" for x in e) + "]")
                if isinstance(e, (list, tuple)) else f"{float(e):.0f}"
                for e in irr_l) + " W/m²",
            "split": SPLIT_NAME if _in_val(module) else "not in the validation split",
            "engine": "validated",
            "created_at": _d.datetime.now().isoformat(timespec="seconds"),
            "hash": _scenario_hash(module, temp, irr_l)}


def _scenario_hash(module, temp, irr) -> str:
    import hashlib
    payload = repr((str(module), round(float(temp), 6), _key(irr)))
    return hashlib.sha1(payload.encode()).hexdigest()[:12]


def _set_draft(module, temp, irr, label):
    st.session_state["scenario_draft"] = _scenario(module, temp, irr, label)


def _mirror_scenario(sc: dict) -> None:
    """The dashboard's ONE write to results/, and it goes in its own directory.

    `results/dashboard/` rather than `results/` proper, so a dashboard artefact
    can never sit beside a benchmark export and be mistaken for one. Everything
    under results/phase2/ is read-only to this app. Failure is swallowed: losing
    the mirror must not take a page down with it. (§2.3)
    """
    import json
    try:
        d = _gcfg.RESULTS_DIR / "dashboard"
        d.mkdir(parents=True, exist_ok=True)
        (d / "current_scenario.json").write_text(
            json.dumps(sc, indent=2, default=str), encoding="utf-8")
    except Exception:
        pass


def _send_scenario():
    """Copy the draft to the sent slot — the one write Watch one run reads."""
    draft = st.session_state.get("scenario_draft")
    if draft:
        st.session_state["scenario_sent"] = dict(draft)
        _mirror_scenario(draft)
    return draft


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


def _dual(label, key, presets, unit, step, vmin, vmax, default, help=None,
          disabled=False):
    """A single dropdown of presets (the extra editable box was removed per request)."""
    st.session_state.setdefault(key, float(default))
    cur = st.session_state[key]
    if cur not in presets:
        cur = min(presets, key=lambda p: abs(float(p) - float(cur)))
        st.session_state[key] = float(cur)
    labels = [_dfmt(p, unit) for p in presets]
    st.caption(label)
    sel = st.selectbox(label, labels, index=presets.index(cur), key=f"{key}_pick",
                       label_visibility="collapsed", help=help, disabled=disabled)
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
# The drifting shadow is one substring wide and crosses the module once per event
# window. Declaring the width here fixes the sweep rate: over `slices` samples no
# substring's coverage can change by more than (n_sub + DRIFT_WIDTH)/slices of
# its own width per slice.
DRIFT_WIDTH = 1.0


def _day_event_state(events, time_hour, base_G, n_sub=3):
    """Convert the configured day events into one instantaneous substring state.

    This is the bridge between the temporal event editor and the static scenario
    representation used by the simulator/scenario workflow. It does not replace
    either engine; it only produces the same per-substring irradiance description
    at a selected instant.
    """
    time_hour = float(time_hour)
    base_G = float(base_G)
    frac_day = (time_hour - 6.0) / 12.0
    sun_G = base_G * float(np.clip(np.sin(np.pi * frac_day), 0.0, None))
    sun_G = max(1.0, sun_G)
    irr = [sun_G] * int(n_sub)
    active = []

    for ev in events:
        t0 = float(ev.get("t0", 0.0))
        t1 = float(ev.get("t1", 1.0))
        if not (t0 <= frac_day <= t1):
            continue
        kind = str(ev.get("kind", "Pole or vent"))
        sub, depth = _KIND_MAP.get(kind, (1, 0.4))
        f = float(np.clip((frac_day - t0) / max(t1 - t0, 1e-9), 0.0, 1.0))
        motion = ev.get("motion", "fixed in place")
        if motion == "grows through the event":
            depth = 1.0 - (1.0 - float(depth)) * f
        elif motion == "drifts across the strips" and sub != "all":
            # A continuous edge sweep, not a jump between strips. The shadow is
            # DRIFT_WIDTH substrings wide and its leading edge crosses the module
            # once per event window, so each substring's irradiance ramps in
            # proportion to how much of it the shadow covers. The previous
            # int(f * n_sub) snapped the whole shadow from one strip to the next
            # between slices, which is a teleport no sun makes. (R17)
            lead = f * (int(n_sub) + DRIFT_WIDTH) - DRIFT_WIDTH
            for s in range(int(n_sub)):
                cover = max(0.0, min(s + 1.0, lead + DRIFT_WIDTH) - max(float(s), lead))
                if cover > 0.0:
                    irr[s] = min(irr[s], sun_G * (1.0 - cover * (1.0 - float(depth))))
            active.append(kind)
            continue

        if sub == "all":
            irr = [min(x, sun_G * float(depth)) for x in irr]
        else:
            sub = int(np.clip(sub, 0, int(n_sub) - 1))
            irr[sub] = min(irr[sub], sun_G * float(depth))
        active.append(kind)

    return [float(max(1.0, x)) for x in irr], sun_G, active


def _day_sample_scenarios(events, base_G, temp, module, step_minutes=15):
    """Sample active day-event states into static scenario records.

    The records are intentionally engine-neutral recipes: the event timeline
    supplies time/irradiance/shading state, while the interactive Simulator
    supplies its own datasheet module. No validated CEC module is silently
    converted into a different datasheet model.
    """
    if not events:
        return []
    step = max(5, int(step_minutes))
    start = min(18.0, max(6.0, min(6.0 + float(e.get("t0", 0))*12 for e in events)))
    end = max(6.0, min(18.0, max(6.0 + float(e.get("t1", 1))*12 for e in events)))
    times = np.arange(start, end + 1e-9, step / 60.0)
    out = []
    for h in times:
        irr, sun_G, active = _day_event_state(events, float(h), base_G, _gcfg.N_SUBSTRINGS)
        if not active:
            continue
        # Which events were live at this instant, with enough of each to
        # reconstruct why the irradiance looks the way it does. `active` is only
        # a list of kind names, which cannot tell two poles apart. (U4)
        live = []
        for ev in events:
            if str(ev.get("kind")) not in active:
                continue
            h0, h1 = 6.0 + float(ev.get("t0", 0)) * 12, 6.0 + float(ev.get("t1", 1)) * 12
            if not (h0 <= float(h) <= h1):
                continue
            live.append({"kind": str(ev.get("kind")), "uid": ev.get("uid"),
                         "start_hour": round(h0, 2), "end_hour": round(h1, 2),
                         "duration_hours": round(h1 - h0, 2),
                         "motion": ev.get("motion", "fixed in place")})
        out.append({
            "source": "Explore · day-event timeline",
            "time_hour": round(float(h), 2),
            "time_label": f"{int(h):02d}:{int(round((h % 1) * 60)) % 60:02d}",
            # module_source is the CEC module the events were designed on;
            # module_applied is the Sandbox datasheet that will actually draw the
            # curve. They are different engines and the record says so. (U4)
            "module_source": str(module),
            "module_applied": str(st.session_state.get("bench_preset", "—")),
            "temperature_C": float(temp),
            "base_irradiance_Wm2": float(sun_G),
            "substring_irradiance_Wm2": irr,
            "active_events": active,
            "events": live,
            "scenario_hash": _scenario_hash(module, temp, irr),
        })
    return out


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


def _day_window_from_hour(hour, duration=1.5):
    """Return a normalized 06:00–18:00 event window starting at `hour`."""
    hour = float(np.clip(hour, 6.0, 18.0))
    duration = float(max(0.25, duration))
    end = min(18.0, hour + duration)
    start = hour
    # Keep the default duration when the playhead is near 18:00 by shifting left.
    if end - start < duration:
        start = max(6.0, end - duration)
    return (start - 6.0) / 12.0, (end - 6.0) / 12.0


def _day_uid() -> str:
    from uuid import uuid4
    return uuid4().hex[:8]


def _day_migrate(events):
    """Give every event a stable id.

    Widgets used to be keyed by list position, so deleting an event shifted every
    later event's window and motion onto its neighbour. Keys follow the event
    now, not its index. (R4)
    """
    for ev in events or []:
        if not ev.get("uid"):
            ev["uid"] = _day_uid()
    return events


def _day_drop(uid):
    """Remove one event and the widget state that belonged to it."""
    events = st.session_state.get("day_events") or []
    st.session_state["day_events"] = [e for e in events if e.get("uid") != uid]
    for k in (f"day_win_{uid}", f"day_mot_{uid}"):
        st.session_state.pop(k, None)
    st.session_state.pop("day_scenario_samples", None)   # derived from the events
    st.session_state.pop("day_ran", None)


def _day_add(kind):
    """Add an event at the current timeline playhead instead of a hard-coded slot."""
    st.session_state.setdefault("day_events", [])
    hour = float(st.session_state.get("day_time", 15.0))
    t0, t1 = _day_window_from_hour(hour, duration=1.5)
    events = st.session_state["day_events"]
    events.append({
        "kind": kind,
        "t0": t0,
        "t1": t1,
        "motion": "fixed in place",
        "created_at_hour": hour,
        "uid": _day_uid(),
    })
    st.session_state.pop("day_scenario_samples", None)
    st.session_state.pop("day_ran", None)


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


@st.cache_data(show_spinner="Running your day through the trackers…")
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
    events = [{"kind": k, "t0": t0, "t1": t1, "motion": motion}
              for k, t0, t1, motion in events_key]
    # G2, the curve-integrity gate transition.py applies: the power the curve
    # reports at v_gmpp must reproduce p_gmpp. A slice that fails it is a curve
    # the trackers would be stepping through incorrectly, so the count is
    # reported rather than assumed.
    g2_pass, g2_total, worst_rel = 0, 0, 0.0
    # A5 plays these slices back, so each one's curve and its own G2 verdict are
    # RECORDED here rather than recomputed by the animation. Nothing about the
    # run changes: the same curves, the same gate, the same counts. (§11)
    slice_curves, slice_g2 = [], []
    for ti, g in zip(times, sun):
        irr, _, _ = _day_event_state(events, float(ti), float(base_G), 3)
        cur = curve_at(irr)
        V, Pp, v_g, p_g = cur
        rel = abs(float(np.interp(v_g, V, Pp)) - p_g) / max(p_g, 1e-9)
        g2_total += 1
        g2_pass += int(rel <= 1e-3)
        worst_rel = max(worst_rel, rel)
        curves.append(cur)
        unshaded.append(curve_at([max(1.0, float(g))] * 3)[3])
        keep = np.linspace(0, len(V) - 1, min(len(V), 200)).astype(int)
        slice_curves.append({"t": float(ti),
                             "V": [float(x) for x in V[keep]],
                             "P": [float(x) for x in Pp[keep]],
                             "gmpp": {"V": float(v_g), "P": float(p_g)},
                             "irr": [list(e) if isinstance(e, (list, tuple))
                                     else float(e) for e in irr]})
        slice_g2.append({"pass": bool(rel <= 1e-3), "rel": float(rel)})

    bs = np.array([SPS] * slices); scored = np.ones(slices, bool)
    mk = lambda: dyn.DynamicTrajectory(curves=curves, block_steps=bs, scored=scored,
                                       module=module)
    out = {"t": [float(x) for x in np.repeat(times, SPS)],
           "unshaded": [float(x) for x in np.repeat(unshaded, SPS)], "methods": {}}

    out["v_hist"] = {}

    def run(name, fn, **kw):
        tj = mk(); fn(tj, n_steps=int(bs.sum()), **kw)
        out["methods"][name] = [float(x) for x in tj.p_hist]
        out["v_hist"][name] = [float(x) for x in tj.v_hist]   # A6 plays these back
        out["avail"] = [float(x) for x in tj.avail_hist]

    run("P&O", trk.perturb_and_observe)
    run("PSO", pso.particle_swarm)
    model = _c3_model()
    if model is not None:
        from gmppt import hybrid as hyb
        run("Hybrid (bounded)", hyb.make_hybrid(model), temp_c=float(temp))
    av = np.array(out["avail"])
    out["energy"] = {m: 100 * float(np.sum(ph)) / max(1e-9, float(np.sum(av)))
                     for m, ph in out["methods"].items()}
    out["has_model"] = model is not None
    out["g2"] = {"passed": int(g2_pass), "total": int(g2_total),
                 "worst_rel": float(worst_rel), "tol": 1e-3}
    out["slice_curves"] = slice_curves
    out["slice_g2"] = slice_g2            # a failed slice is kept, never dropped
    out["slices"] = int(slices)
    out["steps_per_slice"] = int(SPS)
    return out


def _unseen_check(name):
    """What kind of data this panel is, in one line — detail on request. (U1.5, §10)

    This used to print the split counts, the nearest training module and an
    explanation of how the check is performed, right beside the module picker.
    That is bookkeeping about how the app is built, not something a reader needs
    in order to understand the panel in front of them. The one fact that matters
    stays visible; the rest moved into Technical details, where it is still
    available for reproducibility.
    """
    in_train = str(name) in _train_module_names()
    if in_train:
        # This would invalidate the page, so it is a warning, not a detail.
        ui.callout("This panel is not validation data, so its curve cannot be "
                   "compared with the benchmark results.", "Wrong data set", "limit")
        return
    ui.data_chip("Validation data",
                 "Used to compare tracking methods. Held-out test data is not shown.")
    with st.expander("Technical details", expanded=False):
        counts = _split_counts()
        near, dist = _nearest_train(name)
        st.markdown(
            f"- Module set: `{name}`\n"
            f"- Split sizes — train {counts['train']:,}, validation {counts['val']:,}, "
            f"test {counts['test']:,}. The test set is reserved and is never read here.\n"
            f"- Nearest training module: `{near}` at a normalised parameter distance "
            f"of {dist:.2f}.\n"
            f"- Membership is resolved live through `gmppt.dataset.module_split()`, "
            f"the same call `p7_tracker_comparison.py --split val` makes. The model "
            f"file does not store its own training list, so the check is made against "
            f"the split function.")


def page_panels():
    _demo_startup_log()
    ui.page_intro("Your panels",
                  "Put a shadow on a panel and see what it does to the power it can make.",
                  "Understand · The panels")
    c = ui.T()
    try:
        val_mods = _validation_modules()
        assert val_mods
    except Exception as e:
        ui.callout(f"Could not load the validation-module pool ({e}). Make sure the "
                   "`gmppt/` package and `results/cec_pool.parquet` sit beside "
                   "`gmppt_app.py`.", "Engine not connected", "limit")
        return
    # Nothing is drawn unless every module offered is a validation module. (U1.3)
    if not assert_val_modules([n for _, n in val_mods], "The panel dropdown"):
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
                ui.callout("Nanum's target spec is awaited — a validation module is "
                           "shown in the meantime.", "", "info")
            _unseen_check(name)
            rows = int(_dual("Rows of panels", "gm_rows", [1, 2, 3, 4, 6], "", 1, 1, 6, 3))
            per = int(_dual("Panels per row", "gm_per", [1, 2, 3, 4, 5, 6, 8], "", 1, 1, 8, 5))
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
            # Cloud and soiling are modelled as a graded blanket over the whole
            # module, so _event_pattern ignores Width and Runs for them. Disabling
            # the two controls says so instead of letting them look live.
            covers_all = obj in ("Cloud", "Soiling")
            depth = _dual("How dark the shadow is", "gm_depth2",
                          [0, 100, 200, 240, 300, 400, 600, 900], " W/m²", 10, 0, 900, 240,
                          help="Irradiance left under the shadow. Lower = darker.")
            width = _dual("How wide the shadow is", "gm_width",
                          [0.25, 0.4, 0.5, 0.55, 0.75, 1.0], "", 0.05, 0.0, 1.0, 0.55,
                          help=("Unavailable for cloud and soiling: those cover the whole "
                                "module, so there is no width to set." if covers_all
                                else None),
                          disabled=covers_all)
            rc1, rc2 = st.columns(2)
            default_runs = 0 if mount == "Portrait" else 1
            runs = rc1.selectbox("Runs", ["across the strips", "along the strips",
                                          "diagonally"], index=default_runs, key="gm_runs",
                                 disabled=covers_all,
                                 help="Unavailable for cloud and soiling: those cover the "
                                      "whole module as a graded blanket, so direction has "
                                      "nothing to run along." if covers_all else None)
            edge = rc2.selectbox("Edge", ["hard", "soft (penumbra)", "dappled"], key="gm_edge")
            if covers_all:
                shaded_ids = list(ids)
                st.caption("Cloud and soiling cover the whole array, and are graded across "
                           "the module rather than following a direction.")
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
        # No Run button here: the page is reactive and recomputes on every control
        # change, so a button would only ever redraw what is already correct.
        if st.button("Reset shadow", key="gm_reset_shadow", use_container_width=True,
                     help="Restores the shadow controls to their defaults. The module, "
                          "the array size and the conditions are left alone."):
            for _k in ("gm_obj2", "gm_depth2", "gm_width", "gm_runs", "gm_edge",
                       "gm_shaded_ids"):
                st.session_state.pop(_k, None)
            st.toast("Shadow controls reset — module and conditions kept.")
            st.rerun()

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
        # The drag and paint tools are gone rather than shown disabled: a control
        # that can never be enabled is furniture, and the shadow controls on the
        # left already do the job.
        st.markdown(
            f"<div class='bh'>Your panels</div>"
            f"<div style='font-size:13.5px;color:{c['text_muted']}'>{n_panels} panels in "
            f"{rows} string{'s' if rows > 1 else ''} — pick one to inspect it.</div>",
            unsafe_allow_html=True)

        # ---- panel navigation (U3) ----------------------------------------
        # The drag and paint tools are gone (they could never be enabled), but
        # walking the array is a real need, so Previous/Next replace them. These
        # move the INSPECTED panel only: the draft follows, because `sel_irr`
        # depends on whether this panel is shaded, but nothing else does.
        default_id = shaded_ids[0] if shaded_ids else ids[0]
        if st.session_state.get("gm_sel") not in ids:
            st.session_state["gm_sel"] = default_id
        cur_idx = ids.index(st.session_state["gm_sel"])

        def _step_panel(delta):
            """on_click so the keyed selectbox sees the new value on this run."""
            i = ids.index(st.session_state.get("gm_sel", default_id))
            st.session_state["gm_sel"] = ids[min(max(i + delta, 0), len(ids) - 1)]

        # wide enough that the labels never truncate to "‹ Pr…" (§51)
        nav = st.columns([1.15, 2.1, 1.15, 1.6], vertical_alignment="bottom")
        nav[0].button("‹ Prev", key="gm_panel_prev", use_container_width=True,
                      disabled=cur_idx == 0, on_click=_step_panel, args=(-1,),
                      help="Inspect the previous panel in the array. Stops at the "
                           "first panel; it does not wrap around.")
        with nav[1]:
            sel_id = st.selectbox("Select panel", ids, key="gm_sel",
                                  help="Jump straight to a panel. Changing the inspected "
                                       "panel updates the draft scenario, because a "
                                       "shaded panel has a different curve. It does not "
                                       "change the shadow, the conditions, the scenario "
                                       "already sent to Watch one run, or your saved scenarios.")
        nav[2].button("Next ›", key="gm_panel_next", use_container_width=True,
                      disabled=cur_idx == len(ids) - 1, on_click=_step_panel, args=(1,),
                      help="Inspect the next panel in the array. Stops at the last "
                           "panel; it does not wrap around.")
        sel_idx = ids.index(sel_id)
        nav[3].markdown(
            f"<div class='bmono' style='font-size:12.5px;color:{c['text_muted']};"
            f"padding-bottom:10px'>Panel {_e(sel_id)} of {n_panels}</div>",
            unsafe_allow_html=True)
        if st.button("Reset inspected panel", key="tool_clear",
                     help="Go back to the first shaded panel. The shadow, the "
                          "conditions and everything you have saved are left alone."):
            st.session_state["gm_sel"] = default_id
            st.toast(f"Inspecting {default_id} again — nothing else was reset.")
            st.rerun()
        st.markdown(_array_svg(rows, per, shaded_idx, sel_idx,
                               ui.EVENT_COLORS.get(obj, "#C2BFB6"), c, sel_id),
                    unsafe_allow_html=True)
        ui.kpi_row([
            # Not "what the array makes": it is the sum of each module sitting at
            # its own GMPP, which assumes every optimizer has already found it.
            ("Array upper bound",
             f"{array_now/1000:.2f} kW",
             f"of {array_uns/1000:.2f} kW unshaded · every optimizer at its GMPP",
             "hero"),
            ("Shaded panels", str(len(shaded_idx)),
             "covering everything" if covers_all else f"under the {obj.lower()}"),
            ("Shadow type", shadow_type, runs),
        ], weights=[1.25, 1, 1])
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
                # the shared rule, not a third copy of the threshold (§10)
                _state = lambda vk: _diode_state(vk, clamp)
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
                ui.mark_gmpp(fig, det["gmpp"]["V"], det["gmpp"]["P"],
                             textposition="top left"
                             if det["gmpp"]["V"] > 0.7 * (det["voc"] or 1.0)
                             else "top right")
                # headroom for the peak label, over EVERY curve drawn — the
                # unshaded reference is taller than the shaded one
                top = float(max(det["P"]))
                if show_uns and sel_shaded:
                    top = max(top, float(max(uns["P"])))
                fig.update_yaxes(range=[0, 1.18 * top])
                ui.mark_local_peaks(fig, [(v, i, pw) for (v, i, pw) in det["peaks"]
                                          if abs(pw - det["gmpp"]["P"]) > 1e-6])
                ui.style_fig(fig, height=230, x_title="Voltage (V)", y_title="Power (W)")
            else:
                fig.add_trace(go.Scatter(x=det["V"], y=det["I"], name="I–V",
                                         line=dict(color="#2C7FA0", width=3)))
                ui.style_fig(fig, height=230, x_title="Voltage (V)", y_title="Current (A)")
            fig.update_layout(showlegend=False, margin=dict(l=48, r=10, t=10, b=40))
            ui.show_chart(fig)

            with st.container(key="next-panelsend"):
                if st.button("Send this panel to the trackers  →", key="send_trackers",
                             type="primary", use_container_width=True):
                    _send_scenario()
                    st.switch_page(P["run"])

        ui.callout("Not this page. The optimizer behind this panel measures its own "
                   "voltage and current, one point at a time, plus one temperature. "
                   "This view is for you.", "What the algorithm gets to see", "caveat")

    # The draft is rewritten on every render, so Inside a panel always shows what
    # is on screen here. Testing keeps running whatever was last SENT.
    _set_draft(name, T, sel_irr, f"Panel {sel_id} · {obj}")

    # ------------------------------------------------------------------ day timeline (functional)
    _default_t0, _default_t1 = _day_window_from_hour(15.0, duration=1.5)
    st.session_state.setdefault("day_events", [{"kind": "Pole or vent",
                                                "t0": _default_t0, "t1": _default_t1,
                                                "motion": "fixed in place",
                                                "created_at_hour": 15.0,
                                                "uid": _day_uid()}])
    _day_migrate(st.session_state["day_events"])   # events restored from a session file
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
        ph_t = st.slider("Event time / playhead", 6.0, 18.0, 15.0, 0.25, key="day_time", format="%.2f")
        st.caption("Select a time, then add an event. The new event starts at the selected time; adjust its duration and motion below.")
        st.markdown(_day_timeline_svg(st.session_state["day_events"], (ph_t - 6) / 12, c),
                    unsafe_allow_html=True)
        with st.expander("Day behaviour \u2014 timing and motion of each event", expanded=False):
            st.caption("Motion belongs to the day timeline: it decides how an event "
                       "changes while it passes, not what the single-moment curve above "
                       "looks like.")
            _rm = None
            for _ev in list(st.session_state["day_events"]):
                _ev.setdefault("motion", "fixed in place")
                _uid = _ev["uid"]
                ec = st.columns([1.5, 2.5, 1.8, 0.5], vertical_alignment="center")
                ec[0].markdown(f"**{_ev['kind']}**")
                _w = ec[1].slider(f"window {_uid}", 6.0, 18.0,
                                  (6 + _ev["t0"] * 12, 6 + _ev["t1"] * 12), 0.25,
                                  key=f"day_win_{_uid}", label_visibility="collapsed")
                if (_w[0] - 6) / 12 != _ev["t0"] or (_w[1] - 6) / 12 != _ev["t1"]:
                    st.session_state.pop("day_scenario_samples", None)
                    st.session_state.pop("day_ran", None)
                _ev["t0"], _ev["t1"] = (_w[0] - 6) / 12, (_w[1] - 6) / 12
                _opts = _day_motions_for(_ev["kind"])
                if _ev["motion"] not in _opts:
                    _ev["motion"] = _opts[0]
                _new_motion = ec[2].selectbox(
                    f"motion {_uid}", _opts, index=_opts.index(_ev["motion"]),
                    key=f"day_mot_{_uid}", label_visibility="collapsed",
                    help="Day-event motion \u2014 how the shadow changes across its own window.")
                if _new_motion != _ev["motion"]:
                    st.session_state.pop("day_scenario_samples", None)
                    st.session_state.pop("day_ran", None)
                _ev["motion"] = _new_motion
                if ec[3].button("\u2715", key=f"day_rm_{_uid}"):
                    _rm = _uid
            if _rm is not None:
                _day_drop(_rm); st.rerun()
            if st.button("Clear all events", key="day_clear"):
                for _e2 in st.session_state["day_events"]:
                    for _k2 in (f"day_win_{_e2.get('uid')}", f"day_mot_{_e2.get('uid')}"):
                        st.session_state.pop(_k2, None)
                st.session_state["day_events"] = []
                st.session_state.pop("day_scenario_samples", None)
                st.session_state.pop("day_ran", None)
                st.rerun()

        # ------------------------------------------------------------------ scenario bridge
        # The timeline creates temporal event definitions. Sampling them produces
        # instantaneous irradiance recipes that the interactive Simulator can load.
        # The module itself is not silently converted between the validated and
        # simplified engines.
        if st.session_state["day_events"]:
            with st.expander("Use these events as simulator scenarios", expanded=False):
                st.caption("Sample the active event windows into static 15-minute scenario states. "
                           "The event timing and substring irradiance are transferred; the "
                           "Simulator uses its own datasheet module and simplified engine.")
                if st.button("Create scenario samples", key="day_make_samples", use_container_width=True):
                    st.session_state["day_scenario_samples"] = _day_sample_scenarios(
                        st.session_state["day_events"], base_G, T, name, step_minutes=15)
                samples = st.session_state.get("day_scenario_samples") or []
                if samples:
                    st.success(f"Created {len(samples)} instantaneous scenario states from the event window.")
                    sdf = pd.DataFrame([{
                        "Time": x["time_label"],
                        "Sunlight (W/m²)": round(x["base_irradiance_Wm2"]),
                        "Substring irradiance (W/m²)": str([round(v) for v in x["substring_irradiance_Wm2"]]),
                        "Events": ", ".join(x["active_events"]),
                    } for x in samples])
                    st.dataframe(sdf, hide_index=True, width="stretch")
                    sc_idx = st.selectbox("Sample to load", range(len(samples)),
                                          format_func=lambda i: samples[i]["time_label"] + " · " + ", ".join(samples[i]["active_events"]),
                                          key="day_sample_pick")
                    if st.button("Load selected irradiance into Simulator", key="day_load_sim",
                                  type="primary", use_container_width=True):
                        st.session_state["day_sim_import"] = dict(samples[sc_idx])
                        st.switch_page(P["sim_setup"])
                    import json as _json
                    _day_json = _json.dumps(samples, indent=2)
                    st.download_button("Download sampled scenarios (JSON)", _day_json,
                                       "day_event_scenarios.json", "application/json",
                                       use_container_width=True, key="day_samples_json")
        # The tracker run itself lives on Testing · Dynamic irradiance, under
        # "Your day", where it can sit beside the gated EN 50530 result and be
        # labelled against it. This page builds, times and samples the events.
        st.session_state["day_context"] = {"module": name, "temp": int(T),
                                           "base_G": int(base_G)}
        if run_day:
            st.switch_page(P["moving"])


def page_inside():
    # Sections, top to bottom (§15): orientation → operating point → panel
    # response → substring state → why the curve has steps → next action. One
    # idea per section, no bordered card around ordinary text (§20).
    ui.page_intro("Inside a panel",
                  "Move the operating point and see how the panel responds.",
                  "Inspect · Inside a panel")
    draft = st.session_state.get("scenario_draft")
    if not draft:
        ui.callout("Set up a shadow on the panels page first — this page explains "
                   "that result.", "Nothing to show yet", "info")
        st.page_link(P["panels"], label="Go to the panels →")
        return
    c = ui.T()
    name, T = draft["module"], float(draft["temp"])
    irr = [list(e) if isinstance(e, (list, tuple)) else float(e) for e in draft["irr"]]
    irr_key = _key(irr)
    det = _sim(name, irr_key, T)
    voc = det["voc"] or 1.0
    st.caption(f"The scenario you are editing on The panels: {draft.get('label', name)}.")

    # ---------------------------------------------------------- operating point
    ui.section_head("Operating point",
                    "voltage in → current and power out → curves and diodes follow")
    # The slider's stored value can outlive the scenario it was set for: a new
    # shadow gives a different V_oc, and a stale value outside [0, voc] makes
    # st.slider raise. Clamp before rendering. (R7)
    _v_default = float(det["gmpp"]["V"])
    if "gm_vop" in st.session_state:
        try:
            st.session_state["gm_vop"] = min(max(float(st.session_state["gm_vop"]), 0.0),
                                             round(voc, 1))
        except (TypeError, ValueError):
            st.session_state.pop("gm_vop", None)
    v_op = st.slider("Terminal voltage", 0.0, round(voc, 1),
                     round(_v_default, 1), 0.1, key="gm_vop", format="%.2f V",
                     help="The operating voltage currently applied to the panel. "
                          "Everything below follows from it.")
    i_op = float(np.interp(v_op, det["V"], det["I"]))
    ui.kpi_row([("Current", f"{i_op:.2f} A", "at this voltage"),
                ("Power", f"{v_op * i_op:.1f} W", "at this operating point")],
               weights=[1, 1])
    vsub, clamp = _substring_voltages(name, irr, T, i_op)

    # ---------------------------------------------------------- panel response
    st.space(size="small")
    ui.section_head("Panel response",
                    "power and current against voltage, with your operating point on both")
    op = dict(color=ui.PEAK_COLORS["operating"])
    left, right = st.columns(2, gap="medium")
    with left:
        figp = go.Figure(go.Scatter(x=det["V"], y=det["P"], name="P–V",
                                    line=dict(color=c["teal"], width=2.6)))
        # label to the left when the peak is near the right edge, or it clips
        ui.mark_gmpp(figp, det["gmpp"]["V"], det["gmpp"]["P"],
                     textposition="top left" if det["gmpp"]["V"] > 0.7 * voc
                     else "top right")
        ui.mark_local_peaks(figp, [(v, i, pw) for (v, i, pw) in det["peaks"]
                                   if abs(pw - det["gmpp"]["P"]) > 1e-6])
        figp.add_vline(x=v_op, line=dict(width=1.5, dash="dash", **op))
        figp.add_trace(go.Scatter(x=[v_op], y=[v_op * i_op], mode="markers",
                                  name="operating point",
                                  marker=dict(size=11, symbol="circle",
                                              line=dict(color="#fff", width=1.5), **op)))
        ui.style_fig(figp, height=300, x_title="voltage  V", y_title="power  W")
        # headroom so the peak label is never clipped by the plot's top edge
        figp.update_yaxes(range=[0, 1.18 * float(max(det["P"]))])
        figp.update_layout(legend=dict(orientation="h", y=1.12, x=0))
        ui.show_chart(figp, key="inside_pv")
    with right:
        figi = go.Figure(go.Scatter(x=det["V"], y=det["I"], name="I–V",
                                    line=dict(color="#2C7FA0", width=2.6)))
        figi.add_vline(x=v_op, line=dict(width=1.5, dash="dash", **op))
        figi.add_trace(go.Scatter(x=[v_op], y=[i_op], mode="markers",
                                  name="operating point",
                                  marker=dict(size=11, symbol="circle",
                                              line=dict(color="#fff", width=1.5), **op)))
        ui.style_fig(figi, height=300, x_title="voltage  V", y_title="current  A")
        figi.update_layout(legend=dict(orientation="h", y=1.12, x=0))
        ui.show_chart(figi, key="inside_iv")
    ui.legend_note(f"{det['n_peaks']} peak(s). The dashed line and dot are the operating "
                   f"point you are moving.")
    ui.engine_badge("validated")

    # ---------------------------------------------------------- substring state
    st.space(size="small")
    ui.section_head("Substring state", "what each strip is doing at this operating point")
    cells = ""
    for k, (entry, vk) in enumerate(zip(irr, vsub)):
        light = (sum(entry) / len(entry)) if isinstance(entry, (list, tuple)) else entry
        state = _diode_state(vk, clamp)
        tone = c["amber_text"] if state != "off" else c["text"]
        word = {"on": "bypass on — current goes around",
                "partial": "bypass partly on", "off": "bypass off"}[state]
        cells += (f"<div class='gm-sub'><b>S{k + 1}</b>"
                  f"<span>{light:.0f} W/m² of light</span>"
                  f"<span style='color:{tone};font-weight:600'>{word}</span>"
                  f"<span>adds {vk:.2f} V</span></div>")
    st.markdown(f"<div class='gm-subrow'>{cells}</div>", unsafe_allow_html=True)

    # ---------------------------------------------------------- why the steps
    st.space(size="small")
    ui.section_head("Why the curve has steps")
    st.markdown("A shaded substring may not be able to carry the current the other "
                "cells demand. Its bypass diode turns on, and that substring's voltage "
                "drops out of the sum. That is the step in the P–V curve — and each "
                "step can leave a peak behind it.")
    with st.expander("Technical details", expanded=False):
        st.markdown(
            "- A substring (a strip) is the group of cells sharing one bypass diode; "
            f"this module has {_gcfg.N_SUBSTRINGS}.\n"
            "- Diode state is read from the substring's own element I–V curve at the "
            "string current: on when its voltage is at the diode clamp, partly on "
            "when it has gone negative but not to the clamp, off otherwise.\n"
            "- The table above, the sweep below and the bypass table on The panels "
            "all use this one rule.")

    # ---------------------------------------------------------- next action
    st.space(size="small")
    ui.section_head("Next", "send this exact scenario to the tracking methods")
    a, b = st.columns([1.3, 3], vertical_alignment="center")
    if a.button("Watch the trackers →", key="inside_send", type="primary",
                use_container_width=True,
                help="Sends the scenario you are looking at to Watch one run."):
        _send_scenario()
        st.switch_page(P["run"])
    b.markdown(f"<span style='color:{c['text_muted']};font-size:0.9rem'>Each method "
               f"searches this same curve, step by step, and you can see which ones "
               f"settle on the wrong peak.</span>", unsafe_allow_html=True)

    # ---------------------------------------------------------- look further
    st.divider()
    ui.section_head("Look further", "two animations built from this same panel")
    _a3_voltage_sweep(name, irr, T, det, clamp)
    st.space(size="small")
    _a4_peak_formation(name, irr, T)


# =========================================================================== #
# A3 — Voltage sweep and bypass switching  (Update 3 §5.3, user §10)
#
# Every frame is the validated engine's own answer. The operating point walks
# V = 0 -> V_oc along the curve `_sim` already computed; the per-substring
# voltages come from the element I–V curves `_substring_curves` computed once
# from gmppt.device; and the diode state is read through `_diode_state`, the
# same function the table on this page uses. Nothing about a diode transition
# is drawn by hand — the switch annotations sit exactly where the engine's
# state vector changes and nowhere else.
# =========================================================================== #
_A3_FRAMES = 60


def _a3_sweep(name, irr, T, det, clamp, n_frames=_A3_FRAMES):
    """Frames along V = 0 → V_oc, with the diode state at each one.

    Returns (frames, switch_steps). A switch step is a frame whose diode state
    vector differs from the frame before it — the only places an annotation is
    allowed.
    """
    import numpy as np
    V = np.asarray(det["V"], float)
    I = np.asarray(det["I"], float)
    Pw = np.asarray(det["P"], float)
    voc = float(det["voc"])
    curves, _clamp = _substring_curves(name, _key(irr), float(T))

    # first frame V = 0, last frame V = V_oc, exactly (§10)
    vs = np.linspace(0.0, voc, int(n_frames))
    frames, prev, switches = [], None, []
    for k, v in enumerate(vs):
        i_op = float(np.interp(v, V, I))
        p_op = float(np.interp(v, V, Pw))
        vsub = [float(np.interp(i_op, ie[::-1], vv[::-1])) for vv, ie in curves]
        state = tuple(_diode_state(x, clamp) for x in vsub)
        changed = prev is not None and state != prev
        if changed:
            switches.append(k)
            moved = [j for j in range(len(state)) if state[j] != prev[j]]
            title = ("At {:.1f} V — ".format(v) + ", ".join(
                f"S{j+1} bypass {state[j]}" for j in moved))
        else:
            title = "At {:.1f} V — {:.2f} A, {:.0f} W".format(v, i_op, p_op)
        frames.append({
            "step": k, "title": title,
            "markers": {"operating point": {"V": v, "P": p_op},
                        "current": {"V": v, "P": i_op}},
            "trails": {"operating point": [(float(x), float(np.interp(x, V, Pw)))
                                           for x in vs[:k + 1]]},
            "state": list(state),
            "v": float(v), "i": float(i_op), "p": float(p_op),
            "vsub": [round(x, 3) for x in vsub],
        })
        prev = state
    return frames, switches


def _a3_voltage_sweep(name, irr, T, det, clamp):
    """Render A3."""
    c = ui.T()
    ui.section_head("Drive the whole sweep",
                    "from short circuit to open circuit, with each diode switching "
                    "where the engine says it does")
    ui.anim_badge("live", "this panel · validated engine")

    if st.button("▶ Build the sweep", key="a3_build",
                 help="Walks the operating point from 0 V to V_oc on the validated "
                      "engine's curve and reads each diode's state at every step."):
        st.session_state["a3_built"] = True
    if not st.session_state.get("a3_built"):
        st.caption("Press ▶ to sweep the operating point across the whole curve and "
                   "watch the bypass diodes switch.")
        return

    import time as _time
    t0 = _time.perf_counter()
    frames, switches = _a3_sweep(name, irr, T, det, clamp)
    build_s = _time.perf_counter() - t0
    if not frames:
        ui.callout("This panel has no curve to sweep.", "Nothing to show", "limit")
        return

    key_frames = sorted({0, len(frames) - 1, *switches})
    V, Pw, I = list(det["V"]), list(det["P"]), list(det["I"])
    static = [go.Scatter(x=V, y=Pw, mode="lines", name="P–V",
                         line=dict(color=c["teal"], width=2.5)),
              go.Scatter(x=[det["gmpp"]["V"]], y=[det["gmpp"]["P"]], mode="markers",
                         name="true peak",
                         marker=dict(symbol="star", size=15,
                                     color=ui.PEAK_COLORS["gmpp"])),
              ui.panel_trace(go.Scatter(x=V, y=I, mode="lines", name="I–V",
                                        line=dict(color="#2C7FA0", width=2.5)))]
    series = {"operating point": {"color": ui.PEAK_COLORS["operating"],
                                  "symbol": "circle"},
              "current": {"color": "#2C7FA0", "symbol": "square",
                          "panel": "current"}}

    n_sw, n_pk = len(switches), int(det["n_peaks"])
    if n_sw:
        caption = (f"Sweeping from 0 V to {float(det['voc']):.1f} V, a bypass diode "
                   f"changes state {n_sw} time{'s' if n_sw != 1 else ''}: "
                   + "; ".join(f"at {frames[k]['v']:.1f} V" for k in switches[:6])
                   + f". Each switch drops a strip out of the voltage sum, and that "
                     f"is what puts a step in the curve — this one has {n_pk} peak(s).")
    elif n_pk > 1:
        # Say what actually happened, not what usually happens. A curve can have
        # several peaks with no diode ever fully conducting: partial shading
        # WITHIN a strip bends that strip's own characteristic.
        caption = (f"Sweeping the whole curve, no bypass diode ever fully turns on — "
                   f"yet the curve still has {n_pk} peaks. They come from shading "
                   f"within the strips rather than from a strip dropping out. "
                   f"Deepen the shadow on The panels to make a diode switch.")
    else:
        caption = (f"Sweeping from 0 V to {float(det['voc']):.1f} V, no bypass diode "
                   f"changes state and the curve has a single peak — this is the "
                   f"unshaded case an ordinary hill-climber handles.")

    if not ui.anim_on():
        ui.callout("Animations are off, so the switching points are shown as stills. "
                   "Turn them on in the header to drive the sweep.", "Static view", "info")
        ui.snapshot_strip(frames, key_frames,
                          captions=[frames[k]["title"] for k in key_frames],
                          static_traces=static[:2],
                          series={"operating point": series["operating point"]},
                          key="a3")
        st.markdown(f'<div class="gm-legend">{_e(caption)}</div>', unsafe_allow_html=True)
        _a3_detail(frames, switches)
        return

    fig = ui.trace_player(frames, series, static_traces=static, height=520,
                          key_frames=key_frames, step_prefix="step ", frame_ms=90,
                          y_title="power  W")
    ui.show_chart(fig, key="a3_player")
    st.markdown(f'<div class="gm-legend">{_e(caption)}</div>', unsafe_allow_html=True)
    with st.expander("Show every switching point as a still", expanded=False):
        ui.snapshot_strip(frames, key_frames,
                          captions=[frames[k]["title"] for k in key_frames],
                          static_traces=static[:2],
                          series={"operating point": series["operating point"]},
                          key="a3-keys")
    _a3_detail(frames, switches)
    measured = ui.anim_exports(fig, frames,
                               {"badge": "live illustration",
                                "detail": "one panel, validated engine",
                                "module": name, "stride": 1}, key="a3",
                               name="voltage_sweep")
    ui.anim_budget_note(measured, 1, build_s)
    print(f"[gmppt_app] A3 frames={measured['frames']} switches={len(switches)} "
          f"json={measured['figure_json_mb']}MB build={build_s:.3f}s", flush=True)


def _a3_detail(frames, switches):
    rows = "\n".join(
        f"- Step {k} at `{frames[k]['v']:.2f} V` — state "
        f"{', '.join(f'S{j+1}={s}' for j, s in enumerate(frames[k]['state']))}, "
        f"substring volts {frames[k]['vsub']}"
        for k in switches[:12])
    with st.expander("Technical details", expanded=False):
        st.markdown(
            (rows + "\n" if rows else "- The diode state never changes on this "
                                      "scenario.\n")
            + "- The sweep is `numpy.linspace(0, V_oc, "
              f"{len(frames)})` over the curve `gmppt.device.module_iv` returned; "
              "each substring voltage is interpolated along that substring's own "
              "element I–V from the same engine.\n"
              "- Diode state is read through the one `_diode_state` rule the bypass "
              "table above uses, so the animation and the table cannot disagree.\n"
              "- Annotations appear only on the steps listed here; no transition is "
              "drawn where the engine did not report one.")


# =========================================================================== #
# A4 — Peak formation  (Update 3 §5.3, user §10)
#
# The shadow is deepened from "nothing" to the scenario the reader built, and
# the curve is recomputed by the validated engine at every step. Peak counts
# and the GMPP's substring are READ from gmppt.device.analyse at each step, not
# assumed: the key frames are the steps where one of them changes, whatever
# they turn out to be on this scenario.
# =========================================================================== #
_A4_STEPS = 24                       # validated-engine curve evaluations, <= 60
_A4_POINTS = 240                     # points kept per frame, for the JSON budget


def _a4_curves(name, irr, T, steps=_A4_STEPS):
    """Curves from unshaded to the built scenario, plus what changed where.

    Returns (curves, labels, key_frames, facts). Every curve is the engine's;
    the only thing this function invents is the path between them, which is a
    linear ramp of each substring's irradiance from the unshaded base to its
    scenario value.
    """
    import numpy as np
    base = max((max(e) if isinstance(e, (list, tuple)) else e) for e in irr)
    curves, labels, facts = [], [], []
    prev = None
    key = {0}
    for s in range(steps):
        f = s / (steps - 1) if steps > 1 else 1.0
        stage = []
        for e in irr:
            if isinstance(e, (list, tuple)):
                stage.append([float(base + (x - base) * f) for x in e])
            else:
                stage.append(float(base + (e - base) * f))
        det = _sim(name, _key(stage), float(T))
        V = np.asarray(det["V"], float)
        Pw = np.asarray(det["P"], float)
        if len(V) > _A4_POINTS:                      # thin for the frame budget
            idx = np.linspace(0, len(V) - 1, _A4_POINTS).astype(int)
            V, Pw = V[idx], Pw[idx]
        voc = float(det["voc"]) or 1.0
        gv, gp = float(det["gmpp"]["V"]), float(det["gmpp"]["P"])
        strip = min(int(gv / (voc / _gcfg.N_SUBSTRINGS)), _gcfg.N_SUBSTRINGS - 1)
        n_pk = int(det["n_peaks"])
        curves.append({"V": [float(x) for x in V], "P": [float(x) for x in Pw],
                       "gmpp": {"V": gv, "P": gp}})
        darkest = min((min(e) if isinstance(e, (list, tuple)) else e) for e in stage)
        labels.append(f"shadow at {darkest:.0f} W/m² — {n_pk} peak(s), "
                      f"true peak in S{strip + 1} at {gp:.0f} W")
        facts.append({"frac": round(f, 3), "darkest": round(darkest, 1),
                      "n_peaks": n_pk, "strip": strip + 1, "p_gmpp": round(gp, 2)})
        if prev is not None and (n_pk != prev[0] or strip != prev[1]):
            key.add(s)
        prev = (n_pk, strip)
    key.add(steps - 1)
    return curves, labels, sorted(key), facts


def _a4_peak_formation(name, irr, T):
    """Render A4."""
    c = ui.T()
    ui.section_head("Where the peaks came from",
                    "the same panel, shaded from nothing to the shadow you built")
    ui.anim_badge("live", "this panel · validated engine")

    if st.button("▶ Build the shading ramp", key="a4_build",
                 help=f"Recomputes the curve on the validated engine at "
                      f"{_A4_STEPS} shadow depths and shows how the peaks appear."):
        st.session_state["a4_built"] = True
    if not st.session_state.get("a4_built"):
        st.caption(f"Press ▶ to deepen the shadow in {_A4_STEPS} steps and watch the "
                   f"peaks appear. Each step is a full curve from the validated engine.")
        return

    import time as _time
    t0 = _time.perf_counter()
    curves, labels, key_frames, facts = _a4_curves(name, irr, T)
    build_s = _time.perf_counter() - t0
    if not curves:
        ui.callout("This panel has no curve to ramp.", "Nothing to show", "limit")
        return

    changes = [k for k in key_frames if k not in (0, len(curves) - 1)]
    first, last = facts[0], facts[-1]
    if changes:
        caption = ("; ".join(
            f"at {facts[k]['darkest']:.0f} W/m² the curve goes to "
            f"{facts[k]['n_peaks']} peak(s), true peak in S{facts[k]['strip']}"
            for k in changes[:5])
            + f". Unshaded it is {first['n_peaks']} peak(s) at "
              f"{first['p_gmpp']:.0f} W; at the shadow you built, "
              f"{last['n_peaks']} peak(s) at {last['p_gmpp']:.0f} W.")
    else:
        caption = (f"The peak count never changes along this ramp: "
                   f"{first['n_peaks']} peak(s) unshaded and {last['n_peaks']} "
                   f"at full depth, with the true peak staying in "
                   f"S{last['strip']}. Power falls from {first['p_gmpp']:.0f} W "
                   f"to {last['p_gmpp']:.0f} W.")

    if not ui.anim_on():
        ui.callout("Animations are off, so the curves where something changed are "
                   "shown side by side.", "Static view", "info")
        ui.curve_strip(curves, labels, key_frames, key="a4")
        st.markdown(f'<div class="gm-legend">{_e(caption)}</div>', unsafe_allow_html=True)
        _a4_detail(facts, key_frames, build_s)
        return

    fig = ui.curve_morph(curves, labels, key_frames=key_frames, height=420,
                         frame_ms=200)
    ui.show_chart(fig, key="a4_player")
    st.markdown(f'<div class="gm-legend">{_e(caption)}</div>', unsafe_allow_html=True)
    with st.expander("Show the curves where something changed", expanded=False):
        ui.curve_strip(curves, labels, key_frames, key="a4-keys")
    _a4_detail(facts, key_frames, build_s)
    measured = ui.anim_exports(fig, facts,
                               {"badge": "live illustration",
                                "detail": "one panel, validated engine",
                                "module": name, "stride": 1}, key="a4",
                               name="peak_formation")
    ui.anim_budget_note(measured, 1, build_s)
    print(f"[gmppt_app] A4 curves={len(curves)} keys={key_frames} "
          f"json={measured['figure_json_mb']}MB build={build_s:.3f}s", flush=True)


def _a4_detail(facts, key_frames, build_s):
    rows = "\n".join(
        f"- Step {k} — shadow {facts[k]['darkest']:.0f} W/m², "
        f"{facts[k]['n_peaks']} peak(s), true peak in S{facts[k]['strip']} "
        f"at {facts[k]['p_gmpp']:.0f} W" for k in key_frames)
    with st.expander("Technical details", expanded=False):
        st.markdown(
            f"{rows}\n"
            f"- {len(facts)} curves, each one a full `gmppt.device.module_iv` "
            f"solve; peak counts and the true peak come from "
            f"`gmppt.device.analyse` on that same curve. Nothing about the peak "
            f"count is assumed — a scenario whose count never changes says so.\n"
            f"- The path between the unshaded panel and the built scenario is a "
            f"linear ramp of each strip's irradiance. The two ends are the real "
            f"scenarios; the steps between them are an explanatory path, not a "
            f"measurement.\n"
            f"- Curves are thinned to {_A4_POINTS} points per frame so the figure "
            f"stays inside the JSON budget; the solve itself is at full "
            f"resolution.\n"
            f"- Built in {build_s:.2f} s.")


def page_system():
    ui.page_intro("Whole system",
                  "Planned extension: electrical interaction across several modules, "
                  "strings and array configurations.", "Inspect · Whole system (planned)")
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


# =========================================================================== #
# Simulator — your existing app, unchanged
# =========================================================================== #
# =========================================================================== #
# Simulator · Set up a panel  (the "Bench") — the SIMPLIFIED engine (app.py),
# with an editable datasheet.  Matches the Bench mockup; sized to the 1440 grid.
# =========================================================================== #
def _bench_apply_preset():
    # Resetting to a preset replaces the datasheet, so an imported-day label no
    # longer describes what is on screen. (R5)
    st.session_state.pop("bench_import_meta", None)
    st.session_state.pop("bench_import_sig", None)
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
            # A record born from a day-event import carries the same sentence the
            # user saw on import, so the file cannot outlive the explanation. (U4)
            "imported_note": (
                _IMPORT_SENTENCE.format(preset=st.session_state.get("bench_preset", "—"))
                if st.session_state.get("bench_import_meta") else None),
            "bench": {"preset": st.session_state.get("bench_preset"),
                      "obj": st.session_state.get("bench_obj", "Custom"),
                      "ds": {k: ds[k] for k in sim.DS_FIELDS},
                      "nsub": int(n_sub), "mstr": int(m_str), "pstr": int(p_str),
                      "baseG": int(base_G), "T": int(T),
                      "sub_irr": [float(x) for x in sub_irr],
                      "imported_from_day_event": st.session_state.get("bench_import_meta")},
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
    # The list is capped at 12. Dropping the oldest silently loses work the user
    # deliberately kept, so name what went. (R9)
    while len(st.session_state.frozen) > 12:
        dropped = st.session_state.frozen.pop(0)
        st.toast(f"Saved-scenario limit is 12 — removed the oldest: "
                 f"{dropped.get('label', 'unnamed')}.")


# The run signature has ONE builder. It previously existed twice — once inline in
# page_sim_setup and once in _bench_load — and when R6 widened it to carry
# base_G and the array scaling, only the first copy was updated. Loading a saved
# scenario then wrote a 4-tuple that the 7-way unpack could not take, and the
# page died with a ValueError. Two derivations of one quantity, in two places.
_BENCH_SIG_LEN = 7


def _bench_sig(ds, T, sub_irr, n_sub, base_G, m_str, p_str):
    return (tuple(sorted(ds.items())), int(T),
            tuple(float(x) for x in sub_irr), int(n_sub),
            int(base_G), int(m_str), int(p_str))


def _bench_ran():
    """The last run's signature, or None if absent or of an older shape.

    A stale shape is treated as "not run yet" rather than crashing the page: a
    session restored from an older build must degrade to the empty state.
    """
    ran = st.session_state.get("bench_ran")
    if isinstance(ran, tuple) and len(ran) == _BENCH_SIG_LEN:
        return ran
    if ran is not None:
        st.session_state.pop("bench_ran", None)
    return None


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
    ds = {k: (int(v) if k == "Ns" else float(v)) for k, v in b["ds"].items()}
    st.session_state["bench_ran"] = _bench_sig(
        ds, b["T"], b["sub_irr"], b["nsub"], b["baseG"], b["mstr"], b["pstr"])
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


# One sentence, used both on import and inside the saved record, so the note the
# user reads and the note stored with the scenario cannot drift apart. (U4)
_IMPORT_SENTENCE = ("Irradiance conditions were imported; the module was not. This curve "
                    "uses the Sandbox datasheet `{preset}` on the simplified engine.")


def _bh(title):
    return f"<span class='bh'>{title}</span>"


def page_sim_setup():
    _bench_init()
    c = ui.T()
    day_import = st.session_state.pop("day_sim_import", None)
    _bench_css(c)
    ui.page_intro("Set up a panel",
                  "Type a datasheet in yourself and watch the curve — a separate, "
                  "simplified engine.", "Sandbox · Set up a panel")

    with st.container(key="benchroot"):
        if day_import:
            imported_irr = list(day_import.get("substring_irradiance_Wm2", []))
            st.session_state["bench_obj"] = "Custom"
            st.session_state["bench_baseG"] = int(round(day_import.get("base_irradiance_Wm2", st.session_state.get("bench_baseG", 910))))
            st.session_state["bench_T"] = int(round(day_import.get("temperature_C", st.session_state.get("bench_T", 43))))
            n_import = min(len(imported_irr), 12)
            st.session_state["bench_nsub"] = max(1, n_import)
            for i, value in enumerate(imported_irr[:n_import]):
                st.session_state[f"bench_s{i}"] = float(value)
            st.session_state["bench_scen_name"] = f"Day event · {day_import.get('time_label', 'sample')}"
            st.session_state["bench_import_meta"] = {
                "source": day_import.get("source", "Explore · day-event timeline"),
                "time_label": day_import.get("time_label"),
                "time_hour": day_import.get("time_hour"),
                "active_events": list(day_import.get("active_events", [])),
                "events": list(day_import.get("events", [])),
                "module_source": day_import.get("module_source"),
                "module_applied": str(st.session_state.get("bench_preset", "—")),
                "scenario_hash": day_import.get("scenario_hash"),
            }
            st.session_state["bench_import_sig"] = (
                tuple(float(v) for v in imported_irr[:n_import]),
                int(st.session_state["bench_baseG"]), int(st.session_state["bench_T"]))
            st.info(_IMPORT_SENTENCE.format(
                preset=st.session_state.get("bench_preset", "—")))

        # The sub-tab row is gone: ui.app_header already draws the Sandbox tabs,
        # and two tab rows that can disagree is one too many.

        # ---- imported-day provenance, and a way to drop it (R5) --------------
        _imeta = st.session_state.get("bench_import_meta")
        if _imeta:
            ic = st.columns([5, 1.3], vertical_alignment="center")
            ic[0].markdown(
                f"<div class='gm-sandbox'><b>Imported</b><span>Irradiance from "
                f"{_e(str(_imeta.get('source', 'the day-event timeline')))}"
                f"{' at ' + _e(str(_imeta.get('time_label'))) if _imeta.get('time_label') else ''}"
                f"{' · events: ' + _e(', '.join(_imeta.get('active_events') or [])) if _imeta.get('active_events') else ''}"
                f". The module is this tab's own datasheet, not the imported one."
                f"</span></div>", unsafe_allow_html=True)
            if ic[1].button("Clear import", key="bench_clear_import",
                            use_container_width=True,
                            help="Drops the imported-day label. The irradiance values "
                                 "stay as they are; only the provenance note is removed."):
                st.session_state.pop("bench_import_meta", None)
                st.toast("Import label cleared — the numbers are unchanged.")
                st.rerun()

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
                           f"This is the <b>simplified engine</b>; every workflow page uses the validated one on reference-database panels. "
                           f"The two never mix — a day-event import carries irradiance conditions only.</span>", unsafe_allow_html=True)
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
                n_sub = int(st.number_input("Cell strips (one bypass diode each)", 1, 12,
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
                m_str = int(a1.number_input("Modules per string", 1, 40,
                                            key="bench_mstr", step=1))
                p_str = int(a2.number_input("Parallel strings", 1, 40,
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
                base_G = int(row[n_sub + 1].number_input("Sunlight W/m²", 100, 1200,
                                                         key="bench_baseG", step=10))
                T = int(row[n_sub + 2].number_input("Cell temp °C", -10, 80, key="bench_T", step=1))
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
            # base_G and the array scaling are part of the signature because the saved
            # record and the "array (scaled)" KPI quote them: a record must never mix
            # the inputs that were run with ones changed afterwards. (R6)
            cur_sig = _bench_sig(ds, T, sub_irr, n_sub, base_G, m_str, p_str)
            # The import label describes a set of irradiance values. Once any of
            # them (or the conditions) are edited by hand it no longer describes
            # what is on screen, so it goes. (R5)
            _imported_sig = st.session_state.get("bench_import_sig")
            _irr_sig = (tuple(float(x) for x in sub_irr), int(base_G), int(T))
            if st.session_state.get("bench_import_meta"):
                if _imported_sig is None:
                    st.session_state["bench_import_sig"] = _irr_sig
                elif _imported_sig != _irr_sig:
                    st.session_state.pop("bench_import_meta", None)
                    st.session_state.pop("bench_import_sig", None)
            if run_clicked and divides:
                st.session_state["bench_ran"] = cur_sig
            ran = _bench_ran()

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
                r_ds_key, r_T, r_sub, r_nsub, r_baseG, r_mstr, r_pstr = ran
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
                        st.caption("Solved on an 800-point current grid; downloads "
                                   "carry 256 points.")
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
                        ui.show_chart(fig)

                        e = st.columns(5)
                        if e[0].button("Freeze this curve", key="bench_freeze",
                                       use_container_width=True,
                                       help="Save it to Saved scenarios for comparison"):
                            _bench_save(_bench_label(), r_ds, r_nsub, r_mstr, r_pstr,
                                        r_baseG, r_T, r_sub, res)
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
                        # No "Figure SVG" button: server-side SVG export needs kaleido
                        # and a browser this deployment does not have, and a control
                        # that can never be enabled is furniture. It is named once in
                        # the roadmap note under the table instead.
                        e[4].caption("SVG export — roadmap")

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
                        ui.show_chart(hm)
                        ui.legend_note("Each substring is a row band (this engine holds one "
                                       "irradiance per strip).")

                    with tabs[4]:
                        # app.render_sweep() exists and works; this tab showed a
                        # not_built placeholder beside it. (N6)
                        st.caption("Sweeps the built-in module presets across a "
                                   "temperature × irradiance matrix. It does not read the "
                                   "datasheet you typed on the left — it has its own "
                                   "module picker below.")
                        sim.render_sweep()

        # ============================================================= RIGHT
        with right:
            if res is not None:
                Vm, Im, Pm = res["gmpp"]
                Voc, Isc = res["Voc"], res["Isc"]
                ff = Pm / (Voc * Isc) if Voc * Isc > 0 else 0.0
                allkw = Pm * r_mstr * r_pstr / 1000.0
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
                            _bench_save(_bench_label(), r_ds, r_nsub, r_mstr, r_pstr,
                                        r_baseG, r_T, r_sub, res)
                            st.switch_page(P["sim_saved"])
                    if st.button("Use this module for a dataset", key="bench_to_dataset",
                                 use_container_width=True,
                                 help="Copies this datasheet, substring count and "
                                      "conditions into Make a dataset"):
                        _bench_to_dataset(r_ds, r_nsub, r_mstr, r_pstr, r_baseG, r_T)
                        st.switch_page(P["sim_dataset"])
                    st.page_link(P["sim_saved"], label="Saved scenarios")
                    # The trackers run the validated engine on a CEC module; this bench
                    # runs the interactive engine on a datasheet. Say so rather than
                    # offering a "send" that cannot carry anything across.
                    st.markdown(
                        f"<div style='margin-top:10px;padding-top:10px;border-top:1px solid "
                        f"{c['border']};font-size:12px;line-height:1.5;color:{c['text_muted']}'>"
                        f"Scenarios for the trackers come from <b>Understand · The panels</b>, "
                        f"which runs the validated engine on a CEC module. A bench curve "
                        f"cannot be sent there — the two engines take different module "
                        f"definitions.</div>", unsafe_allow_html=True)
                    st.page_link(P["panels"], label="Build a scenario for the trackers →")

            # What this engine cannot show — the one fact a reader needs beside the
            # result. That it is not the benchmark engine is already said once, in
            # the Sandbox banner at the top; it is not repeated here (§24).
            st.markdown(
                "<div style='background:#FBEFEE;border:1px solid #E0A9A4;border-radius:14px;"
                "padding:14px 18px'>"
                "<div style='font-size:11.5px;font-weight:600;letter-spacing:.05em;"
                "text-transform:uppercase;color:#7A2019'>What this engine cannot show</div>"
                "<p style='margin:7px 0 0 0;font-size:12.5px;line-height:1.5;color:#2B3238'>"
                "Shade is one value per strip, so a shadow covering part of a strip "
                "cannot be drawn here, and a cell driven into reverse-bias breakdown is "
                "not modelled. Both are handled by the validated engine on The panels."
                "</p></div>", unsafe_allow_html=True)


def page_sim_saved():
    ui.page_intro("Saved scenarios",
                  "Load a saved scenario back onto Set up a panel, or compare the ones "
                  "you have kept.", "Sandbox · Saved scenarios")
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

    st.divider()
    _a9_sandbox_morph(saved)
    st.divider()

    sim.render_scenarios_section()


# =========================================================================== #
# A9 — Sandbox morph  (Update 3 §5.3, user §14)
#
# Reads `st.session_state.frozen` — and `sweep_results`, when app.py's
# parametric sweep has filled it — and does nothing else to either. No Sandbox
# figure is written anywhere, nothing here reaches a benchmark or export path,
# and app.py is untouched. The Sandbox badge stays on the animation, because
# these curves are the simplified engine's, not the validated one's.
# =========================================================================== #
def _a9_sandbox_morph(saved):
    ui.section_head("Morph between your saved curves",
                    "one frame per saved scenario, in the order you kept them")
    ui.anim_badge("sandbox", "simplified engine · saved Sandbox scenarios")

    # app.py's parametric sweep, if it has been run in this session. It is read,
    # never written, and never mixed with the saved list.
    sweep = st.session_state.get("sweep_results") or []
    source = "saved"
    if len(saved) < 2 and len(sweep) >= 2:
        source = "sweep"
    if source == "saved" and len(saved) < 2:
        ui.unavailable(
            "Not enough saved scenarios",
            "Two or more saved curves are needed to morph between them. Save "
            "another on Set up a panel and this appears.",
            "- Source: `st.session_state.frozen`, read only. "
            "`st.session_state.sweep_results` is used instead when app.py's "
            "parametric sweep has been run in this session.")
        return

    recs = saved if source == "saved" else sweep
    curves = [{"V": list(r["V"]), "P": list(r["P"]),
               "gmpp": {"V": float(r["gmpp"][0]), "P": float(r["gmpp"][2])}}
              for r in recs]
    labels = [f"{r.get('label', f'scenario {i + 1}')} — "
              f"{float(r['gmpp'][2]):.1f} W" for i, r in enumerate(recs)]

    if st.button("▶ Build the morph", key="a9_build",
                 help="Plays the curves you already saved. Nothing is "
                      "re-simulated and nothing is written."):
        st.session_state["a9_built"] = True
    if not st.session_state.get("a9_built"):
        st.caption(f"Press ▶ to morph across your {len(curves)} "
                   f"{'saved scenarios' if source == 'saved' else 'sweep curves'}.")
        return

    import time as _time
    t0 = _time.perf_counter()
    peaks = [c["gmpp"]["P"] for c in curves]
    key_frames = sorted({0, len(curves) - 1,
                         peaks.index(max(peaks)), peaks.index(min(peaks))})
    build_s = _time.perf_counter() - t0
    caption = (f"{len(curves)} curves from the simplified Sandbox engine, "
               f"strongest {max(peaks):.1f} W, weakest {min(peaks):.1f} W. "
               f"These are exploratory: no figure here is a benchmark result.")

    if not ui.anim_on():
        ui.callout("Animations are off, so the strongest and weakest are shown "
                   "side by side.", "Static view", "info")
        ui.curve_strip(curves, labels, key_frames, key="a9")
        st.markdown(f'<div class="gm-legend">{_e(caption)}</div>', unsafe_allow_html=True)
        return

    fig = ui.curve_morph(curves, labels, key_frames=key_frames, height=380,
                         frame_ms=420)
    ui.show_chart(fig, key="a9_player")
    st.markdown(f'<div class="gm-legend">{_e(caption)}</div>', unsafe_allow_html=True)
    with st.expander("Show the extremes", expanded=False):
        ui.curve_strip(curves, labels, key_frames, key="a9-keys")
    measured = ui.anim_exports(
        fig, [{"label": l, "p_gmpp": c["gmpp"]["P"]} for l, c in zip(labels, curves)],
        {"badge": "sandbox", "detail": "simplified engine, not a benchmark result",
         "source": f"session {source}", "stride": 1}, key="a9", name="sandbox_morph")
    ui.anim_budget_note(measured, 1, build_s)


def page_sim_dataset():
    ui.page_intro("Make a dataset",
                  "Generate thousands of scenarios with a fixed seed and download them.",
                  "Sandbox · Make a dataset")
    _dsheet = sim.current_ds()
    st.caption(f"Generating from: {st.session_state.get('ds_name', '—')} · "
               f"{_dsheet['Ns']} cells · {st.session_state.get('topo_nsub', '—')} substrings. "
               f"Use “Use this module for a dataset” on Set up a panel to change it.")
    sim.render_dataset_section()
    ui.callout("These scenarios are produced by the interactive simulator, not by the "
               "validated engine behind the benchmark figures.",
               "Which engine made this dataset", "caveat")


# =========================================================================== #
# Testing
# =========================================================================== #
# =========================================================================== #
# Testing · Watch one run  — real trackers on a real curve (device.py), and the
# trained C3 learned seed. No numbers are typed in; everything is computed.
# =========================================================================== #
# --------------------------------------------------------------------------- #
# One label table for every method variant (§7.1). The bare word "Hybrid" is
# never shown: hybrid.py builds four different functions and the exports carry
# five different hybrid keys, and they do not score the same.
# --------------------------------------------------------------------------- #
_METHOD_LABELS = {
    "hybrid, bounded": "Hybrid (bounded)",
    "hybrid, free": "Hybrid (free)",
    "hybrid_bounded": "Hybrid (bounded)",
    "hybrid_free": "Hybrid (free)",
    "hybrid, no reseed": "Hybrid (no reseed)",
    "hybrid, never reseed": "Hybrid (never reseed)",
    "hybrid, triggered reseed": "Hybrid (triggered reseed)",
    "hybrid, reseed each block": "Hybrid (reseed each block)",
    "seed only": "Model only",
    "seed only, no reseed": "Model only (no reseed)",
    "PSO, triggered reseed": "PSO (triggered reseed)",
    "oracle [not buildable]": "Oracle (not buildable)",
    "P&O": "P&O", "InC": "InC", "PSO": "PSO",
}


UNKNOWN_VARIANT = "Unknown variant — export schema needs review"


def method_label(key: str) -> str:
    """Display name for an export key or an `fn.__name__`.

    Identity comes from the table alone — never from the display text and never
    from a substring match. A key the table does not know is shown as unknown
    rather than being filed under whichever family its name resembles: a new
    hybrid variant silently rendered as "Hybrid" would be read as the headline
    result. (U6)
    """
    return _METHOD_LABELS.get(str(key), UNKNOWN_VARIANT)


_RUN_METHODS = ["P&O", "InC", "PSO", "Model only", "Hybrid (bounded)", "Perfect tracker"]

# Readings per cycle. Populated from gmppt.hybrid.SEED_PROBE_COST and from the
# exports — never typed in here, so one method cannot show two numbers on two
# pages. PROBE_FRACTIONS has five entries, so SEED_PROBE_COST is 5; the old
# table hardcoded 6 (and the method report still says six — see D5).
_READINGS_FIXED = {
    "Hybrid": SEED_PROBE_COST,
    "Model only": SEED_PROBE_COST,
    # P&O and InC take one sample per control step; the exports carry no separate
    # probe budget for them, so the honest entry is "not separately reported".
    "P&O": None, "InC": None, "Perfect tracker": None,
}


def _pso_readings(pso_export: dict | None) -> tuple[int | None, dict | None]:
    """PSO evaluations per cycle, and the sweep row they came from.

    p9 writes `sequential_steps` = population × iterations, i.e. the number of
    particle EVALUATIONS a single converter must take one after another. That is
    the readings figure. `*_median_conv_steps` is the separate convergence
    figure and must not be reused as a cost. (D6)
    """
    if not pso_export or not pso_export.get("pso_sweep"):
        return None, None
    best = max(pso_export["pso_sweep"], key=lambda e: e.get("all_reached_pct", 0))
    val = best.get("sequential_steps")
    return (int(val) if val is not None else None), best


def _run_demo() -> dict:
    """The demo scenario. Irradiance and temperature are unchanged from the
    original; only the module is now resolved rather than hardcoded. (U1.2)"""
    return dict(module=_demo_module()[0], temp=43.0, irr=(910.0, 300.0, 600.0))


@st.cache_resource(show_spinner=False)
def _c3_model():
    """Load the trained two-stage seed. None if sklearn / the .pkl is missing."""
    try:
        from gmppt.model import TwoStageModel
        return TwoStageModel.load("c3_two_stage_full")
    except Exception:
        return None


def _score_traj(t):
    """Scores come from the harness's own Trajectory.metrics() — the same code
    p7_tracker_comparison.py summarises into the exports this app reads.

    The dashboard used to carry its own copy with two defects. It measured
    convergence against the method's OWN final power rather than the GMPP, so a
    tracker that settled firmly on the wrong peak scored as converged; and it
    reported steps = 0 when the final sample was outside the band, i.e. it
    printed "instant" for "never settled". Delegating removes both, and removes
    the possibility of this page and the Compare page disagreeing. (R15)
    """
    import numpy as np
    from gmppt.tracking import STEADY_FRACTION
    m = t.metrics()
    p = np.asarray(t.p_hist, float)
    k = max(1, int(round(STEADY_FRACTION * len(p))))
    lost = max(0.0, float(t.p_gmpp) - float(p[-k:].mean()))
    return dict(reached=bool(m["reached_gmpp"]),
                steps=m["convergence_steps"],        # None = never settled
                lost=float(lost),
                steady_eff_pct=float(m["steady_efficiency_pct"]),
                v_hist=[float(x) for x in t.v_hist],
                p_hist=[float(x) for x in t.p_hist])


@st.cache_data(show_spinner="Running every tracker on this scenario…")
def _run_scenario(module, temp, irr_key):
    import numpy as np
    from gmppt import tracking as trk, trackers as trkx, pso as pso
    from gmppt.scenarios import Scenario
    irr = [list(e) if isinstance(e, tuple) else float(e) for e in irr_key]
    sc = Scenario(module, float(temp), geometry_of(irr), irr, False)
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
                           probes=[float(f) * base.v_oc for f in PROBE_FRACTIONS],
                           n_probes=len(PROBE_FRACTIONS))
        run("Model only", hyb.make_seed_only(model), temp_c=float(temp))
        # Both variants, because hybrid.py builds both and they answer different
        # questions. Bounded is the code default and the headline (D4); free is
        # shown beside it because the docstring argues the clamp never binds.
        bounded = hyb.make_hybrid(model)
        free = hyb.make_hybrid(model, bounded=False)
        out["variant_names"] = {"bounded": bounded.__name__, "free": free.__name__}
        run("Hybrid (bounded)", bounded, temp_c=float(temp))
        run("Hybrid (free)", free, temp_c=float(temp))
        # Did the free variant ever leave the predicted region? That is the
        # measurement hybrid.py settles the bounded/free question with.
        w = base.v_oc / _gcfg.N_SUBSTRINGS
        lo, hi = region * w, (region + 1) * w
        vh = out["methods"]["Hybrid (free)"]["v_hist"]
        out["free_left_region"] = bool(any(v < lo - 1e-9 or v > hi + 1e-9 for v in vh))
    return out


def page_run():
    import numpy as np
    c = ui.T()
    disp, mono = ui.FONTS["display"], ui.FONTS["mono"]
    ui.page_intro("Watch one run",
                  "Watch each tracking method search the same curve, step by step.",
                  "Watch · Watch one run")
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

    _sc = st.session_state.get("scenario_sent")
    if _sc:
        _irrkey = _key(_sc["irr"])
        d = _run_scenario(_sc["module"], _sc["temp"], _irrkey)
        _resend_notice()
        if st.button("Discard sent scenario", key="run_use_example",
                     help="Drops the scenario Explore sent and returns this page to the "
                          "built-in example. Nothing on Explore is changed."):
            st.session_state.pop("scenario_sent", None)
            st.toast("Sent scenario discarded — showing the example again.")
            st.rerun()
    else:
        _demo = _run_demo()
        if not assert_val_modules([_demo["module"]], "Watch one run"):
            return
        d = _run_scenario(_demo["module"], _demo["temp"], _demo["irr"])
        _note = _demo_module()[3]
        ui.callout(
            f"This is the built-in example: {_demo['module']} under a three-region "
            f"shadow. Build your own on Understand · The panels and send it here."
            + (f" {_note}" if _note else ""),
            "Showing the example scenario", "info")
        _unseen_check(_demo["module"])
        st.page_link(P["panels"], label="Build your own scenario →")
    avail = [m for m in _RUN_METHODS + ["Hybrid (free)"] if m in d["methods"]]

    # ---- overlay chooser ----
    oc = st.columns([0.7, 6], vertical_alignment="center")
    oc[0].markdown(f"<span style='font-size:12px;font-weight:600;letter-spacing:.05em;"
                   f"text-transform:uppercase;color:{c['text_muted']}'>Overlay</span>",
                   unsafe_allow_html=True)
    default = [m for m in ("P&O", "Hybrid (bounded)") if m in avail] or avail[:1]
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
            show_seed = seed and any(m.startswith(("Hybrid", "Model only")) for m in sel)
            if show_seed:
                r = seed["region"]
                # The substring windows the seed chooses between, drawn by the
                # design system so every page splits V_oc the same way.
                ui.add_strip_bands(fig, d["v_oc"], _gcfg.N_SUBSTRINGS, highlight=r)
                _bounded_shown = any(m == "Hybrid (bounded)" for m in sel)
                fig.add_annotation(
                    x=(r + 0.5) * d["v_oc"] / _gcfg.N_SUBSTRINGS, y=max(d["P"]),
                    text=("Bounded P&O cannot leave this window" if _bounded_shown
                          else "Seed's predicted region (start only)"),
                    showarrow=False, yshift=14, font=dict(size=11, color=c["teal"]))
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
                              textposition="bottom center",
                              name=f"{SEED_PROBE_COST} readings",
                              marker=dict(color=c["teal"], size=7),
                              textfont=dict(size=9, color=c["teal"])))
            for m in sel:
                r = d["methods"].get(m)
                if not r:
                    continue
                vh, ph = np.array(r["v_hist"]), np.array(r["p_hist"])
                style = ui.method_style(m); col = style["color"]
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
                if not r["reached"]:
                    lab = "stops · %.0f W · −%.1f W" % (ph[-1], r["lost"])
                elif r["steps"] is None:
                    lab = "reaches, never settles"
                else:
                    lab = "settles · %d steps" % r["steps"]
                fig.add_annotation(x=vh[-1], y=ph[-1], text=lab, showarrow=True,
                                   arrowhead=0, ax=0, ay=-24, font=dict(size=10, color=col))
            ui.style_fig(fig, height=400, x_title="terminal voltage  V",
                         y_title="power  W")
            fig.update_layout(legend=dict(orientation="h", y=1.06, x=0))
            ui.show_chart(fig, key="run_pv")
            # Only worth saying when P&O actually failed here. On a curve it wins,
            # the sentence reads as an excuse for a failure that did not happen.
            _po = d["methods"].get("P&O")
            if _po and not _po["reached"]:
                ui.callout("P&O is not defective: on this scenario it is trapped on a local "
                           "peak, and on single-peak curves it reaches the maximum. The "
                           "failure mode being shown is trapping.", "Control", "info")

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
                # Four steps, not five. The old step 5 described the A2 fallback in
                # gmppt/fallback.py, which make_hybrid does not call and this page
                # never runs — so it claimed a safety net that is not in the loop. (N1/D3)
                st.markdown(
                    f"<div style='margin-top:8px;font-size:13px;line-height:1.5;"
                    f"color:{c['text_body']}'><b>1 · Take {SEED_PROBE_COST} readings</b> "
                    f"at fixed voltages across the curve — each costs a little output.<br>"
                    f"<b>2 · Pick a substring</b> — the model chooses which cell strip "
                    f"holds the tallest peak, instead of guessing a voltage.</div>"
                    f"<div style='margin-top:8px;padding:10px 12px;background:"
                    f"{c['muted_fill']};border-radius:8px'>{bars}</div>"
                    f"<div style='margin-top:8px;font-size:13px;line-height:1.5;"
                    f"color:{c['text_body']}'><b>3 · Place the start</b> inside strip "
                    f"S{r+1}, at {seed['v_seed']:.1f} V.<br>"
                    f"<b>4 · Hand to P&amp;O</b> — the ordinary hill-climber, unchanged; "
                    f"it just starts in the right place.</div>"
                    f"<div style='margin-top:8px;font-size:12px;line-height:1.45;"
                    f"color:{c['text_muted']}'>The bounded variant additionally clamps "
                    f"P&amp;O inside strip S{r+1}. Neither variant has a backup scan for "
                    f"a bad seed — nothing here rescues a wrong region.</div>",
                    unsafe_allow_html=True)
                with st.expander("Technical details", expanded=False):
                    st.markdown(
                        "- A confidence-triggered backup scan is implemented in "
                        "`gmppt/fallback.py`, but `make_hybrid` does not call it, so "
                        "it is not part of either variant and never runs on this "
                        "page. The four steps above are the whole method. (N1/D3)")
                if d.get("free_left_region") is False:
                    st.caption("Measured on this scenario: the free variant never left "
                               "the predicted region, so the clamp could not have bound.")
            else:
                ui.unavailable(
                    "Learned seed unavailable",
                    "The trained model could not be loaded, so the Hybrid and Model-only "
                    "traces are absent. The classical trackers here are real.",
                    "- Needs `results/phase3/c3_two_stage.pkl` and scikit-learn; the "
                    "loader is `TwoStageModel.load('c3_two_stage_full')`.",
                    kind="limit")

        with st.container(border=True):
            st.markdown(_bh_run("This scenario, side by side", 15), unsafe_allow_html=True)
            order = [m for m in ("Hybrid (bounded)", "Hybrid (free)", "Model only",
                                 "PSO", "P&O", "InC") if m in d["methods"]]
            pso_reads, _ = _pso_readings(_load_json("phase2/pso_comparison_val.json"))
            head = "".join(f"<span style='color:{c['text_muted']}'>{h}</span>"
                           for h in ("", "found it", "steps", "readings", "lost"))
            rowshtml = ""
            for m in order:
                r = d["methods"][m]
                found = ("<span style='color:%s'>yes</span>" % c["teal"]) if r["reached"] \
                    else ("<span style='color:%s'>no</span>" % c["red"])
                # Convergence is conditional on arrival: a method that never
                # reached the GMPP has no step count, and printing one would
                # invite reading it as a speed.
                steps = "—" if (not r["reached"] or r["steps"] is None) \
                    else f"{int(r['steps'])}"
                reads = pso_reads if m == "PSO" else _READINGS_FIXED.get(
                    m.split(" (")[0], None)
                rowshtml += (f"<span style='font-weight:500'>{_e(m)}</span>{found}"
                             f"<span>{steps}</span><span>{_fmt(reads, '{:.0f}')}</span>"
                             f"<span>{r['lost']:.1f} W</span>")
            st.markdown(f"<div class='bmono' style='margin-top:8px;display:grid;"
                        f"grid-template-columns:1.5fr .7fr .6fr .8fr .8fr;gap:6px 8px;"
                        f"font-size:12px'>{head}{rowshtml}</div>", unsafe_allow_html=True)
            ui.legend_note("Steps are conditional on arrival — a dash means the method "
                           "never reached the global peak, not that it was instant. "
                           "Readings for P&O and InC are not separately reported by the "
                           "exports.")
            with st.container(key="seeall"):
                st.page_link(P["compare"],
                             label="One scenario proves nothing — see the whole set →")

        with st.container(key="seereloc"):
            st.page_link(P["relocation"],
                         label="What happens when the peak jumps to another strip \u2192")

    # ---- A2: how the seed decides, then A1: what every method does ----
    # Headings and dividers, not bordered cards: these are sections of the
    # page, not objects on it (§20).
    st.divider()
    if seed:
        _a2_seed_decision(d, c)
        st.space(size="small")
    _a1_search_replay(d, sel, c)


def _bh_run(title, size=17):
    return f"<span class='bh' style='font-size:{size}px'>{title}</span>"


# =========================================================================== #
# A1 — Watch one run · Search replay  (Update 3 §5.3)
#
# Live illustration: it replays the trajectories `_run_scenario` already
# computed on THIS scenario. No tracker is re-run for the animation and no
# trajectory is invented — every marker is v_hist[k], p_hist[k].
# =========================================================================== #
_PSO_POP, _PSO_ITERS = None, None


def _pso_grouping():
    """Can PSO's particle identity be recovered from the recorded sequence?

    gmppt/pso.py evaluates `for _ in range(iterations): for i in range(population)`
    in fixed order, so evaluation k is particle k % M of iteration k // M. That
    is recoverable, and T26 checks M against the module. If that loop ever stops
    being a fixed-order nest, this returns None and the UI says the identity is
    not recorded rather than guessing a grouping.
    """
    try:
        from gmppt import pso as _pso
        import inspect
        src = inspect.getsource(_pso.particle_swarm)
        fixed = ("for _ in range(iterations)" in src
                 and "for i in range(population)" in src)
        return (int(_pso.DEFAULT_POPULATION), int(_pso.DEFAULT_ITERATIONS)) if fixed else None
    except Exception:
        return None


def _a1_frames(d, methods, n_steps, probe_n):
    """Frames for the search replay, plus the key frames and per-method counters.

    A frame carries only what changes: the marker and a short trail per method.
    The curve, the GMPP and the region band are static background, drawn once.
    """
    per = {}
    for m in methods:
        r = d["methods"][m]
        per[m] = (r["v_hist"], r["p_hist"])
    total = min(n_steps, max((len(v) for v, _ in per.values()), default=0))
    key = {0, max(total - 1, 0)}
    if any(m.startswith(("Hybrid", "Model only")) for m in methods):
        key.add(min(probe_n, max(total - 1, 0)))          # end of the probe phase
    for m in methods:
        r = d["methods"][m]
        if r["reached"] and r["steps"] is not None and r["steps"] < total:
            key.add(int(r["steps"]))                       # arrival step

    keep, stride = ui.downsample(total, sorted(key))
    p_gmpp = float(d["p_gmpp"]) or 1.0
    frames = []
    for k in keep:
        markers, trails, counters = {}, {}, {}
        for m in methods:
            vh, ph = per[m]
            if k >= len(vh):
                continue
            markers[m] = {"V": vh[k], "P": ph[k]}
            lo = max(0, k - 10)
            trails[m] = [(vh[j], ph[j]) for j in range(lo, k + 1)]
            counters[m] = {"steps": k + 1, "power": ph[k],
                           "pct_gmpp": 100.0 * ph[k] / p_gmpp}
        frames.append({"step": k, "markers": markers, "trails": trails,
                       "counters": counters})
    return frames, sorted(key), stride


def _a1_summary(d, methods):
    """The text alternative (§5.5), generated from the same scorer the table uses."""
    bits = []
    for m in methods:
        r = d["methods"][m]
        if not r["reached"]:
            bits.append(f"{m} stops at a local peak (−{r['lost']:.0f} W)")
        elif r["steps"] is None:
            bits.append(f"{m} reaches the true peak but never settles")
        else:
            bits.append(f"{m} reaches the true peak after {int(r['steps'])} steps")
    return "; ".join(bits) + "."


def _a1_search_replay(d, sel, c):
    """Render A1. Returns nothing; everything it shows comes from `d`."""
    st.markdown(_bh_run("Search replay — watch each method look") +
                f"<span style='font-size:13px;color:{c['text_muted']};margin-left:10px'>"
                f"the same curve, step by step, with what each one has spent</span>",
                unsafe_allow_html=True)
    methods = [m for m in sel if m in d["methods"]]
    if not methods:
        st.caption("Choose at least one method above.")
        return

    probe_n = SEED_PROBE_COST
    pso_grp = _pso_grouping()
    ui.anim_badge("live", f"{d.get('module_label', 'this scenario')} · validated engine")

    cA, cB = st.columns([1.2, 1])
    n_steps = int(cA.number_input("Steps to replay", 10, 400, 60, 10, key="a1_steps",
                                  help="The run is longer than this; the replay shows "
                                       "the first N steps, where the searching happens."))
    view = cB.segmented_control("view", ["Together", "Side by side"],
                                default="Together", key="a1_view",
                                label_visibility="collapsed") or "Together"

    # The built state lives in the session, not in the button's return value: a
    # button is True for exactly one run, so reading it directly would make the
    # replay vanish the moment the user touched any other control on the page.
    if st.button("▶ Build the replay", key="a1_build",
                 help="Builds the animation frames from the trajectories already "
                      "computed for this scenario. Nothing is re-simulated."):
        st.session_state["a1_built"] = True
    if not st.session_state.get("a1_built"):
        st.caption("Press ▶ to build the replay from the trajectories already computed "
                   "for this scenario — no tracker is re-run.")
        return

    import time as _time
    t0 = _time.perf_counter()
    frames, key_frames, stride = _a1_frames(d, methods, n_steps, probe_n)
    build_s = _time.perf_counter() - t0
    if not frames:
        ui.callout("No recorded steps for the selected methods.", "Nothing to replay", "limit")
        return

    series = {m: {"color": ui.method_style(m)["color"],
                  "symbol": _A1_SYMBOLS.get(m.split(" (")[0], "circle")}
              for m in methods}

    # static background: the curve, the GMPP, and the seed's region band
    V, Pw = list(d["V"]), list(d["P"])
    static = [go.Scatter(x=V, y=Pw, mode="lines", name="P–V",
                         line=dict(color=c["teal"], width=2.5)),
              go.Scatter(x=[d["v_gmpp"]], y=[d["p_gmpp"]], mode="markers", name="true peak",
                         marker=dict(symbol="star", size=15, color=ui.PEAK_COLORS["gmpp"]))]

    caption = _a1_summary(d, methods)
    if not ui.anim_on():
        ui.callout("Animations are off, so the key frames are shown instead. Turn them "
                   "on in the header to play the search.", "Static view", "info")
        ui.snapshot_strip(frames, [i for i, f in enumerate(frames)
                                   if f["step"] in key_frames],
                          captions=[f"step {k}" for k in key_frames],
                          static_traces=static, series=series, key="a1")
        st.markdown(f'<div class="gm-legend">{_e(caption)}</div>', unsafe_allow_html=True)
        return

    fig = ui.trace_player(frames, series, static_traces=static, height=460,
                          key_frames=key_frames, view=view.lower().replace(" ", "_"))
    ui.show_chart(fig, key="a1_player")

    # counters, from the last frame of the replay
    last = frames[-1]["counters"]
    head = "".join(f"<span style='color:{c['text_muted']};font-size:11px'>{h}</span>"
                   for h in ("method", "control steps", "power now", "% of true peak"))
    body = "".join(
        f"<span style='font-weight:500'>{_e(m)}</span>"
        f"<span>{last[m]['steps']}</span><span>{last[m]['power']:.0f} W</span>"
        f"<span>{last[m]['pct_gmpp']:.1f}%</span>"
        for m in methods if m in last)
    st.markdown(f"<div class='bmono' style='display:grid;"
                f"grid-template-columns:1.6fr .8fr .8fr .9fr;gap:5px 12px;"
                f"font-size:12px'>{head}{body}</div>", unsafe_allow_html=True)

    if "PSO" in methods:
        if pso_grp:
            m_pop, _it = pso_grp
            st.caption(f"PSO evaluates {m_pop} particles per iteration, always in the "
                       f"same order, so every {m_pop} dots are one iteration. Each dot "
                       f"is one evaluation, which is one control step.")
            with st.expander("Technical details", expanded=False):
                st.markdown(f"- `gmppt/pso.py` nests `for _ in range(iterations)` over "
                            f"`for i in range(population)` with `DEFAULT_POPULATION = "
                            f"{m_pop}`, so evaluation k is particle `k % {m_pop}` of "
                            f"iteration `k // {m_pop}`. The loop shape is re-checked at "
                            f"runtime; if it changes, this caption says identity is not "
                            f"recorded instead.")
        else:
            st.caption("Sequential evaluations — particle identity not recorded.")

    st.markdown(f'<div class="gm-legend">{_e(caption)}</div>', unsafe_allow_html=True)
    with st.expander("Show key frames", expanded=False):
        ui.snapshot_strip(frames, [i for i, f in enumerate(frames)
                                   if f["step"] in key_frames],
                          captions=[f"step {k}" for k in key_frames],
                          static_traces=static, series=series, key="a1-keys")
    measured = ui.anim_exports(fig, frames,
                               {"badge": "live illustration",
                                "detail": "one scenario, validated engine",
                                "scenario": d.get("scenario_hash"),
                                "stride": stride}, key="a1", name="search_replay")
    ui.anim_budget_note(measured, stride, build_s)
    print(f"[gmppt_app] A1 frames={measured['frames']} stride={stride} "
          f"json={measured['figure_json_mb']}MB build={build_s:.3f}s", flush=True)


# Markers differ by symbol as well as colour, so colour is never the only cue (§5.5).
_A1_SYMBOLS = {"P&O": "triangle-up", "InC": "triangle-down", "PSO": "diamond",
               "Model only": "square", "Hybrid": "circle", "Perfect tracker": "x"}


# =========================================================================== #
# A2 — How the seed decides  (Update 3 §5.3, user §9)
#
# Stages, in the order the method actually performs them:
#   1..SEED_PROBE_COST  the fixed-fraction readings, taken from the RECORDED
#                       Hybrid trajectory and checked against seed["probes"]
#   +1                  the region decision, from the real seed["proba"]
#   +1                  the landing at seed["v_seed"], which is also where P&O
#                       takes over
# There is no safety stage. `make_hybrid` never calls gmppt/fallback.py, so the
# confidence-triggered scan does not run on any scenario this page can build —
# and a greyed-out stage for something that did not happen would be a claim
# about the method that is not true. (N1/D3)
#
# Probe accounting, settled from the runtime rather than from the prose:
#   extract_features spends exactly len(PROBE_FRACTIONS) = 5 steps, and the
#   recorded v_hist[:5] equals PROBE_FRACTIONS * v_oc exactly. The "six" in the
#   method report is model.EXPECTED_PROBES = 5 features + 1 landing at k*V_oc,
#   which is the MODEL's serving cost; in the hybrid the landing is P&O's first
#   step, charged out of n_steps - SEED_PROBE_COST. Both counts are right about
#   different boundaries, so neither was changed. A2 shows both: five readings,
#   then the landing, labelled as the handover.
# =========================================================================== #
def _a2_stage_frames(d):
    """Frames for the seed decision, plus a caveat if the record disagrees.

    Returns (frames, caveat). Probe positions come from the recorded Hybrid
    trajectory; seed["probes"] is what the declared fractions say they should
    be. If the two differ the RECORDED values are drawn and the caveat is
    raised — a picture of what the fractions imply, when the run did something
    else, would be a picture of nothing that happened.
    """
    import numpy as np
    seed = d["seed"]
    n = int(seed.get("n_probes") or SEED_PROBE_COST)
    declared = [float(x) for x in seed["probes"]]

    # the run the probes were actually spent on
    rec = None
    for m in ("Hybrid (bounded)", "Hybrid (free)", "Model only"):
        r = d["methods"].get(m)
        if r and len(r["v_hist"]) > n:
            rec = (m, r)
            break
    caveat = ""
    if rec is None:
        return [], ("No hybrid run was recorded for this scenario, so the probe "
                    "positions cannot be shown from the record.")
    src, r = rec
    vh, ph = [float(x) for x in r["v_hist"]], [float(x) for x in r["p_hist"]]
    probes = vh[:n]
    if len(declared) != n or not np.allclose(probes, declared, rtol=0, atol=1e-6):
        caveat = (f"Recorded probes differ from the declared probe fractions. The "
                  f"positions drawn below are the ones the run actually measured "
                  f"({src}); the declared fractions are in Technical details.")

    V, Pw = np.asarray(d["V"], float), np.asarray(d["P"], float)
    powers = ph[:n]
    v_seed = float(seed["v_seed"])
    p_seed = float(ph[n]) if len(ph) > n else float(np.interp(v_seed, V, Pw))
    region, proba = int(seed["region"]), [float(x) for x in seed["proba"]]

    frames = []
    for i in range(n):
        frames.append({
            "step": f"reading {i + 1}",
            "title": (f"Reading {i + 1} of {n} — measure power at "
                      f"{probes[i]:.1f} V ({powers[i]:.0f} W)"),
            "markers": {"reading": {"V": probes[i], "P": powers[i]}},
            "trails": {"reading": [(probes[i], powers[i])]},
            "taken": [(probes[i], powers[i])],
        })
    frames.append({
        "step": "decision",
        "title": (f"Decide — strip S{region + 1} holds the tallest peak "
                  f"(p = {proba[region]:.2f})"),
        "markers": {}, "trails": {},
        "taken": [(probes[i], powers[i]) for i in range(n)],
    })
    frames.append({
        "step": "seed",
        "title": (f"Start P&O at {v_seed:.1f} V, inside S{region + 1} — the "
                  f"handover; this reading is P&O's first step"),
        "markers": {"seed": {"V": v_seed, "P": p_seed}},
        "trails": {"seed": [(v_seed, p_seed)]},
        "taken": [(probes[i], powers[i]) for i in range(n)],
    })
    # every stage carries what has been measured so far, so each frame stands
    # alone as a still (§16 / §5.5)
    for f in frames:
        f["trails"]["reading"] = list(f["taken"])
    return frames, caveat


def _a2_seed_decision(d, c):
    """Render A2. Live illustration — this scenario on the validated engine."""
    import numpy as np
    seed = d["seed"]
    st.markdown(_bh_run("How the seed decides") +
                f"<span style='font-size:13px;color:{c['text_muted']};margin-left:10px'>"
                f"the {SEED_PROBE_COST} readings, the choice they lead to, and where "
                f"P&amp;O is handed the curve</span>", unsafe_allow_html=True)
    ui.anim_badge("live", f"{d.get('module_label', 'this scenario')} · validated engine")

    if st.button("▶ Build the seed walkthrough", key="a2_build",
                 help="Builds the stages from the readings this scenario already "
                      "recorded. The model is not re-run."):
        st.session_state["a2_built"] = True
    if not st.session_state.get("a2_built"):
        st.caption("Press ▶ to step through the decision. Every position comes from "
                   "the recorded run — nothing is re-simulated.")
        return

    import time as _time
    t0 = _time.perf_counter()
    frames, caveat = _a2_stage_frames(d)
    build_s = _time.perf_counter() - t0
    if not frames:
        ui.callout(caveat or "Nothing recorded to show.", "Cannot show the decision",
                   "limit")
        return
    if caveat:
        ui.callout(caveat, "Recorded probes differ from the declared fractions", "limit")

    region = int(seed["region"])
    V, Pw = list(d["V"]), list(d["P"])
    static = [go.Scatter(x=V, y=Pw, mode="lines", name="P–V",
                         line=dict(color=c["teal"], width=2.5)),
              go.Scatter(x=[d["v_gmpp"]], y=[d["p_gmpp"]], mode="markers",
                         name="true peak",
                         marker=dict(symbol="star", size=15,
                                     color=ui.PEAK_COLORS["gmpp"]))]
    bandfig = go.Figure()
    ui.add_strip_bands(bandfig, d["v_oc"], _gcfg.N_SUBSTRINGS, highlight=region)
    series = {"reading": {"color": c["teal"], "symbol": "circle"},
              "seed": {"color": ui.method_style("Hybrid (bounded)")["color"],
                       "symbol": "star-diamond"}}
    # the text alternative — the same three facts, in words (§5.5)
    proba = [float(x) for x in seed["proba"]]
    caption = (f"{SEED_PROBE_COST} readings are taken across the curve; the model "
               f"reads them as strip S{region + 1} (p = {proba[region]:.2f}); P&O is "
               f"started at {float(seed['v_seed']):.1f} V inside that strip.")

    key_frames = list(range(len(frames)))          # every stage is a key frame
    if not ui.anim_on():
        ui.callout("Animations are off, so each stage is shown as a still. Turn them "
                   "on in the header to step through it.", "Static view", "info")
        ui.snapshot_strip(frames, key_frames, static_traces=static, series=series,
                          key="a2")
        st.markdown(f'<div class="gm-legend">{_e(caption)}</div>', unsafe_allow_html=True)
        _a2_detail(d, frames)
        return

    fig = ui.trace_player(frames, series, static_traces=static, height=430,
                          key_frames=key_frames, step_prefix="stage ", frame_ms=900)
    for sh in bandfig.layout.shapes:
        fig.add_shape(sh)
    ui.show_chart(fig, key="a2_player")
    st.markdown(f'<div class="gm-legend">{_e(caption)}</div>', unsafe_allow_html=True)
    with st.expander("Show each stage as a still", expanded=False):
        ui.snapshot_strip(frames, key_frames, static_traces=static, series=series,
                          key="a2-keys")
    _a2_detail(d, frames)
    measured = ui.anim_exports(fig, frames,
                               {"badge": "live illustration",
                                "detail": "one scenario, validated engine",
                                "scenario": d.get("scenario_hash"),
                                "stride": 1}, key="a2", name="seed_decision")
    ui.anim_budget_note(measured, 1, build_s)
    print(f"[gmppt_app] A2 frames={measured['frames']} "
          f"json={measured['figure_json_mb']}MB build={build_s:.3f}s", flush=True)


def _a2_detail(d, frames):
    """Declared fractions vs what the run recorded — the audit trail for §9."""
    seed = d["seed"]
    n = int(seed.get("n_probes") or SEED_PROBE_COST)
    declared = [float(x) for x in seed["probes"]]
    taken = (frames[-1].get("taken") or []) if frames else []
    rows = "\n".join(
        f"- Reading {i + 1}: recorded `{taken[i][0]:.3f} V`, declared "
        f"`{declared[i]:.3f} V`" if i < len(declared) and i < len(taken) else ""
        for i in range(n))
    with st.expander("Technical details", expanded=False):
        st.markdown(
            f"{rows}\n"
            f"- Declared positions are `PROBE_FRACTIONS × V_oc`; recorded positions "
            f"are `v_hist[:{n}]` of the hybrid run. They are compared every time "
            f"this animation is built, and a mismatch is stated above rather than "
            f"smoothed over.\n"
            f"- `hybrid.SEED_PROBE_COST` is {SEED_PROBE_COST} — the control steps "
            f"charged to the seed. `model.EXPECTED_PROBES` is "
            f"{SEED_PROBE_COST + 1}, which counts the same readings plus the "
            f"landing at `k · V_oc`; in the hybrid that landing is P&O's first "
            f"step, not a sixth probe. Both counts are correct about different "
            f"boundaries.\n"
            f"- No safety stage is drawn: `make_hybrid` does not call "
            f"`gmppt/fallback.py`, so the confidence-triggered scan never runs "
            f"here. (N1/D3)")


# Snapshot from the validation report (p7 static n=632, p9 convergence). Replace with the
# harness export once --emit exists; never compute these numbers inside the dashboard.
_SNAPSHOT = pd.DataFrame([
    ("Hybrid", 99.88, 98.6, 5, 6, 6.4),
    ("PSO", 99.9, 97.8, 62, 120, None),
    ("Model only", 99.76, 94.5, 0, 6, 6.3),
    ("P&O", 79.51, 46.2, 18, 3, 185.4),
    ("InC", 79.51, 46.2, 18, 3, 185.4),
], columns=["Method", "Energy captured (%)", "Found true peak (%)", "Steps", "Readings", "Worst case (W)"])


def _read_export(rel):
    """(data, problem) for one export. `problem` is None when the file is fine.

    Missing, unreadable, malformed and wrong-shaped are four different things and
    they need four different sentences: "run the script" is useless advice for a
    file that exists but is truncated. Nothing here ever repairs, regenerates or
    normalises the file — the dashboard is read-only over results/phase2/.
    """
    import json
    p = _gcfg.RESULTS_DIR / rel
    if not p.exists():
        return None, "not found"
    try:
        raw = p.read_text(encoding="utf-8")
    except Exception as e:
        return None, f"unreadable ({type(e).__name__}: {e})"
    try:
        data = json.loads(raw)
    except Exception as e:
        return None, f"malformed JSON ({e})"
    if not isinstance(data, dict):
        return None, f"unexpected schema (top level is {type(data).__name__}, not an object)"
    return data, None


def _load_json(rel):
    return _read_export(rel)[0]


# --------------------------------------------------------------------------- #
# Reading harness exports
#
# The dashboard never computes a benchmark number. It reads what the phase2
# runners wrote. Every read goes through these, so a missing file or a missing
# variant produces a named callout rather than a KeyError or, worse, a number
# invented to fill the hole.
# --------------------------------------------------------------------------- #
_EXPORT_SCRIPT = {
    "phase2/tracker_comparison_val.json": "phase2/p7_tracker_comparison.py --split val",
    "phase2/pso_comparison_val.json": "phase2/p9_pso_comparison.py --split val",
    "phase2/dynamic_comparison_30-100_val.json": "phase2/p10_dynamic_comparison.py --split val",
    "phase2/dynamic_comparison_10-50_val.json":
        "phase2/p10_dynamic_comparison.py --split val --sequence 10-50",
    "phase2/relocation_comparison_pole.json": "phase2/p12_relocation_comparison.py --family pole",
}


def _export_path(rel):
    return _gcfg.RESULTS_DIR / rel


# An explicit run identifier would be the right thing to stamp figures with, but
# none of these exports writes one (see the protected-file request in the
# changelog). These are the fields they DO carry that identify which experiment
# a file is, so provenance names the run as precisely as the data allows. (U7)
_RUN_ID_KEYS = ("experiment_id", "run_id", "experiment", "run", "uuid", "id")
_EXPERIMENT_KEYS = ("family", "sequence")


def _experiment_id(data) -> str | None:
    data = data or {}
    for k in _RUN_ID_KEYS:
        if data.get(k) not in (None, ""):
            return str(data[k])
    # No prefix here: ui.provenance already renders this as `experiment=…`, and
    # which key it came from is implied by the file name.
    parts = [str(data[k]) for k in _EXPERIMENT_KEYS if data.get(k) not in (None, "")]
    return " · ".join(parts) or None


def _export_meta(rel, data) -> dict:
    """The provenance fields an export actually carries. Absent = absent."""
    data = data or {}
    return {"path": str(_export_path(rel)),
            "experiment": _experiment_id(data),
            "split": data.get("split"),
            "n": data.get("n_scenarios") or data.get("n_shaded") or data.get("n_windows"),
            "seed": data.get("seed"), "version": data.get("version")}


def missing_export(rel, what=""):
    """Say plainly that the result is not there; keep the machinery out of sight.

    A reader needs to know the result is unavailable and that nothing was made
    up. Which file, which script, and what is wrong with it are for whoever
    regenerates it, so they go under Technical details. (§14)
    """
    _, problem = _read_export(rel)
    problem = problem or "not usable"
    script = _EXPORT_SCRIPT.get(rel, "the analysis that writes it")
    subject = what or "This result"
    if problem == "not found":
        blurb = (f"{subject} has not been generated yet. Nothing is shown here rather "
                 f"than an estimate.")
        tech = (f"- Missing file: `{rel}`\n"
                f"- Produced by: `{script}`\n"
                f"- Run it and reload the page.")
    else:
        blurb = (f"{subject} could not be read. Nothing is shown here rather than an "
                 f"estimate.")
        tech = (f"- File: `{rel}`\n- Problem: {problem}\n"
                f"- The dashboard never repairs or regenerates a results file. "
                f"Re-run `{script}` to rewrite it.")
    ui.unavailable("Results unavailable", blurb, tech)


def missing_field(rel, key, what=""):
    """One figure is absent from an otherwise good result set."""
    script = _EXPORT_SCRIPT.get(rel, "the analysis that writes it")
    ui.unavailable(
        "Some figures unavailable",
        f"{(what or 'One value').capitalize()} was not recorded in this result set, "
        f"so it is shown as a dash rather than filled in.",
        f"- File: `{rel}`\n- Absent field: `{key}`\n- Produced by: `{script}`")


def require_keys(rel, data, keys, what="") -> bool:
    """True when the result set has the fields a page needs.

    A file that parses but has a different shape is a different problem from a
    missing number, and it is one only a maintainer can act on — so the reader
    gets one sentence and the specifics go under Technical details. (§14)
    """
    if not isinstance(data, dict):
        return False
    absent = [k for k in keys if k not in data]
    if not absent:
        return True
    script = _EXPORT_SCRIPT.get(rel, "the analysis that writes it")
    ui.unavailable(
        "Results unavailable",
        f"The stored results for {what or 'this page'} are not in the form it "
        f"expects, so nothing is shown. No value has been inferred from the parts "
        f"that are readable.",
        f"- File: `{rel}`\n"
        f"- Absent top-level {'keys' if len(absent) > 1 else 'key'}: "
        f"{', '.join('`' + k + '`' for k in absent)}\n"
        f"- Produced by: `{script}`\n"
        f"- The export format has probably moved; regenerate it or update the page.")
    return False


def _fmt(v, spec="{:.2f}", dash="—"):
    """Format a number, or a dash when the export did not carry it."""
    try:
        if v is None:
            return dash
        f = float(v)
        if f != f:                      # NaN — censored, not zero
            return dash
        return spec.format(f)
    except (TypeError, ValueError):
        return dash


def page_compare():
    import json
    import pandas as pd
    c = ui.T()
    t_rel, p_rel = "phase2/tracker_comparison_val.json", "phase2/pso_comparison_val.json"
    tc = _load_json(t_rel)
    pso = _load_json(p_rel)
    sub = "multi_peak"
    n_sub = ((tc or {}).get("results") or {}).get("P&O", {}).get(sub, {}).get("n")
    ui.page_intro("Compare methods",
                  f"Every method on the same {_fmt(n_sub, '{:.0f}')} multi-peak validation "
                  f"curves.", "Compare · Compare methods")

    if not tc or not require_keys(t_rel, tc, ("results", "split"), "the comparison table"):
        if not tc:
            missing_export(t_rel, "The tracker comparison")
        ui.callout("The table below is a snapshot of an earlier run, kept so the page "
                   "is not blank. It is not the current result and must not be quoted.",
                   "Snapshot, not the current result", "caveat")
        st.dataframe(_SNAPSHOT, hide_index=True, width="stretch")
        return

    R = tc["results"]

    def g(key):
        """One variant's multi-peak row, or None when the export lacks it."""
        b = (R.get(key) or {}).get(sub)
        if not b:
            return None
        return dict(energy=b.get("steady_eff_pct"), found=b.get("reached_pct"),
                    steps=b.get("median_conv_steps"), worst=b.get("worst_energy_lost_w"))

    head_key = "hybrid, bounded"                 # D4: code default is the headline
    rows = []
    for key in (head_key, "hybrid, free", "seed only", "P&O", "InC"):
        r = g(key)
        if r is None:
            missing_field(t_rel, key, "the comparison table")
            continue
        rows.append((method_label(key), key, r))
    hyb = g(head_key)

    # Keys the export carries that the label table does not know. They are shown,
    # because hiding a row would hide a result, but they are shown as unknown —
    # never folded into whichever family the key's text resembles. (U6)
    unknown = [k for k in R if k not in _METHOD_LABELS]
    for key in unknown:
        r = g(key)
        if r is not None:
            rows.append((f"{UNKNOWN_VARIANT}: {key}", key, r))
    if unknown:
        ui.callout(
            f"`{t_rel}` contains "
            f"{', '.join('`' + str(k) + '`' for k in unknown)}, which this dashboard's "
            f"variant table does not know. They are listed as unknown rather than "
            f"assigned to a method family. Add them to `_METHOD_LABELS` once it is "
            f"settled which variant each one is.",
            "Unrecognised export keys", "caveat")

    pso_read, pso_best = _pso_readings(pso)
    pso_row = None
    if pso_best:
        pso_row = dict(energy=pso_best.get(f"{sub}_steady_eff_pct"),
                       found=pso_best.get(f"{sub}_reached_pct"),
                       steps=pso_best.get(f"{sub}_median_conv_steps"),
                       worst=pso_best.get(f"{sub}_worst_energy_lost_w"))
        rows.insert(2, ("PSO (best of sweep, selected on val)", "PSO", pso_row))
    elif pso:
        missing_field(p_rel, "pso_sweep", "the PSO row")

    # ---- KPIs: cost first, because that is where the difference is ----------
    kp = []
    if hyb and pso_row and pso_read:
        ratio = pso_read / SEED_PROBE_COST
        kp.append(("Readings per cycle — Hybrid vs PSO", f"{ratio:.0f}× fewer",
                   f"{SEED_PROBE_COST} against {pso_read}, at "
                   f"{_fmt(hyb['found'], '{:.1f}')}% vs {_fmt(pso_row['found'], '{:.1f}')}% "
                   f"arrival", "hero"))
    if hyb:
        kp.append(("Found true peak", f"{_fmt(hyb['found'], '{:.1f}')}%",
                   f"{method_label(head_key)}, multi-peak subset"))
        kp.append(("Worst case", f"{_fmt(hyb['worst'], '{:.1f}')} W",
                   "largest single-scenario loss"))
    if kp:
        # the verdict card leads, but as a peer: a little wider, not 1.6× (§12)
        ui.kpi_row(kp, weights=[1.25, 1, 1][:len(kp)])

    left, right = st.columns([1.35, 1], gap="large")
    with left:
        def reads_for(key):
            if key == "PSO":
                return pso_read
            base = method_label(key).split(" (")[0]
            return _READINGS_FIXED.get(base)

        df = pd.DataFrame([{
            "Method": label,
            "Found true peak (%)": None if r["found"] is None else round(r["found"], 1),
            "Worst case (W)": None if r["worst"] is None else round(r["worst"], 1),
            "Steps": ("—" if r["steps"] is None else int(r["steps"])),
            "Readings": reads_for(key) if reads_for(key) is not None else "—",
            "Energy captured (%)": None if r["energy"] is None else round(r["energy"], 2),
        } for label, key, r in rows])
        # No progress bars: a bar that starts at 78% turns a saturated metric into
        # a ranking, which is exactly what the project says not to do with it.
        st.dataframe(df, hide_index=True, width="stretch")
        ui.legend_note(
            f"Multi-peak subset, n={_fmt(n_sub, '{:.0f}')}, split "
            f"{tc.get('split', '—')}, validated engine. Steps are conditional on "
            f"arrival — read them beside Found true peak, never alone. Energy "
            f"captured is saturated for every seeded method and is a value here, "
            f"not a discriminator.")
    with right:
        fig = go.Figure()
        pts = [(label, reads_for(key), max(100 - r["energy"], 0.01))
               for label, key, r in rows
               if reads_for(key) is not None and r["energy"] is not None]
        # Two methods can land on the same point (both hybrids do). Alternate
        # the label side for coincident points so neither overprints the other,
        # and pad the axes so the outermost label is not clipped.
        seen = {}
        for label, x, y in pts:
            k = (round(float(x), 6), round(float(y), 4))
            n = seen.get(k, 0)
            seen[k] = n + 1
            # never "left": the leftmost point sits at the axis and a left label
            # runs off the plot
            pos = ["middle right", "bottom center", "top center"][n % 3]
            # a long table label ("PSO (best of sweep, …)") is a caption, not a
            # marker text — keep the marker text to the method and its variant
            short = label if len(label) <= 18 else label.split(",")[0].rstrip() + (
                ")" if "(" in label.split(",")[0] else "")
            fig.add_trace(go.Scatter(x=[x], y=[y], mode="markers+text", name=label,
                                     text=[short], textposition=pos,
                                     marker=dict(size=13,
                                                 color=ui.method_style(label)["color"],
                                                 symbol=_A1_SYMBOLS.get(
                                                     label.split(" (")[0], "circle"))))
        if pts:
            import math
            xs = [float(x) for _, x, _ in pts]
            ys = [float(y) for _, _, y in pts]
            fig.update_xaxes(range=[math.log10(min(xs)) - 0.35, math.log10(max(xs)) + 0.9])
            fig.update_yaxes(range=[math.log10(min(ys)) - 0.12, math.log10(max(ys)) + 0.12])
        fig.update_xaxes(type="log", title_text="readings per cycle")
        fig.update_yaxes(type="log", title_text="energy lost (%)")
        ui.style_fig(fig, height=360)
        fig.update_layout(showlegend=False,
                          title="Energy lost against readings per cycle",
                          margin=dict(r=30))
        ui.show_chart(fig, key="compare_cost")

    if hyb and pso_row:
        ui.callout(
            f"{method_label(head_key)} and PSO record "
            f"{_fmt(hyb['energy'], '{:.2f}')}% and {_fmt(pso_row['energy'], '{:.2f}')}% "
            f"energy captured — the advantage is cost, not accuracy. "
            f"Split {tc.get('split', '—')}, n={_fmt(n_sub, '{:.0f}')}, validated engine, "
            f"simulated throughout; no field measurements. The PSO row is the "
            f"best-arrival row of a {len(pso.get('pso_sweep', []))}-point sweep selected "
            f"on this same split"
            + (", and its arrival rate could not be separated from its population "
               "size." if pso.get("arrival_separable_by_population") is False
               else "."),
            "Read these alongside", "caveat")
        with st.expander("Technical details", expanded=False):
            st.markdown(
                f"- PSO sweep: {len(pso.get('pso_sweep', []))} population × iteration "
                f"points; the row shown is the one with the highest arrival rate.\n"
                f"- The export records `arrival_separable_by_population = "
                f"{pso.get('arrival_separable_by_population')}`.")
    ui.provenance({t_rel.split("/")[-1]: _export_meta(t_rel, tc),
                   p_rel.split("/")[-1]: _export_meta(p_rel, pso)})

    e1, e2 = st.columns(2)
    e1.download_button("Download table (CSV)", df.to_csv(index=False),
                       "compare_methods.csv", "text/csv", use_container_width=True,
                       key="compare_csv")
    e2.download_button("Download figure data (JSON)",
                       json.dumps({"rows": [{"label": l, "key": k, **r}
                                             for l, k, r in rows],
                                   "readings": {k: reads_for(k) for _, k, _ in rows},
                                   "provenance": {t_rel: _export_meta(t_rel, tc),
                                                  p_rel: _export_meta(p_rel, pso)}},
                                  indent=2, default=str),
                       "compare_methods.json", "application/json",
                       use_container_width=True, key="compare_json")


def _mv_demo() -> dict:
    return dict(module=_demo_module()[0], temp=43.0, shaded=(910.0, 300.0, 600.0))


@st.cache_data(show_spinner="Stepping the trackers through the ramp…")
def _dynamic_day(sequence, shaded, module, temp, shaded_irr):
    """One EN 50530 ramp profile stepped by every tracker — real per-step power."""
    import numpy as np
    from gmppt import dynamic as dyn, tracking as trk, trackers as trkx, pso
    from gmppt.scenarios import Scenario
    slopes = [r[1] for r in dyn.SEQUENCES[sequence][1]]
    prof = dyn.make_profile(sequence, slopes[len(slopes) // 2], max_cycles=1)
    m, tp = str(module), float(temp)
    shaded_irr = [float(x) for x in shaded_irr]
    # The unshaded reference must sit at the SAME base irradiance as the shaded
    # demo, or the gap between the two lines is partly a brightness difference
    # rather than the shading it is labelled as. (R16)
    base = max(shaded_irr)
    irr = shaded_irr if shaded else [base] * len(shaded_irr)
    sc = Scenario(m, tp, geometry_of(irr), list(irr), False)
    uni_irr = [base] * len(shaded_irr)
    uni = Scenario(m, tp, geometry_of(uni_irr), uni_irr, False)

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
        run("Hybrid (bounded)", hyb.make_hybrid(model), temp_c=tp)
        run("Model only", hyb.make_seed_only(model), temp_c=tp)
    return dict(avail=[float(x) for x in shaded_av],
                unshaded=[float(x) for x in unshaded_av],
                traces=traces, t0=20, base_irr=base, has_model=model is not None)


# =========================================================================== #
# Testing · Shading relocation  (p12 export)
# =========================================================================== #
_RELOC_ROWS = ["hybrid, triggered reseed", "hybrid, never reseed", "PSO",
               "PSO, triggered reseed", "seed only", "P&O", "InC"]


def page_relocation():
    c = ui.T()
    ui.page_intro("Shading relocation",
                  "One clean relocation event: the tallest peak moves to another "
                  "substring, and each method has to find it again.",
                  "Explore · Shading relocation")
    rel = "phase2/relocation_comparison_pole.json"
    R = _load_json(rel)
    if not R or not require_keys(rel, R, ("stats", "n_windows"), "the relocation table"):
        if not R:
            missing_export(rel, "The relocation comparison")
        ui.not_built("Drift and cloud relocation families",
                     "Only the pole single-jump family has been run. The drifting-pole "
                     "and cloud-transit families are planned and are not offered as "
                     "options here.")
        return

    S = R.get("stats") or {}
    jump = R.get("settle_steps")
    hold = R.get("window_steps")
    ui.kpi_row([
        ("Relocation windows", f"{R.get('n_windows', '—')}",
         f"{R.get('discarded', '—')} discarded by the screen", "hero"),
        ("Window shape", f"settle {_fmt(jump, '{:.0f}')} → hold {_fmt(hold, '{:.0f}')}",
         "the jump falls at the end of the settle block"),
        ("Trigger threshold", f"{_fmt(100 * (R.get('trigger_drop_frac') or 0), '{:.0f}')}%",
         "measured power drop below the recent best"),
    ])

    # ---- gates -------------------------------------------------------------
    with st.container(border=True):
        st.markdown(_bh("Data-validation gates"), unsafe_allow_html=True)
        crit = R.get("criteria") or {}
        gates = R.get("gates") or R.get("gate_counts")
        if gates:
            cells = "".join(
                f"<span style='color:{c['text_muted']}'>{_e(k)}</span><span>{_e(v)}</span>"
                for k, v in gates.items())
            st.markdown(f"<div class='bmono' style='display:grid;"
                        f"grid-template-columns:1fr 1fr;gap:6px 14px;max-width:460px;"
                        f"font-size:12.5px'>{cells}</div>", unsafe_allow_html=True)
        else:
            # The finding — that this table must not be called gated — is the
            # reader's business. Which file is short of which fields, and what to
            # re-run, is the maintainer's. (§14)
            ui.unavailable(
                "Not presentable as gated",
                f"How many scenarios each acceptance gate passed or discarded was "
                f"not recorded, so these results cannot be described as gated. "
                f"Only a single discarded total ({R.get('discarded', '—')}) and the "
                f"four criteria below were kept.",
                "- File: `phase2/relocation_comparison_pole.json`\n"
                "- Present: one `discarded` total and the four declared acceptance "
                "criteria.\n"
                "- Absent: per-gate G1–G6 pass/discard counts, and a separate G5 "
                "uniform-control result.\n"
                "- Re-run `phase2/p12_relocation_comparison.py` with a version that "
                "writes them before quoting this table as gated.",
                kind="limit")
        if crit:
            names = {"c1": "triggered re-converges on the declared fraction of events",
                     "c2": "re-convergence margin exceeds the across-module spread",
                     "c3": "trigger fires near the actual jump (false-trigger rate low)",
                     "c4": "uniform control: no re-convergence and no trigger firing"}
            rows = "".join(
                f"<span class='bmono'>{_e(k)}</span>"
                f"<span style='color:{c['teal'] if v else c['red']}'>"
                f"{'PASS' if v else 'FAIL'}</span>"
                f"<span style='font-size:12.5px'>{_e(names.get(k, ''))}</span>"
                for k, v in crit.items())
            st.markdown(f"<div style='margin-top:10px;display:grid;"
                        f"grid-template-columns:auto auto 1fr;gap:6px 14px;"
                        f"font-size:13px;align-items:baseline'>{rows}</div>",
                        unsafe_allow_html=True)
            st.caption("These are the four acceptance criteria declared before the run. They are "
                       "an acceptance verdict, not the per-gate data-validation counts.")

    # ---- the table ---------------------------------------------------------
    with st.container(border=True):
        st.markdown(_bh("What each method did after the jump"), unsafe_allow_html=True)
        head = "".join(f"<span style='color:{c['text_muted']};font-size:11.5px'>{h}</span>"
                       for h in ("method", "re-converged (fraction)", "steps (median)",
                                 "worst", "transition energy lost"))
        body = ""
        for key in _RELOC_ROWS:
            sm = S.get(key)
            if not sm:
                continue
            # The export declares no epsilon, so reconv_frac is shown as the number
            # it is rather than converted to yes/no against a threshold this page
            # would have to invent.
            body += (f"<span style='font-weight:500'>{_e(method_label(key))}</span>"
                     f"<span>{_fmt(sm.get('reconv_frac'), '{:.2f}')}</span>"
                     f"<span>{_fmt(sm.get('median'), '{:.0f}')}</span>"
                     f"<span>{_fmt(sm.get('worst'), '{:.0f}')}</span>"
                     f"<span>{_fmt(sm.get('energy_loss_pct'), '{:.1f}')}%</span>")
        st.markdown(f"<div class='bmono' style='display:grid;"
                    f"grid-template-columns:1.6fr 1.2fr 1fr .7fr 1.2fr;gap:6px 12px;"
                    f"font-size:12.5px'>{head}{body}</div>", unsafe_allow_html=True)
        ui.legend_note(
            "A dash is a censored value: the method never re-converged, so it has no "
            "step count. Re-converged is the fraction of windows in which the method "
            "reached and held the new peak. The tolerance that defines 'reached' was "
            "not recorded, so the fraction is shown rather than a verdict.")

        if any((S.get(k) or {}).get("reconv_frac") for k in
               ("hybrid, triggered reseed", "PSO, triggered reseed")):
            missing_field(rel, "trigger_rate / false_trigger_rate",
                          "the trigger rate of the triggered variants")

    # ---- what the numbers say, built from the numbers -----------------------
    trig = S.get("hybrid, triggered reseed") or {}
    never = S.get("hybrid, never reseed") or {}
    stateless = {k: (S.get(k) or {}).get("energy_loss_pct")
                 for k in ("P&O", "InC", "PSO", "seed only", "hybrid, never reseed")}
    vals = [v for v in stateless.values() if v is not None]
    if trig:
        ui.callout(
            f"Family {R.get('family', '—')}, {R.get('n_windows', '—')} relocation windows. "
            f"{method_label('hybrid, triggered reseed')} recovers in a median of "
            f"{_fmt(trig.get('median'), '{:.0f}')} steps "
            f"(worst {_fmt(trig.get('worst'), '{:.0f}')}, s.e. "
            f"{_fmt(trig.get('se'), '{:.2f}')}) and loses "
            f"{_fmt(trig.get('energy_loss_pct'), '{:.1f}')}% in transit, while "
            f"{method_label('hybrid, never reseed')} loses "
            f"{_fmt(never.get('energy_loss_pct'), '{:.1f}')}%. "
            + (f"The stateless methods lose between {min(vals):.1f}% and "
               f"{max(vals):.1f}%. " if vals else "")
            + f"The jump falls at control step {_fmt(jump, '{:.0f}')}. "
              f"Only a measurement-triggered re-seed follows the peak; that is the "
              f"honest negative the triggered variant exists to fix, and it is reported.",
            "What the numbers say", "info")
    ui.provenance({rel.split("/")[-1]: _export_meta(rel, R)})

    ui.not_built("Drift and cloud relocation families",
                 "Only the pole single-jump family has been run. The drifting-pole and "
                 "cloud-transit families are planned; they are named here rather than "
                 "offered as controls that would do nothing.")


# =========================================================================== #
# Testing · Results vs targets
# =========================================================================== #
# Targets are NOT in any export. The static one is quoted from the funded
# proposal; the other two are not recorded anywhere in this repository, so they
# are shown as missing rather than invented. D2 decides which metric the static
# target is measured on, so both candidate rows are shown until it is answered.
_TARGETS = {
    "static_arrival": dict(
        row="Static partial shading — arrival rate", target=99.5,
        source="funded proposal, as quoted in the revision brief",
        pending="definition pending advisor decision"),
    "static_steady": dict(
        row="Static partial shading — steady efficiency", target=99.5,
        source="funded proposal, as quoted in the revision brief",
        pending="definition pending advisor decision"),
    "dynamic": dict(
        row="Dynamic EN 50530 — tracking efficiency", target=None,
        source="not recorded in this repository", pending=""),
    "convergence": dict(
        row="Convergence time", target=None,
        source="not recorded in this repository", pending=""),
}


def page_results():
    c = ui.T()
    ui.page_intro("Results vs targets",
                  "Each funded target beside what was measured, and the caveats that "
                  "belong to it.", "Results · Results vs targets")

    t_rel = "phase2/tracker_comparison_val.json"
    d_rel = "phase2/dynamic_comparison_30-100_val.json"
    p_rel = "phase2/pso_comparison_val.json"
    T = _load_json(t_rel)
    D = _load_json(d_rel)
    Pj = _load_json(p_rel)
    if not T:
        missing_export(t_rel, "The static result")
    elif not require_keys(t_rel, T, ("results",), "the static rows"):
        T = None
    if not D:
        missing_export(d_rel, "The dynamic result")
    elif not require_keys(d_rel, D, ("results",), "the dynamic row"):
        D = None

    head_key = "hybrid, bounded"
    static = ((T or {}).get("results") or {}).get(head_key, {}).get("multi_peak") or {}
    dyn_sh = ((D or {}).get("results") or {}).get("shaded") or {}
    dyn_row = dyn_sh.get("hybrid, no reseed") or {}

    rows = []
    rows.append(dict(
        key="static_arrival", achieved=static.get("reached_pct"), se=None,
        n=static.get("n"), split=(T or {}).get("split"),
        note=f"{method_label(head_key)}, multi-peak subset"))
    rows.append(dict(
        key="static_steady", achieved=static.get("steady_eff_pct"), se=None,
        n=static.get("n"), split=(T or {}).get("split"),
        note=f"{method_label(head_key)}, multi-peak subset — saturated"))
    rows.append(dict(
        key="dynamic", achieved=dyn_row.get("aggregate_pct"),
        se=dyn_row.get("scenario_se_pct"), n=dyn_row.get("n_trajectories"),
        split=(D or {}).get("split"),
        note=f"{method_label('hybrid, no reseed')}, shaded, Seq "
             f"{(D or {}).get('sequence', '—')}"))
    rows.append(dict(
        key="convergence", achieved=static.get("median_conv_steps"), se=None,
        n=static.get("n"), split=(T or {}).get("split"),
        note="median control steps to converge, conditional on arrival"))

    head = "".join(
        f"<span style='color:{c['text_muted']};font-size:11.5px'>{h}</span>"
        for h in ("target", "required", "achieved", "± s.e.", "n", "split", "verdict"))
    body = ""
    for r in rows:
        spec = _TARGETS[r["key"]]
        tgt = spec["target"]
        ach = r["achieved"]
        if tgt is None or ach is None:
            verdict, tone = "—", c["text_muted"]
        elif r["key"] == "convergence":
            verdict, tone = "—", c["text_muted"]
        else:
            passed = float(ach) >= float(tgt)
            verdict = "PASS" if passed else "NOT MET"
            tone = c["teal"] if passed else c["red"]
        req = f"{tgt:.1f}%" if tgt is not None else "not recorded"
        fmt = "{:.1f}" if r["key"] == "convergence" else "{:.2f}"
        unit = "" if r["key"] == "convergence" else "%"
        body += (f"<span style='font-weight:500'>{_e(spec['row'])}"
                 + (f"<br><span style='font-size:11px;color:{c['amber_text']}'>"
                    f"{_e(spec['pending'])}</span>" if spec["pending"] else "")
                 + f"<br><span style='font-size:11px;color:{c['text_muted']}'>"
                   f"{_e(r['note'])}</span></span>"
                 f"<span>{_e(req)}</span>"
                 f"<span>{_fmt(ach, fmt)}{unit}</span>"
                 f"<span>{_fmt(r['se'], '{:.3f}')}</span>"
                 f"<span>{_fmt(r['n'], '{:.0f}')}</span>"
                 f"<span>{_e(r['split'] or '—')}</span>"
                 f"<span style='color:{tone};font-weight:600'>{verdict}</span>")
    st.markdown(f"<div style='display:grid;"
                f"grid-template-columns:2.6fr .9fr .9fr .8fr .7fr .6fr .9fr;"
                f"gap:10px 14px;font-size:13px;align-items:baseline'>{head}{body}</div>",
                unsafe_allow_html=True)
    st.caption("The static target is quoted from the funded proposal. The dynamic and "
               "convergence targets were never written down in this project, so they "
               "are shown as not recorded rather than guessed.")

    ui.callout(
        "Read every row above with these attached. "
        "(1) Against PSO the advantage is cost, not accuracy: the two record the same "
        "energy captured and differ in readings per cycle. "
        "(2) The dynamic margin over P&O is inherited from static trapping — the EN "
        "50530 profile ramps irradiance but barely moves the peak location. "
        "(3) Steady efficiency is saturated near 100% for every seeded method and is "
        "reported as a value, never as a discriminator. "
        "(4) Convergence figures are conditional on arrival and must be read beside the "
        "arrival column. "
        "(5) All data is simulated; there are no field measurements behind any number "
        "here. "
        "(6) The held-out TEST split has not been evaluated — every figure on "
        "this page is a validation-split figure.",
        "Caveats that travel with these numbers", "caveat")

    ui.provenance({t_rel.split("/")[-1]: _export_meta(t_rel, T),
                   d_rel.split("/")[-1]: _export_meta(d_rel, D),
                   p_rel.split("/")[-1]: _export_meta(p_rel, Pj)})

    import json
    csv = "target,required,achieved,se,n,split\n" + "\n".join(
        f"\"{_TARGETS[r['key']]['row']}\","
        f"{_TARGETS[r['key']]['target'] if _TARGETS[r['key']]['target'] is not None else ''},"
        f"{'' if r['achieved'] is None else r['achieved']},"
        f"{'' if r['se'] is None else r['se']},{r['n'] or ''},{r['split'] or ''}"
        for r in rows)
    e1, e2 = st.columns(2)
    e1.download_button("Download table (CSV)", csv, "results_vs_targets.csv", "text/csv",
                       use_container_width=True, key="results_csv")
    e2.download_button("Download figure data (JSON)",
                       json.dumps({"rows": rows, "targets": _TARGETS,
                                   "provenance": {t_rel: _export_meta(t_rel, T),
                                                  d_rel: _export_meta(d_rel, D)}},
                                  indent=2, default=str),
                       "results_vs_targets.json", "application/json",
                       use_container_width=True, key="results_json")


# =========================================================================== #
# The data · Benchmark scenario set
# =========================================================================== #
def page_benchset():
    c = ui.T()
    ui.page_intro("Benchmark scenario set",
                  "What the benchmark figures were measured on.",
                  "Results · Benchmark scenario set")
    t_rel = "phase2/tracker_comparison_val.json"
    d_rel = "phase2/dynamic_comparison_30-100_val.json"
    n_rel = "phase2/near_tie_screen.json"
    T, D, N = _load_json(t_rel), _load_json(d_rel), _load_json(n_rel)
    if T and not require_keys(t_rel, T, ("results",), "the static counts"):
        T = None
    if not T and not D:
        missing_export(t_rel, "The benchmark scenario set")
        return

    mp = ((T or {}).get("results") or {}).get("P&O", {}).get("multi_peak") or {}
    sp = ((T or {}).get("results") or {}).get("P&O", {}).get("single_peak") or {}
    ui.kpi_row([
        ("Static multi-peak scenarios", _fmt(mp.get("n"), "{:.0f}"),
         f"split {(T or {}).get('split', '—')} · of "
         f"{_fmt((T or {}).get('n_scenarios'), '{:.0f}')} total", "hero"),
        ("Static single-peak", _fmt(sp.get("n"), "{:.0f}"), "the control subset"),
        ("Shaded dynamic scenarios", _fmt((D or {}).get("n_shaded"), "{:.0f}"),
         f"uniform {_fmt((D or {}).get('n_uniform'), '{:.0f}')} · EN 50530"),
    ], weights=[1.3, 1, 1.2])

    with st.container(border=True):
        st.markdown(_bh("How the set is built"), unsafe_allow_html=True)
        mix = _scen.GEOMETRY_MIX
        cells = "".join(
            f"<span style='color:{c['text_muted']}'>{_e(k.replace('_', '-'))}</span>"
            f"<span>{100 * v:.0f}%</span>" for k, v in mix.items())
        st.markdown(f"<div class='bmono' style='display:grid;"
                    f"grid-template-columns:1fr .5fr;gap:6px 14px;max-width:320px;"
                    f"font-size:13px'>"
                    f"<span style='color:{c['text_muted']}'>geometry</span>"
                    f"<span style='color:{c['text_muted']}'>share</span>"
                    f"{cells}</div>", unsafe_allow_html=True)
        st.markdown(
            f"- **Panels** — validation panels only; the reserved test set is not "
            f"used anywhere in this dashboard.\n"
            f"- **Temperatures** — {', '.join(str(int(t)) for t in _scen.TEMPERATURES)} °C.\n"
            f"- **Sunlight** — {_scen.IRR_MIN:.0f}–{_scen.IRR_MAX:.0f} W/m².\n"
            f"- **Reproducible** — the whole set regenerates from a single seed.")
        if N:
            frac = N.get("near_tie_fraction") or N.get("fraction")
            if frac is not None:
                st.markdown(f"- **Near ties** — {float(frac) * 100:.1f}% of scenarios have "
                            f"two peaks close enough that picking the wrong one costs "
                            f"almost nothing.")
            else:
                # the bullet stays, so the "dash" the note refers to is on the page
                st.markdown("- **Near ties** — not recorded in this result set.")
                missing_field(n_rel, "near_tie_fraction", "the near-tie share")
        else:
            missing_export(n_rel, "The near-tie screen")

    ui.provenance({t_rel.split("/")[-1]: _export_meta(t_rel, T),
                   d_rel.split("/")[-1]: _export_meta(d_rel, D)})
    # the footer's Next already goes to Where it comes from — no second link


def page_moving():
    import numpy as np
    c = ui.T()
    disp, mono = ui.FONTS["display"], ui.FONTS["mono"]
    st.markdown(f"<style>.bh{{font-family:{disp};font-weight:700;color:{c['text']};}}"
                f"</style>", unsafe_allow_html=True)
    ui.page_intro("Dynamic irradiance",
                  "How each tracking method responds while the irradiance changes, on the "
                  "EN 50530 ramp profile.", "Explore · Dynamic irradiance")
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

    rel = f"phase2/dynamic_comparison_{seq}_val.json"
    dyj = _load_json(rel)
    if not dyj:
        missing_export(rel, "The dynamic comparison")
        dyj = None
    elif not require_keys(rel, dyj, ("results", "split"), "the dynamic KPIs"):
        dyj = None
    if dyj:
        sh = (dyj.get("results") or {}).get("shaded" if shaded else "uniform") or {}

        def agg(m):
            return (sh.get(m) or {}).get("aggregate_pct")

        def se_of(m):
            return (sh.get(m) or {}).get("scenario_se_pct")

        hyb_key = "hybrid, no reseed"
        hyb, pso_v, po = agg(hyb_key), agg("PSO"), agg("P&O")
        if hyb is None:
            missing_field(rel, hyb_key, "the headline efficiency")
        kp = [("Dynamic efficiency", f"{_fmt(hyb, '{:.3f}')}%",
               f"{method_label(hyb_key)} · ±{_fmt(se_of(hyb_key), '{:.3f}')}"
               f" · EN 50530 Seq {dyj.get('sequence', seq)}", "hero")]
        # PSO and P&O carry their own s.e., so a reader can see whether the gap
        # is separable rather than being shown a bare difference.
        if hyb is not None and pso_v is not None:
            kp.append(("vs PSO", f"{hyb - pso_v:+.2f} pt",
                       f"PSO {_fmt(pso_v, '{:.3f}')}% ±{_fmt(se_of('PSO'), '{:.3f}')}"))
        if hyb is not None and po is not None:
            kp.append(("vs P&O", f"{hyb - po:+.1f} pt",
                       f"P&O {_fmt(po, '{:.3f}')}% ±{_fmt(se_of('P&O'), '{:.3f}')}"))
        ui.kpi_row(kp)

        rs_key = "hybrid, reseed each block"
        if rs_key in sh:
            rs = sh[rs_key]
            credited = dyj.get("reseed_credited")
            ui.callout(
                f"Reseeding at every block boundary scores "
                f"{_fmt(rs.get('aggregate_pct'), '{:.3f}')}% "
                f"±{_fmt(rs.get('scenario_se_pct'), '{:.3f}')} against "
                f"{_fmt(hyb, '{:.3f}')}% for the same hybrid without it, for a probe "
                f"overhead of {_fmt(rs.get('reseed_probe_overhead_pct'), '{:.2f}')}%. "
                + ("The benchmark does not credit it." if credited is False else
                   "The benchmark credits it." if credited is True else
                   "Whether it is credited is not recorded."),
                "Negative result — reseeding each block is not credited", "caveat")
            with st.expander("Technical details", expanded=False):
                st.markdown(f"- The export records `reseed_credited = {credited}` and "
                            f"`reseed_probe_overhead_pct = "
                            f"{rs.get('reseed_probe_overhead_pct')}`.")
        ui.provenance({rel.split('/')[-1]: _export_meta(rel, dyj)})

    # ---- live per-step traces on the fixed demo module ----
    demo = _mv_demo()
    try:
        day = _dynamic_day(seq, shaded, demo["module"], demo["temp"], demo["shaded"])
    except Exception as e:
        ui.unavailable("Trace unavailable",
                       "The per-step traces for this profile could not be computed, so "
                       "nothing is drawn below. The benchmark figures above are unaffected.",
                       f"- `_dynamic_day` raised `{type(e).__name__}: {e}`", kind="limit")
        return
    if not day.get("has_model"):
        ui.unavailable(
            "Hybrid unavailable",
            "The trained model could not be loaded, so Hybrid and Model-only are "
            "absent from the traces below. The classical trackers are real.",
            "- Needs `results/phase3/c3_two_stage.pkl` and scikit-learn.", kind="limit")

    avail = np.array(day["avail"]); unshaded = np.array(day["unshaded"])
    t0 = day["t0"]
    x = np.arange(len(avail))
    all_methods = [m for m in ("Hybrid (bounded)", "P&O", "PSO", "Model only", "InC")
                   if m in day["traces"]]
    default = [m for m in ("Hybrid (bounded)", "P&O") if m in all_methods] or all_methods[:1]
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
                              line=dict(width=2, **ui.method_style(m))))
            ui.style_fig(fig, height=320, x_title="EN 50530 profile (control steps)",
                         y_title="power (W)")
        else:
            eff = lambda a: np.where(avail > 1e-9, 100 * a / avail, 100.0)
            fig.add_trace(go.Scatter(x=xs, y=trim(np.full_like(avail, 100.0)),
                          name="available", line=dict(color="#2B3238", width=2)))
            for m in sel:
                fig.add_trace(go.Scatter(x=xs, y=trim(eff(np.array(day["traces"][m]))), name=m,
                              line=dict(width=2, **ui.method_style(m))))
            ui.style_fig(fig, height=320, x_title="EN 50530 profile (control steps)",
                         y_title="tracking efficiency (%)")
            fig.update_yaxes(range=[60, 101])
        fig.update_layout(legend=dict(orientation="h", y=1.08, x=0))
        ui.show_chart(fig)

    with st.container(border=True):
        st.markdown(f"<span class='bh' style='font-size:17px'>Power lost to tracking</span>"
                    f"<span style='font-size:13px;color:{c['text_muted']};margin-left:10px'>"
                    f"the distance from the dark line above — shading excluded, the tracker's "
                    f"own fault only</span>", unsafe_allow_html=True)
        fig2 = go.Figure()
        for m in sel:
            loss = np.maximum(0.0, avail - np.array(day["traces"][m]))
            fig2.add_trace(go.Scatter(x=xs, y=trim(loss), name=m,
                           line=dict(width=2, **ui.method_style(m))))
        ui.style_fig(fig2, height=170, x_title="EN 50530 profile (control steps)",
                     y_title="power lost (W)")
        fig2.update_layout(legend=dict(orientation="h", y=1.15, x=0))
        ui.show_chart(fig2)

    ui.callout("The x-axis is the EN 50530 ramp profile (control steps), not a clock. The "
               "standard ramps irradiance but barely moves the peak location, so the margin "
               "over P&O is largely static trapping carried into a changing scene.",
               "Read this beside the traces", "caveat")

    # ---- A7: the same traces, played through ----
    st.divider()
    _a7_profile_playback(day, sel, seq, shaded, c)
    st.divider()

    _your_day(c)

    ui.not_built("Dragging events on a timeline",
                 "Events are timed with the sliders on Understand · The panels, one event at "
                 "a time. Dragging an event along a timeline, and resizing it by its "
                 "edges, needs a drag-and-drop control this dashboard does not have "
                 "yet. Animated playback of a day run is available above, under Your day.")


# =========================================================================== #
# A7 — EN 50530 profile playback  (Update 3 §5.3, user §12)
#
# Explanatory only. It replays the per-step traces `_dynamic_day` computed for
# the fixed demo module; the headline KPIs above come from the phase-2 export
# and are neither read nor written here. Building or playing this animation
# cannot change a single figure on the page — T32 checks exactly that.
# =========================================================================== #
def _a7_profile_playback(day, sel, seq, shaded, c):
    import numpy as np
    ui.section_head("Play the profile",
                    "the same traces above, one control step at a time")
    ui.anim_badge("live", f"EN 50530 Seq {seq} · demo module · validated engine")
    ui.callout("This plays the per-step traces for one demo module so the shape of "
               "the response is visible. The efficiency figures at the top of the "
               "page are the benchmark result over the whole validation split and "
               "are not affected by anything here.",
               "Explanatory, not the benchmark number", "caveat")

    methods = [m for m in sel if m in day.get("traces", {})]
    if not methods:
        st.caption("Choose at least one method above.")
        return
    if st.button("▶ Build the profile playback", key="a7_build",
                 help="Replays the traces already computed for this profile. "
                      "No tracker is re-run and no benchmark figure is touched."):
        st.session_state["a7_built"] = True
    if not st.session_state.get("a7_built"):
        st.caption("Press ▶ to step through the ramp.")
        return

    import time as _time
    tstart = _time.perf_counter()
    t0 = int(day["t0"])
    avail = np.asarray(day["avail"], float)[t0:]
    unsh = np.asarray(day["unshaded"], float)[t0:]
    tr = {m: np.asarray(day["traces"][m], float)[t0:] for m in methods}
    n = min(len(avail), *(len(v) for v in tr.values()))
    x = list(range(n))

    # key frames: where the available power turns, i.e. the ramp's corners. Read
    # from the profile, not assumed from the sequence name.
    key = {0, n - 1}
    if n > 4:
        d1 = np.diff(avail[:n])
        sign = np.sign(np.round(d1, 6))
        for i in range(1, len(sign)):
            if sign[i] != sign[i - 1] and sign[i] != 0:
                key.add(int(i))
    key = sorted(key)
    keep, stride = ui.downsample(n, key)
    frames = [{
        "step": k,
        "title": f"step {k} — available {avail[k]:.0f} W",
        "markers": {m: {"V": k, "P": float(tr[m][k])} for m in methods},
        "trails": {m: [(j, float(tr[m][j])) for j in range(max(0, k - 30), k + 1)]
                   for m in methods},
    } for k in keep]
    build_s = _time.perf_counter() - tstart

    static = [go.Scatter(x=x, y=[float(v) for v in unsh[:n]], mode="lines",
                         name="unshaded potential",
                         line=dict(color="#B5641A", width=2, dash="dot")),
              go.Scatter(x=x, y=[float(v) for v in avail[:n]], mode="lines",
                         name="available at true peak",
                         line=dict(color="#2B3238", width=2.5))]
    series = {m: {"color": ui.method_style(m)["color"],
                  "symbol": _A1_SYMBOLS.get(m.split(" (")[0], "circle")}
              for m in methods}
    held = {m: 100.0 * float(np.sum(tr[m][:n])) / max(1e-9, float(np.sum(avail[:n])))
            for m in methods}
    caption = ("; ".join(f"{m} holds {held[m]:.2f}% of the available power over this "
                         f"demo profile" for m in methods)
               + f". {len(key) - 2} ramp corner(s) are marked. These are one module's "
                 f"trace, not the split-wide benchmark figure above.")

    if not ui.anim_on():
        ui.callout("Animations are off, so the ramp corners are shown as stills.",
                   "Static view", "info")
        ui.snapshot_strip(frames, [i for i, f in enumerate(frames)
                                   if f["step"] in key][:5],
                          captions=[f["title"] for f in frames
                                    if f["step"] in key][:5],
                          static_traces=static, series=series, key="a7")
        st.markdown(f'<div class="gm-legend">{_e(caption)}</div>', unsafe_allow_html=True)
        return

    fig = ui.trace_player(frames, series, static_traces=static, height=400,
                          key_frames=key, step_prefix="step ", frame_ms=60,
                          x_title="EN 50530 profile  control steps",
                          y_title="power  W")
    ui.show_chart(fig, key="a7_player")
    st.markdown(f'<div class="gm-legend">{_e(caption)}</div>', unsafe_allow_html=True)
    with st.expander("Show the ramp corners", expanded=False):
        ui.snapshot_strip(frames, [i for i, f in enumerate(frames)
                                   if f["step"] in key][:5],
                          captions=[f["title"] for f in frames
                                    if f["step"] in key][:5],
                          static_traces=static, series=series, key="a7-keys")
    measured = ui.anim_exports(fig, frames,
                               {"badge": "live illustration",
                                "detail": f"EN 50530 Seq {seq}, one demo module",
                                "shaded": bool(shaded), "stride": stride},
                               key="a7", name="profile_playback")
    ui.anim_budget_note(measured, stride, build_s)


def _your_day(c):
    """The event-based day run: exploratory, ungated, and labelled as such.

    It lives here so it sits beside the gated EN 50530 result and cannot be
    mistaken for it. The events themselves are built on Understand · The panels.
    """
    import numpy as np
    with st.expander("Your day — event-based run (exploratory, not a benchmark)",
                     expanded=False):
        st.markdown('<div class="gm-sandbox"><b>Exploratory</b>'
                    '<span>Not a benchmark result and not gated: an arbitrary event '
                    'timeline you built, not a declared scenario set. No figure from '
                    'here belongs beside a thesis number.</span></div>',
                    unsafe_allow_html=True)
        events = st.session_state.get("day_events") or []
        ctx = st.session_state.get("day_context") or {}
        if not events or not ctx:
            ui.callout("Build a day on Understand · The panels — add events, set their timing "
                       "and motion — then come back here to run them.",
                       "No day events yet", "info")
            st.page_link(P["panels"], label="Build a day on The panels →")
            return
        st.caption(f"{len(events)} event(s) on {ctx.get('module', '—')} · "
                   f"{ctx.get('temp', '—')} °C · peak sun {ctx.get('base_G', '—')} W/m².")
        if not st.button("Run the whole day through the trackers", key="yourday_run",
                         type="primary"):
            st.session_state.setdefault("day_ran", False)
        else:
            st.session_state["day_ran"] = True
        if not st.session_state.get("day_ran"):
            return

        evkey = tuple((e["kind"], round(e["t0"], 3), round(e["t1"], 3),
                       e.get("motion", "fixed in place")) for e in events)
        try:
            day = _day_run(ctx["module"], ctx["temp"], ctx["base_G"], evkey)
        except Exception as e:
            ui.unavailable("Day run unavailable",
                           "Your day could not be run through the trackers, so nothing "
                           "is shown here. The EN 50530 figures above are unaffected.",
                           f"- `_day_run` raised `{type(e).__name__}: {e}`", kind="limit")
            return
        if not day.get("has_model"):
            ui.callout("The trained seed is not loadable, so no hybrid trace is shown "
                       "below. The classical trackers are real.",
                       "Hybrid unavailable", "limit")

        g2 = day.get("g2") or {}
        tone = "info" if g2.get("passed") == g2.get("total") else "limit"
        ui.callout(f"Curve-integrity check (G2): {g2.get('passed')}/{g2.get('total')} "
                   f"slices reproduce their own p_gmpp at v_gmpp within "
                   f"{g2.get('tol')}; worst relative error "
                   f"{_fmt(g2.get('worst_rel'), '{:.2e}')}.",
                   "Per-slice gate", tone)

        t = np.array(day["t"])
        figd = go.Figure()
        figd.add_trace(go.Scatter(x=t, y=day["unshaded"], name="unshaded potential",
                                  line=dict(color=ui.REF_COLORS["unshaded"],
                                            dash="dot", width=2)))
        figd.add_trace(go.Scatter(x=t, y=day["avail"], name="available at true peak",
                                  line=dict(color=ui.REF_COLORS["available"], width=2.5)))
        for m, ph in day["methods"].items():
            figd.add_trace(go.Scatter(x=t, y=ph, name=m,
                                      line=dict(width=2, **ui.method_style(m))))
        figd.add_vline(x=st.session_state.get("day_time", 15.0),
                       line=dict(color=c["amber"], width=1.5, dash="dot"))
        ui.style_fig(figd, height=300, x_title="time of day (h)", y_title="power (W)")
        figd.update_layout(legend=dict(orientation="h", y=1.1, x=0))
        ui.show_chart(figd, key="yourday_power")
        cells = "".join(f"<span style='font-weight:500'>{_e(m)}</span>"
                        f"<span>{v:.2f}%</span>" for m, v in day["energy"].items())
        st.markdown(f"<div class='bmono' style='display:grid;"
                    f"grid-template-columns:1fr .7fr;gap:6px 14px;max-width:360px;"
                    f"font-size:13px'><span style='color:{c['text_muted']}'>method</span>"
                    f"<span style='color:{c['text_muted']}'>energy captured</span>"
                    f"{cells}</div>", unsafe_allow_html=True)
        ui.legend_note(f"{day.get('slices')} irradiance slices over a sun-arc profile with "
                       f"your events. A drifting shadow sweeps continuously across the "
                       f"strips; it does not jump between them.")

        # A5 and A6 replay this same run. They add no calculation of their own.
        st.divider()
        _a5_day_curves(day, c)
        st.divider()
        _a6_day_tracker(day, c)


# =========================================================================== #
# A5 — Day curve playback   ·   A6 — Your Day tracker playback
#   (Update 3 §5.3, user §11)
#
# Both replay `_day_run`'s own output. The curves, the trajectories, the
# available-power reference and the per-slice G2 verdicts were all computed by
# the day run; these two functions only draw them. A slice that FAILED G2 is
# drawn like any other and marked, because dropping it would quietly improve a
# picture of an exploratory result. Both carry the exploratory badge the run
# itself carries.
# =========================================================================== #
def _a5_day_curves(day, c):
    """The P–V curve at each time slice, played through the day."""
    curves = day.get("slice_curves") or []
    g2 = day.get("slice_g2") or []
    ui.section_head("The curve through the day", "one frame per irradiance slice")
    ui.anim_badge("live", "your event timeline · exploratory, not a benchmark")
    if not curves:
        ui.unavailable("Slice curves unavailable",
                       "This day run did not record a curve for each time slice, so "
                       "there is nothing to play back.",
                       "- `_day_run` returns `slice_curves`; an older cached run "
                       "predates it. Re-run the day to rebuild it.")
        return

    if st.button("▶ Build the day playback", key="a5_build",
                 help="Plays back the curves this day run already computed. "
                      "Nothing is re-simulated."):
        st.session_state["a5_built"] = True
    if not st.session_state.get("a5_built"):
        st.caption("Press ▶ to watch the curve change shape through the day.")
        return

    import time as _time
    t0 = _time.perf_counter()
    labels, key_frames, failed = [], {0, len(curves) - 1}, []
    prev_pk = None
    for i, cur in enumerate(curves):
        ok_g2 = (g2[i]["pass"] if i < len(g2) else True)
        if not ok_g2:
            failed.append(i)
            key_frames.add(i)                     # a failed slice is always shown
        pk = round(float(cur["gmpp"]["P"]), 1)
        labels.append(f"{cur['t']:05.2f} h — true peak {pk:.0f} W"
                      + ("" if ok_g2 else "  ·  G2 FAILED on this slice"))
        if prev_pk is not None and abs(pk - prev_pk) > 0.15 * max(prev_pk, 1e-9):
            key_frames.add(i)                     # the shape moved sharply
        prev_pk = pk
    key_frames = sorted(key_frames)
    build_s = _time.perf_counter() - t0

    caption = (f"{len(curves)} slices from {curves[0]['t']:.1f} h to "
               f"{curves[-1]['t']:.1f} h. The true peak runs from "
               f"{curves[0]['gmpp']['P']:.0f} W to a maximum of "
               f"{max(x['gmpp']['P'] for x in curves):.0f} W. "
               + (f"{len(failed)} slice(s) failed the G2 curve-integrity check and "
                  f"are marked in the playback."
                  if failed else "Every slice passed the G2 curve-integrity check."))

    if not ui.anim_on():
        ui.callout("Animations are off, so the marked slices are shown side by side.",
                   "Static view", "info")
        ui.curve_strip(curves, labels, key_frames[:5], key="a5")
        st.markdown(f'<div class="gm-legend">{_e(caption)}</div>', unsafe_allow_html=True)
        return

    fig = ui.curve_morph(curves, labels, key_frames=key_frames, height=380,
                         frame_ms=160)
    ui.show_chart(fig, key="a5_player")
    st.markdown(f'<div class="gm-legend">{_e(caption)}</div>', unsafe_allow_html=True)
    if failed:
        ui.callout(f"Slices {', '.join(str(i) for i in failed[:10])} failed G2. They "
                   f"are played back unchanged and labelled — a failed slice is not "
                   f"removed from an exploratory run.", "Failed slices kept", "limit")
    with st.expander("Show the marked slices", expanded=False):
        ui.curve_strip(curves, labels, key_frames[:5], key="a5-keys")
    measured = ui.anim_exports(fig, [{"t": x["t"], "p_gmpp": x["gmpp"]["P"]}
                                     for x in curves],
                               {"badge": "live illustration",
                                "detail": "exploratory day run, validated engine",
                                "stride": 1}, key="a5", name="day_curves")
    ui.anim_budget_note(measured, 1, build_s)


def _a6_day_tracker(day, c):
    """Where each tracker sat, against the power that was available."""
    import numpy as np
    ui.section_head("Each tracker through the day",
                    "the power it actually held, against the power that was there")
    ui.anim_badge("live", "your event timeline · exploratory, not a benchmark")
    methods = list(day.get("methods") or {})
    if not methods:
        ui.unavailable("No trajectories recorded",
                       "This day run has no tracker traces to play back.", "")
        return

    if st.button("▶ Build the tracker playback", key="a6_build",
                 help="Replays the trajectories this day run already produced."):
        st.session_state["a6_built"] = True
    if not st.session_state.get("a6_built"):
        st.caption("Press ▶ to follow each tracker across the day.")
        return

    import time as _time
    t0 = _time.perf_counter()
    t = [float(x) for x in day["t"]]
    avail = [float(x) for x in day["avail"]]
    n = min(len(t), *(len(day["methods"][m]) for m in methods))
    sps = int(day.get("steps_per_slice") or 8)
    g2 = day.get("slice_g2") or []
    bad_steps = {i for i, s in enumerate(g2) if not s["pass"]}

    key = {0, n - 1}
    for i in sorted(bad_steps):
        if i * sps < n:
            key.add(i * sps)
    keep, stride = ui.downsample(n, sorted(key))
    frames = []
    for k in keep:
        sl = min(k // sps, max(len(g2) - 1, 0))
        failed = bool(g2) and not g2[sl]["pass"]
        frames.append({
            "step": k,
            "title": (f"{t[k]:05.2f} h — available {avail[k]:.0f} W"
                      + ("  ·  slice failed G2" if failed else "")),
            "markers": {m: {"V": t[k], "P": float(day["methods"][m][k])}
                        for m in methods},
            "trails": {m: [(t[j], float(day["methods"][m][j]))
                           for j in range(max(0, k - 24), k + 1)]
                       for m in methods},
        })
    build_s = _time.perf_counter() - t0

    static = [go.Scatter(x=t[:n], y=day["unshaded"][:n], mode="lines",
                         name="unshaded potential",
                         line=dict(color=ui.REF_COLORS["unshaded"], dash="dot", width=2)),
              go.Scatter(x=t[:n], y=avail[:n], mode="lines",
                         name="available at true peak",
                         line=dict(color=ui.REF_COLORS["available"], width=2.5))]
    series = {m: {"color": ui.method_style(m)["color"],
                  "symbol": _A1_SYMBOLS.get(m.split(" (")[0], "circle")}
              for m in methods}
    energy = day.get("energy") or {}
    caption = ("; ".join(f"{m} captured {energy.get(m, float('nan')):.2f}% of the "
                         f"available energy" for m in methods) +
               f". {len(bad_steps)} of {len(g2)} slices failed G2 and are marked.")

    if not ui.anim_on():
        ui.callout("Animations are off, so the marked moments are shown as stills.",
                   "Static view", "info")
        ui.snapshot_strip(frames, list(range(min(4, len(frames)))),
                          captions=[frames[i]["title"]
                                    for i in range(min(4, len(frames)))],
                          static_traces=static, series=series, key="a6")
        st.markdown(f'<div class="gm-legend">{_e(caption)}</div>', unsafe_allow_html=True)
        return

    fig = ui.trace_player(frames, series, static_traces=static, height=400,
                          key_frames=sorted(key), step_prefix="step ", frame_ms=70,
                          x_title="time of day  h", y_title="power  W")
    ui.show_chart(fig, key="a6_player")
    st.markdown(f'<div class="gm-legend">{_e(caption)}</div>', unsafe_allow_html=True)
    with st.expander("Show key moments", expanded=False):
        ui.snapshot_strip(frames, [i for i, f in enumerate(frames)
                                   if f["step"] in key][:5],
                          captions=[f["title"] for f in frames
                                    if f["step"] in key][:5],
                          static_traces=static, series=series, key="a6-keys")
    measured = ui.anim_exports(fig, frames,
                               {"badge": "live illustration",
                                "detail": "exploratory day run, validated engine",
                                "stride": stride}, key="a6", name="day_tracker")
    ui.anim_budget_note(measured, stride, build_s)


# =========================================================================== #
# The data
# =========================================================================== #
def page_dataset():
    # Title matches the tab ("Sandbox dataset"), so the page is named one way.
    ui.page_intro("Sandbox dataset",
                  "What is in the scenario set you generated, and where the error "
                  "concentrates.", "Sandbox · Sandbox dataset")
    d = st.session_state.get("dataset")
    if not d or d.get("df") is None or len(d["df"]) == 0:
        ui.callout("No dataset has been generated in this session, so there is nothing to "
                   "show here. Generate one on Make a dataset and it appears on this "
                   "page.", "No dataset yet", "info")
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
                     help=f"The download could not be built: {_e}")
    a, b = st.columns(2, gap="large")
    with a:
        fig = go.Figure(go.Histogram(x=df["gmpp_voltage_V"], nbinsx=40,
                                     marker_color=ui.METHOD_COLORS["Model only"]))
        ui.style_fig(fig, 320, "Scenarios", "Voltage of the true peak (V)")
        fig.update_layout(title="Where the tallest peak sits")
        ui.show_chart(fig)
        ui.legend_note("Clusters, not one bump: the peak sits near a strip boundary.")
    with b:
        fig = go.Figure()
        for objname, g in df.groupby("shading_object"):
            fig.add_trace(go.Scatter(x=g["reduction_percent"], y=g["power_loss_percent"],
                                     mode="markers", name=objname, marker=dict(size=6, opacity=0.7)))
        ui.style_fig(fig, 320, "Power lost to shade (%)", "Light blocked (%)")
        fig.update_layout(title="Loss against how dark the shadow is")
        ui.show_chart(fig)
    ui.engine_badge("simplified")


def page_sources():
    c = ui.T()
    ui.page_intro("Where it comes from",
                  "From a laboratory measurement to the figure on screen — and what the numbers cannot tell you.",
                  "Results · Where it comes from")

    # Which page is drawn by which engine, and where each input comes from.
    with st.container(border=True):
        st.markdown(_bh("The two engines"), unsafe_allow_html=True)
        # The model each engine is, in words. Which Python module implements it
        # is provenance for a maintainer and sits in Technical details (§24).
        rows = [
            ("Validated engine",
             "Single-diode cell model with bypass diodes and reverse-bias breakdown, "
             "fitted to the CEC reference database",
             "The panels, Inside a panel, and every Watch, Compare and Explore page",
             "Research and benchmark analysis. Matched to ~1% against 616 laboratory "
             "flash tests."),
            ("Interactive simulator",
             "Simplified single-diode model with per-substring bypass",
             "Sandbox · Set up a panel, Make a dataset, The dataset",
             "Exploratory configuration and visualisation. Not a benchmark result; "
             "reverse-bias breakdown is not modelled."),
        ]
        cells = "".join(
            f"<span style='font-weight:600;color:{c['text']}'>{n}</span>"
            f"<span style='font-size:12.5px'>{model}</span>"
            f"<span style='font-size:12.5px'>{where}</span>"
            f"<span style='font-size:12.5px;color:{c['text_muted']}'>{why}</span>"
            for n, model, where, why in rows)
        st.markdown(
            f"<div style='margin-top:10px;display:grid;"
            f"grid-template-columns:1fr 1.5fr 1.3fr 1.6fr;gap:10px 14px;font-size:13px'>"
            f"<span style='color:{c['text_muted']};font-size:11.5px'>engine</span>"
            f"<span style='color:{c['text_muted']};font-size:11.5px'>model</span>"
            f"<span style='color:{c['text_muted']};font-size:11.5px'>used on</span>"
            f"<span style='color:{c['text_muted']};font-size:11.5px'>what it is for</span>"
            f"{cells}</div>", unsafe_allow_html=True)
        with st.expander("Technical details", expanded=False):
            st.markdown("- Validated engine: `gmppt.device` with `pvlib` CEC parameters.\n"
                        "- Interactive simulator: `app.py`, single-diode + per-substring "
                        "bypass.")

    with st.container(border=True):
        st.markdown(_bh("Where each input comes from"), unsafe_allow_html=True)
        counts = _split_counts()
        st.markdown(
            "- **Panel models** — the CEC module database, the industry reference set "
            "of measured module parameters.\n"
            "- **Which panels are shown** — the validation set only: panels held back "
            "from fitting the model, used to compare tracking methods. A third set is "
            "reserved for a single final test and is never shown here.\n"
            "- **Sandbox panels** — the Sandbox has its own typed-in datasheets. They "
            "are not from the reference database and are never used for a benchmark.\n"
            "- **Tracking methods** — perturb-and-observe, incremental conductance, "
            "particle swarm, and the learned seed with its hybrid refinement.\n"
            "- **Changing-conditions profiles** — the EN 50530 irradiance ramps. These "
            "are a standard test profile, not a time-of-day sun path.\n"
            "- **Comparison figures** — results measured by the analysis runs. When a "
            "result has not been generated the page says so rather than estimating it.")
        with st.expander("Technical details", expanded=False):
            st.markdown(
                f"- Module pool: `pvlib.pvsystem.retrieve_sam(\"CECMod\")`, cached to "
                f"`results/cec_pool.parquet`.\n"
                f"- Split: `gmppt.dataset.module_split()` → train {counts['train']:,}, "
                f"val {counts['val']:,}, test {counts['test']:,}. `test` is exactly "
                f"`gmppt.scenarios.split_modules(pool)[1]`, the 20% reserve declared in "
                f"Phase 1; `val` is carved from the training modules under its own seed.\n"
                f"- This dashboard resolves every module through "
                f"`dataset.module_split().val`, the same set "
                f"`phase2/p7_tracker_comparison.py --split val` runs on. No code path "
                f"here reads `split.test`; it is opened only through "
                f"`p3_final_comparison.py --confirm-test`, which ledgers each opening.\n"
                f"- Trackers: `gmppt.tracking`, `gmppt.trackers`, `gmppt.pso`, "
                f"`gmppt.model` + `gmppt.hybrid`.\n"
                f"- Profiles: `gmppt.dynamic.SEQUENCES`. Figures: `results/phase2/`.")

    # app.py's validation record lists result files by name. That is provenance
    # a maintainer needs and a reader does not, so it sits behind one heading
    # rather than in the page body. app.py itself is untouched.
    ui.section_head("Validation record",
                    "how the simplified engine was checked against the validated one")
    with st.expander("Technical details", expanded=False):
        sim.page_validation()


# =========================================================================== #
# Navigation shell
#
# One header (ui.app_header), one footer (ui.footer_nav), rendered by a single
# wrapper that every page goes through. No page draws its own chrome, so a page
# cannot disagree with the rest of the app about where the user is.
# =========================================================================== #
_PAGE_FUNCS = {
    "home": (page_home, "Home", "home"),
    "panels": (page_panels, "The panels", "panels"),
    "inside": (page_inside, "Inside a panel", "panel"),
    "system": (None, "Whole system", "system"),          # None = greyed "· coming"
    "run": (page_run, "Watch one run", "run"),
    "compare": (page_compare, "Compare methods", "compare"),
    "moving": (page_moving, "Dynamic irradiance", "dynamic-irradiance"),
    "relocation": (page_relocation, "Shading relocation", "relocation"),
    "results": (page_results, "Results vs targets", "results"),
    "benchset": (page_benchset, "Benchmark scenario set", "benchmark-set"),
    "sources": (page_sources, "Where it comes from", "sources"),
    "sim_setup": (page_sim_setup, "Set up a panel", "simulator"),
    "sim_saved": (page_sim_saved, "Saved scenarios", "saved"),
    "sim_dataset": (page_sim_dataset, "Make a dataset", "make-dataset"),
    "dataset": (page_dataset, "Sandbox dataset", "data"),
}

# Section order = the order a reader walks the work. "Whole system" is in the
# Explore list so it shows as "· coming", but it is not in STEPS, so it never
# inflates the step count with a page that has nothing on it.
# --------------------------------------------------------------------------- #
# THE ONE WORKFLOW TABLE (§3).
#
# A stage is what the reader is doing, not where a file lives. Everything that
# names a stage reads it from here — the header strip, the page eyebrow, the
# footer, the Home stepper, the tutorial and the tests — so they cannot drift
# apart the way the old header sections ("Explore / Testing / The data") and the
# stage names had. Sandbox is a separate engine and sits outside the journey.
# --------------------------------------------------------------------------- #
STAGES = [
    ("Understand", ["panels"]),                    # build the scenario
    ("Inspect",    ["inside", "system"]),          # look at what it did to the curve
    ("Watch",      ["run"]),                       # watch each tracker search it
    ("Compare",    ["compare"]),                   # every method on the whole set
    ("Explore",    ["moving", "relocation"]),      # changing conditions
    ("Results",    ["results", "benchset", "sources"]),   # targets and provenance
]
SANDBOX = ["sim_setup", "sim_saved", "sim_dataset", "dataset"]
JOURNEY = [s for s, _ in STAGES]

SECTION_KEYS = {s: list(ks) for s, ks in STAGES}
SECTION_KEYS["Sandbox"] = list(SANDBOX)
# The sequence the footer walks. "system" is planned, not built, so it is not a
# step.
_FLOW = [k for _, ks in STAGES for k in ks if k != "system"]
_SANDBOX_FLOW = list(SANDBOX)
_FLOW_STAGE = {k: s for s, ks in STAGES for k in ks if k != "system"}


def stage_of(key: str) -> str:
    """The workflow stage a page belongs to, or 'Sandbox'."""
    return _FLOW_STAGE.get(key) or ("Sandbox" if key in SANDBOX else "")

# One sentence per page, shown under the title, answering "what is this for?".
_PAGE_PURPOSE = {
    "panels": "Build a scenario: choose a module, place a shadow, set the conditions.",
    "inside": "Inspect the scenario you built — every peak, and what the bypass "
              "diodes are doing.",
    "run": "Watch each tracking method search the same curve.",
    "compare": "Compare the methods across the whole validation set.",
    "moving": "See how the methods behave while conditions change.",
    "relocation": "See what happens when the strongest peak moves to another strip.",
    "results": "The measured results beside the targets.",
    "benchset": "What those results were measured on.",
    "sources": "Where every input comes from.",
}

# What each workflow stage is for, for the hover help on the flow strip (§7).
# Derived from the page purposes so the two can never drift apart: a stage is
# described by the first page that carries it.
_STAGE_PURPOSE = {}
for _k, _stage in _FLOW_STAGE.items():
    _STAGE_PURPOSE.setdefault(_stage, _PAGE_PURPOSE.get(_k, ""))

_NEXT_WHY = {
    "panels": "You have a scenario. Look at why its curve has more than one peak.",
    "inside": "You know why the peaks are there. Watch each method try to find the tallest.",
    "run": "One curve proves nothing on its own. See every method on every shaded case.",
    "compare": "Now see whether it holds while the irradiance changes.",
    "moving": "A ramp barely moves the peak. See what happens when the peak jumps.",
    "relocation": "You have seen every experiment. Read them against the funded targets.",
    "results": "Every number rests on a scenario set. See what is in it.",
    "benchset": "And where each of its inputs came from.",
    "sim_setup": "Keep a curve to compare against later.",
    "sim_saved": "Or generate thousands of scenarios like it.",
    "sim_dataset": "Then look at what you generated.",
}

# Widget keys that must survive a page change (R2). Streamlit deletes a widget's
# key on any run that does not render it, which in a multipage app is every run
# spent on another page.
_PERSIST_KEYS = [
    "gm_panel", "gm_obj2", "gm_runs", "gm_edge", "gm_shaded_ids", "gm_sel",
    "gm_showuns", "gm_pv", "gm_vop", "gm_rows", "gm_per", "gm_mount",
    "gm_depth2", "gm_width", "gm_G2", "gm_T2",
    "run_overlay", "mv_scen", "mv_show", "mv_mode", "saved_pick", "day_time",
    "gm_anim", "a1_steps", "a1_view", "a1_built", "a2_built", "a3_built",
    "a4_built", "a5_built", "a6_built", "a7_built", "a9_built",
    "bench_preset", "bench_nsub", "bench_mstr", "bench_pstr", "bench_obj",
    "bench_baseG", "bench_T", "bench_scen_name",
] + [f"bench_{f}" for f in sim.DS_FIELDS] + [
    # The per-substring irradiance inputs, listed explicitly rather than matched
    # by a "bench_s" prefix. That prefix also caught `bench_save` and
    # `bench_scen_name`; pre-setting a BUTTON's value is an error Streamlit
    # raises when the widget is created, which no try/except around the
    # assignment can catch. 12 is the substring maximum the number_input allows.
    f"bench_s{i}" for i in range(12)
]
_PERSIST_PREFIXES = ("day_win_", "day_mot_", "swp_")


def _step_of(key):
    if key in _FLOW:
        return _FLOW.index(key) + 1, len(_FLOW), _FLOW
    if key in _SANDBOX_FLOW:
        return _SANDBOX_FLOW.index(key) + 1, len(_SANDBOX_FLOW), _SANDBOX_FLOW
    return None, None, None


def _make_page(key):
    fn, title, url = _PAGE_FUNCS[key]

    def _wrapped():
        # The header's stage strip is the one persistent "where am I" (§5); it is
        # drawn from STAGES, with the stage's purpose as hover help (§7).
        ui.app_header({k: P.get(k) if _PAGE_FUNCS[k][0] else None for k in _PAGE_FUNCS},
                      SECTION_KEYS, key, journey=JOURNEY, stage_help=_STAGE_PURPOSE)
        stage = _FLOW_STAGE.get(key)
        if stage:
            # Which stages this session has reached — the stepper's "done" marks.
            seen = st.session_state.setdefault("gm_visited", [])
            if key not in seen:
                seen.append(key)
        if key in SECTION_KEYS["Sandbox"]:
            st.markdown('<div class="gm-sandbox"><b>Sandbox · simplified engine</b>'
                        '<span>Exploratory configuration and visualisation. Nothing here '
                        'is a benchmark result.</span></div>', unsafe_allow_html=True)
        fn()
        if key == "home":
            # After the body, so every control the tour points at is on the page.
            ui.tutorial(_tutorial_steps())

        step, total, flow = _step_of(key)
        if flow:
            i = flow.index(key)
            prev_key = flow[i - 1] if i > 0 else "home"
            next_key = flow[i + 1] if i + 1 < len(flow) else None
            ui.footer_nav(P.get(prev_key), P.get(next_key) if next_key else None,
                          step, total, _NEXT_WHY.get(key, ""))

    _wrapped.__name__ = f"page_{key}"
    return st.Page(_wrapped, title=title, url_path=url, default=(key == "home"))


def _resend_notice():
    """Shown on Watch one run ONLY when the draft has diverged from what is running.

    The always-on scenario bar was removed. This is not a status line: it appears
    only when Explore has been edited since the scenario was sent, which is the
    one case where the page would otherwise be showing a curve the user thinks
    they have already changed.
    """
    draft = st.session_state.get("scenario_draft")
    sent = st.session_state.get("scenario_sent")
    if not (draft and sent) or draft.get("hash") == sent.get("hash"):
        return
    a, b = st.columns([5, 1.2], vertical_alignment="center")
    with a:
        ui.callout(f"The scenario running here is “{sent.get('label', 'the sent one')}”. "
                   f"You have since edited The panels to “{draft.get('label', 'something else')}” "
                   f"without sending it.", "Edited since sent", "caveat")
    if b.button("Resend", key="run_resend", use_container_width=True,
                help="Run the scenario you are now editing on The panels."):
        st.session_state["scenario_sent"] = dict(draft)
        st.toast("Resent the scenario you are editing.")
        st.rerun()


for _k in _PAGE_FUNCS:
    if _PAGE_FUNCS[_k][0] is not None:
        P[_k] = _make_page(_k)

SECTIONS = {"": [P["home"]]}
for _sec, _keys in SECTION_KEYS.items():
    SECTIONS[_sec] = [P[k] for k in _keys if k in P]

ui.persist_widget_state(_PERSIST_KEYS, _PERSIST_PREFIXES)

# Built-in nav hidden — ui.app_header is the visible one, on every page.
nav = st.navigation(SECTIONS, position="hidden")
nav.run()
