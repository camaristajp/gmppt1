"""
gmppt_scenario.py — state, identity, hashing, time and drawing helpers for the
Scenario page. Orchestration only: every curve is computed by gmppt.device.

The three state boundaries the rest of the app (and the next phase) rely on:

    PV SYSTEM        persistent hardware / topology: module model, n_series,
                     n_parallel, panel identities, electrical connections,
                     optimiser architecture, blocking diodes. Built ONCE on
                     Scenario. Hashed as `system_hash`.

    STATIC CONDITION one environmental snapshot of that system: a time (minutes
                     after midnight), temperature, base irradiance, and each
                     panel's shading. Hashed, together with the system, as
                     `scenario_hash`.

    DYNAMIC TIMELINE (next phase, not built here) will inherit the PV SYSTEM
                     unchanged — same module, n_series, n_parallel, panel uids,
                     connections, optimiser architecture — and vary G(t), T(t)
                     and Shade(t) over time. It will reference `system_hash` as
                     its `base_system_hash` so a topology change can be detected
                     as "system changed — review/rebuild the timeline".

Time is always minutes after midnight (06:00 = 360, 15:00 = 900); the only
formatting goes through minutes_to_hhmm / hhmm_to_minutes. No fractions.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import uuid

import plotly.graph_objects as go

SCHEMA_VERSION = 2
N_SUB = 3                      # gmppt.config.N_SUBSTRINGS; passed in by the app

# Shadow shapes are USER-FACING ways of producing an irradiance pattern. They
# are not physics: the engine only ever sees `module_irradiances`.
SHAPES = ["None", "Pole", "Tree", "Leaf", "Dirt", "Cloud"]
SHAPE_HELP = {
    "None": "Nothing is shading this panel.",
    "Pole": "A narrow, hard shadow over one section.",
    "Tree": "A broad, soft shadow: one section dark, its neighbours dimmed.",
    "Leaf": "A small object on part of one section (a cell group).",
    "Dirt": "Soiling: a graded film over the whole panel.",
    "Cloud": "An even dimming of the whole panel.",
}
DEFAULT_SHADOW = {"shape": "None", "darkness": 240.0, "position": 0.5}


# --------------------------------------------------------------------------- #
# Time — minutes after midnight, nothing else
# --------------------------------------------------------------------------- #
def minutes_to_hhmm(m) -> str:
    m = int(round(float(m)))
    return f"{m // 60:02d}:{m % 60:02d}"


def hhmm_to_minutes(s: str) -> int:
    h, mm = str(s).strip().split(":")
    return int(h) * 60 + int(mm)


def time_to_minutes(t: _dt.time) -> int:
    return int(t.hour) * 60 + int(t.minute)


def minutes_to_time(m) -> _dt.time:
    m = int(round(float(m))) % (24 * 60)
    return _dt.time(m // 60, m % 60)


# --------------------------------------------------------------------------- #
# Panels: stable identity, deterministic topology migration
# --------------------------------------------------------------------------- #
def new_uid() -> str:
    return uuid.uuid4().hex[:12]


def display_id(row: int, pos: int) -> str:
    """S<row>-M<pos>, both 1-based, in reading order across a row."""
    return f"S{row + 1}-M{pos + 1:02d}"


def new_panel(row: int, pos: int) -> dict:
    return {"uid": new_uid(), "display_id": display_id(row, pos), "row": int(row),
            "pos": int(pos), "shadow": dict(DEFAULT_SHADOW)}


def migrate_panels(panels: list[dict], n_series: int, n_parallel: int) -> list[dict]:
    """Fit an existing panel list to a topology, deterministically.

    A panel is the thing at (row, pos). Growing the topology keeps every
    existing (row, pos) — its uid and its shading — and adds unshaded panels
    in the new places; shrinking drops only the panels whose (row, pos) no
    longer exists. Nothing is ever re-indexed, so a shadow can never slide
    from one panel to another. Row-major order.
    """
    by_place = {(int(p["row"]), int(p["pos"])): p for p in (panels or [])
                if "row" in p and "pos" in p}
    out = []
    for r in range(int(n_parallel)):
        for k in range(int(n_series)):
            p = by_place.get((r, k))
            if p is None:
                p = new_panel(r, k)
            else:
                p = dict(p)
                p["display_id"] = display_id(r, k)
                p.setdefault("shadow", dict(DEFAULT_SHADOW))
            out.append(p)
    return out


def rows_of(panels: list[dict], n_series: int, n_parallel: int) -> list[list[dict]]:
    """Panels grouped by row, in series order — the shape string_iv wants."""
    grid = [[None] * int(n_series) for _ in range(int(n_parallel))]
    for p in panels:
        grid[int(p["row"])][int(p["pos"])] = p
    return grid


# --------------------------------------------------------------------------- #
# Shadow -> irradiance pattern (the ONLY translation; it produces exactly what
# module_iv / string_iv accept, so nothing downstream has to convert anything)
# --------------------------------------------------------------------------- #
def shadow_pattern(shadow: dict, base_G: float, n_sub: int = N_SUB, n_groups: int = 3):
    """One module's irradiance entry for its shadow.

    Uniform per section (a list of n_sub floats) for every shape except Leaf,
    which shades one cell group of one section and returns a nested entry
    ([G, [G, dark, G], G]) — the sub-substring geometry module_iv accepts.
    `position` (0..1) picks which section the shadow falls on, left to right.
    """
    G = float(base_G)
    shape = str((shadow or {}).get("shape", "None"))
    dark = float((shadow or {}).get("darkness", DEFAULT_SHADOW["darkness"]))
    dark = min(dark, G)
    pos = float((shadow or {}).get("position", 0.5))
    k = int(min(n_sub - 1, max(0, round(pos * (n_sub - 1)))))
    if shape == "Pole":
        return [dark if s == k else G for s in range(n_sub)]
    if shape == "Tree":
        half = (dark + G) / 2.0
        return [dark if s == k else (half if abs(s - k) == 1 else G) for s in range(n_sub)]
    if shape == "Leaf":
        g = int(min(n_groups - 1, max(0, round(pos * (n_groups - 1)))))
        group = [dark if j == g else G for j in range(n_groups)]
        return [group if s == k else G for s in range(n_sub)]
    if shape == "Dirt":
        return [max(dark, G * f) for f in (0.55, 0.70, 0.85)][:n_sub]
    if shape == "Cloud":
        return [dark] * n_sub
    return [G] * n_sub


def is_shaded(entry, base_G: float) -> bool:
    for e in entry:
        vals = e if isinstance(e, (list, tuple)) else [e]
        if any(float(v) < float(base_G) - 1e-9 for v in vals):
            return True
    return False


def is_nested(entry) -> bool:
    return any(isinstance(e, (list, tuple)) for e in entry)


def module_irradiances(system: dict, base_G: float, n_sub: int = N_SUB) -> list[list]:
    """[row][module] -> the engine's module entry, in series order."""
    grid = rows_of(system["panels"], system["n_series"], system["n_parallel"])
    return [[shadow_pattern(p["shadow"], base_G, n_sub) for p in row] for row in grid]


