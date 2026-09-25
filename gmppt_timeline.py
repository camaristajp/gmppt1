"""
gmppt_timeline.py — the DYNAMIC TIMELINE behind the Dynamic Test section.

Pure functions, no Streamlit. The timeline INHERITS the PV SYSTEM that Scenario ·
Build system made (module, n_series, n_parallel, panel identities, electrical
connections, optimiser architecture) and never rebuilds it. On top of that one
system it adds three time-varying inputs:

    G(t)      sunlight — a clear-sky arc between DAY_START and DAY_END, scaled by
              the peak the reader sets
    T(t)      cell temperature — a dawn/dusk value rising to a solar-noon value on
              the same arc (cells warm with the light)
    Shade(t)  shading events — shape, target panel, how much light is left, where
              the shadow falls, a window and a motion

ONE canonical time: minutes after midnight, exactly as on Scenario
(gmppt_scenario.minutes_to_hhmm / hhmm_to_minutes). No fractions of a day.

ONE canonical shadow function: `shadow_at(event, t, sun_G)` produces the same
shadow record Scenario's controls produce, and `gmppt_scenario.shadow_pattern`
turns it into the irradiance entry the validated engine takes. The drawing and
the physics both read `state_at(...)`; there is no separate animation position.

The record it produces (`build_dynamic_scenario`) carries `base_system_hash`,
so a topology change on Scenario is detected as "system changed" rather than
silently applied.
"""
from __future__ import annotations

import datetime as _dt
import json
import uuid

import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

import gmppt_scenario as scn

SCHEMA_VERSION = 1
DAY_START, DAY_END = 6 * 60, 18 * 60           # 06:00 .. 18:00, minutes after midnight
DAY_MINUTES = DAY_END - DAY_START
DEFAULT_SLICES = 48                             # irradiance slices over the day
STEPS_PER_SLICE = 8                             # control steps the tracker spends on each
DEFAULT_EVENT_MINUTES = 90
DEFAULT_LIGHT_PCT = 30.0                        # light left under a fresh shadow

# Shapes a timeline event may take: Scenario's own list, minus "None".
EVENT_SHAPES = [s for s in scn.SHAPES if s != "None"]
WHOLE_PANEL_SHAPES = ("Cloud", "Dirt")          # no position, and they cover every panel
EVENT_MOTIONS = ["fixed in place", "drifts across the panel", "deepens through the event"]
ALL_PANELS = "all"


# --------------------------------------------------------------------------- #
# Time
# --------------------------------------------------------------------------- #
def clamp_minutes(m) -> int:
    return int(min(DAY_END, max(DAY_START, int(round(float(m))))))


def window_from_minutes(start, duration=DEFAULT_EVENT_MINUTES) -> tuple[int, int]:
    """An event window starting at `start`, kept to `duration` by shifting left
    when the playhead is near the end of the day. Never leaves the day."""
    duration = int(max(15, duration))
    start = clamp_minutes(start)
    end = min(DAY_END, start + duration)
    if end - start < duration:
        start = max(DAY_START, end - duration)
    return start, end


def sample_times(slices: int = DEFAULT_SLICES) -> np.ndarray:
    return np.linspace(DAY_START, DAY_END, int(max(2, slices)))


def hhmm(m) -> str:
    return scn.minutes_to_hhmm(m)


# --------------------------------------------------------------------------- #
# G(t) and T(t)
# --------------------------------------------------------------------------- #
def sun_fraction(t) -> float:
    """0 at dawn and dusk, 1 at solar noon: sin over the day."""
    f = (float(t) - DAY_START) / DAY_MINUTES
    s = float(np.clip(np.sin(np.pi * np.clip(f, 0.0, 1.0)), 0.0, 1.0))
    return 0.0 if s < 1e-12 else s          # sin(π) is 1e-16, not zero


def sun_irradiance(t, peak) -> float:
    """G(t) in W/m². Never below 1 W/m², so the engine always has a curve."""
    return max(1.0, float(peak) * sun_fraction(t))


def cell_temperature(t, t_dawn, t_noon) -> float:
    """T(t) in °C: dawn value rising to the noon value on the sun arc."""
    return float(t_dawn) + (float(t_noon) - float(t_dawn)) * sun_fraction(t)


