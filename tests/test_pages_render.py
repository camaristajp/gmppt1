"""Every navigation page renders headlessly, and the research workflow's
state flow works end to end: Build system → Send → Static test → Timeline →
Tracker response → Energy, plus system-change detection and legacy migration.

AppTest cannot `switch_page` to an st.navigation page by file, but after the
first run it holds the registry st.navigation filled, so a page is selected by
its url_path through that registry. This takes about a minute: it runs the
trackers on the validated engine.

Run:  python -m pytest tests/test_pages_render.py -q
"""
from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

pytestmark = pytest.mark.skipif(not (ROOT / "results" / "cec_pool.parquet").exists(),
                                reason="no module pool; the workflow pages cannot draw")

URLS = ["panels", "panel", "run", "compare-methods", "timeline", "tracker-response", "energy",
        "summary", "compare", "dynamic-performance", "results", "benchmark-set", "validation",
        "sources", "simulator", "saved", "sweep", "make-dataset"]


def _goto(at, url_path):
    for h, info in at._registered_pages.items():
        if info.get("url_pathname") == url_path:
            at._page_hash = h
            return at
    raise KeyError(f"{url_path!r} is not a registered page: "
                   f"{sorted(i.get('url_pathname') for i in at._registered_pages.values())}")


def _clean(at, name):
    exc = [str(e.value)[:500] for e in at.exception]
    assert not exc, f"{name}: {exc}"
    assert not [e.value for e in at.error], f"{name}: st.error shown"


def _md(at, needle):
    return [m.value for m in at.markdown if needle in m.value]


def _ss(at, key, default=None):
    """SafeSessionState has no .get()."""
    try:
        return at.session_state[key]
    except (KeyError, AttributeError):
        return default


@pytest.fixture(scope="module")
def at():
    from streamlit.testing.v1 import AppTest
    a = AppTest.from_file(str(ROOT / "gmppt_app.py"), default_timeout=900)
    a.run()
    _clean(a, "home")
    return a


def test_every_page_renders(at):
    registered = {i.get("url_pathname") for i in at._registered_pages.values()}
    assert set(URLS) <= registered, registered
    extra = {r for r in registered - set(URLS) if r}
    assert extra <= {"home"}, f"pages outside the six sections: {extra}"
    for u in URLS:
        _goto(at, u)
        at.run()
        _clean(at, u)


def test_workflow_state_flow(at):
    # a legacy day-event session converts to a timeline event in canonical minutes
    at.session_state["day_events"] = [{"kind": "Pole or vent", "t0": 0.25, "t1": 0.5,
                                       "motion": "drifts across the strips", "uid": "old1"}]
    _goto(at, "panels"); at.run(); _clean(at, "panels")
    [b for b in at.button if b.key == "send_trackers"][0].click(); at.run()
    sent = at.session_state["scenario_sent"]
    assert sent.get("system") and sent.get("system_hash")

    _goto(at, "run"); at.run(); _clean(at, "run")
    assert _md(at, "Exploratory")
    _goto(at, "compare-methods"); at.run(); _clean(at, "compare-methods")
    table = at.dataframe[0].value
    assert "Hybrid (bounded) · proposed" in table["Method"].tolist()
    assert set(table["Method"]) >= {"P&O", "InC", "PSO"}

    _goto(at, "timeline"); at.run(); _clean(at, "timeline")
    ev = at.session_state["tl_events"]
    assert len(ev) == 1 and ev[0]["kind"] == "Pole" and (ev[0]["start"], ev[0]["end"]) == (540, 720)
    assert ev[0]["motion"] == "drifts across the panel" and ev[0]["migrated_from"] == "Pole or vent"
    assert not _ss(at, "day_events")
    win = [s for s in at.slider if str(s.key).startswith("tlw_win_")][0]
    win.set_value((dt.time(9, 0), dt.time(11, 30))); at.run(); _clean(at, "timeline edit")
    assert (at.session_state["tl_events"][0]["start"], at.session_state["tl_events"][0]["end"]) == (540, 690)
    [s for s in at.slider if s.key == "tl_time"][0].set_value(dt.time(10, 0)); at.run()
    assert _md(at, "At 10:00") and any("Pole · " in m for m in _md(at, "Active shadows"))
    dscn = at.session_state["dynamic_scenario"]
    assert dscn["base_system_hash"] == sent["system_hash"] and dscn["time_unit"] == "minutes after midnight"

    _goto(at, "tracker-response"); at.run(); _clean(at, "tracker-response")
    table = at.dataframe[0].value
    assert "Hybrid (bounded) · proposed" in table["Method"].tolist()
    assert table["Re-converged"].str.contains("of 2").all(), table["Re-converged"].tolist()
    assert _md(at, "Exploratory") and _md(at, "Per-slice gate")
    _goto(at, "energy"); at.run(); _clean(at, "energy")
    en = at.dataframe[0].value
    assert (en["Share of available (%)"] <= 100.0).all() and (en["Lost to shading (Wh)"] >= 0).all()

    # rebuilding the system is detected, not silently applied
    _goto(at, "panels"); at.run()
    [n for n in at.number_input if n.key == "gm_per"][0].set_value(2); at.run(); _clean(at, "panels 2S")
    [b for b in at.button if b.key == "send_trackers"][0].click(); at.run()
    assert at.session_state["scenario_sent"]["system_hash"] != sent["system_hash"]
    _goto(at, "tracker-response"); at.run(); _clean(at, "tracker-response changed")
    assert _md(at, "System changed")
    _goto(at, "timeline"); at.run(); _clean(at, "timeline reviewed")
    assert _md(at, "timeline reviewed") and len(at.session_state["tl_events"]) == 1
    assert at.session_state["dynamic_scenario"]["base_system_hash"] == at.session_state["scenario_sent"]["system_hash"]