def scenario_geometry(rows: list[list], geometry_of) -> str:
    """The most complex geometry present: sub_substring > whole_substring > uniform."""
    rank = {"uniform": 0, "whole_substring": 1, "sub_substring": 2}
    best = "uniform"
    for row in rows:
        for entry in row:
            g = geometry_of(entry)
            if rank.get(g, 0) > rank[best]:
                best = g
    return best


def focus_panel(system: dict, rows: list[list], base_G: float) -> dict:
    """The one panel handed to the module-level tracker page: the most shaded
    panel (lowest mean light), ties broken by topology order. A rule on the
    physical state, never the panel the user happens to be looking at."""
    grid = rows_of(system["panels"], system["n_series"], system["n_parallel"])
    best, best_mean = None, None

    def mean_of(entry):
        vals = []
        for e in entry:
            vals += list(e) if isinstance(e, (list, tuple)) else [e]
        return sum(float(v) for v in vals) / max(1, len(vals))

    for r, row in enumerate(grid):
        for k, p in enumerate(row):
            m = mean_of(rows[r][k])
            if best is None or m < best_mean - 1e-9:
                best, best_mean = p, m
    return best


# --------------------------------------------------------------------------- #
# Hashes: system (hardware) and scenario (system + condition)
# --------------------------------------------------------------------------- #
def _digest(obj) -> str:
    return hashlib.sha1(json.dumps(obj, sort_keys=True, separators=(",", ":"),
                                   default=str).encode()).hexdigest()[:12]


def _round_entry(entry):
    return [[round(float(v), 3) for v in e] if isinstance(e, (list, tuple))
            else round(float(e), 3) for e in entry]


def system_hash(system: dict) -> str:
    """Hardware only: module, topology, panel identities, optimiser
    architecture, blocking diodes. No temperature, light, shadow, time, and
    nothing about what is selected on screen."""
    return _digest({
        "module": str(system["module"]),
        "n_series": int(system["n_series"]),
        "n_parallel": int(system["n_parallel"]),
        "optimisers_enabled": bool(system.get("optimisers_enabled", True)),
        "blocking_diodes": bool(system.get("blocking_diodes", True)),
        "panels": [(p["uid"], p["display_id"]) for p in system["panels"]],
    })


