#!/usr/bin/env python3
"""2D preview of the dilating iris so blade overlap can be tuned before CAD."""

from __future__ import annotations

import math
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyBboxPatch, PathPatch, Wedge
from matplotlib.path import Path as MPath
import numpy as np

N = 8
R_PIVOT = 34.0
R_INNER_HOUSING = 40.0
R_OUTER_HOUSING = 48.0
R_DRIVE = 38.5
PHI_CLOSED = math.radians(8)
PHI_OPEN = math.radians(46)


def blade_local_polygon():
    """Comma-shaped blade in local coords. Pivot at origin. Housing center at (-R_PIVOT, 0)."""
    # Outer leaf body: ellipse-like set of points, then cut by an offset circle.
    ts = np.linspace(0, 2 * math.pi, 180, endpoint=False)
    body = np.column_stack((12.5 + 16.0 * np.cos(ts), 7.5 + 12.5 * np.sin(ts)))

    # Keep points outside the aperture-forming cutter and inside the housing.
    cx, cy, cr = 20.0, -9.5, 17.5
    hx, hy = -R_PIVOT, 0.0
    keep = []
    for x, y in body:
        if (x - cx) ** 2 + (y - cy) ** 2 < cr * cr:
            continue
        if (x - hx) ** 2 + (y - hy) ** 2 > (R_INNER_HOUSING + 1.2) ** 2:
            continue
        if x * x + y * y < 2.4**2:
            continue
        keep.append((x, y))

    # Guarantee a hub ring around the pivot so the blade always has material there.
    hub = [
        (3.2 * math.cos(t), 3.2 * math.sin(t))
        for t in np.linspace(0, 2 * math.pi, 36, endpoint=False)
    ]
    return np.array(keep), np.array(hub)


def transform(points, pivot_ang, phi):
    ang = pivot_ang + phi
    c, s = math.cos(ang), math.sin(ang)
    px, py = R_PIVOT * math.cos(pivot_ang), R_PIVOT * math.sin(pivot_ang)
    rot = np.array([[c, -s], [s, c]])
    return points @ rot.T + np.array([px, py])


def draw(path: Path, t: float, title: str):
    phi = PHI_CLOSED + t * (PHI_OPEN - PHI_CLOSED)
    fig, ax = plt.subplots(figsize=(7.2, 7.2), dpi=120)
    ax.set_aspect("equal")
    ax.set_xlim(-56, 56)
    ax.set_ylim(-56, 56)
    ax.axis("off")
    ax.set_facecolor("#f3f6fb")
    fig.patch.set_facecolor("#f3f6fb")

    ax.add_patch(Circle((0, 0), R_OUTER_HOUSING, fill=False, lw=2.2, ec="#8a94a1"))
    ax.add_patch(Circle((0, 0), R_INNER_HOUSING, fill=False, lw=1.2, ec="#b7c0ca"))
    ax.add_patch(Circle((0, 0), R_DRIVE, fill=False, lw=1.0, ls="--", ec="#c48a00", alpha=0.7))

    body, hub = blade_local_polygon()
    colors = ["#9aa4b0", "#868f9b", "#7a8490", "#6e7884"]
    for i in range(N):
        pang = i * 2 * math.pi / N
        pts = transform(body, pang, phi)
        if len(pts) > 3:
            ax.fill(pts[:, 0], pts[:, 1], color=colors[i % len(colors)], alpha=0.88, lw=0.4, ec="#3d4652")
        hpts = transform(hub, pang, phi)
        ax.fill(hpts[:, 0], hpts[:, 1], color="#c9a227", alpha=0.95, lw=0)
        ax.plot(*zip(*(R_PIVOT * math.cos(pang), R_PIVOT * math.sin(pang))), "o", color="#c48a00", ms=3)

    # Approximate aperture
    ax.add_patch(Circle((0, 0), 3 + 24 * t, fill=False, lw=1.4, ec="#0a8ea3"))
    ax.set_title(title, fontsize=11, color="#122033", pad=8)
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    print("wrote", path, "points", len(body))


def main():
    out = Path("/tmp/iris-preview")
    out.mkdir(exist_ok=True)
    draw(out / "closed.png", 0.0, "Iris closed")
    draw(out / "mid.png", 0.45, "Iris mid")
    draw(out / "open.png", 1.0, "Iris open")


if __name__ == "__main__":
    main()
