"""
gmppt_app.py — entry point for the GMPPT Bench dashboard.

Wraps the existing app.py (kept unchanged, imported as `sim`) in the research
workflow navigation and the gmppt_ui design system.

    Run:  streamlit run gmppt_app.py
    Needs: streamlit >= 1.63, plotly, numpy, pandas — plus app.py, gmppt_ui.py,
           gmppt_hero.py, gmppt_scenario.py and gmppt_timeline.py in the same folder.

Sections — the research experiment lifecycle (see DESIGN.md §2):
    SCENARIO           Build system · PV analysis
    STATIC TEST        One run · Compare methods            (the user's scenario)
    DYNAMIC TEST       Timeline · Tracker response · Energy (the user's scenario)
    RESULTS            Research summary · Static performance · Dynamic performance ·
                       Targets                              (validated exports only)
    DATA & VALIDATION  Benchmark set · PV model validation · Experiment provenance
    SANDBOX            Simulator · Saved scenarios · Sweep · Dataset generator

The principle: Scenario defines the experiment once; the Static and Dynamic
tests reuse that same physical PV system; Results reports the validated
research evidence separately from the user's exploratory runs, and is never
populated by one. Visualisation is functional here, not decoration: every
drawing is driven by the same state and engine output as the numbers beside it.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import app as sim          # your existing simulator — physics, presets, pages
import gmppt_hero as hero  # the landing page
import gmppt_scenario as scn  # Scenario page state: system / condition / hashes / time
import gmppt_timeline as tl   # Dynamic test: G(t), T(t), Shade(t) on the inherited system
import gmppt_ui as ui
from gmppt import config as _gcfg, dataset as _ds, device as _eng, scenarios as _scen
from gmppt.hybrid import SEED_PROBE_COST

st.set_page_config(page_title="GMPPT Bench", layout="wide", initial_sidebar_state="collapsed")
sim.init_state()
st.session_state.setdefault("gm_theme", "Dark")   # dark is the default on every page; Light stays a switch
st.session_state.setdefault("gm_lang", "EN")     # landing copy only; read in gmppt_hero
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
# Home  (landing) — drawn by gmppt_hero. This file keeps only what the tutorial
# and the tests need to see: the tour's step targets, which are the hero's two
# links and the five cards, all real controls on the page.
# --------------------------------------------------------------------------- #
def _tutorial_steps():
    """The onboarding tour (§6–7): each step points at a REAL control on Home.

    The targets are the hero's primary and secondary links and the five cards,
    which are the same links the reader will use once the tour is over.
    """
    card = lambda k: f".st-key-gm-card-{k}"
    return [
        {"target": ".st-key-hero-primary a", "title": "Start here",
         "body": "This button takes you to Scenario · Build system, the first step "
                 "of the journey. Everything else on this page is a shortcut into it."},
        {"target": card("sim_setup"), "title": "Build the panel",
         "body": "Pick a module and set the sunlight and the cell temperature, "
                 "starting from a clean unshaded curve."},
        {"target": card("panels"), "title": "Place the shadow",
         "body": "Drag a shadow along or across the cell strips and watch the "
                 "power curve grow extra peaks."},
        {"target": card("inside"), "title": "Read the curve",
         "body": "Every peak and the true maximum are marked, with each bypass "
                 "diode's state as you move the operating point."},
        {"target": card("run"), "title": "Run the trackers",
         "body": "Send the scenario to the tracking methods and watch how each "
                 "one searches the same curve."},
        {"target": card("compare"), "title": "Compare and export",
         "body": "The validated result: what each method captured over the whole "
                 "validation set, and the tables and figures as files."},
        {"target": ".st-key-hero-secondary a", "title": "Or watch first",
         "body": "Prefer to see it before you touch anything? This opens a "
                 "worked example with a shadow already in place."},
    ]



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
                    for k in ("scenario_system", "scenario_draft", "scenario_sent", "frozen",
                              "day_events", "tl_events", "dynamic_scenario"):
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
        "scenario_system": st.session_state.get("scenario_system"),
        "scenario_draft": st.session_state.get("scenario_draft"),
        "scenario_sent": st.session_state.get("scenario_sent"),
        "frozen": st.session_state.get("frozen", []),
        "tl_events": st.session_state.get("tl_events", []),
        "dynamic_scenario": st.session_state.get("dynamic_scenario"),
        "exports": exports,
    }, indent=2, default=str)


def page_home():
    hero.render_hero(P)
    hero.render_cards(P)
    _session_io()
    hero.render_footer(P)



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


# --------------------------------------------------------------------------- #
# The scenario store. Two states, one shape (R3).
#
#   scenario_draft  what Build system is showing right now — rewritten every render
#   scenario_sent   what the Static and Dynamic tests run — written only by Send
#
# Keeping them apart is what lets a page say "edited since sent" instead of
# letting an edit on Build system silently change the curve a test page already
# drew. `hash` is what the two are compared on. Records are built by
# gmppt_scenario.build_draft; _scenario_hash below is the legacy module-level
# hash the Sandbox import records still carry.
# --------------------------------------------------------------------------- #
def _scenario_hash(module, temp, irr) -> str:
    import hashlib
    payload = repr((str(module), round(float(temp), 6), _key(irr)))
    return hashlib.sha1(payload.encode()).hexdigest()[:12]


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


# --------------------------------------------------------------------------- #
# Dynamic test · the timeline runner.
#
# The timeline itself — G(t), T(t), Shade(t) on the PV SYSTEM inherited from
# Scenario, in canonical minutes — lives in gmppt_timeline. This runs ONE
# dynamic scenario through the trackers exactly the way the EN 50530 harness
# does: one validated-engine curve per irradiance slice, a DynamicTrajectory
# over those curves, and the harness's own metrics() on the result. Every
# figure it produces is scenario-specific and exploratory; none is a benchmark.
# --------------------------------------------------------------------------- #
def _dyn_key(dscn: dict) -> str:
    """A hashable, order-stable cache key: the dynamic-scenario record itself."""
    import json
    return json.dumps(dscn, sort_keys=True, default=str)


def _to_plain(v):
    """numpy scalars → Python, so the run dict survives st.cache_data and JSON."""
    if isinstance(v, (bool, np.bool_)):
        return bool(v)
    if isinstance(v, (int, float, np.integer, np.floating)):
        return float(v)
    return v


@st.cache_data(show_spinner="Running your timeline through the trackers…")
def _timeline_run(dkey: str) -> dict:
    import json
    from gmppt import dynamic as dyn, tracking as trk, trackers as trkx, pso, config as gc, device
    from gmppt.tracking import REACH_TOLERANCE
    dscn = json.loads(dkey)
    system, events = dscn["system"], dscn["events"]
    peak = float(dscn["sun"]["peak_Wm2"])
    t_dawn = float(dscn["temperature"]["dawn_C"])
    t_noon = float(dscn["temperature"]["noon_C"])
    tracked = dscn["tracked_panel"]["uid"]
    slices = int(dscn["slices"])
    SPS = int(dscn.get("steps_per_slice", tl.STEPS_PER_SLICE))
    n_sub = int(_gcfg.N_SUBSTRINGS)
    mp = _mparams(dscn["module"])
    times = tl.sample_times(slices)

    def curve_at(entry, T):
        cv = device.module_iv(mp, entry, float(T), bd=gc.breakdown())
        a = device.analyse(cv)
        V = np.asarray(cv["V"], float); P = np.asarray(cv["P"], float)
        o = np.argsort(V)
        return (V[o], P[o], float(a["gmpp"]["V"]), float(a["gmpp"]["P"]), int(a["n_peaks"]))

    curves, unshaded, slice_curves, slice_g2, slice_env = [], [], [], [], []
    g2_pass, worst_rel = 0, 0.0
    for ti in times:
        stt = tl.state_at(system, events, float(ti), peak, t_dawn, t_noon, n_sub)
        entry = tl.entry_for(stt, system, tracked)
        V, Pp, v_g, p_g, n_pk = curve_at(entry, stt["temp_c"])
        # G2, the curve-integrity gate the harness applies: the curve must
        # reproduce its own GMPP. A failing slice is counted, never dropped.
        rel = abs(float(np.interp(v_g, V, Pp)) - p_g) / max(p_g, 1e-9)
        ok = rel <= trk.PARITY_TOL
        g2_pass += int(ok)
        worst_rel = max(worst_rel, rel)
        curves.append((V, Pp, v_g, p_g))
        unshaded.append(curve_at([max(1.0, stt["sun_G"])] * n_sub, stt["temp_c"])[3])
        keep = np.linspace(0, len(V) - 1, min(len(V), 200)).astype(int)
        slice_curves.append({"t": int(round(float(ti))),
                             "V": [float(x) for x in V[keep]],
                             "P": [float(x) for x in Pp[keep]],
                             "gmpp": {"V": float(v_g), "P": float(p_g)},
                             "irr": entry, "n_peaks": int(n_pk)})
        slice_g2.append({"pass": bool(ok), "rel": float(rel)})
        slice_env.append({"t": int(round(float(ti))), "sun_G": float(stt["sun_G"]),
                          "temp_c": float(stt["temp_c"]), "active": list(stt["active"]),
                          "shaded_uids": sorted(stt["shaded_uids"]), "entry": entry})

    bs = np.array([SPS] * slices)
    scored = np.ones(slices, bool)
    n_steps = int(bs.sum())

    def mk():
        return dyn.DynamicTrajectory(curves=curves, block_steps=bs, scored=scored,
                                     module=str(dscn["module"]), profile_name="timeline")

    out = {"t": [float(x) for x in np.repeat(times, SPS)],
           "unshaded": [float(x) for x in np.repeat(unshaded, SPS)],
           "methods": {}, "v_hist": {}, "metrics": {}, "avail": []}

    def run(name, fn, **kw):
        tj = mk()
        fn(tj, n_steps=n_steps, **kw)
        out["methods"][name] = [float(x) for x in tj.p_hist]
        out["v_hist"][name] = [float(x) for x in tj.v_hist]
        out["avail"] = [float(x) for x in tj.avail_hist]
        out["metrics"][name] = {k: _to_plain(v) for k, v in tj.metrics().items()}

    run("P&O", trk.perturb_and_observe)
    run("InC", trkx.incremental_conductance)
    run("PSO", pso.particle_swarm)
    model = _c3_model()
    seed_temp = float(slice_env[0]["temp_c"])
    if model is not None:
        from gmppt import hybrid as hyb
        # The seed reads ONE module temperature (hybrid.seed_voltage's contract);
        # in a run that starts at dawn it is the dawn cell temperature.
        run("Hybrid (bounded)", hyb.make_hybrid(model), temp_c=seed_temp)
        run("Model only", hyb.make_seed_only(model), temp_c=seed_temp)

    av = np.asarray(out["avail"], float)
    minutes_per_step = tl.DAY_MINUTES / max(1, n_steps)
    out["energy"] = {m: 100.0 * float(np.sum(ph)) / max(1e-9, float(np.sum(av)))
                     for m, ph in out["methods"].items()}
    out["energy_wh"] = {m: tl.energy_wh(ph, minutes_per_step) for m, ph in out["methods"].items()}
    out["available_wh"] = tl.energy_wh(av, minutes_per_step)
    out["unshaded_wh"] = tl.energy_wh(out["unshaded"], minutes_per_step)

    # Condition changes (an event starting or ending) and, per method, how many
    # steps it took to settle again — the harness's convergence rule applied to
    # each segment between changes. Read from the events, never assumed.
    changes = tl.change_points(events, times)
    for ch in changes:
        ch["step"] = int(ch["slice"]) * SPS
    bounds = [ch["step"] for ch in changes] + [n_steps]
    out["reconv"] = {}
    for m, ph in out["methods"].items():
        rows = []
        for i, ch in enumerate(changes):
            rows.append({"t": ch["t"], "step": ch["step"],
                         "steps": tl.reconvergence_steps(ph, av, ch["step"], bounds[i + 1],
                                                         REACH_TOLERANCE)})
        out["reconv"][m] = rows

    out.update(has_model=model is not None, seed_temp_c=seed_temp,
               g2={"passed": int(g2_pass), "total": int(slices),
                   "worst_rel": float(worst_rel), "tol": float(trk.PARITY_TOL)},
               slice_curves=slice_curves, slice_g2=slice_g2, slice_env=slice_env,
               slices=int(slices), steps_per_slice=int(SPS), n_steps=int(n_steps),
               minutes_per_step=float(minutes_per_step), changes=changes,
               tolerance=float(REACH_TOLERANCE), tracked=dict(dscn["tracked_panel"]),
               hash=str(dscn["hash"]), module=str(dscn["module"]))
    return out


def _run_step_at(run: dict, t_minutes) -> int:
    """The control step the playhead is on."""
    n = int(run.get("n_steps") or len(run["t"]))
    f = (float(t_minutes) - tl.DAY_START) / tl.DAY_MINUTES
    return int(min(max(round(f * (n - 1)), 0), n - 1))


def _unseen_check(name, chip=True):
    """What kind of data this panel is, in one line — detail on request. (U1.5, §10)

    This used to print the split counts, the nearest training module and an
    explanation of how the check is performed, right beside the module picker.
    That is bookkeeping about how the app is built, not something a reader needs
    in order to understand the panel in front of them. The one fact that matters
    stays visible; the rest moved into Technical details, where it is still
    available for reproducibility.

    chip=False keeps only the guard: the membership check still runs and a
    training module still stops the page, but nothing is printed for a
    validation module. Scenario uses this — the data class is not something
    a reader building a system needs to see beside the panel picker.
    """
    in_train = str(name) in _train_module_names()
    if in_train:
        # This would invalidate the page, so it is a warning, not a detail.
        ui.callout("This panel is not validation data, so its curve cannot be "
                   "compared with the benchmark results.", "Wrong data set", "limit")
        return
    if not chip:
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


def _key_rows(rows):
    """Hashable key for [row][module] irradiances (each module entry through _key)."""
    return tuple(tuple(_key(entry) for entry in row) for row in rows)


def _unkey_entry(entry_key):
    return [list(e) if isinstance(e, tuple) else float(e) for e in entry_key]


def _pack_curve(c):
    """analyse() + the V>=0, V-ascending arrays every chart here draws."""
    a = _eng.analyse(c)
    V, I, P = c["V"], c["I"], c["P"]
    m = V >= 0
    V, I, P = V[m], I[m], P[m]
    o = np.argsort(V)
    return dict(V=V[o], I=I[o], P=P[o], gmpp=a["gmpp"], peaks=a["peaks"],
                n_peaks=a["n_peaks"], voc=float(V.max()))


@st.cache_data(show_spinner=False)
def _sim_string(name, row_key, T):
    """One row of panels in series — the validated string_iv, never a copy of it.
    Cache key: module, temperature, the ordered module irradiances (n_series is
    their count)."""
    mp = _mparams(name)
    irr = [_unkey_entry(e) for e in row_key]
    return _pack_curve(_eng.string_iv(mp, irr, float(T), bd=_gcfg.breakdown()))


@st.cache_data(show_spinner=False)
def _sim_array(name, rows_key, T, blocking=True):
    """Every row in parallel — device.array_iv (the one additive engine function).
    Cache key: module, temperature, every string's irradiances (n_series and
    n_parallel are their shape), blocking-diode configuration."""
    mp = _mparams(name)
    strings = [[_unkey_entry(e) for e in row] for row in rows_key]
    return _pack_curve(_eng.array_iv(mp, strings, float(T), bd=_gcfg.breakdown(),
                                     blocking_diodes=bool(blocking)))


def _topo_click_to_selection():
    """A click on the topology drawing (delivered by Plotly on the run after the
    click) selects that panel. Runs before any widget is created, because a
    widget's key may only be set before the widget exists. Selection is VIEW
    STATE: it changes which panel is shown, and nothing else."""
    ev = st.session_state.get("gm_topo")
    try:
        pts = ev["selection"]["points"]
    except (TypeError, KeyError):
        return
    if not pts:
        return
    uid = pts[0].get("customdata")
    if isinstance(uid, (list, tuple)):
        uid = uid[0] if uid else None
    if not uid or uid == st.session_state.get("gm_topo_seen"):
        return
    st.session_state["gm_topo_seen"] = uid
    for p in (st.session_state.get("scenario_system") or {}).get("panels", []):
        if p["uid"] == uid:
            st.session_state["gm_sel"] = p["display_id"]
            return


def _clear_shadow_keys(uids):
    """on_click: reset the shading widgets of these panels to 'no shadow'."""
    for uid in uids:
        st.session_state[f"shp_{uid}"] = "None"
        st.session_state[f"drk_{uid}"] = int(scn.DEFAULT_SHADOW["darkness"])
        st.session_state[f"pos_{uid}"] = 50


def page_panels():
    _demo_startup_log()
    c = ui.T()
    disp, mono = ui.FONTS["display"], ui.FONTS["mono"]
    st.markdown(f"<style>.bh{{font-family:{disp};font-weight:700;color:{c['text']};font-size:15px;}}"
                f".bmono,.bmono *{{font-family:{mono};}}"
                f".gm-status{{font-family:{mono};font-size:12.5px;margin:6px 0;}}"
                f".gm-badges{{display:flex;flex-direction:column;gap:6px;font-family:{mono};"
                f"font-size:12.5px;}} .gm-badges span{{display:flex;justify-content:space-between;}}"
                f"</style>", unsafe_allow_html=True)
    ui.page_intro("Build system",
                  "Build the PV system once, then define what is happening to it right now.",
                  "Scenario · Build system")
    # T13: the engine or its module pool missing is an explicit stop. Nothing
    # from the sandbox and no example module ever stands in for it.
    try:
        val_mods = _validation_modules()
        assert val_mods
    except Exception as e:
        ui.unavailable("The validated engine is not connected",
                       "No panel data could be loaded, so nothing on this page can be drawn. "
                       "No example or sandbox result is shown in its place.",
                       f"- `{type(e).__name__}: {_e(e)}`\n- Needs `results/cec_pool.parquet` "
                       f"beside `gmppt_app.py` (produced once by Phase 1).", kind="limit")
        return
    # Nothing is drawn unless every module offered is a validation module. (U1.3)
    if not assert_val_modules([n for _, n in val_mods], "The panel dropdown"):
        return
    label_to_name = dict(val_mods)
    _topo_click_to_selection()

    hdr = st.columns([5, 1.1], vertical_alignment="center")
    with hdr[1]:
        lab = bool(st.toggle("Lab details", key="gm_lab",
                             help="Section and cell-group labels, internal ids, hashes and "
                                  "the technical names. View only — it changes nothing."))
    ctrl, mid, right = st.columns([0.92, 1.5, 1.18], gap="large")

    # ================================================================ 1 · system
    # PV SYSTEM: persistent hardware / topology. Built once here; the static
    # test freezes one snapshot of it and the future dynamic timeline will
    # inherit it unchanged (module, n_series, n_parallel, panel uids,
    # connections, optimiser architecture) while G, T and shading vary.
    with ctrl:
        # Collapsed-card summaries come from the live session values, never
        # from a second copy of the state. The open/closed flags are view state.
        _pp = int(round(float(st.session_state.get("gm_per", 1) or 1)))
        _rr = int(round(float(st.session_state.get("gm_rows", 1) or 1)))
        _model = str(st.session_state.get("gm_panel") or val_mods[0][0]).split(" · ")[0]
        with ui.collapsible("1 · Your PV system", "scenario_system_expanded",
                            summary=f"{_pp * _rr} panel{'s' if _pp * _rr != 1 else ''} · {_model}"):
            labels = [l for l, _ in val_mods] + ["Nanum target panel — [awaiting spec]"]
            pick = st.selectbox("Panel type", labels, key="gm_panel")
            awaiting = pick.startswith("Nanum")
            name = val_mods[0][1] if awaiting else label_to_name[pick]
            if awaiting:
                ui.callout("Nanum's target spec is awaited — a validation module is "
                           "shown in the meantime.", "", "info")
            _unseen_check(name, chip=False)      # the guard only; no data-class chip here
            # Topology, as integers. Older sessions carry floats from the preset
            # dropdowns these controls replaced; they are kept, not reset.
            for _k in ("gm_per", "gm_rows"):
                try:
                    st.session_state[_k] = int(min(12, max(1, round(float(
                        st.session_state.get(_k, 1))))))
                except (TypeError, ValueError):
                    st.session_state[_k] = 1
            n_series = int(st.number_input("Panels in a row", 1, 12, step=1, key="gm_per",
                                           help="Panels wired one after another in a row."))
            n_parallel = int(st.number_input("Rows", 1, 12, step=1, key="gm_rows",
                                             help="Rows joined side by side on the DC bus."))
            n_panels = n_series * n_parallel
            if n_panels > 1:
                st.session_state.setdefault("gm_opt", True)
                optimisers = bool(st.checkbox("Every panel has its own optimiser", key="gm_opt",
                                              help="On: each panel is tracked on its own (the "
                                                   "product's architecture). Off: one shared "
                                                   "tracker on the whole array."))
            else:
                optimisers = bool(st.session_state.get("gm_opt", True))
            st.markdown(f"<div class='gm-status'>{n_panels} panel{'s' if n_panels != 1 else ''}"
                        + (f" · {n_series}S × {n_parallel}P · {n_panels} module"
                           f"{'s' if n_panels != 1 else ''} · {_gcfg.N_SUBSTRINGS} substrings/module"
                           if lab else "") + "</div>", unsafe_allow_html=True)

        prev_sys = st.session_state.get("scenario_system") or {}
        panels = scn.migrate_panels(prev_sys.get("panels"), n_series, n_parallel)
        system = {"module": str(name), "n_series": n_series, "n_parallel": n_parallel,
                  "optimisers_enabled": optimisers, "blocking_diodes": True,
                  "panels": panels}
        st.session_state["scenario_system"] = system
        ids = [p["display_id"] for p in panels]
        by_id = {p["display_id"]: p for p in panels}
        # selection is VIEW STATE (which panel is shown); resolved before the
        # shading card because that card edits the selected panel's shadow
        if st.session_state.get("gm_sel") not in ids:
            st.session_state["gm_sel"] = ids[0]
        sel = by_id[st.session_state["gm_sel"]]
        sel_id = sel["display_id"]

        # ============================================================ 2 · conditions
        # STATIC CONDITION: one environmental snapshot. Time is minutes after
        # midnight (15:00 = 900) and is metadata today — it anchors the future
        # timeline; it does not enter the physics.
        st.session_state.setdefault("gm_time", scn.minutes_to_time(900))
        _cond = (f"{scn.minutes_to_hhmm(scn.time_to_minutes(st.session_state['gm_time']))} · "
                 f"{float(st.session_state.get('gm_G2', 910)):.0f} W/m² · "
                 f"{float(st.session_state.get('gm_T2', 43)):.0f} °C")
        with ui.collapsible("2 · Conditions", "scenario_conditions_expanded", summary=_cond):
            t_val = st.time_input("Time", key="gm_time", step=900,
                                  help="The moment this snapshot describes. It anchors a "
                                       "future timeline; it does not change the physics.")
            time_minutes = scn.time_to_minutes(t_val)
            base_G = int(_dual("Sunlight (W/m²)", "gm_G2",
                               [100, 200, 400, 600, 800, 910, 1000], " W/m²", 10, 100, 1000, 910))
            T = int(_dual("Cell temperature (°C)", "gm_T2",
                          [10, 25, 43, 55, 70], " °C", 1, 10, 70, 43,
                          help="Cell (not air) temperature."))

        # ============================================================ 3 · shading
        # Per panel: the widgets are keyed by the panel's uid, so each panel
        # keeps its own shadow and nothing has to be copied when the selection
        # changes. The panel record is the state; the widgets edit it.
        # summary from the live widget values (current on every run), falling
        # back to the panel record for panels never edited
        _shaded = []
        for _p in panels:
            _shape = st.session_state.get(f"shp_{_p['uid']}", (_p.get("shadow") or {}).get("shape", "None"))
            if _shape not in (None, "None"):
                _dark = st.session_state.get(f"drk_{_p['uid']}", (_p.get("shadow") or {}).get("darkness", 0))
                _shaded.append((_p["display_id"], _shape, float(_dark)))
        _shade = ("No shade" if not _shaded
                  else f"{_shaded[0][1]} · {_shaded[0][0] if n_panels > 1 else 'Panel 1'} · {_shaded[0][2]:.0f} W/m²"
                  if len(_shaded) == 1 else f"shadow on {len(_shaded)} panels")
        with ui.collapsible("3 · Shading", "scenario_shading_expanded", summary=_shade,
                            open_note=f"on {sel_id if (lab or n_panels > 1) else 'Panel 1'}"):
            uid = sel["uid"]
            sh = sel.get("shadow") or dict(scn.DEFAULT_SHADOW)
            st.session_state.setdefault(f"shp_{uid}", sh["shape"])
            st.session_state.setdefault(f"drk_{uid}", int(sh["darkness"]))
            st.session_state.setdefault(f"pos_{uid}", int(round(float(sh["position"]) * 100)))
            # the darkness slider is bounded by the sunlight; keep stored values inside
            st.session_state[f"drk_{uid}"] = int(min(max(st.session_state[f"drk_{uid}"], 0), base_G))
            shapes = list(scn.SHAPES)
            leaf_ok = n_panels == 1 or st.session_state[f"shp_{uid}"] == "Leaf"
            if not leaf_ok:
                shapes.remove("Leaf")
            if st.session_state[f"shp_{uid}"] not in shapes:
                st.session_state[f"shp_{uid}"] = "None"
            shape = st.segmented_control("What casts it", shapes, key=f"shp_{uid}",
                                         help=scn.SHAPE_HELP[st.session_state[f"shp_{uid}"]]) or "None"
            if not leaf_ok:
                st.caption("Leaf (part of one section) is available on a single panel only: "
                           "the validated row engine takes one light level per section.")
            dark = st.slider("How dark", 0, int(base_G), key=f"drk_{uid}", step=10,
                             format="%d W/m²", disabled=shape == "None",
                             help="Light left under the shadow. Lower is darker.")
            pos = st.slider("Where it falls", 0, 100, key=f"pos_{uid}", step=5, format="%d%%",
                            disabled=shape in ("None", "Dirt", "Cloud"),
                            help="Left to right across the panel: which section the shadow "
                                 "lands on. Dirt and cloud cover the whole panel.")
            sel["shadow"] = {"shape": shape, "darkness": float(dark), "position": pos / 100.0}
            b1, b2 = st.columns(2)
            b1.button("Clear this shadow", key="gm_clear_one", use_container_width=True,
                      on_click=_clear_shadow_keys, args=([uid],))
            b2.button("Clear all shadows", key="gm_clear_all", use_container_width=True,
                      on_click=_clear_shadow_keys, args=([p["uid"] for p in panels],))

    # ================================================================ compute
    # Every panel's entry is exactly what module_iv / string_iv accept.
    rows_irr = scn.module_irradiances(system, base_G, _gcfg.N_SUBSTRINGS)
    for p in panels:                                    # the record carries the widget state
        p["shadow"] = by_id[p["display_id"]]["shadow"]
    uniform = [float(base_G)] * _gcfg.N_SUBSTRINGS
    geometry = scn.scenario_geometry(rows_irr, geometry_of)
    glabel = geometry.replace("_", "-")
    sel_irr = rows_irr[sel["row"]][sel["pos"]]
    det = _sim(name, _key(sel_irr), T)
    uns = _sim(name, _key(uniform), T)
    powers, shaded_uids = {}, set()
    for p in panels:
        entry = rows_irr[p["row"]][p["pos"]]
        powers[p["uid"]] = _sim(name, _key(entry), T)["gmpp"]["P"]   # cached per pattern
        if scn.is_shaded(entry, base_G):
            shaded_uids.add(p["uid"])
    nested_rows = {r for r, row in enumerate(rows_irr) if any(scn.is_nested(e) for e in row)}
    focus = scn.focus_panel(system, rows_irr, base_G)
    condition = {"time_minutes": int(time_minutes), "temperature_c": float(T),
                 "base_irradiance": float(base_G), "module_irradiances": rows_irr,
                 "shadow_metadata": [{"uid": p["uid"], "display_id": p["display_id"],
                                      **p["shadow"]} for p in panels]}
    draft = scn.build_draft(system, condition, geometry, glabel, focus,
                            rows_irr[focus["row"]][focus["pos"]],
                            SPLIT_NAME if _in_val(name) else "not in the validation split")
    # The draft is rewritten on every render; Watch one run keeps whatever was SENT.
    st.session_state["scenario_draft"] = draft
    sel_shaded = sel["uid"] in shaded_uids
    vsub, clamp = _substring_voltages(name, sel_irr, T, det["gmpp"]["I"])
    states = [_diode_state(vk, clamp) for vk in vsub]

    # ================================================================ centre
    with mid:
        head = (f"System: {n_series}S × {n_parallel}P · {n_panels} panels" if n_panels > 1
                else "Panel 1")
        st.markdown(f"<div class='bh'>{_e(head)}</div>"
                    + (f"<div style='font-size:13px;color:{c['text_muted']}'>"
                       f"pick a panel to inspect it — click it, or use the controls below</div>"
                       if n_panels > 1 else ""), unsafe_allow_html=True)
        if n_panels > 1:
            ui.show_chart(scn.topology_figure(system, shaded_uids, sel["uid"], powers, c, lab),
                          key="gm_topo", on_select="rerun", selection_mode="points")
            default_id = ids[0]
            cur_idx = ids.index(sel_id)

            def _step_panel(delta):
                """on_click so the keyed selectbox sees the new value on this run."""
                i = ids.index(st.session_state.get("gm_sel", default_id))
                st.session_state["gm_sel"] = ids[min(max(i + delta, 0), len(ids) - 1)]

            nav = st.columns([1.15, 2.1, 1.15, 1.6], vertical_alignment="bottom")
            nav[0].button("‹ Prev", key="gm_panel_prev", use_container_width=True,
                          disabled=cur_idx == 0, on_click=_step_panel, args=(-1,),
                          help="Inspect the previous panel. Stops at the first; no wrap.")
            with nav[1]:
                st.selectbox("Select panel", ids, key="gm_sel",
                             help="Which panel is shown. View only: it does not change the "
                                  "shadow, the conditions, the hash or what was sent.")
            nav[2].button("Next ›", key="gm_panel_next", use_container_width=True,
                          disabled=cur_idx == len(ids) - 1, on_click=_step_panel, args=(1,),
                          help="Inspect the next panel. Stops at the last; no wrap.")
            nav[3].markdown(
                f"<div class='bmono' style='font-size:12.5px;color:{c['text_muted']};"
                f"padding-bottom:10px'>Panel {_e(sel_id)} of {n_panels}</div>",
                unsafe_allow_html=True)

            def _reset_panel(d=default_id):
                st.session_state["gm_sel"] = d

            st.button("Reset inspected panel", key="tool_clear", on_click=_reset_panel,
                      help="Show the first panel again. Nothing else changes.")
        face, info = st.columns([1, 1.1], vertical_alignment="top")
        face.markdown(scn.module_face_svg(sel_irr, base_G, c, lab, sel["shadow"]["shape"]),
                      unsafe_allow_html=True)
        with info:
            word = {"on": "bypassed", "partial": "partly bypassed", "off": "working"}
            badges = "".join(
                f"<span><span style='color:{c['text_muted']}'>{scn.section_name(k, lab)}</span>"
                f"<span style='color:{c['amber_text'] if s != 'off' else c['text']}'>"
                f"{word[s]}{' · bypass ' + s if lab else ''}</span></span>"
                for k, s in enumerate(states))
            st.markdown(f"<div class='gm-badges'>{badges}"
                        f"<span><span style='color:{c['text_muted']}'>{'V_oc' if lab else 'open-circuit'}</span>"
                        f"<span>{det['voc']:.1f} V</span></span></div>", unsafe_allow_html=True)
            st.markdown(f"<p style='margin-top:10px;font-size:14px;line-height:1.5'>"
                        f"{_e(scn.bypass_sentence(states, sel_shaded, det['n_peaks'], lab))}</p>",
                        unsafe_allow_html=True)
        if lab:
            st.markdown(f"<div class='bmono' style='font-size:11.5px;color:{c['text_muted']}'>"
                        f"{_e(sel_id)} · uid {_e(sel['uid'])} · geometry {_e(geometry_label(sel_irr))} · "
                        f"pattern {_e(str([round(float(x), 0) if not isinstance(x, list) else [round(float(y), 0) for y in x] for x in sel_irr]))}"
                        f"</div>", unsafe_allow_html=True)
            ui.engine_badge("validated")

    # ================================================================ right rail
    with right:
        with st.container(border=True):
            st.markdown("<div class='bh'>4 · What it makes</div>", unsafe_allow_html=True)
            scopes = ["This panel", "The row", "Whole system"]
            if n_panels == 1:
                scope = "This panel"
                st.segmented_control("scope", ["This panel"], default="This panel",
                                     key="gm_scope_one", label_visibility="collapsed")
                st.caption("The row and Whole system — add panels to unlock.")
            else:
                st.session_state.setdefault("gm_scope", "This panel")
                scope = st.segmented_control("scope", scopes, key="gm_scope",
                                             label_visibility="collapsed") or "This panel"
            blocked = ((scope == "The row" and sel["row"] in nested_rows)
                       or (scope == "Whole system" and nested_rows))
            if blocked:
                ui.unavailable(
                    "The row engine takes one light level per section",
                    "A Leaf shadow shades part of one section. The validated engine composes "
                    "a row from one light level per section, so this view cannot be drawn "
                    "while a Leaf shadow is on a panel in it. Change that panel's shadow to "
                    "Pole, Tree, Dirt or Cloud, or look at This panel.",
                    "- `gmppt.device.string_iv` builds each module pattern with "
                    "`np.asarray(..., dtype=float)`, which rejects nested (sub-substring) "
                    "entries; `module_iv` alone accepts them. Not changed here: the file is "
                    "protected.", kind="limit")
                cur = ref = None
            elif scope == "The row":
                row_key = tuple(_key(e) for e in rows_irr[sel["row"]])
                cur = _sim_string(name, row_key, T)
                ref = _sim_string(name, tuple(_key(uniform) for _ in range(n_series)), T)
                making, noshadow, peaks = cur["gmpp"]["P"], ref["gmpp"]["P"], cur["n_peaks"]
                note_now, note_ref = f"row {sel['row'] + 1} at its real peak", "same row, no shadow"
            elif scope == "Whole system":
                cur = _sim_array(name, _key_rows(rows_irr), T, True)
                ref = _sim_array(name, tuple(tuple(_key(uniform) for _ in range(n_series))
                                             for _ in range(n_parallel)), T, True)
                shared, shared_ref = cur["gmpp"]["P"], ref["gmpp"]["P"]
                optimised = float(sum(powers.values()))
                optimised_ref = n_panels * uns["gmpp"]["P"]
                if optimisers:
                    making, noshadow = optimised, optimised_ref
                    note_now, note_ref = "every panel at its own real peak", "same system, no shadow"
                else:
                    making, noshadow = shared, shared_ref
                    note_now, note_ref = "one shared tracker at the array's real peak", "same system, no shadow"
                peaks = cur["n_peaks"]
            else:
                cur, ref = det, uns
                making, noshadow, peaks = det["gmpp"]["P"], uns["gmpp"]["P"], det["n_peaks"]
                note_now, note_ref = "this panel at its real peak", "same panel, no shadow"

            if cur is not None:
                fig = go.Figure()
                if ref is not None and abs(ref["gmpp"]["P"] - cur["gmpp"]["P"]) > 1e-6:
                    fig.add_trace(go.Scatter(x=ref["V"], y=ref["P"], name="no shadow",
                                             line=dict(color=ui.REF_COLORS["unshaded"],
                                                       width=2, dash="dot")))
                fig.add_trace(go.Scatter(x=cur["V"], y=cur["P"], name="now",
                                         line=dict(color=c["teal"], width=3)))
                ui.mark_gmpp(fig, cur["gmpp"]["V"], cur["gmpp"]["P"],
                             label="GMPP" if lab else "the real peak",
                             textposition="top left"
                             if cur["gmpp"]["V"] > 0.7 * (cur["voc"] or 1.0) else "top right")
                top = float(max(cur["P"]))
                if ref is not None:
                    top = max(top, float(max(ref["P"])))
                fig.update_yaxes(range=[0, 1.18 * top])
                ui.mark_local_peaks(fig, [(v, i, pw) for (v, i, pw) in cur["peaks"]
                                          if abs(pw - cur["gmpp"]["P"]) > 1e-6])
                ui.style_fig(fig, height=260, x_title="Voltage (V)", y_title="Power (W)")
                fig.update_layout(showlegend=False, margin=dict(l=48, r=10, t=10, b=40))
                ui.show_chart(fig, key="gm_scn_pv")
                # three siblings, equal widths, equal heights (the layout rule)
                ui.kpi_row([("Making now", f"{making:.0f} W", note_now, "hero"),
                            ("No shadow", f"{noshadow:.0f} W", note_ref),
                            ("Peaks", str(peaks), "on the curve shown")])
                if scope == "Whole system":
                    if optimisers:
                        ui.callout(f"With one shared tracker instead — {shared:.0f} W",
                                   "", "info")
                    else:
                        ui.callout(f"With an optimiser on every panel instead — {optimised:.0f} W",
                                   "", "info")
                    st.caption("An instantaneous power comparison for this scenario, not a "
                               "measured energy gain.")
                if lab:
                    ui.legend_note("Peaks and the GMPP come from gmppt.device.analyse on the "
                                   "curve shown. Scenario outputs, not benchmark results.")

        # ========================================================== 5 · hand over
        with st.container(border=True):
            st.markdown("<div class='bh'>5 · Hand it to the tracker</div>", unsafe_allow_html=True)
            st.markdown(f"<p style='font-size:14px;line-height:1.5;margin:6px 0'>"
                        f"{_e(scn.summary_sentence(system, condition))}</p>", unsafe_allow_html=True)
            if lab:
                st.markdown(
                    f"<div class='bmono' style='font-size:11.5px;color:{c['text_muted']};line-height:1.7'>"
                    f"{n_series}S × {n_parallel}P · optimisers {'on' if optimisers else 'off'} · "
                    f"blocking diodes on · validated engine · geometry {_e(glabel)}<br>"
                    f"hash {_e(draft['hash'])} · system {_e(draft['system_hash'])} · handed "
                    f"panel {_e(focus['display_id'])} (the most shaded)</div>", unsafe_allow_html=True)
            sent = st.session_state.get("scenario_sent")
            if not sent:
                status, tone = "● not sent yet", c["text_muted"]
            elif sent.get("hash") == draft["hash"]:
                status, tone = "● sent", c["teal"]
            else:
                status, tone = "● changed since sent", c["amber_text"]
            st.markdown(f"<div class='gm-status' style='color:{tone}'>{status}</div>",
                        unsafe_allow_html=True)
            with st.container(key="next-panelsend"):
                if st.button("Send this setup" if not sent else "Send again", key="send_trackers",
                             type="primary", use_container_width=True,
                             disabled=bool(sent) and sent.get("hash") == draft["hash"],
                             help="Hands this exact scenario to the tracker pages. The "
                                  "footer's Next takes you there."):
                    _send_scenario()
                    st.toast("Sent. The tracker pages now run this scenario.")
                    st.rerun()

    _dynamic_pointer(c)


def _dynamic_pointer(c):
    """Where the day went: the event timeline is a Dynamic test page now. It
    inherits the system sent from here and adds G(t), T(t) and Shade(t) in
    canonical minutes; nothing about the topology is rebuilt there."""
    with st.container(border=True):
        a, b = st.columns([3.2, 1.3], vertical_alignment="center")
        a.markdown(
            f"<span class='bh'>Let it change through the day</span>"
            f"<span style='font-size:13px;color:{c['text_muted']};margin-left:10px'>"
            f"the Dynamic test inherits this PV system unchanged and adds sunlight, "
            f"temperature and shading that move — build the timeline after sending</span>",
            unsafe_allow_html=True)
        with b:
            st.page_link(P["timeline"], label="Dynamic test · Timeline →")


def page_inside():
    # Sections, top to bottom (§15): orientation → operating point → panel
    # response → substring state → why the curve has steps → next action. One
    # idea per section, no bordered card around ordinary text (§20).
    ui.page_intro("PV analysis",
                  "Why this condition gives this curve: the shadow, the sections it "
                  "weakens, the bypass diodes it switches, and the peaks that leaves.",
                  "Scenario · PV analysis")
    draft = st.session_state.get("scenario_draft")
    if not draft:
        ui.callout("Build a system and put a shadow on it on Build system first — this "
                   "page explains that result.", "Nothing to show yet", "info")
        st.page_link(P["panels"], label="Go to Build system →")
        return
    c = ui.T()
    name, T = draft["module"], float(draft["temp"])
    irr = [list(e) if isinstance(e, (list, tuple)) else float(e) for e in draft["irr"]]
    irr_key = _key(irr)
    det = _sim(name, irr_key, T)
    voc = det["voc"] or 1.0
    focus = (draft.get("focus_panel") or {}).get("display_id", "the handed panel")
    st.caption(f"The scenario you are editing on Build system: {draft.get('label', name)} · "
               f"analysing {focus}, the panel handed to the trackers. This page reads the "
               f"draft; it edits nothing.")

    # ---------------------------------------------------------- shadow → sections → curve
    # Cause and effect in one row, all from the same engine call: the shadow on
    # the panel face, each section's bypass state at the true peak, and the
    # curve with and without the shadow. (§16–17)
    ui.section_head("What the shadow did",
                    "shading → section irradiance → bypass state → P–V landscape → peaks")
    base_G = float((draft.get("static_condition") or {}).get(
        "base_irradiance", max((max(e) if isinstance(e, list) else e) for e in irr)))
    uns0 = _sim(name, _key([base_G] * _gcfg.N_SUBSTRINGS), T)
    vsub0, clamp0 = _substring_voltages(name, irr, T, det["gmpp"]["I"])
    states0 = [_diode_state(vk, clamp0) for vk in vsub0]
    shaded0 = scn.is_shaded(irr, base_G)
    shape0 = next((m.get("shape") for m in (draft.get("static_condition") or {}).get(
        "shadow_metadata", []) if m.get("uid") == (draft.get("focus_panel") or {}).get("uid")),
        "None")
    f1, f2, f3 = st.columns([0.85, 1.0, 1.5], gap="medium")
    with f1:
        st.markdown(scn.module_face_svg(irr, base_G, c, False, shape0 or "None", width=170),
                    unsafe_allow_html=True)
    with f2:
        word = {"on": "bypassed", "partial": "partly bypassed", "off": "working"}
        cells = "".join(
            f"<div class='gm-sub'><b>{scn.section_name(k, False)}</b>"
            f"<span>{(sum(e) / len(e)) if isinstance(e, list) else e:.0f} W/m² of light</span>"
            f"<span style='color:{c['amber_text'] if s != 'off' else c['text']};font-weight:600'>"
            f"{word[s]} at the true peak</span></div>"
            for k, (e, s) in enumerate(zip(irr, states0)))
        st.markdown(f"<div class='gm-subrow' style='grid-template-columns:1fr'>{cells}</div>",
                    unsafe_allow_html=True)
        st.markdown(f"<p style='margin-top:8px;font-size:13.5px;line-height:1.5'>"
                    f"{_e(scn.bypass_sentence(states0, shaded0, det['n_peaks'], False))}</p>",
                    unsafe_allow_html=True)
    with f3:
        fig0 = go.Figure()
        if abs(uns0["gmpp"]["P"] - det["gmpp"]["P"]) > 1e-6:
            fig0.add_trace(go.Scatter(x=uns0["V"], y=uns0["P"], name="no shadow",
                                      line=dict(color=ui.REF_COLORS["unshaded"], width=2,
                                                dash="dot")))
        fig0.add_trace(go.Scatter(x=det["V"], y=det["P"], name="with the shadow",
                                  line=dict(color=c["teal"], width=3)))
        ui.mark_gmpp(fig0, det["gmpp"]["V"], det["gmpp"]["P"],
                     textposition="top left" if det["gmpp"]["V"] > 0.7 * voc else "top right")
        ui.mark_local_peaks(fig0, [(v, i, pw) for (v, i, pw) in det["peaks"]
                                   if abs(pw - det["gmpp"]["P"]) > 1e-6])
        fig0.update_yaxes(range=[0, 1.18 * max(float(max(det["P"])), float(max(uns0["P"])))])
        ui.style_fig(fig0, height=260, x_title="voltage  V", y_title="power  W")
        fig0.update_layout(legend=dict(orientation="h", y=1.12, x=0),
                           margin=dict(l=48, r=10, t=10, b=40))
        ui.show_chart(fig0, key="inside_overlay")
    ui.kpi_row([("True peak", f"{det['gmpp']['P']:.0f} W", "with the shadow"),
                ("No shadow", f"{uns0['gmpp']['P']:.0f} W", "same panel, same conditions"),
                ("Lost to shade", f"{max(0.0, uns0['gmpp']['P'] - det['gmpp']['P']):.0f} W",
                 "the hardware's problem, not the tracker's"),
                ("Peaks", str(det["n_peaks"]), "lower peaks are traps for a hill-climber")])
    ui.callout("A bypassed section drops out of the voltage sum, which puts a step in the "
               "curve; a peak can sit on either side of every step. The mapping from a "
               "section to a peak is not one-to-one — the sweep at the foot of this page "
               "shows where each diode actually switches.", "How to read it", "info")
    st.space(size="small")

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
            "- The table above, the sweep below and the bypass table on Scenario "
            "all use this one rule.")

    # ---------------------------------------------------------- next action
    st.space(size="small")
    ui.section_head("Next", "send this exact scenario to the tracking methods")
    a, b = st.columns([1.3, 3], vertical_alignment="center")
    if a.button("Run the static test →", key="inside_send", type="primary",
                use_container_width=True,
                help="Sends the scenario you are looking at to Static test · One run."):
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
                   f"Deepen the shadow on Scenario to make a diode switch.")
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
    ui.page_intro("Simulator",
                  "Type a datasheet in yourself and watch the curve — a separate, "
                  "simplified engine.", "Sandbox · Simulator")

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
                "source": day_import.get("source", "Dynamic test · Timeline"),
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
                st.page_link(P["panels"], label="Scenario (validated) →")

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
                    tabs = st.tabs(["I–V / P–V", "Substrings", "Peaks", "Cell map"])
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

                    # The parametric sweep is its own Sandbox page (Sweep): it has
                    # its own module picker and does not read this datasheet.
                    st.page_link(P["sim_sweep"],
                                 label="Sweep the presets across temperature × irradiance →")

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
                                      "conditions into the Dataset generator"):
                        _bench_to_dataset(r_ds, r_nsub, r_mstr, r_pstr, r_baseG, r_T)
                        st.switch_page(P["sim_dataset"])
                    st.page_link(P["sim_saved"], label="Saved scenarios")
                    # The trackers run the validated engine on a CEC module; this bench
                    # runs the interactive engine on a datasheet. Say so rather than
                    # offering a "send" that cannot carry anything across.
                    st.markdown(
                        f"<div style='margin-top:10px;padding-top:10px;border-top:1px solid "
                        f"{c['border']};font-size:12px;line-height:1.5;color:{c['text_muted']}'>"
                        f"Scenarios for the trackers come from <b>Scenario · Build system</b>, "
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
                "not modelled. Both are handled by the validated engine on Scenario."
                "</p></div>", unsafe_allow_html=True)


def page_sim_saved():
    ui.page_intro("Saved scenarios",
                  "Load a saved scenario back onto the Simulator, or compare the ones "
                  "you have kept.", "Sandbox · Saved scenarios")
    saved = st.session_state.get("frozen") or []
    if not saved:
        ui.callout("Nothing saved yet. On the Simulator, run a simulation and press "
                   "“Freeze this curve” or “Save to Saved scenarios”.",
                   "No saved scenarios", "info")
        st.page_link(P["sim_setup"], label="Go to the Simulator →")
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
        if bc[0].button("Load onto the Simulator", key="saved_load", type="primary",
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
            "another on the Simulator and this appears.",
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
    ui.page_intro("Dataset generator",
                  "Generate thousands of scenarios with a fixed seed, look at what you "
                  "generated, and download them.", "Sandbox · Dataset generator")
    _dsheet = sim.current_ds()
    st.caption(f"Generating from: {st.session_state.get('ds_name', '—')} · "
               f"{_dsheet['Ns']} cells · {st.session_state.get('topo_nsub', '—')} substrings. "
               f"Use “Use this module for a dataset” on the Simulator to change it.")
    sim.render_dataset_section()
    ui.callout("These scenarios are produced by the interactive simulator, not by the "
               "validated engine behind the benchmark figures. They never reach Results.",
               "Which engine made this dataset", "caveat")
    st.divider()
    _dataset_view()


def page_sim_sweep():
    ui.page_intro("Sweep",
                  "The built-in presets across a temperature × irradiance grid, on the "
                  "simplified engine.", "Sandbox · Sweep")
    st.caption("This sweep has its own module picker; it does not read the datasheet "
               "typed on the Simulator. Its curves feed the morph on Saved scenarios "
               "when fewer than two scenarios are saved.")
    sim.render_sweep()
    ui.engine_badge("simplified")


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
    ui.page_intro("One run",
                  "One frozen condition. Watch each tracking method search the same "
                  "curve, step by step: where it starts, what it measures, where it stops.",
                  "Static test · One run")
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
        ui.data_chip("Exploratory", "Your scenario, one frozen condition, validated engine. "
                                    "Not a benchmark result.")
        if st.button("Discard sent scenario", key="run_use_example",
                     help="Drops the scenario Build system sent and returns this page to "
                          "the built-in example. Nothing on Build system is changed."):
            st.session_state.pop("scenario_sent", None)
            st.toast("Sent scenario discarded — showing the example again.")
            st.rerun()
    else:
        _demo = _run_demo()
        if not assert_val_modules([_demo["module"]], "One run"):
            return
        d = _run_scenario(_demo["module"], _demo["temp"], _demo["irr"])
        _note = _demo_module()[3]
        ui.callout(
            f"This is the built-in example: {_demo['module']} under a three-region "
            f"shadow. Build your own on Scenario · Build system and send it here."
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
                st.page_link(P["static_compare"],
                             label="Every method on this condition, side by side →")

        with st.container(key="seereloc"):
            st.page_link(P["compare"],
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


# =========================================================================== #
# Static test · Compare methods — every method on the SAME sent condition.
#
# The scores are the harness's own (Trajectory.metrics, through _score_traj):
# the code p7 summarises into the validated exports. This page lays them side
# by side for ONE scenario and says so. Nothing here is a benchmark number; the
# split-wide comparison is Results · Static performance.
# =========================================================================== #
PROPOSED = "Hybrid (bounded)"          # the proposed GMPPT method as shipped (D4)
_STATIC_ORDER = ["P&O", "InC", "PSO", "Model only", PROPOSED, "Hybrid (free)",
                 "Perfect tracker"]
_ROLE = {"P&O": "baseline", "InC": "baseline", "PSO": "baseline",
         "Model only": "ablation", PROPOSED: "proposed", "Hybrid (free)": "variant",
         "Perfect tracker": "control"}


def _static_scenario(what):
    """(run, record or None, is_example). The one rule for the Static test pages:
    they run the SENT scenario; the built-in example stands in only while
    nothing has been sent, and says so."""
    sc = st.session_state.get("scenario_sent")
    if sc:
        return _run_scenario(sc["module"], sc["temp"], _key(sc["irr"])), sc, False
    demo = _run_demo()
    if not assert_val_modules([demo["module"]], what):
        return None, None, True
    return _run_scenario(demo["module"], demo["temp"], demo["irr"]), None, True


def _static_scenario_line(sc, is_example):
    """One line saying whose scenario the page is running."""
    if is_example:
        demo = _run_demo()
        _note = _demo_module()[3]
        ui.callout(f"Nothing has been sent from Scenario yet, so this is the built-in "
                   f"example: {demo['module']} under a three-region shadow."
                   + (f" {_note}" if _note else ""),
                   "Showing the example scenario", "info")
        st.page_link(P["panels"], label="Build and send your own →")
        return
    ui.data_chip("Exploratory", "Your scenario, one frozen condition, validated engine. "
                                "Not a benchmark result.")
    st.caption(f"{sc.get('label', '')} · {sc.get('module', '')} · {sc.get('pattern', '')} · "
               f"{sc.get('geometry_label', '')} · {float(sc.get('temp', 0)):.0f} °C · "
               f"hash {sc.get('hash', '')}")


def page_static_compare():
    import json
    c = ui.T()
    ui.page_intro("Compare methods",
                  "P&O, InC, PSO and the proposed method on the same frozen condition.",
                  "Static test · Compare methods")
    d, sc, is_example = _static_scenario("Compare methods")
    if d is None:
        return
    _static_scenario_line(sc, is_example)
    if not is_example:
        _resend_notice()

    methods = [m for m in _STATIC_ORDER if m in d["methods"]]
    pso_reads, _ = _pso_readings(_load_json("phase2/pso_comparison_val.json"))

    def reads(m):
        return pso_reads if m == "PSO" else _READINGS_FIXED.get(m.split(" (")[0])

    rows = []
    for m in methods:
        r = d["methods"][m]
        rows.append({"method": m, "role": _ROLE.get(m, ""), "reached": bool(r["reached"]),
                     "steady_eff_pct": float(r["steady_eff_pct"]),
                     "steps": (None if not r["reached"] else r["steps"]),
                     "readings": reads(m), "lost_w": float(r["lost"])})

    default = [m for m in ("P&O", "InC", "PSO", PROPOSED) if m in methods]
    sel = st.segmented_control("Show on the landscape", methods, selection_mode="multi",
                               default=None if "sc_show" in st.session_state else default,
                               key="sc_show") or default

    left, right = st.columns([1.45, 1], gap="large")
    with left:
        with st.container(border=True):
            st.markdown(_bh_run("The same landscape, every method") +
                        f"<span style='font-size:13px;color:{c['text_muted']};"
                        f"margin-left:10px'>where each one started, its path, and where "
                        f"it stopped</span>", unsafe_allow_html=True)
            V, Pw = np.asarray(d["V"], float), np.asarray(d["P"], float)
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=V, y=Pw, name="P–V",
                                     line=dict(color=c["teal"], width=2.5)))
            fig.add_trace(go.Scatter(x=[d["v_gmpp"]], y=[d["p_gmpp"]], mode="markers",
                                     name="true peak",
                                     marker=dict(symbol="star", size=15,
                                                 color=ui.PEAK_COLORS["gmpp"])))
            for m in sel:
                r = d["methods"].get(m)
                if not r:
                    continue
                vh, ph = np.asarray(r["v_hist"], float), np.asarray(r["p_hist"], float)
                col = ui.method_style(m)["color"]
                sym = _A1_SYMBOLS.get(m.split(" (")[0], "circle")
                fig.add_trace(go.Scatter(x=vh[::4], y=ph[::4], mode="lines",
                                         line=dict(color=col, width=1.2, dash="dot"),
                                         opacity=0.55, showlegend=False, hoverinfo="skip"))
                fig.add_trace(go.Scatter(x=[vh[0]], y=[ph[0]], mode="markers",
                                         marker=dict(color=col, size=8, symbol="circle-open",
                                                     line=dict(width=2)),
                                         showlegend=False, hoverinfo="skip"))
                fig.add_trace(go.Scatter(x=[vh[-1]], y=[ph[-1]], mode="markers", name=m,
                                         marker=dict(color=col, size=12, symbol=sym,
                                                     line=dict(color="#fff", width=1))))
                lab = "found it" if r["reached"] else f"stops · −{r['lost']:.0f} W"
                fig.add_annotation(x=vh[-1], y=ph[-1], text=lab, showarrow=True,
                                   arrowhead=0, ax=0, ay=-22, font=dict(size=10, color=col))
            fig.update_yaxes(range=[0, 1.18 * float(max(Pw))])
            ui.style_fig(fig, height=380, x_title="terminal voltage  V", y_title="power  W")
            fig.update_layout(legend=dict(orientation="h", y=1.06, x=0))
            ui.show_chart(fig, key="sc_landscape")
            ui.legend_note("Open circle: where the method started. Filled marker: where it "
                           "ended. Dotted: its path, thinned. Every method was given this "
                           "same curve.")
    with right:
        with st.container(border=True):
            st.markdown(_bh_run("Power held, as a share of the true peak", 15),
                        unsafe_allow_html=True)
            ys = list(reversed(methods))
            figb = go.Figure(go.Bar(
                y=ys, x=[d["methods"][m]["steady_eff_pct"] for m in ys], orientation="h",
                marker=dict(color=[ui.method_style(m)["color"] for m in ys]),
                text=[f"{d['methods'][m]['steady_eff_pct']:.1f}%" for m in ys],
                textposition="outside", showlegend=False, hoverinfo="skip"))
            figb.add_vline(x=100, line=dict(color=c["text_muted"], dash="dot", width=1))
            figb.update_xaxes(range=[0, 114], title_text="tracking efficiency (%)")
            ui.style_fig(figb, height=380)
            figb.update_layout(margin=dict(l=8, r=24, t=16, b=40))
            ui.show_chart(figb, key="sc_bars")
            ui.legend_note("Steady-state efficiency: the mean of the last quarter of the "
                           "window over the true peak.")

    df = pd.DataFrame([{
        "Method": r["method"] + (" · proposed" if r["method"] == PROPOSED else ""),
        "Role": r["role"],
        "GMPP reached": "yes" if r["reached"] else "no",
        "Tracking efficiency (%)": round(r["steady_eff_pct"], 2),
        "Convergence (steps)": "—" if r["steps"] is None else str(int(r["steps"])),
        "Readings / evaluations": _fmt(r["readings"], "{:.0f}"),
        "Power loss (W)": round(r["lost_w"], 1),
    } for r in rows])
    st.dataframe(df, hide_index=True, width="stretch")
    ui.legend_note("Definitions are the harness's, gmppt.tracking.Trajectory.metrics: "
                   "tracking efficiency is the steady-state mean over the true peak; "
                   "GMPP reached means that mean is within 1% of the peak; convergence is "
                   "the first step after which power stays within tolerance, so it is "
                   "conditional on arrival and a dash otherwise. Readings for P&O and InC "
                   "are not separately reported; PSO's count is the evaluation budget the "
                   "benchmark selected on the validation split.")

    got = [m for m in methods if d["methods"][m]["reached"] and m != "Perfect tracker"]
    missed = [m for m in methods if not d["methods"][m]["reached"]]
    prop = d["methods"].get(PROPOSED)
    text = (f"Under this condition ({d['n_peaks']} peak(s)), "
            + (f"{', '.join(got)} reached the true peak" if got
               else "no method reached the true peak")
            + (f"; {', '.join(missed)} stopped on a lower peak." if missed else "."))
    if prop:
        text += (f" The proposed method held {prop['steady_eff_pct']:.1f}% of the available "
                 f"power" + (f", at {SEED_PROBE_COST} readings against {pso_reads} PSO "
                             f"evaluations per cycle." if pso_reads else "."))
    ui.callout(text + " One scenario supports no general claim; the comparison over the "
               "whole validation set is on Results · Static performance.",
               "What this one scenario shows", "info")
    with st.container(key="seeall2"):
        st.page_link(P["compare"], label="The same comparison over the whole validation set →")

    e1, e2 = st.columns(2)
    e1.download_button("Download table (CSV)", df.to_csv(index=False),
                       "static_compare_methods.csv", "text/csv", use_container_width=True,
                       key="sc_csv")
    e2.download_button("Download figure data (JSON)",
                       json.dumps({"scenario": (sc or {"example": _run_demo()}),
                                   "rows": rows, "exploratory": True,
                                   "definitions": "gmppt.tracking.Trajectory.metrics"},
                                  indent=2, default=str),
                       "static_compare_methods.json", "application/json",
                       use_container_width=True, key="sc_json")

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
    ui.page_intro("Static performance",
                  f"The validated static result: every method on the same "
                  f"{_fmt(n_sub, '{:.0f}')} multi-peak validation curves.",
                  "Results · Static performance")
    ui.data_chip("Benchmark result", "Read from the phase-2 exports. No interactive run "
                                     "contributes to any figure on this page.")

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
            # always a string: a column mixing ints and "—" cannot be serialised
            # to Arrow and made Streamlit patch the frame on every render
            "Readings": _fmt(reads_for(key), "{:.0f}"),
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


def _relocation_section(c):
    """The p12 relocation export, as a section of Results · Dynamic performance."""
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
    ui.page_intro("Targets",
                  "The project's static, dynamic and convergence objectives beside what "
                  "was measured, and the caveats that belong to each.", "Results · Targets")
    ui.data_chip("Benchmark result", "Only validated exports populate this page. A target "
                                     "with no recorded value stays blank.")

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
    ui.page_intro("Benchmark set",
                  "What the validated results were measured on: the scenario population "
                  "and the split.", "Data & validation · Benchmark set")
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


# =========================================================================== #
# Results · Dynamic performance  — the validated EN 50530 exports (p10) and the
# relocation export (p12). Static figures only: this is evidence, not a player.
# =========================================================================== #
_DYN_ROWS = ["hybrid, no reseed", "seed only, no reseed", "PSO", "P&O", "InC"]


def _dynamic_export_block(seq: str, c: dict):
    """One sequence's validated result: KPIs, the method table, the reseed note.
    Returns the export (or None) so the caller can stamp provenance."""
    rel = f"phase2/dynamic_comparison_{seq}_val.json"
    dyj = _load_json(rel)
    if not dyj:
        missing_export(rel, f"The dynamic comparison for Seq {seq}")
        return None
    if not require_keys(rel, dyj, ("results", "split"), f"the Seq {seq} dynamic figures"):
        return None
    sh = (dyj.get("results") or {}).get("shaded") or {}
    un = (dyj.get("results") or {}).get("uniform") or {}

    def agg(block, m):
        return (block.get(m) or {}).get("aggregate_pct")

    def se_of(block, m):
        return (block.get(m) or {}).get("scenario_se_pct")

    hyb_key = "hybrid, no reseed"
    hyb, pso_v, po = agg(sh, hyb_key), agg(sh, "PSO"), agg(sh, "P&O")
    if hyb is None:
        missing_field(rel, hyb_key, "the headline efficiency")
    kp = [("Dynamic efficiency", f"{_fmt(hyb, '{:.3f}')}%",
           f"{method_label(hyb_key)} · ±{_fmt(se_of(sh, hyb_key), '{:.3f}')} · shaded · "
           f"EN 50530 Seq {dyj.get('sequence', seq)}", "hero")]
    if hyb is not None and pso_v is not None:
        kp.append(("vs PSO", f"{hyb - pso_v:+.2f} pt",
                   f"PSO {_fmt(pso_v, '{:.3f}')}% ±{_fmt(se_of(sh, 'PSO'), '{:.3f}')}"))
    if hyb is not None and po is not None:
        kp.append(("vs P&O", f"{hyb - po:+.1f} pt",
                   f"P&O {_fmt(po, '{:.3f}')}% ±{_fmt(se_of(sh, 'P&O'), '{:.3f}')}"))
    ui.kpi_row(kp)

    unknown = [k for k in list(sh) + list(un) if k not in _METHOD_LABELS]
    keys = [k for k in _DYN_ROWS if k in sh or k in un] + sorted(set(unknown))
    df = pd.DataFrame([{
        "Method": method_label(k) if k in _METHOD_LABELS else f"{UNKNOWN_VARIANT}: {k}",
        "Shaded — dynamic efficiency (%)": _fmt(agg(sh, k), "{:.3f}"),
        "± s.e.": _fmt(se_of(sh, k), "{:.3f}"),
        "Uniform control (%)": _fmt(agg(un, k), "{:.3f}"),
        "n": _fmt((sh.get(k) or {}).get("n_trajectories"), "{:.0f}"),
    } for k in keys])
    st.dataframe(df, hide_index=True, width="stretch")
    ui.legend_note(f"Split {dyj.get('split', '—')} · {_fmt(dyj.get('n_shaded'), '{:.0f}')} "
                   f"shaded and {_fmt(dyj.get('n_uniform'), '{:.0f}')} uniform scenarios · "
                   f"EN 50530 eq. (5) over scored blocks, aggregated by eq. (7). The "
                   f"uniform control has one peak, so it shows what the ramp alone does.")
    if unknown:
        ui.callout(f"`{rel}` contains {', '.join('`' + str(k) + '`' for k in unknown)}, "
                   f"which this dashboard's variant table does not know. They are listed "
                   f"as unknown rather than assigned to a method family.",
                   "Unrecognised export keys", "caveat")

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
    return dyj


def page_dynamic_perf():
    c = ui.T()
    ui.page_intro("Dynamic performance",
                  "The validated response to changing irradiance: the EN 50530 ramps, and "
                  "one clean relocation of the peak.", "Results · Dynamic performance")
    ui.data_chip("Benchmark result", "Read from the phase-2 exports. No interactive run "
                                     "contributes to any figure on this page.")
    seq = st.segmented_control("EN 50530 sequence", ["30-100", "10-50"],
                               default=None if "dp_seq" in st.session_state else "30-100",
                               key="dp_seq", format_func=lambda s: f"Seq {s}") or "30-100"
    st.caption("EN 50530 ramps irradiance on a control-step axis. It is a standard test "
               "profile, not a time-of-day sun path.")
    dyj = _dynamic_export_block(seq, c)
    ui.callout("The standard ramps irradiance but barely moves the peak location, so the "
               "margin over P&O here is largely static trapping carried into a changing "
               "scene. The relocation family below is where the peak actually moves.",
               "Read this beside the table", "caveat")
    if dyj:
        rel = f"phase2/dynamic_comparison_{seq}_val.json"
        ui.provenance({rel.split('/')[-1]: _export_meta(rel, dyj)})

    st.divider()
    ui.section_head("Shading relocation",
                    "one clean event: the tallest peak moves to another substring, and "
                    "each method has to find it again")
    _relocation_section(c)


# =========================================================================== #
# The EN 50530 ramp on the SAME panel the static test ran — the live per-step
# traces (real trackers, validated engine) and their playback (A7). Explanatory:
# the benchmark figures live on Results · Dynamic performance.
# =========================================================================== #
def _en50530_section(c):
    scen = st.segmented_control("Irradiance profile",
                                ["EN 50530 · Seq 30-100", "EN 50530 · Seq 10-50",
                                 "Unshaded control"],
                                default=None if "mv_scen" in st.session_state
                                else "EN 50530 · Seq 30-100", key="mv_scen") \
        or "EN 50530 · Seq 30-100"
    seq = "10-50" if "10-50" in scen else "30-100"
    shaded = "Unshaded" not in scen
    sc = st.session_state.get("scenario_sent")
    if sc:
        module, temp, irr = sc["module"], float(sc["temp"]), tuple(_key(sc["irr"]))
        if any(isinstance(e, tuple) for e in irr):
            ui.callout("The handed panel carries a part-of-a-section (Leaf) shadow. The "
                       "ramp harness scales whole sections, so it cannot take this "
                       "pattern; the built-in example is stepped instead.",
                       "Pattern not rampable", "limit")
            demo = _mv_demo()
            module, temp, irr = demo["module"], demo["temp"], demo["shaded"]
        else:
            st.caption(f"Ramping the panel Build system handed over: {module} · "
                       f"{sc.get('pattern', '')} · {temp:.0f} °C.")
    else:
        demo = _mv_demo()
        module, temp, irr = demo["module"], demo["temp"], demo["shaded"]
        if not assert_val_modules([module], "The ramp"):
            return
        st.caption(f"Nothing sent from Scenario yet, so the built-in example module "
                   f"{module} is stepped through the ramp.")
    try:
        day = _dynamic_day(seq, shaded, module, temp, irr)
    except Exception as e:
        ui.unavailable("Trace unavailable",
                       "The per-step traces for this profile could not be computed, so "
                       "nothing is drawn below.",
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
                               default=None if "mv_show" in st.session_state else default,
                               key="mv_show") or default
    mode = st.segmented_control("mode", ["Power", "Efficiency %"],
                                default=None if "mv_mode" in st.session_state else "Power",
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
                          line=dict(color=ui.REF_COLORS["unshaded"], width=2, dash="dot")))
            fig.add_trace(go.Scatter(x=xs, y=trim(avail), name="available at true peak",
                          line=dict(color=ui.REF_COLORS["available"], width=2.5)))
            for m in sel:
                fig.add_trace(go.Scatter(x=xs, y=trim(np.array(day["traces"][m])), name=m,
                              line=dict(width=2, **ui.method_style(m))))
            ui.style_fig(fig, height=320, x_title="EN 50530 profile (control steps)",
                         y_title="power (W)")
        else:
            eff = lambda a: np.where(avail > 1e-9, 100 * a / avail, 100.0)
            fig.add_trace(go.Scatter(x=xs, y=trim(np.full_like(avail, 100.0)),
                          name="available", line=dict(color=ui.REF_COLORS["available"], width=2)))
            for m in sel:
                fig.add_trace(go.Scatter(x=xs, y=trim(eff(np.array(day["traces"][m]))), name=m,
                              line=dict(width=2, **ui.method_style(m))))
            ui.style_fig(fig, height=320, x_title="EN 50530 profile (control steps)",
                         y_title="tracking efficiency (%)")
            fig.update_yaxes(range=[60, 101])
        fig.update_layout(legend=dict(orientation="h", y=1.08, x=0))
        ui.show_chart(fig, key="mv_power")

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
        ui.show_chart(fig2, key="mv_loss")

    ui.callout("The x-axis is the EN 50530 ramp profile (control steps), not a clock. The "
               "standard ramps irradiance but barely moves the peak location, so the margin "
               "over P&O is largely static trapping carried into a changing scene.",
               "Read this beside the traces", "caveat")
    st.divider()
    _a7_profile_playback(day, sel, seq, shaded, c)


# =========================================================================== #
# A7 — EN 50530 profile playback  (Update 3 §5.3, user §12)
#
# Explanatory only. It replays the per-step traces `_dynamic_day` computed; the
# benchmark KPIs on Results · Dynamic performance come from the phase-2 export
# and are neither read nor written here. Building or playing this animation
# cannot change a single benchmark figure — T32 checks exactly that.
# =========================================================================== #
def _a7_profile_playback(day, sel, seq, shaded, c):
    import numpy as np
    ui.section_head("Play the profile",
                    "the same traces above, one control step at a time")
    ui.anim_badge("live", f"EN 50530 Seq {seq} · this panel · validated engine")
    ui.callout("This plays the per-step traces for one panel so the shape of the "
               "response is visible. The efficiency figures on Results · Dynamic "
               "performance are the benchmark result over the whole validation split "
               "and are not affected by anything here.",
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
                         line=dict(color=ui.REF_COLORS["unshaded"], width=2, dash="dot")),
              go.Scatter(x=x, y=[float(v) for v in avail[:n]], mode="lines",
                         name="available at true peak",
                         line=dict(color=ui.REF_COLORS["available"], width=2.5))]
    series = {m: {"color": ui.method_style(m)["color"],
                  "symbol": _A1_SYMBOLS.get(m.split(" (")[0], "circle")}
              for m in methods}
    held = {m: 100.0 * float(np.sum(tr[m][:n])) / max(1e-9, float(np.sum(avail[:n])))
            for m in methods}
    caption = ("; ".join(f"{m} holds {held[m]:.2f}% of the available power over this "
                         f"profile" for m in methods)
               + f". {len(key) - 2} ramp corner(s) are marked. These are one panel's "
                 f"trace, not the split-wide benchmark figure.")

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
                                "detail": f"EN 50530 Seq {seq}, one panel",
                                "shaded": bool(shaded), "stride": stride},
                               key="a7", name="profile_playback")
    ui.anim_budget_note(measured, stride, build_s)


# =========================================================================== #
# Dynamic test · Timeline
#
# The PV SYSTEM is inherited from the SENT scenario and never rebuilt here. The
# page adds G(t), T(t) and Shade(t) in canonical minutes, previews the system
# at the playhead through the one state function (gmppt_timeline.state_at),
# and writes `dynamic_scenario` — the record Tracker response and Energy run.
# =========================================================================== #
def _tl_inherit():
    """(sent, system, system_hash), or (None, None, None) after saying why."""
    sent = st.session_state.get("scenario_sent")
    draft = st.session_state.get("scenario_draft")
    if not sent:
        ui.callout("The dynamic test runs on the PV system you send from Scenario · "
                   "Build system. Nothing has been sent yet.", "No system sent", "info")
        if draft and draft.get("system"):
            if st.button("Send the scenario you are editing", key="tl_send_draft",
                         type="primary"):
                _send_scenario()
                st.rerun()
        st.page_link(P["panels"], label="Build the system →")
        return None, None, None
    if not sent.get("system") or not sent.get("system_hash"):
        ui.callout("The sent scenario predates the PV-system record, so the timeline "
                   "cannot inherit a topology from it. Send it again from Build system.",
                   "Older scenario record", "limit")
        st.page_link(P["panels"], label="Go to Build system →")
        return None, None, None
    return sent, sent["system"], sent["system_hash"]


def _tl_playhead_minutes(key="tl_time", default=900) -> int:
    v = st.session_state.get(key)
    try:
        return int(scn.time_to_minutes(v)) if v is not None else int(default)
    except Exception:
        return int(default)


def _tl_add(kind, target_uid):
    """on_click: a new event starting at the playhead."""
    st.session_state.setdefault("tl_events", [])
    start, end = tl.window_from_minutes(_tl_playhead_minutes())
    st.session_state["tl_events"].append(tl.new_event(kind, target_uid, start, end))
    st.session_state.pop("a5_built", None)
    st.session_state.pop("a6_built", None)


def _tl_remove(uid):
    ev = st.session_state.get("tl_events") or []
    st.session_state["tl_events"] = [e for e in ev if e.get("uid") != uid]
    for k in list(st.session_state.keys()):
        if str(k).startswith("tlw_") and str(k).endswith(f"_{uid}"):
            st.session_state.pop(k, None)


def _tl_clear():
    for e in st.session_state.get("tl_events") or []:
        _tl_remove(e.get("uid"))
    st.session_state["tl_events"] = []


def _tl_event_editor(events, by_uid, n_panels, c):
    """The per-event controls. Widgets are keyed by the event's uid (prefix
    tlw_), so each event keeps its own settings; the event dict is rebuilt from
    the widgets on every run. Canonical minutes in, canonical minutes out."""
    import datetime as _dt
    t_lo, t_hi = scn.minutes_to_time(tl.DAY_START), scn.minutes_to_time(tl.DAY_END)
    for ev in list(events):
        uid = ev["uid"]
        with st.container(border=True):
            hd = st.columns([3, 0.6], vertical_alignment="center")
            hd[0].markdown(f"**{_e(tl.event_label(ev, by_uid))}**"
                           + (f"  <span style='font-size:11.5px;color:{c['text_muted']}'>"
                              f"converted from “{_e(ev['migrated_from'])}”</span>"
                              if ev.get("migrated_from") else ""), unsafe_allow_html=True)
            hd[1].button("Remove", key=f"tl_rm_{uid}", on_click=_tl_remove, args=(uid,),
                         use_container_width=True)
            st.session_state.setdefault(f"tlw_win_{uid}",
                                        (scn.minutes_to_time(ev["start"]),
                                         scn.minutes_to_time(ev["end"])))
            w = st.slider("Window", min_value=t_lo, max_value=t_hi,
                          step=_dt.timedelta(minutes=15), key=f"tlw_win_{uid}",
                          help="When the shadow is on the panel. Minutes after midnight, "
                               "the same clock as Build system.")
            s, e = int(scn.time_to_minutes(w[0])), int(scn.time_to_minutes(w[1]))
            if e <= s:
                e = min(tl.DAY_END, s + 15)
            ev["start"], ev["end"] = s, e
            a, b = st.columns(2)
            st.session_state.setdefault(f"tlw_light_{uid}", int(round(ev.get("light_pct", 30))))
            ev["light_pct"] = float(a.slider("Light left under it", 0, 100, step=5,
                                             format="%d%%", key=f"tlw_light_{uid}",
                                             help="Of the sunlight at that moment. Lower is "
                                                  "darker."))
            opts = tl.motions_for(ev["kind"])
            if st.session_state.get(f"tlw_mot_{uid}") not in opts:
                st.session_state[f"tlw_mot_{uid}"] = (ev.get("motion") if ev.get("motion") in opts
                                                      else opts[0])
            ev["motion"] = b.selectbox("Motion", opts, key=f"tlw_mot_{uid}",
                                       help="Fixed: the same shadow throughout. Drifts: the "
                                            "shadow moves from one position to the other "
                                            "over the window. Deepens: it darkens from "
                                            "nothing to the set darkness.")
            whole = ev["kind"] in tl.WHOLE_PANEL_SHAPES
            p1, p2 = st.columns(2)
            st.session_state.setdefault(f"tlw_pos0_{uid}", int(ev.get("pos_from", 50)))
            st.session_state.setdefault(f"tlw_pos1_{uid}", int(ev.get("pos_to", 50)))
            ev["pos_from"] = int(p1.slider("Position" + (" at the start" if ev["motion"].startswith("drifts") else ""),
                                           0, 100, step=5, format="%d%%", key=f"tlw_pos0_{uid}",
                                           disabled=whole,
                                           help="Left to right across the panel: which "
                                                "section the shadow lands on. A cloud or "
                                                "dirt covers the whole panel."))
            ev["pos_to"] = int(p2.slider("Position at the end", 0, 100, step=5, format="%d%%",
                                         key=f"tlw_pos1_{uid}",
                                         disabled=whole or not ev["motion"].startswith("drifts"),
                                         help="Where the shadow has drifted to when the "
                                              "event ends."))


def _tl_preview(system, events, t_min, peak, t_dawn, t_noon, tracked, c, key="tl"):
    """The system at one instant, drawn from ONE state — the same function the
    run reads. Returns the state."""
    stt = tl.state_at(system, events, t_min, peak, t_dawn, t_noon, _gcfg.N_SUBSTRINGS)
    entry = tl.entry_for(stt, system, tracked["uid"])
    n_sub = _gcfg.N_SUBSTRINGS
    det = _sim(system["module"], _key(entry), float(stt["temp_c"]))
    uns = _sim(system["module"], _key([float(stt["sun_G"])] * n_sub), float(stt["temp_c"]))
    by_uid = {p["uid"]: p for p in system["panels"]}
    shapes_here = [sh["shape"] for sh in stt["shadows"].get(tracked["uid"], [])]
    active_names = [tl.event_label(ev, by_uid) for ev in events if ev["uid"] in stt["active"]]
    ui.kpi_row([
        ("Sunlight", f"{stt['sun_G']:.0f} W/m²", "clear-sky arc × the peak you set"),
        ("Cell temperature", f"{stt['temp_c']:.0f} °C", "rises with the sun"),
        ("Active shadows", str(len(stt["active"])),
         ", ".join(active_names)[:60] if active_names else "none at this moment"),
        ("Peaks on the tracked panel", str(det["n_peaks"]),
         f"true peak {det['gmpp']['P']:.0f} W of {uns['gmpp']['P']:.0f} W unshaded"),
    ])
    a, b, d = st.columns([0.9, 1.15, 1.35], gap="medium")
    with a:
        st.markdown(f"<div class='bh'>{_e(tracked['display_id'])} · the tracked panel</div>",
                    unsafe_allow_html=True)
        st.markdown(scn.module_face_svg(entry, stt["sun_G"], c, False,
                                        " + ".join(shapes_here).lower() if shapes_here else "None",
                                        width=170), unsafe_allow_html=True)
    with b:
        if len(system["panels"]) > 1:
            st.markdown("<div class='bh'>The system now</div>", unsafe_allow_html=True)
            ui.show_chart(scn.topology_figure(system, stt["shaded_uids"], tracked["uid"], {},
                                              c, False), key=f"{key}_topo")
            st.caption("Shaded panels are tinted; the tracked panel is outlined.")
        else:
            st.markdown("<div class='bh'>The system now</div>", unsafe_allow_html=True)
            st.caption("One panel. Add panels on Build system and the wiring appears here.")
    with d:
        st.markdown("<div class='bh'>The curve now</div>", unsafe_allow_html=True)
        fig = go.Figure()
        if abs(uns["gmpp"]["P"] - det["gmpp"]["P"]) > 1e-6:
            fig.add_trace(go.Scatter(x=uns["V"], y=uns["P"], name="no shadow",
                                     line=dict(color=ui.REF_COLORS["unshaded"], width=2,
                                               dash="dot")))
        fig.add_trace(go.Scatter(x=det["V"], y=det["P"], name="now",
                                 line=dict(color=c["teal"], width=3)))
        ui.mark_gmpp(fig, det["gmpp"]["V"], det["gmpp"]["P"],
                     textposition="top left" if det["gmpp"]["V"] > 0.7 * (det["voc"] or 1.0)
                     else "top right")
        ui.mark_local_peaks(fig, [(v, i, pw) for (v, i, pw) in det["peaks"]
                                  if abs(pw - det["gmpp"]["P"]) > 1e-6])
        fig.update_yaxes(range=[0, 1.18 * max(float(max(det["P"])), float(max(uns["P"])))])
        ui.style_fig(fig, height=250, x_title="Voltage (V)", y_title="Power (W)")
        fig.update_layout(showlegend=False, margin=dict(l=48, r=10, t=10, b=40))
        ui.show_chart(fig, key=f"{key}_pv")
    return stt


def page_timeline():
    import datetime as _dt
    c = ui.T()
    disp, mono = ui.FONTS["display"], ui.FONTS["mono"]
    st.markdown(f"<style>.bh{{font-family:{disp};font-weight:700;color:{c['text']};font-size:15px;}}"
                f".bmono,.bmono *{{font-family:{mono};}}"
                f".gm-status{{font-family:{mono};font-size:12.5px;margin:6px 0;}}</style>",
                unsafe_allow_html=True)
    ui.page_intro("Timeline",
                  "The same PV system, with sunlight, temperature and shading that change "
                  "through the day.", "Dynamic test · Timeline")
    sent, system, sys_hash = _tl_inherit()
    if not system:
        return
    panels = system["panels"]
    by_uid = {p["uid"]: p for p in panels}
    ids = [p["display_id"] for p in panels]
    by_id = {p["display_id"]: p for p in panels}
    n_panels = len(panels)
    cond = sent.get("static_condition") or {}

    # ---- inherit, migrate, and detect a rebuilt system ------------------------
    st.session_state.setdefault("tl_events", [])
    if not st.session_state["tl_events"] and st.session_state.get("day_events"):
        focus_uid = (sent.get("focus_panel") or {}).get("uid") or panels[0]["uid"]
        st.session_state["tl_events"] = tl.migrate_legacy_events(
            st.session_state.pop("day_events"), focus_uid, n_panels)
        st.toast("Day events from an earlier session were converted to the timeline.")
    events = st.session_state["tl_events"]
    prev = st.session_state.get("dynamic_scenario")
    if prev and prev.get("base_system_hash") != sys_hash:
        gone = [e for e in events if e["target"] != tl.ALL_PANELS and e["target"] not in by_uid]
        for e in gone:
            _tl_remove(e["uid"])
        events = st.session_state["tl_events"]
        ui.callout(f"The PV system was rebuilt on Scenario after this timeline was made, so "
                   f"the timeline now runs on the new system. "
                   f"{len(gone)} event(s) aimed at panels that no longer exist were removed; "
                   f"the rest were kept.", "System changed — timeline reviewed", "caveat")
    model_label = str(st.session_state.get("gm_panel") or system["module"]).split(" · ")[0]
    ui.callout(f"Inherited from Build system: {model_label} · {system['n_series']}S × "
               f"{system['n_parallel']}P · {n_panels} panel{'s' if n_panels != 1 else ''} · "
               f"system {sys_hash}. The topology is not editable here; change it on Build "
               f"system and send again.", "The PV system", "info")

    left, right = st.columns([0.9, 1.7], gap="large")
    with left:
        with st.container(border=True):
            st.markdown("<div class='bh'>1 · Sun and temperature</div>", unsafe_allow_html=True)
            st.session_state.setdefault("tl_peak", int(cond.get("base_irradiance", 910) or 910))
            peak = int(st.number_input("Peak sunlight at noon (W/m²)", 100, 1200, step=10,
                                       key="tl_peak",
                                       help="G(t) is a clear-sky arc from 06:00 to 18:00 "
                                            "scaled to this peak."))
            t1, t2 = st.columns(2)
            st.session_state.setdefault("tl_tdawn", 25)
            st.session_state.setdefault("tl_tnoon", int(cond.get("temperature_c", 43) or 43))
            t_dawn = int(t1.number_input("Cell °C at dawn", -10, 80, step=1, key="tl_tdawn"))
            t_noon = int(t2.number_input("Cell °C at noon", -10, 80, step=1, key="tl_tnoon",
                                         help="T(t) rises from the dawn value to this one on "
                                              "the same arc as the sun."))
        with st.container(border=True):
            st.markdown("<div class='bh'>2 · Tracked panel</div>", unsafe_allow_html=True)
            focus_id = (sent.get("focus_panel") or {}).get("display_id") or ids[0]
            if st.session_state.get("tl_panel") not in ids:
                st.session_state["tl_panel"] = focus_id if focus_id in ids else ids[0]
            tracked_id = st.selectbox("Panel the trackers run on", ids, key="tl_panel",
                                      help="By default the panel Build system handed to the "
                                           "static test (the most shaded one). Every tracker "
                                           "runs on this panel's curve.")
            tracked = by_id[tracked_id]
        with st.container(border=True):
            st.markdown("<div class='bh'>3 · Add a shading event</div>", unsafe_allow_html=True)
            kinds = [k for k in tl.EVENT_SHAPES if k != "Leaf" or n_panels == 1]
            if st.session_state.get("tl_kind") not in kinds:
                st.session_state["tl_kind"] = kinds[0]
            kind = st.selectbox("What casts it", kinds, key="tl_kind",
                                help=scn.SHAPE_HELP.get(st.session_state.get("tl_kind", kinds[0]), ""))
            whole = kind in tl.WHOLE_PANEL_SHAPES
            if st.session_state.get("tl_target") not in ids:
                st.session_state["tl_target"] = tracked_id
            target_id = st.selectbox("On which panel", ids, key="tl_target", disabled=whole,
                                     help="A cloud or dirt covers every panel.")
            st.button("Add at the playhead", key="tl_add", type="primary", use_container_width=True,
                      on_click=_tl_add, args=(kind, tl.ALL_PANELS if whole else by_id[target_id]["uid"]),
                      help=f"Adds a {tl.DEFAULT_EVENT_MINUTES}-minute event starting at the "
                           f"playhead. Edit its window, darkness, position and motion below.")
            if n_panels > 1:
                st.caption("Leaf (part of one section) is available on a single panel only.")

    with right:
        st.session_state.setdefault("tl_time", scn.minutes_to_time(
            int(cond.get("time_minutes", 900) or 900)))
        ph = st.slider("Playhead", min_value=scn.minutes_to_time(tl.DAY_START),
                       max_value=scn.minutes_to_time(tl.DAY_END),
                       step=_dt.timedelta(minutes=15), key="tl_time",
                       help="The moment previewed below. New events start here.")
        t_min = int(scn.time_to_minutes(ph))
        changes = tl.change_points(events, tl.sample_times(tl.DEFAULT_SLICES))
        ui.show_chart(tl.timeline_figure(events, t_min, peak, t_dawn, t_noon, by_uid,
                                         ui.EVENT_COLORS | {"Pole": "#F0C68A", "Tree": "#A9C79F",
                                                            "Dirt": "#E9A08C", "Leaf": "#8FA0A6",
                                                            "Cloud": "#C2BFB6"},
                                         c, changes), key="tl_fig")
        with st.expander(f"Events — {len(events)} on the timeline", expanded=bool(events)):
            if not events:
                st.caption("No shading events yet. Pick a shape on the left and add one at "
                           "the playhead.")
            _tl_event_editor(events, by_uid, n_panels, c)
            if events:
                st.button("Clear all events", key="tl_clear", on_click=_tl_clear)

    # ---- the system at the playhead: one state, one drawing --------------------
    st.space(size="small")
    ui.section_head(f"At {tl.hhmm(t_min)}",
                    "what the system sees, and what the tracked panel's curve looks like")
    _tl_preview(system, events, t_min, peak, t_dawn, t_noon, tracked, c, key="tl")
    ui.engine_badge("validated")

    # ---- the record --------------------------------------------------------------
    dscn = tl.build_dynamic_scenario(system, sys_hash, tracked, peak, t_dawn, t_noon, events)
    st.session_state["dynamic_scenario"] = dscn
    st.space(size="small")
    with st.container(border=True):
        st.markdown("<div class='bh'>4 · Run it</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='gm-status' style='color:{c['teal']}'>● timeline ready · "
                    f"{len(events)} event{'s' if len(events) != 1 else ''} · "
                    f"{tl.DEFAULT_SLICES} slices of {tl.STEPS_PER_SLICE} control steps · "
                    f"hash {_e(dscn['hash'])}</div>", unsafe_allow_html=True)
        a, b = st.columns([1.4, 3], vertical_alignment="center")
        with a:
            with st.container(key="next-tlrun"):
                if st.button("Run the timeline through the trackers →", key="tl_run",
                             type="primary", use_container_width=True):
                    st.switch_page(P["tracker_response"])
        b.markdown(f"<span style='color:{c['text_muted']};font-size:0.9rem'>P&O, InC, PSO "
                   f"and the proposed method each step through this same day on "
                   f"{_e(tracked_id)}. Exploratory — your timeline, not a benchmark.</span>",
                   unsafe_allow_html=True)

    with st.expander("Use an instant of this timeline in the Sandbox", expanded=False):
        st.caption("Sample the shaded span into 15-minute records. The irradiance and "
                   "conditions are transferred; the Sandbox uses its own datasheet module "
                   "and simplified engine — the module is never converted.")
        samples = tl.sample_records(system, events, peak, t_dawn, t_noon, tracked["uid"],
                                    str(st.session_state.get("bench_preset", "—")), 15,
                                    _scenario_hash)
        if not samples:
            st.caption("Add a shading event first.")
        else:
            sdf = pd.DataFrame([{
                "Time": x["time_label"], "Sunlight (W/m²)": round(x["base_irradiance_Wm2"]),
                "Cell °C": round(x["temperature_C"]),
                "Section irradiance (W/m²)": str([round(v) if not isinstance(v, list)
                                                  else [round(y) for y in v]
                                                  for v in x["substring_irradiance_Wm2"]]),
                "Events": ", ".join(x["active_events"]),
            } for x in samples])
            st.dataframe(sdf, hide_index=True, width="stretch")
            sc_idx = st.selectbox("Instant to load", range(len(samples)),
                                  format_func=lambda i: samples[i]["time_label"] + " · "
                                  + ", ".join(samples[i]["active_events"]), key="tl_sample_pick")
            if st.button("Load this instant into the Simulator", key="tl_load_sim",
                         use_container_width=True):
                st.session_state["day_sim_import"] = dict(samples[sc_idx])
                st.switch_page(P["sim_setup"])
            import json as _json
            st.download_button("Download sampled records (JSON)", _json.dumps(samples, indent=2),
                               "timeline_samples.json", "application/json",
                               use_container_width=True, key="tl_samples_json")

    with st.expander("Technical details", expanded=False):
        st.markdown(
            "- Time is minutes after midnight everywhere on the dynamic pages, the same "
            "clock as Build system (`gmppt_scenario.time_to_minutes`); 06:00 = 360, "
            "18:00 = 1080. No fractions of a day.\n"
            "- G(t) = peak × sin(π · (t − 06:00) / 12 h), never below 1 W/m². "
            "T(t) = dawn + (noon − dawn) × the same arc.\n"
            "- A shadow's darkness is a share of the sunlight AT THAT MOMENT; the event's "
            "record is turned into the engine's entry by `gmppt_scenario.shadow_pattern`, "
            "the same translation Build system uses. The drawing and the physics both "
            "read `gmppt_timeline.state_at`, so they cannot disagree. A drifting shadow "
            "moves section by section, because the validated engine takes one light level "
            "per section (per cell group for a Leaf).\n"
            "- Two shadows on one panel combine section by section as the darker one; a "
            "shadow never brightens a panel.\n"
            f"- The record carries `base_system_hash = {sys_hash}`. A topology change on "
            f"Build system is detected against it, not silently applied.\n"
            "- Events restored from an older session (fractions of the day) are converted "
            "to minutes and marked as converted.")


# =========================================================================== #
# Dynamic test · Tracker response  and  · Energy
#
# Both read ONE run of the dynamic scenario (_timeline_run): real trackers on
# validated-engine curves, scored by the harness's own DynamicTrajectory.metrics.
# Every view is driven by the same playhead, and every figure is exploratory.
# =========================================================================== #
def _dyn_ready(what="This page"):
    """The dynamic scenario and its run, or None after saying why."""
    dscn = st.session_state.get("dynamic_scenario")
    if not dscn:
        ui.callout(f"{what} runs the timeline you build on Dynamic test · Timeline. "
                   f"No timeline has been built yet.", "No timeline yet", "info")
        st.page_link(P["timeline"], label="Build the timeline →")
        return None, None
    sent = st.session_state.get("scenario_sent") or {}
    if sent.get("system_hash") and sent["system_hash"] != dscn.get("base_system_hash"):
        ui.callout("The PV system was rebuilt on Scenario after this timeline was made. "
                   "Open Timeline to review it; until then these traces are for the "
                   "earlier system.", "System changed", "caveat")
    if not dscn.get("events"):
        ui.callout("The timeline has no shading events, so only the sun arc and the "
                   "temperature change. Add events on Timeline to make the peak move.",
                   "No shading events", "info")
    try:
        run = _timeline_run(_dyn_key(dscn))
    except Exception as e:
        ui.unavailable("Run unavailable",
                       "Your timeline could not be run through the trackers, so nothing "
                       "is shown here.",
                       f"- `_timeline_run` raised `{type(e).__name__}: {e}`", kind="limit")
        return dscn, None
    return dscn, run


def _hours(ts):
    return [float(t) / 60.0 for t in ts]


def _hour_axis(fig, **kw):
    ticks = list(range(tl.DAY_START, tl.DAY_END + 1, 120))
    fig.update_xaxes(tickvals=[v / 60.0 for v in ticks], ticktext=[tl.hhmm(v) for v in ticks],
                     range=[tl.DAY_START / 60.0, tl.DAY_END / 60.0], **kw)


def _dyn_methods(run):
    return [m for m in ("P&O", "InC", "PSO", "Model only", "Hybrid (bounded)")
            if m in run["methods"]]


def page_tracker_response():
    import datetime as _dt
    c = ui.T()
    disp, mono = ui.FONTS["display"], ui.FONTS["mono"]
    st.markdown(f"<style>.bh{{font-family:{disp};font-weight:700;color:{c['text']};font-size:15px;}}"
                f".bmono,.bmono *{{font-family:{mono};}}</style>", unsafe_allow_html=True)
    ui.page_intro("Tracker response",
                  "The same timeline through P&O, InC, PSO and the proposed method — how "
                  "quickly and reliably each one recovers the moving peak.",
                  "Dynamic test · Tracker response")
    dscn, run = _dyn_ready("Tracker response")
    if not run:
        return
    system, events = dscn["system"], dscn["events"]
    by_uid = {p["uid"]: p for p in system["panels"]}
    tracked = by_uid.get(run["tracked"]["uid"]) or run["tracked"]
    peak, t_dawn, t_noon = (dscn["sun"]["peak_Wm2"], dscn["temperature"]["dawn_C"],
                            dscn["temperature"]["noon_C"])
    ui.data_chip("Exploratory", "Your timeline on the validated engine. Scenario-specific; "
                                "not a benchmark result.")
    st.caption(f"{tracked.get('display_id', '—')} on {system['module']} · "
               f"{len(events)} event{'s' if len(events) != 1 else ''} · {run['slices']} "
               f"slices × {run['steps_per_slice']} control steps · timeline {run['hash']}")
    if not run.get("has_model"):
        ui.callout("The trained seed is not loadable, so no hybrid trace is shown. The "
                   "classical trackers are real.", "Hybrid unavailable", "limit")
    g2 = run["g2"]
    ui.callout(f"Curve-integrity check (G2): {g2['passed']}/{g2['total']} slices reproduce "
               f"their own p_gmpp at v_gmpp within {g2['tol']}; worst relative error "
               f"{_fmt(g2['worst_rel'], '{:.2e}')}.", "Per-slice gate",
               "info" if g2["passed"] == g2["total"] else "limit")

    methods = _dyn_methods(run)
    default = [m for m in ("P&O", "PSO", "Hybrid (bounded)") if m in methods] or methods[:1]
    sel = st.segmented_control("Show", methods, selection_mode="multi",
                               default=None if "tr_show" in st.session_state else default,
                               key="tr_show") or default

    # ---- the one playhead -------------------------------------------------------
    st.session_state.setdefault("tr_time", scn.minutes_to_time(720))
    ph = st.slider("Playhead", min_value=scn.minutes_to_time(tl.DAY_START),
                   max_value=scn.minutes_to_time(tl.DAY_END), step=_dt.timedelta(minutes=5),
                   key="tr_time", help="Every view below is at this moment.")
    t_min = int(scn.time_to_minutes(ph))
    k = _run_step_at(run, t_min)
    sl = min(k // int(run["steps_per_slice"]), run["slices"] - 1)
    env = run["slice_env"][sl]
    cur = run["slice_curves"][sl]
    avail_k = float(run["avail"][k])

    # fixed KPI positions: the values change, the cards do not move (§27)
    kp = [("Available at the true peak", f"{avail_k:.0f} W",
           f"{env['sun_G']:.0f} W/m² · {env['temp_c']:.0f} °C · {cur['n_peaks']} peak(s)", "hero")]
    for m in sel[:3]:
        pk = float(run["methods"][m][k])
        kp.append((m, f"{pk:.0f} W", f"{100 * pk / max(avail_k, 1e-9):.1f}% of available"))
    ui.kpi_row(kp)

    a, b = st.columns([1, 1.35], gap="medium")
    with a:
        st.markdown(f"<div class='bh'>The system at {tl.hhmm(t_min)}</div>", unsafe_allow_html=True)
        stt = tl.state_at(system, events, t_min, peak, t_dawn, t_noon, _gcfg.N_SUBSTRINGS)
        shapes_here = [sh["shape"] for sh in stt["shadows"].get(tracked["uid"], [])]
        f1, f2 = st.columns([0.8, 1.2])
        f1.markdown(scn.module_face_svg(tl.entry_for(stt, system, tracked["uid"]), stt["sun_G"],
                                        c, False, " + ".join(shapes_here).lower() if shapes_here
                                        else "None", width=150), unsafe_allow_html=True)
        with f2:
            if len(system["panels"]) > 1:
                ui.show_chart(scn.topology_figure(system, stt["shaded_uids"], tracked["uid"], {},
                                                  c, False), key="tr_topo")
            else:
                st.caption("One panel; its face is on the left.")
            names = [tl.event_label(ev, by_uid) for ev in events if ev["uid"] in stt["active"]]
            st.caption("Active: " + (", ".join(names) if names else "no shadow"))
    with b:
        st.markdown(f"<div class='bh'>The curve at {tl.hhmm(t_min)}, and where each tracker sits</div>",
                    unsafe_allow_html=True)
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=cur["V"], y=cur["P"], name="P–V now",
                                 line=dict(color=c["teal"], width=2.5)))
        fig.add_trace(go.Scatter(x=[cur["gmpp"]["V"]], y=[cur["gmpp"]["P"]], mode="markers",
                                 name="true peak", marker=dict(symbol="star", size=15,
                                                               color=ui.PEAK_COLORS["gmpp"])))
        for m in sel:
            fig.add_trace(go.Scatter(x=[run["v_hist"][m][k]], y=[run["methods"][m][k]],
                                     mode="markers", name=m,
                                     marker=dict(color=ui.method_style(m)["color"], size=12,
                                                 symbol=_A1_SYMBOLS.get(m.split(" (")[0], "circle"),
                                                 line=dict(color="#fff", width=1))))
        fig.update_yaxes(range=[0, 1.18 * max(float(max(cur["P"])), 1.0)])
        ui.style_fig(fig, height=290, x_title="terminal voltage  V", y_title="power  W")
        fig.update_layout(legend=dict(orientation="h", y=1.08, x=0),
                          margin=dict(l=48, r=10, t=10, b=40))
        ui.show_chart(fig, key="tr_pv")

    # ---- power over the day, with the changes and the re-convergence points ------
    with st.container(border=True):
        st.markdown(f"<span class='bh' style='font-size:17px'>Tracker power over the day</span>"
                    f"<span style='font-size:13px;color:{c['text_muted']};margin-left:10px'>"
                    f"the gap to the dotted line is shading; the gap to the dark line is "
                    f"tracking — only the second is the method's</span>", unsafe_allow_html=True)
        xs = _hours(run["t"])
        figd = go.Figure()
        figd.add_trace(go.Scatter(x=xs, y=run["unshaded"], name="unshaded potential",
                                  line=dict(color=ui.REF_COLORS["unshaded"], dash="dot", width=2)))
        figd.add_trace(go.Scatter(x=xs, y=run["avail"], name="available at true peak",
                                  line=dict(color=ui.REF_COLORS["available"], width=2.5)))
        for m in sel:
            figd.add_trace(go.Scatter(x=xs, y=run["methods"][m], name=m,
                                      line=dict(width=2, **ui.method_style(m))))
            rc = [r for r in run["reconv"].get(m, []) if r["steps"] is not None]
            if rc:
                kk = [min(r["step"] + r["steps"], len(xs) - 1) for r in rc]
                figd.add_trace(go.Scatter(x=[xs[i] for i in kk], y=[run["methods"][m][i] for i in kk],
                                          mode="markers", name=f"{m} settled",
                                          marker=dict(color=ui.method_style(m)["color"], size=10,
                                                      symbol="diamond-open", line=dict(width=2)),
                                          showlegend=False,
                                          hovertemplate=f"{m} settled after %{{text}} steps<extra></extra>",
                                          text=[str(r["steps"]) for r in rc]))
        for ch in run["changes"]:
            figd.add_vline(x=ch["t"] / 60.0, line=dict(color=c["text_faint"], width=1, dash="dot"))
        if run["changes"]:
            figd.add_annotation(x=run["changes"][0]["t"] / 60.0, y=1.0, yref="paper", yanchor="bottom",
                                showarrow=False, text="condition changes (dotted)",
                                font=dict(size=10, color=c["text_muted"]))
        figd.add_vline(x=t_min / 60.0, line=dict(color=c["teal"], width=2))
        ui.style_fig(figd, height=320, y_title="power  W")
        _hour_axis(figd, title_text="time of day")
        figd.update_layout(legend=dict(orientation="h", y=1.1, x=0))
        ui.show_chart(figd, key="tr_power")
        ui.legend_note("Open diamonds mark where a method settled again after a condition "
                       "change (the harness's convergence rule on the segment). A method "
                       "with no diamond after a change never settled before the next one.")

    # ---- the table --------------------------------------------------------------
    pso_reads, _ = _pso_readings(_load_json("phase2/pso_comparison_val.json"))
    n_ch = len(run["changes"])
    rows = []
    for m in methods:
        mt = run["metrics"][m]
        rc = [r["steps"] for r in run["reconv"].get(m, [])]
        settled = [x for x in rc if x is not None]
        rows.append({
            "Method": m + (" · proposed" if m == "Hybrid (bounded)" else ""),
            "Dynamic efficiency (%)": round(float(mt.get("dynamic_efficiency_pct", float("nan"))), 2),
            "Energy captured (Wh)": round(run["energy_wh"][m], 1),
            "Energy lost (Wh)": round(run["available_wh"] - run["energy_wh"][m], 1),
            "Worst instant loss (W)": round(float(mt.get("worst_instant_loss_w", float("nan"))), 1),
            "Re-converged": f"{len(settled)} of {n_ch}" if n_ch else "no changes",
            "Median re-convergence (steps)": (str(int(np.median(settled))) if settled else "—"),
            "Readings / evaluations": _fmt(pso_reads if m == "PSO"
                                           else _READINGS_FIXED.get(m.split(" (")[0]), "{:.0f}"),
            "Reseed / trigger": "none in this variant",
        })
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    ui.legend_note(f"Dynamic efficiency and the energies are DynamicTrajectory.metrics, the "
                   f"harness's own (EN 50530 eq. 5), over every step of the day. "
                   f"Re-convergence is the harness's convergence rule (power stays within "
                   f"{100 * (1 - run['tolerance']):.0f}% of the available power for the rest "
                   f"of the segment) applied after each of the {n_ch} condition change(s); a "
                   f"dash is censored, not zero. The hybrid variant run here has no re-seed "
                   f"trigger, so none can fire. The seed read one cell temperature, at dawn: "
                   f"{run['seed_temp_c']:.0f} °C.")

    st.divider()
    _a5_day_curves(run, c)
    st.divider()
    _a6_day_tracker(run, c)

    st.divider()
    with st.expander("The standard ramp (EN 50530) on the same panel", expanded=False):
        st.caption("The benchmark's own dynamic profile, stepped on the panel Build system "
                   "handed over. Its split-wide result is on Results · Dynamic performance.")
        _en50530_section(c)


def page_energy():
    c = ui.T()
    disp = ui.FONTS["display"]
    st.markdown(f"<style>.bh{{font-family:{disp};font-weight:700;color:{c['text']};font-size:15px;}}"
                f"</style>", unsafe_allow_html=True)
    ui.page_intro("Energy",
                  "What each method captured over the whole timeline, against what was there.",
                  "Dynamic test · Energy")
    dscn, run = _dyn_ready("Energy")
    if not run:
        return
    ui.data_chip("Exploratory", "Your timeline on the validated engine. Scenario-specific; "
                                "not a benchmark result.")
    methods = _dyn_methods(run)
    av_wh, un_wh = run["available_wh"], run["unshaded_wh"]
    prop = "Hybrid (bounded)" if "Hybrid (bounded)" in methods else None
    kp = [("Available at the true peak", f"{av_wh:.0f} Wh",
           f"of {un_wh:.0f} Wh with nothing shading the panel", "hero")]
    if prop:
        kp.append(("Proposed method captured", f"{run['energy_wh'][prop]:.0f} Wh",
                   f"{run['energy'][prop]:.2f}% of available"))
    if "P&O" in methods:
        kp.append(("P&O captured", f"{run['energy_wh']['P&O']:.0f} Wh",
                   f"{run['energy']['P&O']:.2f}% of available"))
    if prop and "P&O" in methods:
        kp.append(("Recovered by the proposed method", f"{run['energy_wh'][prop] - run['energy_wh']['P&O']:+.0f} Wh",
                   "against P&O, over this day"))
    ui.kpi_row(kp)

    left, right = st.columns([1, 1.25], gap="large")
    with left:
        with st.container(border=True):
            st.markdown("<div class='bh'>Energy captured, as a share of available</div>",
                        unsafe_allow_html=True)
            ys = ["Available at true peak"] + list(reversed(methods))
            xs = [100.0] + [run["energy"][m] for m in reversed(methods)]
            cols = [ui.REF_COLORS["available"]] + [ui.method_style(m)["color"] for m in reversed(methods)]
            figb = go.Figure(go.Bar(y=ys, x=xs, orientation="h", marker=dict(color=cols),
                                    text=[f"{v:.1f}%" for v in xs], textposition="outside",
                                    showlegend=False, hoverinfo="skip"))
            figb.update_xaxes(range=[0, 116], title_text="share of the available energy (%)")
            ui.style_fig(figb, height=320)
            figb.update_layout(margin=dict(l=8, r=24, t=10, b=40))
            ui.show_chart(figb, key="en_bars")
    with right:
        with st.container(border=True):
            st.markdown("<div class='bh'>Where the energy was lost</div>", unsafe_allow_html=True)
            if st.session_state.get("en_show") not in methods:
                st.session_state["en_show"] = prop or methods[0]
            m = st.selectbox("Method", methods, key="en_show", label_visibility="collapsed")
            xs = _hours(run["t"])
            figl = go.Figure()
            figl.add_trace(go.Scatter(x=xs, y=run["avail"], name="available at true peak",
                                      line=dict(color=ui.REF_COLORS["available"], width=2)))
            figl.add_trace(go.Scatter(x=xs, y=run["methods"][m], name=m, fill="tonexty",
                                      fillcolor="rgba(163,43,36,0.18)",
                                      line=dict(width=2, **ui.method_style(m))))
            for ch in run["changes"]:
                figl.add_vline(x=ch["t"] / 60.0, line=dict(color=c["text_faint"], width=1, dash="dot"))
            ui.style_fig(figl, height=320, y_title="power  W")
            _hour_axis(figl, title_text="time of day")
            figl.update_layout(legend=dict(orientation="h", y=1.1, x=0))
            ui.show_chart(figl, key="en_loss")
            ui.legend_note(f"The shaded area is the power {m} did not capture — the calculated "
                           f"loss, {av_wh - run['energy_wh'][m]:.0f} Wh over the day.")

    rows = [{"Method": m + (" · proposed" if m == prop else ""),
             "Captured (Wh)": round(run["energy_wh"][m], 1),
             "Share of available (%)": round(run["energy"][m], 2),
             "Lost to tracking (Wh)": round(av_wh - run["energy_wh"][m], 1),
             "Lost to shading (Wh)": round(un_wh - av_wh, 1)} for m in methods]
    df = pd.DataFrame(rows)
    st.dataframe(df, hide_index=True, width="stretch")
    ui.legend_note(f"E = Σ P·Δt over {run['n_steps']} control steps of "
                   f"{run['minutes_per_step']:.2f} min each, 06:00–18:00. Lost to shading is "
                   f"the same for every method: it is the hardware's, not the tracker's.")
    ui.callout("These are the consequences of one timeline you built. They say what trapping "
               "and slow recovery cost on this day; they support no general claim. The "
               "validated dynamic results are on Results · Dynamic performance.",
               "Exploratory", "caveat")
    e1, e2 = st.columns(2)
    e1.download_button("Download table (CSV)", df.to_csv(index=False), "timeline_energy.csv",
                       "text/csv", use_container_width=True, key="en_csv")
    import json as _json
    e2.download_button("Download run (JSON)",
                       _json.dumps({"dynamic_scenario": dscn, "energy_wh": run["energy_wh"],
                                    "available_wh": av_wh, "unshaded_wh": un_wh,
                                    "metrics": run["metrics"], "reconvergence": run["reconv"],
                                    "changes": run["changes"], "exploratory": True},
                                   indent=2, default=str),
                       "timeline_run.json", "application/json", use_container_width=True,
                       key="en_json")


# =========================================================================== #
# A5 — Day curve playback   ·   A6 — Tracker playback   (Update 3 §5.3, user §11)
#
# Both replay `_timeline_run`'s own output. The curves, the trajectories, the
# available-power reference and the per-slice G2 verdicts were all computed by
# the run; these two functions only draw them. A slice that FAILED G2 is drawn
# like any other and marked, because dropping it would quietly improve a
# picture of an exploratory result.
# =========================================================================== #
def _a5_day_curves(run, c):
    """The P–V curve at each time slice, played through the day."""
    curves = run.get("slice_curves") or []
    g2 = run.get("slice_g2") or []
    ui.section_head("The curve through the day", "one frame per irradiance slice")
    ui.anim_badge("live", "your timeline · exploratory, not a benchmark")
    if not curves:
        ui.unavailable("Slice curves unavailable",
                       "This run did not record a curve for each time slice, so there is "
                       "nothing to play back.", "")
        return
    if st.button("▶ Build the day playback", key="a5_build",
                 help="Plays back the curves this run already computed. Nothing is re-simulated."):
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
            key_frames.add(i)
        pk = round(float(cur["gmpp"]["P"]), 1)
        labels.append(f"{tl.hhmm(cur['t'])} — true peak {pk:.0f} W, {cur.get('n_peaks', '?')} peak(s)"
                      + ("" if ok_g2 else "  ·  G2 FAILED on this slice"))
        if prev_pk is not None and abs(pk - prev_pk) > 0.15 * max(prev_pk, 1e-9):
            key_frames.add(i)
        prev_pk = pk
    for ch in run.get("changes", []):
        key_frames.add(int(ch["slice"]))
    key_frames = sorted(key_frames)
    build_s = _time.perf_counter() - t0

    caption = (f"{len(curves)} slices from {tl.hhmm(curves[0]['t'])} to "
               f"{tl.hhmm(curves[-1]['t'])}. The true peak runs from "
               f"{curves[0]['gmpp']['P']:.0f} W to a maximum of "
               f"{max(x['gmpp']['P'] for x in curves):.0f} W. "
               + (f"{len(failed)} slice(s) failed the G2 curve-integrity check and are marked."
                  if failed else "Every slice passed the G2 curve-integrity check."))

    if not ui.anim_on():
        ui.callout("Animations are off, so the marked slices are shown side by side.",
                   "Static view", "info")
        ui.curve_strip(curves, labels, key_frames[:5], key="a5")
        st.markdown(f'<div class="gm-legend">{_e(caption)}</div>', unsafe_allow_html=True)
        return

    fig = ui.curve_morph(curves, labels, key_frames=key_frames, height=380, frame_ms=160)
    ui.show_chart(fig, key="a5_player")
    st.markdown(f'<div class="gm-legend">{_e(caption)}</div>', unsafe_allow_html=True)
    if failed:
        ui.callout(f"Slices {', '.join(str(i) for i in failed[:10])} failed G2. They are "
                   f"played back unchanged and labelled — a failed slice is not removed "
                   f"from an exploratory run.", "Failed slices kept", "limit")
    with st.expander("Show the marked slices", expanded=False):
        ui.curve_strip(curves, labels, key_frames[:5], key="a5-keys")
    measured = ui.anim_exports(fig, [{"t": x["t"], "p_gmpp": x["gmpp"]["P"]} for x in curves],
                               {"badge": "live illustration",
                                "detail": "exploratory timeline run, validated engine",
                                "stride": 1}, key="a5", name="day_curves")
    ui.anim_budget_note(measured, 1, build_s)


def _a6_day_tracker(run, c):
    """Where each tracker sat, against the power that was available."""
    ui.section_head("Each tracker through the day",
                    "the power it actually held, against the power that was there")
    ui.anim_badge("live", "your timeline · exploratory, not a benchmark")
    methods = _dyn_methods(run)
    if not methods:
        ui.unavailable("No trajectories recorded", "This run has no tracker traces to play back.", "")
        return
    if st.button("▶ Build the tracker playback", key="a6_build",
                 help="Replays the trajectories this run already produced."):
        st.session_state["a6_built"] = True
    if not st.session_state.get("a6_built"):
        st.caption("Press ▶ to follow each tracker across the day.")
        return

    import time as _time
    t0 = _time.perf_counter()
    th = _hours(run["t"])
    avail = [float(x) for x in run["avail"]]
    n = min(len(th), *(len(run["methods"][m]) for m in methods))
    sps = int(run.get("steps_per_slice") or tl.STEPS_PER_SLICE)
    g2 = run.get("slice_g2") or []
    bad_steps = {i for i, s in enumerate(g2) if not s["pass"]}
    key = {0, n - 1}
    for i in sorted(bad_steps):
        if i * sps < n:
            key.add(i * sps)
    for ch in run.get("changes", []):
        if ch["step"] < n:
            key.add(int(ch["step"]))
    keep, stride = ui.downsample(n, sorted(key))
    frames = []
    for k in keep:
        sl = min(k // sps, max(len(g2) - 1, 0))
        failed = bool(g2) and not g2[sl]["pass"]
        frames.append({
            "step": k,
            "title": (f"{tl.hhmm(run['t'][k])} — available {avail[k]:.0f} W"
                      + ("  ·  slice failed G2" if failed else "")),
            "markers": {m: {"V": th[k], "P": float(run["methods"][m][k])} for m in methods},
            "trails": {m: [(th[j], float(run["methods"][m][j])) for j in range(max(0, k - 24), k + 1)]
                       for m in methods},
        })
    build_s = _time.perf_counter() - t0

    static = [go.Scatter(x=th[:n], y=run["unshaded"][:n], mode="lines", name="unshaded potential",
                         line=dict(color=ui.REF_COLORS["unshaded"], dash="dot", width=2)),
              go.Scatter(x=th[:n], y=avail[:n], mode="lines", name="available at true peak",
                         line=dict(color=ui.REF_COLORS["available"], width=2.5))]
    series = {m: {"color": ui.method_style(m)["color"],
                  "symbol": _A1_SYMBOLS.get(m.split(" (")[0], "circle")} for m in methods}
    energy = run.get("energy") or {}
    caption = ("; ".join(f"{m} captured {energy.get(m, float('nan')):.2f}% of the available "
                         f"energy" for m in methods)
               + f". {len(bad_steps)} of {len(g2)} slices failed G2 and are marked; "
                 f"{len(run.get('changes', []))} condition change(s) are key frames.")

    if not ui.anim_on():
        ui.callout("Animations are off, so the marked moments are shown as stills.",
                   "Static view", "info")
        ui.snapshot_strip(frames, list(range(min(4, len(frames)))),
                          captions=[frames[i]["title"] for i in range(min(4, len(frames)))],
                          static_traces=static, series=series, key="a6")
        st.markdown(f'<div class="gm-legend">{_e(caption)}</div>', unsafe_allow_html=True)
        return

    fig = ui.trace_player(frames, series, static_traces=static, height=400,
                          key_frames=sorted(key), step_prefix="step ", frame_ms=70,
                          x_title="time of day  h", y_title="power  W")
    ui.show_chart(fig, key="a6_player")
    st.markdown(f'<div class="gm-legend">{_e(caption)}</div>', unsafe_allow_html=True)
    with st.expander("Show key moments", expanded=False):
        ui.snapshot_strip(frames, [i for i, f in enumerate(frames) if f["step"] in key][:5],
                          captions=[f["title"] for f in frames if f["step"] in key][:5],
                          static_traces=static, series=series, key="a6-keys")
    measured = ui.anim_exports(fig, frames,
                               {"badge": "live illustration",
                                "detail": "exploratory timeline run, validated engine",
                                "stride": stride}, key="a6", name="day_tracker")
    ui.anim_budget_note(measured, stride, build_s)


# =========================================================================== #
# Sandbox · the generated dataset, shown under the generator
# =========================================================================== #
def _dataset_view():
    d = st.session_state.get("dataset")
    if not d or d.get("df") is None or len(d["df"]) == 0:
        ui.callout("No dataset has been generated in this session yet. Generate one above "
                   "and its summary appears here.", "No dataset yet", "info")
        return
    df = d["df"]
    _cfg = d.get("cfg", {})
    ui.section_head("What you generated", "where the peaks sit and where the error concentrates")
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
    except Exception as _err:
        hd[1].button("Download (.zip)", disabled=True, use_container_width=True,
                     help=f"The download could not be built: {_err}")
    a, b = st.columns(2, gap="large")
    with a:
        fig = go.Figure(go.Histogram(x=df["gmpp_voltage_V"], nbinsx=40,
                                     marker_color=ui.METHOD_COLORS["Model only"]))
        ui.style_fig(fig, 320, "Scenarios", "Voltage of the true peak (V)")
        fig.update_layout(title="Where the tallest peak sits")
        ui.show_chart(fig, key="ds_hist")
        ui.legend_note("Clusters, not one bump: the peak sits near a strip boundary.")
    with b:
        fig = go.Figure()
        for objname, g in df.groupby("shading_object"):
            fig.add_trace(go.Scatter(x=g["reduction_percent"], y=g["power_loss_percent"],
                                     mode="markers", name=objname, marker=dict(size=6, opacity=0.7)))
        ui.style_fig(fig, 320, "Power lost to shade (%)", "Light blocked (%)")
        fig.update_layout(title="Loss against how dark the shadow is")
        ui.show_chart(fig, key="ds_scatter")
    ui.engine_badge("simplified")


# =========================================================================== #
# Results · Research summary — the validated findings in four numbers and one
# table. Every value is read from a phase-2 export; the interactive pages
# contribute nothing here. Static figures only.
# =========================================================================== #
def page_summary():
    c = ui.T()
    ui.page_intro("Research summary",
                  "P&O, InC, PSO and the proposed method under the same partial-shading, "
                  "dynamic and convergence challenges — the validated evidence.",
                  "Results · Research summary")
    ui.data_chip("Benchmark result", "Every number on this page is read from a research "
                                     "export. Interactive runs never populate it.")
    t_rel = "phase2/tracker_comparison_val.json"
    p_rel = "phase2/pso_comparison_val.json"
    d_rel = "phase2/dynamic_comparison_30-100_val.json"
    T, Pj, D = _load_json(t_rel), _load_json(p_rel), _load_json(d_rel)
    if not T:
        missing_export(t_rel, "The static comparison")
    elif not require_keys(t_rel, T, ("results", "split"), "the static summary"):
        T = None
    if not D:
        missing_export(d_rel, "The dynamic comparison")
    elif not require_keys(d_rel, D, ("results", "split"), "the dynamic summary"):
        D = None
    if not T and not D:
        return

    head, sub = "hybrid, bounded", "multi_peak"
    R = (T or {}).get("results") or {}

    def stat(key, field):
        return ((R.get(key) or {}).get(sub) or {}).get(field)

    pso_read, pso_best = _pso_readings(Pj)
    sh = ((D or {}).get("results") or {}).get("shaded") or {}

    def dyn(key, field="aggregate_pct"):
        return (sh.get(key) or {}).get(field)

    n_static = stat("P&O", "n")
    kp = [("Static partial shading — found the true peak",
           f"{_fmt(stat(head, 'reached_pct'), '{:.1f}')}%",
           f"{method_label(head)} · n={_fmt(n_static, '{:.0f}')} multi-peak · split "
           f"{(T or {}).get('split', '—')}", "hero"),
          ("Dynamic EN 50530 — tracking efficiency",
           f"{_fmt(dyn('hybrid, no reseed'), '{:.2f}')}%",
           f"{method_label('hybrid, no reseed')} · ±{_fmt(dyn('hybrid, no reseed', 'scenario_se_pct'), '{:.3f}')}"
           f" · Seq {(D or {}).get('sequence', '30-100')} shaded"),
          ("Convergence", f"{_fmt(stat(head, 'median_conv_steps'), '{:.0f}')} steps",
           "median control steps, conditional on arrival"),
          ("Cost per cycle", f"{SEED_PROBE_COST} readings",
           f"against {_fmt(pso_read, '{:.0f}')} PSO evaluations, at "
           f"{_fmt((pso_best or {}).get('multi_peak_reached_pct'), '{:.1f}')}% PSO arrival")]
    ui.kpi_row(kp, weights=[1.3, 1.2, 0.9, 1.1])

    # ---- the comparison table: the four methods the project set out to compare
    specs = [("P&O", "P&O", "P&O", None),
             ("InC", "InC", "InC", None),
             ("PSO", None, "PSO", pso_read),
             (f"{method_label(head)} · proposed", head, "hybrid, no reseed", SEED_PROBE_COST)]
    rows = []
    for label, skey, dkey, reads in specs:
        if skey is None and pso_best:
            found, steady, steps, worst = (pso_best.get("multi_peak_reached_pct"),
                                           pso_best.get("multi_peak_steady_eff_pct"),
                                           pso_best.get("multi_peak_median_conv_steps"),
                                           pso_best.get("multi_peak_worst_energy_lost_w"))
        else:
            found, steady, steps, worst = (stat(skey, "reached_pct"), stat(skey, "steady_eff_pct"),
                                           stat(skey, "median_conv_steps"),
                                           stat(skey, "worst_energy_lost_w")) if skey else (None,) * 4
        rows.append({"Method": label,
                     "Found true peak (%)": _fmt(found, "{:.1f}"),
                     "Steady efficiency (%)": _fmt(steady, "{:.2f}"),
                     "Convergence (steps)": _fmt(steps, "{:.0f}"),
                     "Dynamic efficiency (%)": _fmt(dyn(dkey), "{:.2f}"),
                     "± s.e.": _fmt(dyn(dkey, "scenario_se_pct"), "{:.3f}"),
                     "Readings / evaluations": _fmt(reads, "{:.0f}"),
                     "Worst case (W)": _fmt(worst, "{:.1f}"),
                     "_found": found})
    left, right = st.columns([1.35, 1], gap="large")
    with left:
        df = pd.DataFrame([{k: v for k, v in r.items() if not k.startswith("_")} for r in rows])
        st.dataframe(df, hide_index=True, width="stretch")
        ui.legend_note(f"Static columns: multi-peak subset, n={_fmt(n_static, '{:.0f}')}, "
                       f"split {(T or {}).get('split', '—')}. Dynamic: EN 50530 Seq "
                       f"{(D or {}).get('sequence', '—')}, shaded, "
                       f"{_fmt((D or {}).get('n_shaded'), '{:.0f}')} scenarios. The PSO row "
                       f"is the best-arrival row of the PSO sweep, selected on this same "
                       f"split. Convergence is conditional on arrival.")
    with right:
        figb = go.Figure()
        labs = [r["Method"].split(" · ")[0] for r in rows if r["_found"] is not None]
        vals = [float(r["_found"]) for r in rows if r["_found"] is not None]
        if vals:
            figb.add_trace(go.Bar(x=labs, y=vals, marker=dict(color=[ui.method_style(l)["color"] for l in labs]),
                                  text=[f"{v:.1f}%" for v in vals], textposition="outside",
                                  showlegend=False, hoverinfo="skip"))
            figb.update_yaxes(range=[0, 112], title_text="found the true peak (%)")
            ui.style_fig(figb, height=330)
            figb.update_layout(title="Static partial shading — arrival rate", margin=dict(r=10))
            ui.show_chart(figb, key="sum_bars")
        else:
            ui.unavailable("Arrival rates unavailable", "The static export carries no arrival rate.", "")

    bits = []
    if stat(head, "reached_pct") is not None and stat("P&O", "reached_pct") is not None:
        bits.append(f"Under static partial shading the proposed method found the true peak on "
                    f"{_fmt(stat(head, 'reached_pct'), '{:.1f}')}% of multi-peak scenarios against "
                    f"{_fmt(stat('P&O', 'reached_pct'), '{:.1f}')}% for P&O and "
                    f"{_fmt(stat('InC', 'reached_pct'), '{:.1f}')}% for InC.")
    if pso_best and stat(head, "steady_eff_pct") is not None:
        bits.append(f"Against PSO the advantage is cost, not accuracy: "
                    f"{_fmt(stat(head, 'steady_eff_pct'), '{:.2f}')}% and "
                    f"{_fmt(pso_best.get('multi_peak_steady_eff_pct'), '{:.2f}')}% energy captured, "
                    f"at {SEED_PROBE_COST} readings against {_fmt(pso_read, '{:.0f}')} evaluations "
                    f"per cycle.")
    if dyn("hybrid, no reseed") is not None and dyn("P&O") is not None:
        bits.append(f"Under the EN 50530 ramp it held {_fmt(dyn('hybrid, no reseed'), '{:.2f}')}% "
                    f"against {_fmt(dyn('P&O'), '{:.2f}')}% for P&O — a margin largely inherited "
                    f"from static trapping, since the ramp barely moves the peak.")
    if bits:
        ui.callout(" ".join(bits) + " All figures are simulated on the validation split; the "
                   "held-out test split has not been evaluated.",
                   "What the evidence supports", "info")
    ui.provenance({t_rel.split("/")[-1]: _export_meta(t_rel, T),
                   p_rel.split("/")[-1]: _export_meta(p_rel, Pj),
                   d_rel.split("/")[-1]: _export_meta(d_rel, D)})


# =========================================================================== #
# Data & validation · PV model validation  and  · Experiment provenance
# =========================================================================== #
def page_validation_model():
    c = ui.T()
    ui.page_intro("PV model validation",
                  "The device model every workflow page runs on, where its parameters come "
                  "from, how it was checked, and what it cannot claim.",
                  "Data & validation · PV model validation")
    with st.container(border=True):
        st.markdown(_bh("The two engines"), unsafe_allow_html=True)
        rows = [
            ("Validated engine",
             "Single-diode cell model with bypass diodes and reverse-bias breakdown, "
             "fitted to the CEC reference database",
             "Scenario, Static test, Dynamic test, and every Results figure",
             "Research and benchmark analysis. Matched to ~1% against 616 laboratory "
             "flash tests."),
            ("Interactive simulator",
             "Simplified single-diode model with per-substring bypass",
             "Sandbox only",
             "Exploratory configuration and visualisation. Not benchmark evidence; "
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
            st.markdown("- Validated engine: `gmppt.device` (`module_iv`, `string_iv`, "
                        "`array_iv`, `analyse`) with `pvlib` CEC parameters and "
                        "`gmppt.config.breakdown()`.\n"
                        "- Interactive simulator: `app.py`, single-diode + per-substring "
                        "bypass on a typed-in datasheet.")
    ui.engine_badge("validated")

    with st.container(border=True):
        st.markdown(_bh("Reference source and procedure"), unsafe_allow_html=True)
        counts = _split_counts()
        st.markdown(
            "- **Parameters** — the CEC module database (`pvlib`'s CECMod table), the "
            "industry reference set of measured single-diode parameters, restricted to "
            "the c-Si pool declared in Phase 1.\n"
            f"- **Split by module** — train {counts['train']:,} · validation {counts['val']:,} "
            f"· test {counts['test']:,}. The dashboard shows validation modules only; the "
            f"test split is reserved for one ledgered opening and is never read here.\n"
            "- **STC verification (S2)** — V_oc, V_mp and I_mp match the datasheet to three "
            "significant figures across the design span. Temperature coefficients are "
            "carried as a documented bias (the β_oc deviation equals |Adjust| under the "
            "CEC parameterisation), not a failure.\n"
            "- **Shading physics (S3)** — stepped I–V and multi-peak P–V reproduced; "
            "reverse-bias avalanche parameters recorded as a swept range.\n"
            "- **External validation (S4)** — structural agreement with Başoğlu (peak "
            "count, region, ordering); single-diode versus the Sandia measurement model "
            "at ~2% near STC and ~2.5% at 55 °C over 108 c-Si twin pairs.\n"
            "- **Array generalisation (S5)** — one module is the N = 1 case of the string "
            "engine; a shaded string is multi-peak by the same mechanism as a shaded "
            "module.")
    with st.container(border=True):
        st.markdown(_bh("What the model cannot claim"), unsafe_allow_html=True)
        st.markdown(
            "- **No field measurements** — every figure in this dashboard is simulated.\n"
            "- **Multi-peak magnitude** — quantitative validation of multi-peak curves "
            "against measured data is deferred (no public dataset exists); only the "
            "structure is validated.\n"
            "- **Off-STC temperature behaviour** carries the ~2.5% error bar above.\n"
            "- **One light level per section** for a row or an array; part-of-a-section "
            "shading is modelled for a single module only.")
    ui.section_head("Validation record",
                    "the simplified engine's gates, the measured layers and the literature")
    with st.expander("Technical details", expanded=False):
        sim.page_validation()


def page_provenance():
    import datetime as _dt
    c = ui.T()
    ui.page_intro("Experiment provenance",
                  "Which script, export, split, seed and model produced each figure — so a "
                  "reviewer can answer where a number came from.",
                  "Data & validation · Experiment provenance")
    rows = []
    exports = dict(_EXPORT_SCRIPT)
    exports.setdefault("phase2/near_tie_screen.json", "phase2/p5_near_tie_screen.py")
    for rel, script in exports.items():
        data, problem = _read_export(rel)
        p = _export_path(rel)
        meta = _export_meta(rel, data)
        variants = []
        if isinstance(data, dict):
            r = data.get("results") or data.get("stats") or {}
            if isinstance(r, dict):
                nested = all(isinstance(v, dict) and any(isinstance(x, dict) for x in v.values())
                             for v in r.values()) and set(r) <= {"shaded", "uniform"}
                keys = (sorted({k for v in r.values() for k in v}) if nested else list(r))
                variants = [method_label(k) if k in _METHOD_LABELS else f"unknown: {k}" for k in keys]
            if "pso_sweep" in data:
                variants = [f"PSO sweep, {len(data['pso_sweep'])} points"]
        try:
            mtime = _dt.datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M") if p.exists() else "—"
        except Exception:
            mtime = "—"
        rows.append({"Export": rel.split("/")[-1], "Produced by": script,
                     "Status": "present" if not problem else problem,
                     "Experiment": meta.get("experiment") or "—",
                     "Split": meta.get("split") or "—", "n": _fmt(meta.get("n"), "{:.0f}"),
                     "Seed": "—" if meta.get("seed") in (None, "") else str(meta.get("seed")),
                     "Version": "—" if meta.get("version") in (None, "") else str(meta.get("version")),
                     "Method variants": ", ".join(variants) if variants else "—",
                     "Written": mtime})
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    ui.legend_note("A dash means the export does not record that field; nothing is filled "
                   "in. None of these exports writes an explicit run id, so the experiment "
                   "column shows the family or sequence the file carries.")

    with st.container(border=True):
        st.markdown(_bh("The trained seed"), unsafe_allow_html=True)
        model_p = _gcfg.RESULTS_DIR / "phase3" / "c3_two_stage_full.pkl"
        try:
            if model_p.exists():
                st.markdown(f"- `{model_p.name}` · {model_p.stat().st_size / 1e6:.2f} MB · written "
                            f"{_dt.datetime.fromtimestamp(model_p.stat().st_mtime).strftime('%Y-%m-%d %H:%M')} "
                            f"· loaded by `TwoStageModel.load('c3_two_stage_full')` · "
                            f"{'loads' if _c3_model() is not None else 'DOES NOT LOAD'} in this session.\n"
                            f"- The seed spends `SEED_PROBE_COST = {SEED_PROBE_COST}` control "
                            f"steps on readings; `model.EXPECTED_PROBES` counts one more for "
                            f"the landing. Both are correct about different boundaries.\n"
                            f"- The model file does not record its training list; membership "
                            f"is resolved live through `gmppt.dataset.module_split()`.")
            else:
                ui.unavailable("Model file absent", "The trained seed is not in this copy of "
                               "the repository, so no hybrid trace can be produced.",
                               f"- Expected at `{model_p}`.")
        except Exception as e:
            st.caption(f"Could not stat the model file: {e}")

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
            "- **Changing-conditions profiles** — the EN 50530 irradiance ramps (a "
            "standard test profile, not a sun path) and the pole relocation family.\n"
            "- **Comparison figures** — results measured by the analysis runs. When a "
            "result has not been generated the page says so rather than estimating it.")
        with st.expander("Technical details", expanded=False):
            prov = ""
            try:
                prov = str(_gcfg.provenance())
            except Exception as e:
                prov = f"config.provenance() unavailable: {e}"
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
                f"`gmppt.model` + `gmppt.hybrid`. Profiles: `gmppt.dynamic.SEQUENCES`; "
                f"relocation: `phase2/transition.py`.\n"
                f"- The dashboard's one write is `results/dashboard/current_scenario.json`; "
                f"everything under `results/phase2/` is read-only to it.\n"
                f"- Environment stamp: `{_e(prov)}`")

# =========================================================================== #
# Navigation shell
#
# One header (ui.app_header), one footer (ui.footer_nav), rendered by a single
# wrapper that every page goes through. No page draws its own chrome, so a page
# cannot disagree with the rest of the app about where the user is.
# =========================================================================== #
_PAGE_FUNCS = {
    "home": (page_home, "Home", "home"),
    # Scenario
    "panels": (page_panels, "Build system", "panels"),        # url slug kept: links and sessions
    "inside": (page_inside, "PV analysis", "panel"),
    # Static test
    "run": (page_run, "One run", "run"),
    "static_compare": (page_static_compare, "Compare methods", "compare-methods"),
    # Dynamic test
    "timeline": (page_timeline, "Timeline", "timeline"),
    "tracker_response": (page_tracker_response, "Tracker response", "tracker-response"),
    "energy": (page_energy, "Energy", "energy"),
    # Results — validated exports only
    "summary": (page_summary, "Research summary", "summary"),
    "compare": (page_compare, "Static performance", "compare"),
    "dynamic_perf": (page_dynamic_perf, "Dynamic performance", "dynamic-performance"),
    "results": (page_results, "Targets", "results"),
    # Data & validation
    "benchset": (page_benchset, "Benchmark set", "benchmark-set"),
    "validation": (page_validation_model, "PV model validation", "validation"),
    "sources": (page_provenance, "Experiment provenance", "sources"),
    # Sandbox — the simplified engine, outside the research workflow
    "sim_setup": (page_sim_setup, "Simulator", "simulator"),
    "sim_saved": (page_sim_saved, "Saved scenarios", "saved"),
    "sim_sweep": (page_sim_sweep, "Sweep", "sweep"),
    "sim_dataset": (page_sim_dataset, "Dataset generator", "make-dataset"),
}

# --------------------------------------------------------------------------- #
# THE ONE WORKFLOW TABLE.
#
# The dashboard is organised around the research experiment lifecycle:
#
#   SCENARIO       build the physical PV system once (Build system), and read
#                  why its curve looks the way it does (PV analysis)
#   STATIC TEST    every tracker on the same frozen condition (One run,
#                  Compare methods) — the user's scenario, exploratory
#   DYNAMIC TEST   the same system with G(t), T(t), Shade(t) (Timeline),
#                  the trackers through it (Tracker response), and what that
#                  cost or recovered (Energy) — the user's scenario, exploratory
#   RESULTS        the validated research evidence, read from the harness
#                  exports only; never populated by an interactive run
#   DATA & VALIDATION  what the evidence was measured on, how the PV model was
#                  validated, and where every number came from
#   SANDBOX        the simplified engine, outside the workflow
#
# Everything that names a section reads it from here — the header, the page
# eyebrow, the footer, the tutorial and the tests — so they cannot drift.
# --------------------------------------------------------------------------- #
STAGES = [
    ("Scenario",          ["panels", "inside"]),
    ("Static test",       ["run", "static_compare"]),
    ("Dynamic test",      ["timeline", "tracker_response", "energy"]),
    ("Results",           ["summary", "compare", "dynamic_perf", "results"]),
    ("Data & validation", ["benchset", "validation", "sources"]),
]
SANDBOX = ["sim_setup", "sim_saved", "sim_sweep", "sim_dataset"]
JOURNEY = [s for s, _ in STAGES]

SECTION_KEYS = {s: list(ks) for s, ks in STAGES}
SECTION_KEYS["Sandbox"] = list(SANDBOX)
# The guided journey the footer walks, with step numbers: build → analyse →
# one run → compare → timeline → response → energy → the validated summary.
# The remaining Results and Data & validation pages, and the Sandbox, get a
# Previous / Next within their own section but no step number.
_FLOW = ["panels", "inside", "run", "static_compare", "timeline", "tracker_response",
         "energy", "summary"]
_SANDBOX_FLOW = list(SANDBOX)
_FLOW_STAGE = {k: s for s, ks in STAGES for k in ks}


def stage_of(key: str) -> str:
    """The workflow section a page belongs to, or 'Sandbox'."""
    return _FLOW_STAGE.get(key) or ("Sandbox" if key in SANDBOX else "")


# One sentence per page, answering "what is this for?".
_PAGE_PURPOSE = {
    "panels": "Build the PV system once, then set the shadow and the conditions right now.",
    "inside": "Why this condition gives this curve: sections, bypass diodes, peaks.",
    "run": "Watch one tracker search the frozen condition, step by step.",
    "static_compare": "P&O, InC, PSO and the proposed method on the same condition.",
    "timeline": "The same system with sunlight, temperature and shading that change.",
    "tracker_response": "How each method follows the moving peak through your timeline.",
    "energy": "What tracking cost or recovered over the whole timeline.",
    "summary": "The validated research findings, in four numbers.",
    "compare": "Validated static partial-shading results over the whole validation set.",
    "dynamic_perf": "Validated EN 50530 and relocation results.",
    "results": "The project's targets beside what was measured.",
    "benchset": "What the validated results were measured on.",
    "validation": "How the PV model was validated, and what it cannot claim.",
    "sources": "Which script, export, split and seed produced each figure.",
}

# What each section is for, for the hover help on the header (derived from the
# first page that carries it, so the two cannot drift apart).
_STAGE_PURPOSE = {}
for _k, _stage in _FLOW_STAGE.items():
    _STAGE_PURPOSE.setdefault(_stage, _PAGE_PURPOSE.get(_k, ""))
_STAGE_PURPOSE["Sandbox"] = "The simplified engine, for exploration. Not benchmark evidence."

_NEXT_WHY = {
    "panels": "You have a system and a condition. Read why its curve has more than one peak.",
    "inside": "You know why the peaks are there. Watch one method try to find the tallest.",
    "run": "Now every baseline and the proposed method on this same condition.",
    "static_compare": "The condition was frozen. Let it change through a day.",
    "timeline": "Send the timeline through the trackers.",
    "tracker_response": "What did trapping and slow recovery cost over the day?",
    "energy": "Your runs were exploratory. Read the validated evidence.",
    "summary": "The static result in full, with its caveats.",
    "compare": "Then the dynamic and relocation results.",
    "dynamic_perf": "Read them against the project's targets.",
    "results": "Every number rests on a scenario set. See what is in it.",
    "benchset": "And how the PV model behind it was validated.",
    "validation": "And exactly which run produced each figure.",
    "sim_setup": "Keep a curve to compare against later.",
    "sim_saved": "Or sweep the presets across temperature and light.",
    "sim_sweep": "Or generate thousands of scenarios.",
}

# Widget keys that must survive a page change (R2). Streamlit deletes a widget's
# key on any run that does not render it, which in a multipage app is every run
# spent on another page. No button key may appear here or match a prefix.
_PERSIST_KEYS = [
    "gm_panel", "gm_sel", "gm_vop", "gm_rows", "gm_per", "gm_G2", "gm_T2",
    "run_overlay", "mv_scen", "mv_show", "mv_mode", "saved_pick",
    "gm_opt", "gm_time", "gm_scope", "gm_lab", "gm_topo_seen",
    # which Scenario cards are folded: view state, kept across pages, never hashed
    "scenario_system_expanded", "scenario_conditions_expanded", "scenario_shading_expanded",
    # Static test
    "sc_show",
    # Dynamic test: the timeline controls and both playheads (view state)
    "tl_time", "tl_peak", "tl_tdawn", "tl_tnoon", "tl_panel", "tl_kind", "tl_target",
    "tr_time", "tr_show", "en_show", "dp_seq",
    "gm_anim", "gm_lang", "a1_steps", "a1_view", "a1_built", "a2_built", "a3_built",
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
# shp_/drk_/pos_ are the per-panel shading widgets on Scenario, keyed by panel
# uid; tlw_ are the per-event widgets on Timeline, keyed by event uid. Buttons
# on those pages are keyed gm_*/tl_* so no prefix can reach one.
_PERSIST_PREFIXES = ("swp_", "shp_", "drk_", "pos_", "tlw_")


def _step_of(key):
    """(step, total, flow). Numbered along the guided journey; the other
    Results, Data & validation and Sandbox pages get Previous / Next within
    their own section without a step number."""
    if key in _FLOW:
        return _FLOW.index(key) + 1, len(_FLOW), _FLOW
    keys = SECTION_KEYS.get(stage_of(key)) or []
    if key in keys:
        return None, None, keys
    return None, None, None


def _make_page(key):
    fn, title, url = _PAGE_FUNCS[key]

    def _wrapped():
        # The header's stage strip is the one persistent "where am I" (§5); it is
        # drawn from STAGES, with the stage's purpose as hover help (§7). The
        # landing is the one page without it: no section or page tabs until the
        # reader starts exploring — just the mark, EN/KO and Light/Dark.
        if key == "home":
            hero.top_bar()
        else:
            ui.app_header({k: P.get(k) if _PAGE_FUNCS[k][0] else None for k in _PAGE_FUNCS},
                          SECTION_KEYS, key, journey=JOURNEY, stage_help=_STAGE_PURPOSE)
        # A deploy that is missing the module pool cannot draw a single panel.
        # Say so in a sentence, with the file list one click away, rather than
        # dying in pd.read_parquet with a redacted traceback (Streamlit Cloud
        # hides the message). Home and the Sandbox do not need the pool.
        if key not in SANDBOX and key != "home" and not _gcfg.CEC_POOL.exists():
            ui.unavailable(
                "This deployment has no panel data",
                "The module database the validated engine reads from is not part of "
                "this copy of the app, so nothing on the workflow pages can be drawn. "
                "The Sandbox still works.",
                f"- Missing: `{_gcfg.CEC_POOL}`.\n"
                f"- It is produced once by Phase 1 and must be committed alongside "
                f"the app (see `.gitignore`: `!/results/cec_pool.parquet`). The "
                f"benchmark pages also need `results/phase2/*_val.json`, "
                f"`relocation_comparison_pole.json`, `near_tie_screen.json` and "
                f"`results/phase3/c3_two_stage_full.pkl`.",
                kind="limit")
            return
        stage = _FLOW_STAGE.get(key)
        if stage:
            # Which stages this session has reached — the stepper's "done" marks.
            seen = st.session_state.setdefault("gm_visited", [])
            if key not in seen:
                seen.append(key)
        if key in SECTION_KEYS["Sandbox"]:
            # The persistent Sandbox indicator: every Sandbox page, every render.
            st.markdown('<div class="gm-sandbox">'
                        '<b>Sandbox · simplified engine · not benchmark evidence</b>'
                        '<span>Exploratory configuration and visualisation on a typed-in '
                        'datasheet. Nothing here reaches Results.</span></div>',
                        unsafe_allow_html=True)
        fn()
        if key == "home":
            # After the body, so every control the tour points at is on the page.
            ui.tutorial(_tutorial_steps())

        step, total, flow = _step_of(key)
        if flow:
            i = flow.index(key)
            prev_key = flow[i - 1] if i > 0 else "home"
            next_key = flow[i + 1] if i + 1 < len(flow) else None
            if next_key is None:
                # the journey ends on Research summary; carry on through Results
                sec = SECTION_KEYS.get(stage_of(key)) or []
                if key in sec and sec.index(key) + 1 < len(sec):
                    next_key = sec[sec.index(key) + 1]
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
                   f"You have since edited Build system to "
                   f"“{draft.get('label', 'something else')}” without sending it.",
                   "Edited since sent", "caveat")
    if b.button("Resend", key="run_resend", use_container_width=True,
                help="Run the scenario you are now editing on Build system."):
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