def scenario_hash(sys_hash: str, condition: dict, geometry: str) -> str:
    """system_hash + the static condition. View state never enters."""
    return _digest({
        "system_hash": sys_hash,
        "time_minutes": int(condition["time_minutes"]),
        "temperature_c": round(float(condition["temperature_c"]), 3),
        "base_irradiance": round(float(condition["base_irradiance"]), 3),
        "module_irradiances": [[_round_entry(e) for e in row]
                               for row in condition["module_irradiances"]],
        "geometry": str(geometry),
    })


def build_draft(system: dict, condition: dict, geometry: str, geometry_label: str,
                focus: dict, focus_entry, split: str) -> dict:
    """The schema-2 scenario record: the PV SYSTEM, the STATIC CONDITION, both
    hashes — plus the legacy top-level keys (module, temp, irr, label, hash)
    that Inside a panel and Watch one run already read, so nothing downstream
    has to rebuild the system from widget state."""
    sh = system_hash(system)
    h = scenario_hash(sh, condition, geometry)
    n = len(system["panels"])
    n_shaded = sum(1 for row in condition["module_irradiances"] for e in row
                   if is_shaded(e, condition["base_irradiance"]))
    label = (f"{n} panel{'s' if n != 1 else ''}"
             f"{f' · shadow on {n_shaded}' if n_shaded else ' · no shadow'}"
             f" · {minutes_to_hhmm(condition['time_minutes'])}")
    irr = [list(e) if isinstance(e, (list, tuple)) else float(e) for e in focus_entry]
    return {
        "schema_version": SCHEMA_VERSION,
        "system": json.loads(json.dumps(system)),           # a copy, plain types
        "system_hash": sh,
        "static_condition": json.loads(json.dumps(condition)),
        "geometry": geometry,
        "geometry_label": geometry_label,
        "focus_panel": {"uid": focus["uid"], "display_id": focus["display_id"]},
        # ---- legacy keys read by Inside a panel / Watch one run / the banner
        "module": str(system["module"]),
        "temp": float(condition["temperature_c"]),
        "irr": irr,
        "label": label,
        "pattern": " / ".join(
            ("[" + ",".join(f"{float(x):.0f}" for x in e) + "]")
            if isinstance(e, (list, tuple)) else f"{float(e):.0f}" for e in irr) + " W/m²",
        "split": split,
        "engine": "validated",
        "created_at": _dt.datetime.now().isoformat(timespec="seconds"),
        "hash": h,
    }


def summary_sentence(system: dict, condition: dict) -> str:
    n = len(system["panels"])
    rows = int(system["n_parallel"])
    n_shaded = sum(1 for row in condition["module_irradiances"] for e in row
                   if is_shaded(e, condition["base_irradiance"]))
    where = (f"{n} panel{'s' if n != 1 else ''} in {rows} row{'s' if rows != 1 else ''}"
             if n > 1 else "1 panel")
    shade = (f"with a partial shadow on {n_shaded} of them" if n > 1 and n_shaded
             else "with a partial shadow on it" if n_shaded else "with no shadow")
    return (f"{where}, {shade}, in {condition['base_irradiance']:.0f} W/m² of sunlight "
            f"at {condition['temperature_c']:.0f} °C, at "
            f"{minutes_to_hhmm(condition['time_minutes'])}.")


# --------------------------------------------------------------------------- #
# Drawing
# --------------------------------------------------------------------------- #
SECTION_NAMES = ["A", "B", "C", "D", "E", "F"]


def section_name(k: int, lab: bool) -> str:
    return f"S{k + 1}" if lab else SECTION_NAMES[k] if k < len(SECTION_NAMES) else f"{k + 1}"


