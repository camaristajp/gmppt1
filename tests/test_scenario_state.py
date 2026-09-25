"""Scenario page state: stable panel identity, per-panel shading, the two
hashes, draft/sent, canonical time, and no hidden fallback. (Brief §12, §29–31,
§38, §45–47, T1, T7–T11, T13.)

Run:  python -m pytest tests/test_scenario_state.py -q
"""
from __future__ import annotations

import ast
import copy
import datetime as dt
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import gmppt_scenario as scn          # noqa: E402  (no Streamlit import inside)

APP_SRC = (ROOT / "gmppt_app.py").read_text(encoding="utf-8")
SCN_SRC = (ROOT / "gmppt_scenario.py").read_text(encoding="utf-8")


def _geometry_of():
    """gmppt_app.geometry_of, without importing the Streamlit app."""
    tree = ast.parse(APP_SRC)
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "geometry_of")
    ns = {}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), "<g>", "exec"), ns)
    return ns["geometry_of"]


def _fn(name, src=APP_SRC):
    tree = ast.parse(src)
    fn = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == name)
    return ast.get_source_segment(src, fn)


def _system(n_series=1, n_parallel=1, module="M", panels=None, opt=True):
    return {"module": module, "n_series": n_series, "n_parallel": n_parallel,
            "optimisers_enabled": opt, "blocking_diodes": True,
            "panels": panels if panels is not None else scn.migrate_panels([], n_series, n_parallel)}


def _condition(system, G=910.0, T=43.0, minutes=900):
    rows = scn.module_irradiances(system, G)
    return {"time_minutes": minutes, "temperature_c": T, "base_irradiance": G,
            "module_irradiances": rows, "shadow_metadata": []}


def _draft(system, cond):
    g = scn.scenario_geometry(cond["module_irradiances"], _geometry_of())
    f = scn.focus_panel(system, cond["module_irradiances"], cond["base_irradiance"])
    return scn.build_draft(system, cond, g, g.replace("_", "-"), f,
                           cond["module_irradiances"][f["row"]][f["pos"]], "val")


# --------------------------------------------------------------------------- #
# T1 — default system
# --------------------------------------------------------------------------- #
def test_T1_fresh_session_is_one_panel():
    p = scn.migrate_panels([], 1, 1)
    assert len(p) == 1 and p[0]["display_id"] == "S1-M01" and p[0]["shadow"]["shape"] == "None"
    body = _fn("page_panels")
    assert 'st.session_state.get(_k, 1)' in body, "gm_per / gm_rows default to 1"
    assert '"gm_per"' in body and '"gm_rows"' in body
    assert "optimisers = bool(st.session_state.get(\"gm_opt\", True))" in body


# --------------------------------------------------------------------------- #
# T7 — stable panel shading through topology changes
# --------------------------------------------------------------------------- #
def test_T7_shading_stays_on_its_panel_when_a_row_is_added():
    p = scn.migrate_panels([], 3, 1)
    uid2 = p[1]["uid"]
    p[1]["shadow"] = {"shape": "Pole", "darkness": 200.0, "position": 0.5}
    q = scn.migrate_panels(p, 3, 2)
    assert len(q) == 6
    assert [x["display_id"] for x in q] == ["S1-M01", "S1-M02", "S1-M03", "S2-M01", "S2-M02", "S2-M03"]
    assert q[1]["uid"] == uid2 and q[1]["shadow"]["shape"] == "Pole"
    assert [x["uid"] for x in q[:3]] == [x["uid"] for x in p]
    assert all(x["shadow"]["shape"] == "None" for x in q[3:]), "new panels unshaded"
    # shrink back: the same three panels survive, nothing remapped
    r = scn.migrate_panels(q, 3, 1)
    assert [x["uid"] for x in r] == [x["uid"] for x in p] and r[1]["shadow"]["shape"] == "Pole"
    # dropping a column removes only the panel that no longer exists
    s = scn.migrate_panels(q, 2, 2)
    assert [x["display_id"] for x in s] == ["S1-M01", "S1-M02", "S2-M01", "S2-M02"]
    assert s[1]["uid"] == uid2 and s[1]["shadow"]["shape"] == "Pole"


def test_uids_are_not_positions():
    p = scn.migrate_panels([], 2, 2)
    assert len({x["uid"] for x in p}) == 4
    assert all(len(x["uid"]) >= 8 and x["uid"] != x["display_id"] for x in p)