# --------------------------------------------------------------------------- #
# Events
# --------------------------------------------------------------------------- #
def new_uid() -> str:
    return uuid.uuid4().hex[:8]


def new_event(kind: str, target: str, start: int, end: int, *,
              light_pct: float = DEFAULT_LIGHT_PCT, pos_from: int = 50,
              pos_to: int = 50, motion: str = EVENT_MOTIONS[0]) -> dict:
    """One shading event. `target` is a panel uid, or ALL_PANELS."""
    kind = kind if kind in EVENT_SHAPES else "Pole"
    if kind in WHOLE_PANEL_SHAPES:
        target = ALL_PANELS
    return {"uid": new_uid(), "kind": kind, "target": str(target),
            "start": clamp_minutes(start), "end": clamp_minutes(end),
            "light_pct": float(light_pct), "pos_from": int(pos_from),
            "pos_to": int(pos_to), "motion": motion if motion in EVENT_MOTIONS else EVENT_MOTIONS[0]}


def motions_for(kind: str) -> list[str]:
    """A cloud or a film of dirt has no position to drift across."""
    if kind in WHOLE_PANEL_SHAPES:
        return [m for m in EVENT_MOTIONS if not m.startswith("drifts")]
    return list(EVENT_MOTIONS)


def event_progress(ev: dict, t) -> float | None:
    """0..1 through the event's window, or None when the event is not active."""
    s, e = int(ev["start"]), int(ev["end"])
    t = float(t)
    if e <= s or t < s or t > e:
        return None
    return float(np.clip((t - s) / (e - s), 0.0, 1.0))


def shadow_at(ev: dict, t, sun_G) -> dict | None:
    """THE canonical shadow function: the Scenario-shaped shadow record this event
    casts at minute `t`, or None when it is not active.

    darkness is absolute light under the shadow (W/m²), as Scenario's controls
    define it, derived from the event's "light left" percentage of the sun level
    at that instant — so a shadow stays a shadow as the sun climbs.
    """
    f = event_progress(ev, t)
    if f is None:
        return None
    light = float(ev.get("light_pct", DEFAULT_LIGHT_PCT)) / 100.0
    motion = str(ev.get("motion", EVENT_MOTIONS[0]))
    pos = float(ev.get("pos_from", 50)) / 100.0
    if motion.startswith("drifts"):
        p1 = float(ev.get("pos_to", ev.get("pos_from", 50))) / 100.0
        pos = pos + (p1 - pos) * f
    elif motion.startswith("deepens"):
        light = 1.0 - (1.0 - light) * f
    light = float(np.clip(light, 0.0, 1.0))
    return {"shape": str(ev["kind"]), "darkness": float(sun_G) * light,
            "position": float(np.clip(pos, 0.0, 1.0))}


def combine_entries(a, b):
    """The darker of two module entries, section by section. A nested
    (cell-group) section combines group by group; a scalar section is spread
    over the groups first. Two shadows on one panel never brighten it."""
    out = []
    for x, y in zip(a, b):
        xn, yn = isinstance(x, (list, tuple)), isinstance(y, (list, tuple))
        if not xn and not yn:
            out.append(min(float(x), float(y)))
            continue
        n = len(x) if xn else len(y)
        xs = list(x) if xn else [float(x)] * n
        ys = list(y) if yn else [float(y)] * n
        out.append([min(float(p), float(q)) for p, q in zip(xs, ys)])
    return out


def state_at(system: dict, events: list[dict], t, peak, t_dawn, t_noon,
             n_sub: int = scn.N_SUB) -> dict:
    """Everything about the PV system at minute `t`, from the one set of rules.

    Returns sun_G, temp_c, rows ([row][module] engine entries, in series order),
    active (event uids), shadows ({panel uid: [shadow records]}) and
    shaded_uids. The rows are exactly what module_iv / string_iv accept.
    """
    sun_G = sun_irradiance(t, peak)
    temp_c = cell_temperature(t, t_dawn, t_noon)
    panels = system["panels"]
    shadows = {p["uid"]: [] for p in panels}
    active = []
    for ev in events or []:
        sh = shadow_at(ev, t, sun_G)
        if sh is None:
            continue
        active.append(ev["uid"])
        targets = ([p["uid"] for p in panels] if str(ev.get("target")) == ALL_PANELS
                   else [str(ev.get("target"))])
        for uid in targets:
            if uid in shadows:
                shadows[uid].append(sh)
    grid = scn.rows_of(panels, system["n_series"], system["n_parallel"])
    rows = []
    for row in grid:
        entries = []
        for p in row:
            entry = [float(sun_G)] * int(n_sub)
            for sh in shadows[p["uid"]]:
                entry = combine_entries(entry, scn.shadow_pattern(sh, sun_G, n_sub))
            entries.append(entry)
        rows.append(entries)
    shaded = {p["uid"] for p in panels if shadows[p["uid"]]}
    return {"t": int(round(float(t))), "sun_G": sun_G, "temp_c": temp_c, "rows": rows,
            "active": active, "shadows": shadows, "shaded_uids": shaded}


