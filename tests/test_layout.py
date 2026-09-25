"""Layout revision: collapsible Scenario cards, sibling-row equal heights,
the dashboard-wide layout rule. View state only — nothing physical moves.

Run:  python -m pytest tests/test_layout.py -q
"""
from __future__ import annotations

import ast
import inspect
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import gmppt_ui as ui                 # noqa: E402

APP_SRC = (ROOT / "gmppt_app.py").read_text(encoding="utf-8")
UI_SRC = (ROOT / "gmppt_ui.py").read_text(encoding="utf-8")
SCN_SRC = (ROOT / "gmppt_scenario.py").read_text(encoding="utf-8")
KEYS = ("scenario_system_expanded", "scenario_conditions_expanded", "scenario_shading_expanded")


def _fn(name, src=APP_SRC):
    tree = ast.parse(src)
    fn = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == name)
    return ast.get_source_segment(src, fn)


def test_layout_rule_is_documented_and_reusable():
    assert "GMPPT Bench layout rule" in UI_SRC
    assert "ROW-LOCAL" in UI_SRC and "SEMANTIC" in UI_SRC
    assert callable(ui.sibling_row) and callable(ui.collapsible)
    params = inspect.signature(ui.kpi_row).parameters
    assert list(params) == ["items", "weights", "equal_height"] and params["equal_height"].default is True
    assert "st-key-gm-siblings-" in UI_SRC and 'key=f"gm-siblings-{next(_ROW_IDS)}"' in UI_SRC
    assert "_ROW_IDS = itertools.count()" in _fn("setup", UI_SRC), "row keys restart every run"
    # no per-card pixel heights
    for magic in ("height: 172px", "height: 181px", "height: 195px"):
        assert magic not in UI_SRC and magic not in APP_SRC


def test_kpi_card_structure_aligns_label_value_note():
    css = UI_SRC.split("\n    .gm-kpi {{ background")[1].split("@container")[0]
    assert "display: flex; flex-direction: column" in css
    assert "@container (max-width: 300px)" in UI_SRC, "narrow sibling rows stack"
    assert "white-space: nowrap" in UI_SRC.split(".gm-kpi .k {{")[1].split("}}")[0]
    assert "white-space: nowrap" in UI_SRC.split(".gm-kpi .v {{")[1].split("}}")[0]
    assert "@container (max-width: 150px)" in UI_SRC, "long values shrink instead of overflowing"


def test_scenario_cards_are_collapsible_with_state_derived_summaries():
    body = _fn("page_panels")
    for title, key in (("1 · Your PV system", KEYS[0]), ("2 · Conditions", KEYS[1]),
                       ("3 · Shading", KEYS[2])):
        assert f'ui.collapsible("{title}", "{key}"' in body, title
    # summaries read live session values, not a stored copy
    assert 'st.session_state.get("gm_per", 1)' in body and 'st.session_state.get("gm_panel")' in body
    assert "st.session_state['gm_time']" in body and "gm_G2" in body and "gm_T2" in body
    assert 'f"shp_{_p[\'uid\']}"' in body and '"No shade"' in body
    # the old bordered containers with a heading are gone for cards 1-3
    assert "<div class='bh'>1 · Your PV system</div>" not in body
    assert "<div class='bh'>2 · Conditions</div>" not in body
    assert "<div class='bh'>3 · Shading" not in body
    # cards are independent (no accordion): collapsible never closes another key
    col = _fn("collapsible", UI_SRC).split('"""')[-1]        # code, not the docstring
    assert "on_change=\"rerun\"" in col and "st.expander(" in col
    assert col.count("st.session_state[") == 0, "collapsible never writes another card's state"


def test_expander_state_is_view_state_only():
    for k in KEYS:
        assert k in APP_SRC.split("_PERSIST_KEYS")[1][:2000], f"{k} survives page changes"
        assert k not in SCN_SRC, f"{k} must never reach a scenario record or hash"
    assert "expanded" not in _fn("build_draft", SCN_SRC)
    assert "expanded" not in _fn("system_hash", SCN_SRC) and "expanded" not in _fn("scenario_hash", SCN_SRC)


def test_kpi_row_in_what_it_makes_is_three_equal_siblings():
    body = _fn("page_panels")
    seg = body.split('("Making now"')[1].split("])")[0]
    assert "weights=" not in body.split('ui.kpi_row([("Making now"')[1].split(")\n")[0]
    assert "Peaks" in seg and "No shadow" in seg


def test_centre_is_one_vertical_panel_stack():
    """The panel is the dominant object: larger, centred, with one status cell
    per section under it, then the panel-level line, then the sentence. Every
    value shown comes from the engine results the page already holds."""
    import gmppt_scenario as scn
    body = _fn("page_panels")
    assert "face, info = st.columns" not in body, "the two-column centre is gone"
    assert "gm-badges" not in body
    assert "scn.section_strip_html(states, lab, c, width=vw)" in body
    assert "scn.module_face_svg(sel_irr, base_G, c, lab, sel[\"shadow\"][\"shape\"], width=vw)" in body
    assert "gm-panelline" in body and "det['voc']" in body
    assert "scn.bypass_sentence(states, sel_shaded, det['n_peaks'], lab)" in body
    # larger and responsive, not a fixed pixel width
    assert scn.PANEL_VISUAL_WIDTH >= 190 * 1.35 and scn.PANEL_VISUAL_WIDTH <= 190 * 1.55
    svg = scn.module_face_svg([900.0, 900.0, 900.0], 900.0, {"bg": "#0F1A22", "surface_alt": "#1A2B36",
                              "border_strong": "#335063", "amber": "#E0913F", "text_muted": "#9AA7B0",
                              "teal": "#2FA3AE", "amber_text": "#F0B06E"}, False)
    assert 'style="width:min(100%,280px);height:auto;display:block;margin-inline:auto;"' in svg
    assert 'viewBox="0 0 200 300"' in svg
    # the strip mirrors the engine states, one cell per section, no inference
    c = {"amber_text": "#F0B06E", "text": "#F2F4F5"}
    strip = scn.section_strip_html(["off", "on", "partial"], False, c)
    assert strip.count("gm-seccell") == 3
    assert "Working" in strip and "Bypassed" in strip and "Partly bypassed" in strip
    assert strip.index("Working") < strip.index("Bypassed") < strip.index("Partly bypassed")
    assert 'style="width:min(100%,280px);padding:0 3.0% 0 7.0%;"' in strip
    assert "bypass on" in scn.section_strip_html(["on"], True, c)
    # the sentence is generated from state
    s = scn.bypass_sentence(["off", "on", "off"], True, 2, False)
    assert s == ("Section B is bypassed because of the shadow, so current goes around it at the "
                 "real peak. The panel now has 2 possible power peaks.")
    assert scn.bypass_sentence(["off"] * 3, False, 1, False) == \
        "Nothing is shading this panel. Every section works and the curve has 1 peak."


def test_collapsible_is_the_native_accessible_expander():
    col = _fn("collapsible", UI_SRC)
    assert "key=key" in col, "keyed: the state lives in session_state"
    assert 'kw = {} if key in st.session_state else {"expanded": expanded}' in col, \
        "no second source of truth once the key exists"
    assert "aria-expanded" in col or "native control" in col
