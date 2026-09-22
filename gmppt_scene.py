"""
gmppt_scene.py — the panels, the shadows and the day.

Turns a layout (rows × panels, portrait or landscape) and a list of shading
events into per-cell light, then into one irradiance value per cell strip —
the input app.module_iv expects. Also draws the three scene figures used on
the Explore · The panels page: the array, the selected panel's face, and the
day timeline.

Model of a shadow
    Each event is a shape in array coordinates (a band, a blob, a half-plane or
    "everything" for a cloud) that may move between its start and end time.
    A cell's transmission is the product over active events of (1 − depth·inside).
    A strip's irradiance is set by its DARKEST cell, because cells in series can
    only pass what the weakest one allows. That is the right answer for the
    simplified engine, which accepts one value per strip; the validated engine
    would take every cell individually.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

EVENT_KINDS = ["Row in front", "Pole or vent", "Tree branch", "Cloud", "Soiling",
               "Bird dropping", "Leaf", "Snow band", "Building edge"]

EVENT_HELP = {
    "Row in front": "Morning and evening shadow from the row ahead. Rises or falls along the lower edge.",
    "Pole or vent": "A narrow diagonal shadow that sweeps across the array over the event.",
    "Tree branch": "A soft, dappled patch that drifts slowly.",
    "Cloud": "Dims every panel equally for its duration — no extra peaks, only less light.",
    "Soiling": "Dirt along the lower edge of every panel. Stays until cleaned.",
    "Bird dropping": "One small, dark spot on a single panel.",
    "Leaf": "A small opaque patch on one panel.",
    "Snow band": "A thick band along the lower edge of every panel after partial melt.",
    "Building edge": "A large shadow advancing from one side of the array.",
}

DEFAULT_EVENTS = [
    dict(kind="Row in front", start="06:00", end="08:00", depth=70, size=40),
    dict(kind="Pole or vent", start="09:20", end="12:40", depth=75, size=55),
    dict(kind="Cloud", start="09:50", end="09:56", depth=60, size=100),
    dict(kind="Cloud", start="13:10", end="13:20", depth=55, size=100),
    dict(kind="Row in front", start="16:00", end="18:00", depth=70, size=40),
    dict(kind="Soiling", start="06:00", end="18:00", depth=10, size=30),
]

DAY_START, DAY_END = 6 * 60, 18 * 60


def to_min(hhmm) -> int:
    """'09:20' -> 560. Accepts datetime.time too."""
    if hasattr(hhmm, "hour"):
        return hhmm.hour * 60 + hhmm.minute
    h, m = str(hhmm).strip().split(":")[:2]
    return int(h) * 60 + int(m)


def fmt_min(m: int) -> str:
    return f"{int(m) // 60:02d}:{int(m) % 60:02d}"


# --------------------------------------------------------------------------- #
# Layout
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Layout:
    rows: int = 3
    per_row: int = 5
    portrait: bool = True
    ns: int = 60           # cells per panel
    n_sub: int = 3         # cell strips (bypass diodes)
    gap: float = 0.12
    row_gap: float = 0.45

    @property
    def cell_cols(self) -> int:
        return 6

    @property
    def cell_rows(self) -> int:
        return self.ns // 6

    @property
    def size(self) -> tuple[float, float]:
        long_side = self.cell_rows / 6.0
        return (1.0, long_side) if self.portrait else (long_side, 1.0)

    @property
    def n_panels(self) -> int:
        return self.rows * self.per_row

    @property
    def extent(self) -> tuple[float, float]:
        w, h = self.size
        return (self.per_row * (w + self.gap) - self.gap, self.rows * (h + self.row_gap) - self.row_gap)

    def rect(self, idx: int) -> tuple[float, float, float, float]:
        r, c = divmod(idx, self.per_row)
        w, h = self.size
        x0 = c * (w + self.gap)
        y0 = (self.rows - 1 - r) * (h + self.row_gap)   # row A drawn at the top
        return x0, y0, x0 + w, y0 + h

    def panel_id(self, idx: int) -> str:
        r, c = divmod(idx, self.per_row)
        return f"{'ABCDEFGHJK'[r]}-{c + 1:02d}"

    def cell_grid(self):
        """Snake order: down column 0, up column 1, ... — the usual series chain.
        Returns (col, row, strip) arrays of length ns in chain order."""
        cols, rows = [], []
        for i in range(self.cell_cols):
            rr = range(self.cell_rows) if i % 2 == 0 else range(self.cell_rows - 1, -1, -1)
            for j in rr:
                cols.append(i)
                rows.append(j)
        per = self.ns // self.n_sub
        strip = np.arange(self.ns) // per
        return np.array(cols), np.array(rows), strip

    def cell_centres(self) -> np.ndarray:
        """(n_panels, ns, 2) centres in array coordinates."""
        col, row, _ = self.cell_grid()
        w, h = self.size
        out = np.zeros((self.n_panels, self.ns, 2))
        for p in range(self.n_panels):
            x0, y0, _, _ = self.rect(p)
            if self.portrait:      # columns run up the panel, strips are vertical bands
                out[p, :, 0] = x0 + (col + 0.5) * w / self.cell_cols
                out[p, :, 1] = y0 + h - (row + 0.5) * h / self.cell_rows
            else:                  # rotated: columns run across, strips are horizontal bands
                out[p, :, 0] = x0 + (row + 0.5) * w / self.cell_rows
                out[p, :, 1] = y0 + h - (col + 0.5) * h / self.cell_cols
        return out


# --------------------------------------------------------------------------- #
# Shadow shapes
# --------------------------------------------------------------------------- #
def _circle(cx, cy, r, n=20, wobble=0.0):
    a = np.linspace(0, 2 * math.pi, n, endpoint=False)
    rr = r * (1 + wobble * np.sin(3 * a + 0.7))
    return list(zip(cx + rr * np.cos(a), cy + rr * np.sin(a)))


def event_shapes(ev: dict, t: int, L: Layout):
    """Shapes cast by one event at minute t. Returns (shapes, depth) where shapes is
    a list of polygons, or the string 'all' for a whole-array dimming (cloud)."""
    s, e = to_min(ev["start"]), to_min(ev["end"])
    if not (s <= t <= e) or e <= s:
        return [], 0.0
    p = (t - s) / (e - s)
    d = max(0.0, min(1.0, float(ev.get("depth", 50)) / 100.0))
    k = max(0.0, min(1.0, float(ev.get("size", 50)) / 100.0))
    X, Y = L.extent
    w, h = L.size
    kind = ev["kind"]
    shapes = []

    if kind == "Cloud":
        return "all", d
    if kind == "Row in front":
        grow = (0.4 + 0.6 * p) if s >= 12 * 60 else (1.0 - 0.6 * p)
        for r in range(L.rows):
            _, y0, _, _ = L.rect(r * L.per_row)
            hh = k * h * grow
            shapes.append([(-1, y0 - 0.01), (X + 1, y0 - 0.01), (X + 1, y0 + hh), (-1, y0 + hh)])
    elif kind == "Pole or vent":
        xc = -0.15 * X + p * 1.3 * X
        bw = (0.10 + 0.35 * k) * w
        sk = 0.25 * Y
        shapes.append([(xc - bw + sk, Y + 1), (xc + bw + sk, Y + 1), (xc + bw - sk, -1), (xc - bw - sk, -1)])
    elif kind == "Tree branch":
        shapes.append(_circle(0.18 * X + 0.25 * X * p, 0.62 * Y, (0.3 + 1.0 * k) * w, wobble=0.25))
        d *= 0.75                                    # dappled, not solid
    elif kind in ("Soiling", "Snow band"):
        frac = (0.06 + 0.15 * k) if kind == "Soiling" else (0.2 + 0.4 * k)
        for i in range(L.n_panels):
            x0, y0, x1, _ = L.rect(i)
            if L.portrait:
                shapes.append([(x0, y0), (x1, y0), (x1, y0 + frac * h), (x0, y0 + frac * h)])
            else:
                shapes.append([(x0, y0), (x1, y0), (x1, y0 + frac * h), (x0, y0 + frac * h)])
    elif kind == "Bird dropping":
        x0, y0, x1, y1 = L.rect(L.n_panels - 1)
        shapes.append(_circle(x0 + 0.62 * (x1 - x0), y0 + 0.35 * (y1 - y0), 0.05 + 0.05 * k, n=12))
    elif kind == "Leaf":
        x0, y0, x1, y1 = L.rect(min(3, L.per_row - 1))
        shapes.append(_circle(x0 + 0.4 * (x1 - x0), y0 + 0.7 * (y1 - y0), (0.10 + 0.2 * k) * w, wobble=0.3))
    elif kind == "Building edge":
        edge = X * (1 - (0.15 + 0.5 * k) * (1 - 0.7 * p))
        shapes.append([(edge, -1), (X + 1, -1), (X + 1, Y + 1), (edge, Y + 1)])
    return shapes, d


def _inside(pts: np.ndarray, poly) -> np.ndarray:
    """Vectorised ray casting. pts (..., 2); poly list of (x, y)."""
    x, y = pts[..., 0], pts[..., 1]
    inside = np.zeros(x.shape, dtype=bool)
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        cond = ((y1 > y) != (y2 > y))
        with np.errstate(divide="ignore", invalid="ignore"):
            xint = (x2 - x1) * (y - y1) / (y2 - y1 + 1e-12) + x1
        inside ^= cond & (x < xint)
    return inside


def scene_at(events: list[dict], t: int, L: Layout, G: float) -> dict:
    """Light on every cell of every panel at minute t, and one irradiance per strip."""
    centres = L.cell_centres()
    T = np.ones(centres.shape[:2])
    drawn = []
    for ev in events:
        shapes, d = event_shapes(ev, t, L)
        if shapes == "all":
            T *= (1 - d)
            drawn.append((ev["kind"], "all"))
            continue
        for poly in shapes:
            T *= 1 - d * _inside(centres, poly)
            drawn.append((ev["kind"], poly))
    _, _, strip = L.cell_grid()
    sub = np.zeros((L.n_panels, L.n_sub))
    cover = np.zeros((L.n_panels, L.n_sub))
    for k in range(L.n_sub):
        m = strip == k
        sub[:, k] = G * T[:, m].min(axis=1)           # weakest cell sets the strip
        cover[:, k] = (T[:, m] < 0.999).mean(axis=1)  # share of the strip in shade
    return dict(T=T, sub=np.round(sub, 1), cover=cover, drawn=drawn)


def shadow_type(cover_row: np.ndarray) -> str:
    """Plain-language geometry for one panel from its per-strip shaded share."""
    shaded = cover_row > 0.001
    if not shaded.any():
        return "No shadow"
    if np.all(cover_row[shaded] > 0.95):
        return "Along the strips"
    return "Across the strips"


# --------------------------------------------------------------------------- #
# Figures
# --------------------------------------------------------------------------- #
def array_figure(L: Layout, scene: dict, selected: int, powers: list[float],
                 colors: dict, panel_fill="#26404F", line="#3E6076", ground="#EFEDE6",
                 accent="#B5641A") -> go.Figure:
    X, Y = L.extent
    w, h = L.size
    fig = go.Figure()
    shapes = []
    for i in range(L.n_panels):
        x0, y0, x1, y1 = L.rect(i)
        shapes.append(dict(type="rect", x0=x0, y0=y0, x1=x1, y1=y1, fillcolor=panel_fill,
                           line=dict(color=line, width=1), layer="below"))
        if (L.ns // L.n_sub) % L.cell_rows == 0:       # strips are whole column groups
            for k in range(1, L.n_sub):
                f = k / L.n_sub
                if L.portrait:
                    shapes.append(dict(type="line", x0=x0 + f * w, x1=x0 + f * w, y0=y0, y1=y1,
                                       line=dict(color="#6F8FA3", width=1), layer="below"))
                else:
                    shapes.append(dict(type="line", y0=y1 - f * h, y1=y1 - f * h, x0=x0, x1=x1,
                                       line=dict(color="#6F8FA3", width=1), layer="below"))
    for kind, poly in scene["drawn"]:
        if poly == "all":
            shapes.append(dict(type="rect", x0=-1, y0=-1, x1=X + 1, y1=Y + 1,
                               fillcolor="rgba(120,120,120,0.18)", line=dict(width=0)))
            continue
        path = "M " + " L ".join(f"{px:.3f},{py:.3f}" for px, py in poly) + " Z"
        shapes.append(dict(type="path", path=path, fillcolor="rgba(16,26,32,0.55)", line=dict(width=0)))
    x0, y0, x1, y1 = L.rect(selected)
    shapes.append(dict(type="rect", x0=x0, y0=y0, x1=x1, y1=y1, line=dict(color=accent, width=3)))

    cx = [(L.rect(i)[0] + L.rect(i)[2]) / 2 for i in range(L.n_panels)]
    cy = [(L.rect(i)[1] + L.rect(i)[3]) / 2 for i in range(L.n_panels)]
    ids = [L.panel_id(i) for i in range(L.n_panels)]
    fig.add_trace(go.Scatter(
        x=cx, y=cy, mode="markers+text", customdata=list(range(L.n_panels)),
        text=ids, textfont=dict(color="rgba(255,255,255,0.75)", size=10, family="IBM Plex Mono, monospace"),
        marker=dict(symbol="square", size=34, color="rgba(0,0,0,0.001)"),
        hovertemplate="%{text}<br>%{meta}<extra></extra>",
        meta=[f"{p:.0f} W at its true peak" for p in powers], showlegend=False))
    fig.update_layout(shapes=shapes, height=400, margin=dict(l=8, r=8, t=8, b=8),
                      plot_bgcolor=ground, paper_bgcolor=ground, dragmode=False,
                      clickmode="event+select", hovermode="closest")
    fig.update_xaxes(visible=False, range=[-0.3, X + 0.3], fixedrange=True)
    fig.update_yaxes(visible=False, range=[-0.3, Y + 0.3], scaleanchor="x", fixedrange=True)
    return fig


def face_figure(L: Layout, T_panel: np.ndarray, height=230) -> go.Figure:
    """The selected panel seen from the front, cell by cell."""
    col, row, strip = L.cell_grid()
    z = np.ones((L.cell_rows, L.cell_cols))
    for idx in range(L.ns):
        z[row[idx], col[idx]] = T_panel[idx]
    if not L.portrait:
        z = z.T
    fig = go.Figure(go.Heatmap(z=z, zmin=0, zmax=1, showscale=False, xgap=2, ygap=2,
                               colorscale=[[0, "#0B1418"], [0.5, "#1B2F3A"], [1, "#3E6076"]],
                               hovertemplate="light %{z:.0%}<extra></extra>"))
    per = L.ns // L.n_sub
    shapes = []
    if per % L.cell_rows == 0:
        cols_per = per // L.cell_rows
        for k in range(1, L.n_sub):
            v = k * cols_per - 0.5
            shapes.append(dict(type="line", x0=v, x1=v, y0=-0.5, y1=L.cell_rows - 0.5,
                               line=dict(color="#B5641A", width=2)) if L.portrait else
                          dict(type="line", y0=v, y1=v, x0=-0.5, x1=L.cell_rows - 0.5,
                               line=dict(color="#B5641A", width=2)))
    fig.update_layout(shapes=shapes, height=height, margin=dict(l=4, r=4, t=4, b=4),
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    fig.update_xaxes(visible=False, fixedrange=True)
    fig.update_yaxes(visible=False, autorange="reversed", scaleanchor="x", fixedrange=True)
    return fig


def timeline_figure(events: list[dict], t: int, peaks: list[tuple[int, int]], colors: dict,
                    accent="#B5641A", teal="#16616B") -> go.Figure:
    kinds = [k for k in EVENT_KINDS if any(e["kind"] == k for e in events)] or ["Cloud"]
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.78, 0.22], vertical_spacing=0.06)
    for e in events:
        s, en = to_min(e["start"]), to_min(e["end"])
        yi = kinds.index(e["kind"])
        fig.add_trace(go.Bar(x=[max(en - s, 4)], base=[s], y=[e["kind"]], orientation="h",
                             marker=dict(color=colors.get(e["kind"], "#C2BFB6"), line=dict(width=0)),
                             width=0.62, showlegend=False,
                             hovertemplate=f"{e['kind']}<br>{e['start']}–{e['end']}"
                                           f"<br>depth {e.get('depth', 0)}%<extra></extra>"), row=1, col=1)
    # peaks on the selected panel's curve through the day
    shade = {1: "#E3DFD4", 2: "#9BBDBF", 3: teal}
    for (m, n) in peaks:
        fig.add_trace(go.Bar(x=[20], base=[m], y=["Peaks"], orientation="h", width=0.9,
                             marker=dict(color=shade.get(min(n, 3), teal), line=dict(width=0)),
                             showlegend=False, hovertemplate=f"{fmt_min(m)} · {n} peak(s)<extra></extra>"),
                      row=2, col=1)
    for r in (1, 2):
        fig.add_vline(x=t, line=dict(color=accent, width=2), row=r, col=1)
    ticks = list(range(DAY_START, DAY_END + 1, 120))
    fig.update_xaxes(range=[DAY_START, DAY_END], tickvals=ticks, ticktext=[fmt_min(v) for v in ticks],
                     showgrid=True, fixedrange=True, row=2, col=1)
    fig.update_xaxes(range=[DAY_START, DAY_END], showticklabels=False, fixedrange=True, row=1, col=1)
    fig.update_yaxes(categoryorder="array", categoryarray=list(reversed(kinds)), fixedrange=True, row=1, col=1)
    fig.update_yaxes(fixedrange=True, row=2, col=1)
    fig.update_layout(barmode="overlay", height=90 + 34 * len(kinds), margin=dict(l=8, r=8, t=8, b=8),
                      bargap=0.3)
    return fig