def entry_for(state: dict, system: dict, uid: str):
    """The tracked panel's engine entry out of a state_at() result."""
    for p in system["panels"]:
        if p["uid"] == uid:
            return state["rows"][int(p["row"])][int(p["pos"])]
    return None


def change_points(events: list[dict], times) -> list[dict]:
    """Slice indices where the set of active events changes — the moments a
    tracker has to re-find the peak. Read from the events, never assumed."""
    out, prev = [], None
    for i, t in enumerate(times):
        act = tuple(sorted(ev["uid"] for ev in events or [] if event_progress(ev, t) is not None))
        if prev is not None and act != prev:
            started = [u for u in act if u not in prev]
            ended = [u for u in prev if u not in act]
            out.append({"slice": int(i), "t": int(round(float(t))),
                        "started": started, "ended": ended})
        prev = act
    return out


def reconvergence_steps(p, avail, k0: int, k1: int, tolerance: float) -> int | None:
    """The harness's convergence rule (tracking.Trajectory.metrics) applied to
    the segment [k0, k1): the number of steps after the change until captured
    power stays at or above tolerance × available for the REST of the segment.
    None = never settled before the next change (censored)."""
    p = np.asarray(p, float)[k0:k1]
    a = np.asarray(avail, float)[k0:k1]
    if len(p) == 0:
        return None
    below = np.nonzero(p < float(tolerance) * a)[0]
    if len(below) == 0:
        return 0
    if below[-1] < len(p) - 1:
        return int(below[-1] + 1)
    return None


def energy_wh(p_hist, minutes_per_step: float) -> float:
    return float(np.sum(np.asarray(p_hist, float)) * float(minutes_per_step) / 60.0)


# --------------------------------------------------------------------------- #
# The record
# --------------------------------------------------------------------------- #
def timeline_hash(base_system_hash: str, tracked_uid: str, peak, t_dawn, t_noon,
                  events: list[dict], slices: int) -> str:
    return scn._digest({
        "base_system_hash": str(base_system_hash), "tracked": str(tracked_uid),
        "peak": round(float(peak), 3), "t_dawn": round(float(t_dawn), 3),
        "t_noon": round(float(t_noon), 3), "slices": int(slices),
        "events": [{k: ev.get(k) for k in ("kind", "target", "start", "end", "light_pct",
                                            "pos_from", "pos_to", "motion")}
                   for ev in sorted(events or [], key=lambda e: (e["start"], e["uid"]))],
    })


def build_dynamic_scenario(system: dict, base_system_hash: str, tracked: dict,
                           peak, t_dawn, t_noon, events: list[dict],
                           slices: int = DEFAULT_SLICES) -> dict:
    """The dynamic scenario: the inherited system, the tracked panel and the
    three time-varying inputs, hashed. View state never enters."""
    events = [dict(e) for e in (events or [])]
    return {
        "schema_version": SCHEMA_VERSION,
        "base_system_hash": str(base_system_hash),
        "system": json.loads(json.dumps(system)),
        "module": str(system["module"]),
        "n_series": int(system["n_series"]), "n_parallel": int(system["n_parallel"]),
        "tracked_panel": {"uid": tracked["uid"], "display_id": tracked["display_id"]},
        "sun": {"peak_Wm2": float(peak), "profile": "clear-sky arc 06:00–18:00"},
        "temperature": {"dawn_C": float(t_dawn), "noon_C": float(t_noon),
                        "profile": "rises with the sun arc"},
        "events": events,
        "slices": int(slices), "steps_per_slice": int(STEPS_PER_SLICE),
        "time_unit": "minutes after midnight",
        "engine": "validated",
        "created_at": _dt.datetime.now().isoformat(timespec="seconds"),
        "hash": timeline_hash(base_system_hash, tracked["uid"], peak, t_dawn, t_noon,
                              events, slices),
    }