# --------------------------------------------------------------------------- #
# shadow -> pattern (the engine's own shapes)
# --------------------------------------------------------------------------- #
def test_shadow_patterns_are_engine_entries():
    G = 900.0
    assert scn.shadow_pattern({"shape": "None"}, G) == [G, G, G]
    pole = scn.shadow_pattern({"shape": "Pole", "darkness": 200, "position": 0.5}, G)
    assert pole == [G, 200.0, G]
    assert scn.shadow_pattern({"shape": "Pole", "darkness": 200, "position": 0.0}, G) == [200.0, G, G]
    tree = scn.shadow_pattern({"shape": "Tree", "darkness": 200, "position": 1.0}, G)
    assert tree == [G, 550.0, 200.0]
    leaf = scn.shadow_pattern({"shape": "Leaf", "darkness": 200, "position": 0.5}, G)
    assert leaf == [G, [G, 200.0, G], G] and scn.is_nested(leaf)
    assert scn.shadow_pattern({"shape": "Cloud", "darkness": 300}, G) == [300.0] * 3
    dirt = scn.shadow_pattern({"shape": "Dirt", "darkness": 100}, G)
    assert dirt == [max(100.0, G * f) for f in (0.55, 0.70, 0.85)]
    # darkness can never exceed the sunlight
    assert scn.shadow_pattern({"shape": "Pole", "darkness": 2000, "position": 0.5}, G) == [G, G, G]
    g = _geometry_of()
    assert g(pole) == "whole_substring" and g(leaf) == "sub_substring" and g([G, G, G]) == "uniform"
    assert scn.scenario_geometry([[pole, leaf], [[G, G, G]]], g) == "sub_substring"
    assert scn.scenario_geometry([[pole], [[G, G, G]]], g) == "whole_substring"
    assert scn.scenario_geometry([[[G, G, G]]], g) == "uniform"
    assert scn.is_shaded(pole, G) and not scn.is_shaded([G, G, G], G)


def test_module_irradiances_have_the_string_iv_shape():
    s = _system(3, 2)
    s["panels"][4]["shadow"] = {"shape": "Pole", "darkness": 250.0, "position": 1.0}
    rows = scn.module_irradiances(s, 1000.0)
    assert len(rows) == 2 and all(len(r) == 3 for r in rows)
    assert rows[1][1] == [1000.0, 1000.0, 250.0]
    assert rows[0] == [[1000.0] * 3] * 3


def test_focus_panel_is_the_most_shaded_by_rule():
    s = _system(2, 2)
    s["panels"][3]["shadow"] = {"shape": "Cloud", "darkness": 300.0, "position": 0.5}
    s["panels"][1]["shadow"] = {"shape": "Pole", "darkness": 100.0, "position": 0.5}
    rows = scn.module_irradiances(s, 1000.0)
    assert scn.focus_panel(s, rows, 1000.0)["display_id"] == "S2-M02"     # mean 300 < mean 700
    s2 = _system(2, 1)
    assert scn.focus_panel(s2, scn.module_irradiances(s2, 900.0), 900.0)["display_id"] == "S1-M01"


# --------------------------------------------------------------------------- #
# T8 / T9 — hashes: physical state only
# --------------------------------------------------------------------------- #
def test_T9_hash_sensitivity():
    s = _system(2, 2)
    c = _condition(s)
    sh, h = scn.system_hash(s), scn.scenario_hash(scn.system_hash(s), c, "uniform")
    # temperature / light / shadow / time -> scenario changes, system does not
    for change in ({"temperature_c": 25.0}, {"base_irradiance": 600.0}, {"time_minutes": 540}):
        c2 = dict(c, **change)
        if "base_irradiance" in change:
            c2["module_irradiances"] = scn.module_irradiances(s, 600.0)
        assert scn.scenario_hash(sh, c2, "uniform") != h
        assert scn.system_hash(s) == sh
    s3 = copy.deepcopy(s)
    s3["panels"][0]["shadow"] = {"shape": "Pole", "darkness": 200.0, "position": 0.5}
    c3 = _condition(s3)
    assert scn.system_hash(s3) == sh, "a shadow is not hardware"
    assert scn.scenario_hash(sh, c3, "whole_substring") != h
    # module / topology / optimiser architecture -> both change
    for s4 in (_system(2, 2, module="Other", panels=s["panels"]),
               _system(3, 2, panels=scn.migrate_panels(s["panels"], 3, 2)),
               _system(2, 2, panels=s["panels"], opt=False)):
        assert scn.system_hash(s4) != sh
        assert scn.scenario_hash(scn.system_hash(s4), _condition(s4), "uniform") != h


def test_T8_view_state_never_enters_the_hashes():
    s = _system(2, 2)
    c = _condition(s)
    d1 = _draft(s, c)
    d2 = _draft(s, c)
    assert d1["hash"] == d2["hash"] and d1["system_hash"] == d2["system_hash"]
    for key in ("system_hash", "scenario_hash"):
        src = _fn(key, SCN_SRC)
        code = src.split('"""')[-1]                     # after the docstring
        for banned in ("selected", "gm_sel", "scope", "gm_lab", "zoom"):
            assert banned not in code, f"{key} hashes {banned}"
    # the page: only gm_sel is written by the selection callbacks
    step = _fn("_step_panel")
    assert '["gm_sel"]' in step and "scenario" not in step
    click = _fn("_topo_click_to_selection")
    assert '["gm_sel"]' in click and "scenario_draft" not in click and "scenario_sent" not in click
    assert "gm_scope" not in _fn("build_draft", SCN_SRC)