def module_face_svg(entry, base_G: float, c: dict, lab: bool, shape: str = "None",
                    width: int = 190) -> str:
    """One panel seen from the front: 6 × 10 cells, three sections as column
    pairs, the shadow as darkening (and, for a nested entry, only over the
    affected cell group), a sun whose size follows the light level."""
    W, H = 200, 300
    X0, Y0, COLS, ROWS, CW, CH, GAP = 14, 40, 6, 10, 28, 24, 2.2
    n_sub = len(entry)
    per = COLS // n_sub
    cell, line = ("#33556A", "#4A7089") if c.get("bg", "").lower() == "#0f1a22" else ("#DCE8E8", "#A8C0C1")
    out = [f'<svg viewBox="0 0 {W} {H}" style="width:{width}px;max-width:100%;height:auto;" role="img" '
           f'aria-label="panel face">',
           f'<rect x="4" y="30" width="192" height="258" rx="8" fill="{c["surface_alt"]}" '
           f'stroke="{c["border_strong"]}"></rect>']
    # sun
    g = max(0.0, min(1.0, float(base_G) / 1000.0))
    r = 6 + 6 * g
    out.append(f'<circle cx="176" cy="16" r="{r:.1f}" fill="{c["amber"]}" opacity="{0.35 + 0.6 * g:.2f}"></circle>')
    out.append(f'<text x="8" y="20" font-family="IBM Plex Mono, monospace" font-size="10.5" '
               f'fill="{c["text_muted"]}">{float(base_G):.0f} W/m²</text>')
    for rr in range(ROWS):
        for cc in range(COLS):
            out.append(f'<rect x="{X0 + cc * (CW + GAP):.1f}" y="{Y0 + rr * (CH + GAP):.1f}" '
                       f'width="{CW}" height="{CH}" rx="1.5" fill="{cell}" stroke="{line}"></rect>')
    # sections and shadow
    for s in range(n_sub):
        x = X0 + s * per * (CW + GAP) - 1
        w = per * (CW + GAP) - GAP + 2
        if s > 0:
            out.append(f'<line x1="{x - 0.6:.1f}" y1="{Y0 - 4}" x2="{x - 0.6:.1f}" y2="{Y0 + ROWS * (CH + GAP)}" '
                       f'stroke="{c["teal"]}" stroke-width="1.4" stroke-dasharray="3 3" opacity=".8"></line>')
        e = entry[s]
        groups = list(e) if isinstance(e, (list, tuple)) else [e]
        gh = (ROWS * (CH + GAP) - GAP) / len(groups)
        for gi, gv in enumerate(groups):
            dark = 1.0 - float(gv) / max(float(base_G), 1e-9)
            if dark > 0.001:
                out.append(f'<rect x="{x:.1f}" y="{Y0 + gi * gh:.1f}" width="{w:.1f}" height="{gh:.1f}" '
                           f'rx="3" fill="#101A20" opacity="{0.18 + 0.6 * dark:.2f}"></rect>')
            if lab and len(groups) > 1 and gi > 0:
                out.append(f'<line x1="{x:.1f}" y1="{Y0 + gi * gh:.1f}" x2="{x + w:.1f}" y2="{Y0 + gi * gh:.1f}" '
                           f'stroke="{c["amber"]}" stroke-width="1" stroke-dasharray="2 2"></line>')
        out.append(f'<text x="{x + w / 2:.1f}" y="{H - 6}" text-anchor="middle" font-family="IBM Plex Mono, monospace" '
                   f'font-size="11" fill="{c["text_muted"]}">{section_name(s, lab)}</text>')
    if shape not in ("None", None):
        out.append(f'<text x="8" y="{H - 6}" font-family="IBM Plex Mono, monospace" font-size="10" '
                   f'fill="{c["amber_text"]}">{shape.lower()}</text>')
    out.append("</svg>")
    return "".join(out)