def event_label(ev: dict, panels_by_uid: dict) -> str:
    tgt = ("every panel" if str(ev.get("target")) == ALL_PANELS
           else panels_by_uid.get(str(ev.get("target")), {}).get("display_id", "?"))
    return f"{ev['kind']} · {tgt}"


def sample_records(system: dict, events: list[dict], peak, t_dawn, t_noon,
                   tracked_uid: str, module_applied: str, step_minutes: int = 15,
                   scenario_hash=None) -> list[dict]:
    """Instantaneous records, one per `step_minutes`, over the span the events
    cover — recipes the Sandbox can import (irradiance only; never the module).
    Canonical minutes throughout."""
    if not events:
        return []
    step = max(5, int(step_minutes))
    start = clamp_minutes(min(int(e["start"]) for e in events))
    end = clamp_minutes(max(int(e["end"]) for e in events))
    out = []
    for t in range(start, end + 1, step):
        stt = state_at(system, events, t, peak, t_dawn, t_noon)
        if not stt["active"]:
            continue
        entry = entry_for(stt, system, tracked_uid)
        live = [{"kind": ev["kind"], "uid": ev["uid"], "target": ev["target"],
                 "start_minutes": int(ev["start"]), "end_minutes": int(ev["end"]),
                 "duration_minutes": int(ev["end"]) - int(ev["start"]),
                 "motion": ev.get("motion", EVENT_MOTIONS[0])}
                for ev in events if ev["uid"] in stt["active"]]
        out.append({
            "source": "Dynamic test · Timeline",
            "time_minutes": int(t), "time_label": hhmm(t),
            "module_source": str(system["module"]),
            "module_applied": str(module_applied),
            "temperature_C": round(stt["temp_c"], 2),
            "base_irradiance_Wm2": round(stt["sun_G"], 1),
            "substring_irradiance_Wm2": entry,
            "active_events": [ev["kind"] for ev in events if ev["uid"] in stt["active"]],
            "events": live,
            "scenario_hash": scenario_hash(system["module"], stt["temp_c"], entry)
            if scenario_hash else None,
        })
    return out


# --------------------------------------------------------------------------- #
# Migration from the pre-revision day editor (fractions of a 06:00–18:00 day)
# --------------------------------------------------------------------------- #
_LEGACY_KIND = {"Pole or vent": "Pole", "Row in front": "Pole", "Building edge": "Pole",
                "Paint your own": "Pole", "Tree branch": "Tree", "Cloud": "Cloud",
                "Snow band": "Cloud", "Soiling": "Dirt", "Bird dropping": "Leaf", "Leaf": "Leaf"}
_LEGACY_LIGHT = {"Row in front": 35, "Building edge": 40, "Pole or vent": 28, "Tree branch": 45,
                 "Snow band": 55, "Paint your own": 40, "Cloud": 55, "Soiling": 80,
                 "Bird dropping": 20, "Leaf": 30}


def migrate_legacy_events(old: list[dict], default_target: str, n_panels: int) -> list[dict]:
    """Old records carried t0/t1 as fractions of the day and a kind vocabulary of
    their own. They become canonical-minute events on the tracked panel; nothing
    is silently discarded, and the mapping is stated in the record."""
    out = []
    for ev in old or []:
        kind = _LEGACY_KIND.get(str(ev.get("kind")), "Pole")
        if kind == "Leaf" and n_panels != 1:
            kind = "Pole"
        t0 = float(ev.get("t0", 0.0)); t1 = float(ev.get("t1", 1.0))
        start = DAY_START + int(round(t0 * DAY_MINUTES))
        end = DAY_START + int(round(t1 * DAY_MINUTES))
        motion = str(ev.get("motion", "fixed in place"))
        motion = ("drifts across the panel" if motion.startswith("drifts")
                  else "deepens through the event" if motion.startswith("grows")
                  else EVENT_MOTIONS[0])
        new = new_event(kind, default_target, start, max(end, start + 15),
                        light_pct=_LEGACY_LIGHT.get(str(ev.get("kind")), DEFAULT_LIGHT_PCT),
                        pos_from=0 if motion.startswith("drifts") else 50,
                        pos_to=100 if motion.startswith("drifts") else 50, motion=motion)
        new["migrated_from"] = str(ev.get("kind"))
        out.append(new)
    return out


