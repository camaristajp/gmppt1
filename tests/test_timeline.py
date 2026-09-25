"""The dynamic timeline: canonical minutes, one shadow function shared by the
drawing and the physics, inheritance of the PV system, change detection,
the harness's re-convergence rule, and legacy migration.

Run:  python -m pytest tests/test_timeline.py -q
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import gmppt_scenario as scn          # noqa: E402
import gmppt_timeline as tl           # noqa: E402

TL_SRC = (ROOT / "gmppt_timeline.py").read_text(encoding="utf-8")


def _system(n_series=1, n_parallel=1):
    return {"module": "M", "n_series": n_series, "n_parallel": n_parallel,
            "optimisers_enabled": True, "blocking_diodes": True,
            "panels": scn.migrate_panels([], n_series, n_parallel)}


def test_canonical_time_is_minutes_after_midnight():
    assert tl.DAY_START == 360 and tl.DAY_END == 1080
    assert tl.hhmm(tl.DAY_START) == "06:00" and tl.hhmm(900) == "15:00"
    for banned in ("* 12", "/ 12.0", "frac_day", "time_hour"):
        assert banned not in TL_SRC, f"day fractions are gone: {banned!r}"
    assert tl.clamp_minutes(100) == tl.DAY_START and tl.clamp_minutes(5000) == tl.DAY_END


def test_sun_and_temperature_profiles():
    assert tl.sun_fraction(tl.DAY_START) == 0.0 and tl.sun_fraction(tl.DAY_END) == 0.0
    assert abs(tl.sun_fraction(720) - 1.0) < 1e-12
    assert tl.sun_irradiance(tl.DAY_START, 900) == 1.0, "never below 1 W/m²"
    assert abs(tl.sun_irradiance(720, 900) - 900) < 1e-9
    assert tl.cell_temperature(tl.DAY_START, 25, 45) == 25
    assert abs(tl.cell_temperature(720, 25, 45) - 45) < 1e-9
    assert 25 < tl.cell_temperature(540, 25, 45) < 45


def test_shadow_at_is_the_scenario_shadow_and_scales_with_the_sun():
    ev = tl.new_event("Pole", "uid1", 540, 600, light_pct=25, pos_from=50)
    assert tl.shadow_at(ev, 500, 800) is None and tl.shadow_at(ev, 601, 800) is None
    sh = tl.shadow_at(ev, 570, 800.0)
    assert sh == {"shape": "Pole", "darkness": 200.0, "position": 0.5}
    # exactly the record Build system's controls produce, so the same translation applies
    assert scn.shadow_pattern(sh, 800.0) == [800.0, 200.0, 800.0]
    # darker sun, same share
    assert tl.shadow_at(ev, 570, 400.0)["darkness"] == 100.0


def test_motions_drift_and_deepen():
    drift = tl.new_event("Pole", "u", 600, 700, light_pct=30, pos_from=0, pos_to=100,
                         motion="drifts across the panel")
    assert tl.shadow_at(drift, 600, 900)["position"] == 0.0
    assert abs(tl.shadow_at(drift, 650, 900)["position"] - 0.5) < 1e-9
    assert tl.shadow_at(drift, 700, 900)["position"] == 1.0
    # the drawing and the physics read the same position: the pattern moves section by section
    pats = [scn.shadow_pattern(tl.shadow_at(drift, t, 900), 900) for t in (600, 650, 700)]
    assert [p.index(min(p)) for p in pats] == [0, 1, 2]
    deep = tl.new_event("Cloud", "any", 600, 700, light_pct=40, motion="deepens through the event")
    assert deep["target"] == tl.ALL_PANELS, "a cloud covers every panel"
    assert tl.shadow_at(deep, 600, 900)["darkness"] == 900.0
    assert abs(tl.shadow_at(deep, 700, 900)["darkness"] - 360.0) < 1e-9
    assert "drifts across the panel" not in tl.motions_for("Cloud")


def test_state_at_inherits_the_system_and_targets_panels():
    s = _system(3, 2)
    p = s["panels"]
    events = [tl.new_event("Pole", p[4]["uid"], 600, 700, light_pct=25, pos_from=100),
              tl.new_event("Cloud", tl.ALL_PANELS, 650, 660, light_pct=50)]
    st = tl.state_at(s, events, 655, 1000, 25, 45)
    assert len(st["rows"]) == 2 and all(len(r) == 3 for r in st["rows"])
    G = st["sun_G"]
    # the cloud halves every panel; the pole additionally darkens S2-M02's last section
    assert st["rows"][0][0] == [G * 0.5] * 3
    assert st["rows"][1][1] == [G * 0.5, G * 0.5, G * 0.25]
    assert st["shaded_uids"] == {q["uid"] for q in p}
    assert set(st["active"]) == {events[0]["uid"], events[1]["uid"]}
    assert tl.entry_for(st, s, p[4]["uid"]) == st["rows"][1][1]
    # outside both windows: uniform sun on every panel, nothing shaded
    st2 = tl.state_at(s, events, 800, 1000, 25, 45)
    assert st2["shaded_uids"] == set() and st2["active"] == []
    assert all(e == [st2["sun_G"]] * 3 for row in st2["rows"] for e in row)


def test_two_shadows_never_brighten_a_panel():
    a = [900.0, 300.0, 900.0]
    b = [900.0, 900.0, [900.0, 200.0, 900.0]]
    out = tl.combine_entries(a, b)
    assert out == [900.0, 300.0, [900.0, 200.0, 900.0]]
    assert tl.combine_entries([500.0, 500.0, 500.0], [900.0] * 3) == [500.0] * 3


def test_change_points_are_read_from_the_events():
    times = tl.sample_times(48)
    ev = [tl.new_event("Pole", "u", 600, 700)]
    ch = tl.change_points(ev, times)
    assert len(ch) == 2
    assert ch[0]["started"] == [ev[0]["uid"]] and ch[1]["ended"] == [ev[0]["uid"]]
    assert 600 <= ch[0]["t"] <= 620 and 700 < ch[1]["t"] <= 720
    assert tl.change_points([], times) == []


def test_reconvergence_is_the_harness_rule_on_a_segment():
    avail = np.full(40, 100.0)
    p = np.concatenate([np.full(10, 100.0), np.full(5, 60.0), np.full(25, 99.5)])
    # the change at step 10: settles at step 15 (5 steps), then stays
    assert tl.reconvergence_steps(p, avail, 10, 40, 0.99) == 5
    # never settles before the segment ends -> censored
    p2 = np.concatenate([np.full(10, 100.0), np.full(30, 60.0)])
    assert tl.reconvergence_steps(p2, avail, 10, 40, 0.99) is None
    # already inside tolerance -> 0, like Trajectory.metrics
    assert tl.reconvergence_steps(avail, avail, 10, 40, 0.99) == 0
    # dips out again before the segment ends -> not converged at the first entry
    p3 = np.concatenate([np.full(10, 100.0), np.full(5, 60.0), np.full(20, 100.0), np.full(5, 60.0)])
    assert tl.reconvergence_steps(p3, avail, 10, 40, 0.99) is None


def test_record_hash_ignores_view_state_and_tracks_the_system():
    s = _system(2, 1)
    p = s["panels"]
    ev = [tl.new_event("Pole", p[0]["uid"], 600, 700)]
    r1 = tl.build_dynamic_scenario(s, "sysA", p[0], 900, 25, 43, ev)
    r2 = tl.build_dynamic_scenario(s, "sysA", p[0], 900, 25, 43, ev)
    assert r1["hash"] == r2["hash"] and r1["base_system_hash"] == "sysA"
    assert r1["time_unit"] == "minutes after midnight" and r1["engine"] == "validated"
    assert tl.build_dynamic_scenario(s, "sysB", p[0], 900, 25, 43, ev)["hash"] != r1["hash"]
    assert tl.build_dynamic_scenario(s, "sysA", p[1], 900, 25, 43, ev)["hash"] != r1["hash"]
    assert tl.build_dynamic_scenario(s, "sysA", p[0], 800, 25, 43, ev)["hash"] != r1["hash"]
    ev2 = [dict(ev[0], end=760)]
    assert tl.build_dynamic_scenario(s, "sysA", p[0], 900, 25, 43, ev2)["hash"] != r1["hash"]
    code = TL_SRC.split("def timeline_hash(")[1].split("\ndef ")[0]
    for banned in ("tl_time", "tr_time", "playhead", "gm_sel"):
        assert banned not in code


def test_energy_and_windows():
    assert abs(tl.energy_wh([100.0] * 60, 1.0) - 100.0) < 1e-9
    assert tl.window_from_minutes(900) == (900, 990)
    assert tl.window_from_minutes(1075) == (990, 1080)


def test_legacy_events_migrate_to_minutes_and_keep_their_meaning():
    old = [{"kind": "Pole or vent", "t0": 0.25, "t1": 0.5, "motion": "drifts across the strips"},
           {"kind": "Cloud", "t0": 0.0, "t1": 0.1, "motion": "grows through the event"},
           {"kind": "Bird dropping", "t0": 0.5, "t1": 0.6}]
    new = tl.migrate_legacy_events(old, "uidX", 4)
    assert [e["kind"] for e in new] == ["Pole", "Cloud", "Pole"]      # Leaf needs one panel
    assert new[0]["start"] == 540 and new[0]["end"] == 720
    assert new[0]["motion"] == "drifts across the panel" and (new[0]["pos_from"], new[0]["pos_to"]) == (0, 100)
    assert new[1]["target"] == tl.ALL_PANELS and new[1]["motion"] == "deepens through the event"
    assert new[2]["target"] == "uidX" and new[2]["migrated_from"] == "Bird dropping"
    assert len(new) == len(old), "nothing is silently discarded"


def test_sample_records_are_canonical():
    s = _system(1, 1)
    uid = s["panels"][0]["uid"]
    ev = [tl.new_event("Pole", uid, 600, 660, light_pct=20, pos_from=50)]
    recs = tl.sample_records(s, ev, 900, 25, 43, uid, "Preset", 15)
    assert [r["time_minutes"] for r in recs] == [600, 615, 630, 645, 660]
    assert recs[0]["time_label"] == "10:00" and recs[0]["source"] == "Dynamic test · Timeline"
    assert recs[0]["events"][0]["start_minutes"] == 600 and recs[0]["events"][0]["duration_minutes"] == 60
    assert recs[0]["module_source"] == "M" and recs[0]["module_applied"] == "Preset"
    assert recs[0]["substring_irradiance_Wm2"][1] < recs[0]["substring_irradiance_Wm2"][0]


def test_timeline_figure_builds_for_every_case():
    s = _system(2, 1)
    by_uid = {p["uid"]: p for p in s["panels"]}
    c = {"amber": "#B5641A", "red": "#A32B24", "teal": "#16616B", "text_muted": "#666",
         "text_faint": "#999"}
    fig = tl.timeline_figure([], 720, 900, 25, 43, by_uid, {}, c)
    assert fig is not None
    ev = [tl.new_event("Pole", s["panels"][0]["uid"], 600, 700),
          tl.new_event("Cloud", tl.ALL_PANELS, 650, 700)]
    fig = tl.timeline_figure(ev, 720, 900, 25, 43, by_uid, {}, c, tl.change_points(ev, tl.sample_times()))
    assert any(getattr(t, "orientation", None) == "h" for t in fig.data)