def topology_figure(system: dict, shaded_uids: set, selected_uid: str, powers: dict,
                    c: dict, lab: bool) -> go.Figure:
    """The array as wired: rows of panels joined in series, a DC bus joining
    the rows in parallel. Panels are clickable points (customdata = uid)."""
    ns, npar = int(system["n_series"]), int(system["n_parallel"])
    grid = rows_of(system["panels"], ns, npar)
    pw, ph, gx, gy = 1.0, 0.62, 0.42, 0.55
    fig = go.Figure()
    shapes, ann = [], []
    xs, ys, ids, uids, hover = [], [], [], [], []
    bus_x = ns * (pw + gx) + 0.25
    for r, row in enumerate(grid):
        y1 = -r * (ph + gy)
        y0 = y1 - ph
        ann.append(dict(x=-0.15, y=(y0 + y1) / 2, text=f"ROW {r + 1}", showarrow=False,
                        xanchor="right", font=dict(family="IBM Plex Mono, monospace", size=10,
                                                   color=c["text_muted"])))
        for k, p in enumerate(row):
            x0 = k * (pw + gx)
            x1 = x0 + pw
            fill = c["panel"]
            shapes.append(dict(type="rect", x0=x0, y0=y0, x1=x1, y1=y1, fillcolor=fill,
                               line=dict(color=c["border_strong"], width=1), layer="below"))
            for j in (1, 2):
                shapes.append(dict(type="line", x0=x0 + j * pw / 3, x1=x0 + j * pw / 3, y0=y0, y1=y1,
                                   line=dict(color="#6F8FA3", width=1), layer="below"))
            if p["uid"] in shaded_uids:
                shapes.append(dict(type="rect", x0=x0, y0=y0, x1=x1, y1=y1,
                                   fillcolor=c["amber"], opacity=0.45, line=dict(width=0)))
            if p["uid"] == selected_uid:
                shapes.append(dict(type="rect", x0=x0 - 0.05, y0=y0 - 0.05, x1=x1 + 0.05, y1=y1 + 0.05,
                                   line=dict(color=c["amber"], width=3)))
            if k < ns - 1:                                   # series link to the next panel
                shapes.append(dict(type="line", x0=x1, x1=x1 + gx, y0=(y0 + y1) / 2, y1=(y0 + y1) / 2,
                                   line=dict(color=c["text_muted"], width=2)))
            xs.append((x0 + x1) / 2); ys.append((y0 + y1) / 2)
            ids.append(p["display_id"] if lab else f"M{k + 1:02d}" if npar > 1 else f"Panel {k + 1}")
            uids.append(p["uid"])
            pw_ = powers.get(p["uid"])
            hover.append(f"{p['display_id']}<br>{pw_:.0f} W at its real peak" if pw_ is not None
                         else p["display_id"])
        # row to bus
        shapes.append(dict(type="line", x0=ns * pw + (ns - 1) * gx, x1=bus_x, y0=(y0 + y1) / 2,
                           y1=(y0 + y1) / 2, line=dict(color=c["text_muted"], width=2)))
        shapes.append(dict(type="line", x0=-0.25, x1=0, y0=(y0 + y1) / 2, y1=(y0 + y1) / 2,
                           line=dict(color=c["text_muted"], width=2)))
    y_top, y_bot = -ph / 2, -(npar - 1) * (ph + gy) - ph / 2
    if npar > 1:
        shapes.append(dict(type="line", x0=bus_x, x1=bus_x, y0=y_top, y1=y_bot,
                           line=dict(color=c["teal"], width=3)))
        shapes.append(dict(type="line", x0=-0.25, x1=-0.25, y0=y_top, y1=y_bot,
                           line=dict(color=c["teal"], width=3)))
    ann.append(dict(x=bus_x + 0.12, y=(y_top + y_bot) / 2, text="DC", showarrow=False, xanchor="left",
                    font=dict(family="IBM Plex Mono, monospace", size=11, color=c["teal"])))
    fig.add_trace(go.Scatter(
        x=xs, y=ys, mode="markers+text", customdata=uids, text=ids,
        textfont=dict(color="rgba(255,255,255,0.85)", size=10, family="IBM Plex Mono, monospace"),
        marker=dict(symbol="square", size=42, color="rgba(0,0,0,0.001)"),
        hovertext=hover, hoverinfo="text", showlegend=False))
    fig.update_layout(shapes=shapes, annotations=ann, margin=dict(l=8, r=8, t=8, b=8),
                      height=int(min(420, 90 + npar * 84)), dragmode=False, clickmode="event+select",
                      hovermode="closest", plot_bgcolor=c["muted_fill"], paper_bgcolor=c["muted_fill"])
    fig.update_xaxes(visible=False, range=[-0.9, bus_x + 0.6], fixedrange=True)
    fig.update_yaxes(visible=False, range=[y_bot - 0.45, y_top + 0.45], fixedrange=True)
    return fig


def bypass_sentence(states: list[str], shaded: bool, n_peaks: int, lab: bool) -> str:
    """Plain words generated from the electrical state — never asserted."""
    names = [section_name(k, lab) for k in range(len(states))]
    on = [n for n, s in zip(names, states) if s == "on"]
    partial = [n for n, s in zip(names, states) if s == "partial"]
    peaks = f"{n_peaks} peak{'s' if n_peaks != 1 else ''}"
    if not shaded:
        return f"Nothing is shading this panel: every section works and the curve has {peaks}."
    if on:
        return (f"The shadow weakens section {' and '.join(on)}, so its bypass path is active at "
                f"the real peak and current goes around it. The curve has {peaks}.")
    if partial:
        return (f"The shadow weakens section {' and '.join(partial)}; its bypass path is partly "
                f"conducting at the real peak. The curve has {peaks}.")
    return (f"The shadow dims part of this panel, but at the real peak every section still "
            f"carries the current: no bypass path is active. The curve has {peaks}.")