# --------------------------------------------------------------------------- #
# T10 — draft / sent
# --------------------------------------------------------------------------- #
def test_T10_draft_sent_flow():
    s = _system(2, 1)
    c = _condition(s)
    draft = _draft(s, c)
    sent = dict(draft)                                      # Send this setup
    assert draft["hash"] == sent["hash"]
    s2 = copy.deepcopy(s)
    s2["panels"][1]["shadow"] = {"shape": "Tree", "darkness": 300.0, "position": 0.0}
    draft2 = _draft(s2, _condition(s2))
    assert draft2["hash"] != sent["hash"]                   # changed since sent
    draft3 = _draft(s2, _condition(s2))                     # "select another panel": no input changes
    assert draft3["hash"] == draft2["hash"]
    sent = dict(draft3)                                     # Send again
    assert sent["hash"] == draft3["hash"]
    body = _fn("page_panels")
    for s_ in ("● not sent yet", "● sent", "● changed since sent", '"Send this setup"', '"Send again"'):
        assert s_ in body, s_
    assert "st.switch_page" not in body.split("5 · Hand it to the tracker")[1].split("_dynamic_pointer")[0], \
        "Send updates state; the footer navigates"


def test_draft_carries_the_handoff_contract_and_legacy_keys():
    s = _system(2, 2)
    s["panels"][2]["shadow"] = {"shape": "Pole", "darkness": 200.0, "position": 0.5}
    d = _draft(s, _condition(s))
    assert d["schema_version"] == 2
    assert set(d["system"]) >= {"module", "n_series", "n_parallel", "optimisers_enabled",
                                "blocking_diodes", "panels"}
    assert set(d["static_condition"]) >= {"time_minutes", "temperature_c", "base_irradiance",
                                          "module_irradiances", "shadow_metadata"}
    assert d["geometry"] == "whole_substring" and d["engine"] == "validated"
    assert len(d["hash"]) == 12 and len(d["system_hash"]) == 12
    # legacy keys Watch one run / Inside a panel read, pointing at the handed panel
    assert d["module"] == "M" and d["temp"] == 43.0
    assert d["irr"] == [910.0, 200.0, 910.0] and d["focus_panel"]["display_id"] == "S2-M01"
    assert "shadow on 1" in d["label"] and "15:00" in d["label"]


# --------------------------------------------------------------------------- #
# T11 — time
# --------------------------------------------------------------------------- #
def test_T11_time_is_minutes_after_midnight():
    assert scn.hhmm_to_minutes("15:00") == 900
    assert scn.minutes_to_hhmm(900) == "15:00"
    assert scn.time_to_minutes(dt.time(15, 0)) == 900
    assert scn.minutes_to_time(900) == dt.time(15, 0)
    for hh, m in (("06:00", 360), ("09:00", 540), ("18:00", 1080)):
        assert scn.hhmm_to_minutes(hh) == m and scn.minutes_to_hhmm(m) == hh
    assert "6.0 + t * 12" not in SCN_SRC and "* 12" not in SCN_SRC
    body = _fn("page_panels")
    assert "scn.time_to_minutes(t_val)" in body and '"time_minutes": int(time_minutes)' in body


# --------------------------------------------------------------------------- #
# T13 — no hidden fallback
# --------------------------------------------------------------------------- #
def test_T13_engine_failure_is_an_explicit_stop():
    body = _fn("page_panels")
    head = body.split("_topo_click_to_selection()")[0]
    assert 'ui.unavailable("The validated engine is not connected"' in head
    assert 'kind="limit"' in head and "return" in head
    for hidden in ("_run_demo(", "_demo_module()[0]", "sim.module_iv", "MODULE_PRESETS"):
        assert hidden not in body, f"{hidden} must not stand in for the engine"


def test_summary_is_generated_from_state():
    s = _system(4, 2)
    s["panels"][0]["shadow"] = {"shape": "Pole", "darkness": 200.0, "position": 0.5}
    s["panels"][5]["shadow"] = {"shape": "Cloud", "darkness": 300.0, "position": 0.5}
    txt = scn.summary_sentence(s, _condition(s, G=850.0, T=42.0, minutes=900))
    assert txt == ("8 panels in 2 rows, with a partial shadow on 2 of them, in 850 W/m² of "
                   "sunlight at 42 °C, at 15:00.")
    one = scn.summary_sentence(_system(1, 1), _condition(_system(1, 1)))
    assert one.startswith("1 panel, with no shadow")


def test_state_boundaries_are_documented():
    for word in ("PV SYSTEM", "STATIC CONDITION", "DYNAMIC TIMELINE", "base_system_hash"):
        assert word in SCN_SRC
    body = _fn("page_panels")
    assert "PV SYSTEM" in body and "STATIC CONDITION" in body