# --------------------------------------------------------------------------- #
# The timeline figure: G(t), T(t), one lane per event, the playhead
# --------------------------------------------------------------------------- #
def timeline_figure(events: list[dict], t, peak, t_dawn, t_noon, panels_by_uid: dict,
                    event_colors: dict, c: dict, changes: list[dict] | None = None,
                    height: int | None = None) -> go.Figure:
    ts = np.linspace(DAY_START, DAY_END, 145)
    G = [sun_irradiance(x, peak) for x in ts]
    T = [cell_temperature(x, t_dawn, t_noon) for x in ts]
    evs = list(events or [])
    n_lanes = max(1, len(evs))
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True,
                        row_heights=[0.34, 0.24, 0.42], vertical_spacing=0.05,
                        subplot_titles=("Sunlight G(t)  W/m²", "Cell temperature T(t)  °C",
                                        "Shading events"))
    fig.add_trace(go.Scatter(x=ts, y=G, mode="lines", name="G(t)",
                             line=dict(color=c["amber"], width=2.2),
                             fill="tozeroy", fillcolor="rgba(181,100,26,0.10)"), row=1, col=1)
    for ev in evs:                                   # cloud / dirt dim the sun itself
        if ev["kind"] in WHOLE_PANEL_SHAPES:
            xs = [x for x in ts if event_progress(ev, x) is not None]
            ys = [(shadow_at(ev, x, sun_irradiance(x, peak)) or {}).get("darkness", 0) for x in xs]
            if xs:
                fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines", showlegend=False,
                                         line=dict(color=c["text_muted"], width=1.6, dash="dot"),
                                         hovertemplate="%{y:.0f} W/m² under the " + ev["kind"].lower()
                                                       + "<extra></extra>"), row=1, col=1)
    fig.add_trace(go.Scatter(x=ts, y=T, mode="lines", name="T(t)",
                             line=dict(color=c["red"], width=2)), row=2, col=1)
    lane_names = []
    for i, ev in enumerate(evs):
        lab = event_label(ev, panels_by_uid)
        lane_names.append(lab)
        fig.add_trace(go.Bar(x=[max(int(ev["end"]) - int(ev["start"]), 5)], base=[int(ev["start"])],
                             y=[lab], orientation="h", width=0.62, showlegend=False,
                             marker=dict(color=event_colors.get(ev["kind"], "#C2BFB6"), line=dict(width=0)),
                             hovertemplate=(f"{lab}<br>{hhmm(ev['start'])}–{hhmm(ev['end'])}"
                                            f"<br>{float(ev.get('light_pct', 0)):.0f}% light left"
                                            f"<br>{ev.get('motion', '')}<extra></extra>")),
                      row=3, col=1)
    if not evs:
        fig.add_annotation(x=(DAY_START + DAY_END) / 2, y=0, text="no shading events yet — add one below",
                           showarrow=False, font=dict(size=12, color=c["text_muted"]), row=3, col=1)
    for ch in changes or []:
        fig.add_vline(x=ch["t"], line=dict(color=c["text_faint"], width=1, dash="dot"), row=3, col=1)
    for r in (1, 2, 3):
        fig.add_vline(x=float(t), line=dict(color=c["teal"], width=2), row=r, col=1)
    ticks = list(range(DAY_START, DAY_END + 1, 120))
    for r in (1, 2, 3):
        fig.update_xaxes(range=[DAY_START, DAY_END], tickvals=ticks, ticktext=[hhmm(v) for v in ticks],
                         fixedrange=True, showticklabels=(r == 3), row=r, col=1)
    fig.update_yaxes(fixedrange=True, rangemode="tozero", row=1, col=1)
    fig.update_yaxes(fixedrange=True, row=2, col=1)
    fig.update_yaxes(fixedrange=True, categoryorder="array", categoryarray=list(reversed(lane_names)),
                     row=3, col=1)
    fig.update_layout(barmode="overlay", bargap=0.3, showlegend=False,
                      height=height or int(260 + 30 * n_lanes),
                      margin=dict(l=8, r=8, t=28, b=8))
    return fig
