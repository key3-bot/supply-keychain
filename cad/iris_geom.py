#!/usr/bin/env python3
"""Dilating iris — clean comma blades, offset pitch circles, sliding slot.

Units: mm. Blade local: pivot at origin, +X toward the drive pin / slot.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

N = 8
R_PIVOT = 32.0
R_DRIVE = 40.0
R_WINDOW = 35.0
R_OUTER = 48.0
R_BLADE_OUTER = 43.5
R_CLOSED = 6.0
BLADE_THICK = 0.70
RING_THICK = 2.8
COVER_THICK = 1.8
PIN_R = 1.05
BOSS_R = 3.2
SLOT_IN = 6.0
SLOT_OUT = 26.5
SLOT_HALF = 1.2

# Drive-ring travel. Offset radii give a large blade swing.
THETA_CLOSED = math.radians(10.0)
THETA_OPEN = math.radians(40.0)

# Closed-pose inner edge: arc of the small aperture circle.
INNER_A0 = math.radians(-42.0)
INNER_A1 = math.radians(78.0)


def clamp01(t: float) -> float:
    return max(0.0, min(1.0, t))


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * clamp01(t)


def rotor_angle(t: float) -> float:
    return lerp(THETA_CLOSED, THETA_OPEN, t)


def pivot_xy(i: int) -> tuple[float, float]:
    a = 2.0 * math.pi * i / N
    return (R_PIVOT * math.cos(a), R_PIVOT * math.sin(a))


def drive_xy(i: int, theta: float) -> tuple[float, float]:
    a = 2.0 * math.pi * i / N + theta
    return (R_DRIVE * math.cos(a), R_DRIVE * math.sin(a))


def blade_angle(i: int, theta: float) -> float:
    px, py = pivot_xy(i)
    dx, dy = drive_xy(i, theta)
    return math.atan2(dy - py, dx - px)


def local_to_world(x: float, y: float, i: int, theta: float) -> tuple[float, float]:
    px, py = pivot_xy(i)
    ang = blade_angle(i, theta)
    c, s = math.cos(ang), math.sin(ang)
    return (px + x * c - y * s, py + x * s + y * c)


def world_to_local(x: float, y: float, i: int, theta: float) -> tuple[float, float]:
    px, py = pivot_xy(i)
    ang = blade_angle(i, theta)
    dx, dy = x - px, y - py
    c, s = math.cos(ang), math.sin(ang)
    return (dx * c + dy * s, -dx * s + dy * c)


def _arc(cx: float, cy: float, r: float, a0: float, a1: float, steps: int) -> list[tuple[float, float]]:
    pts = []
    for k in range(steps + 1):
        a = a0 + (a1 - a0) * k / steps
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def _bezier(p0, p1, p2, steps: int) -> list[tuple[float, float]]:
    pts = []
    for k in range(1, steps + 1):
        t = k / steps
        u = 1.0 - t
        x = u * u * p0[0] + 2 * u * t * p1[0] + t * t * p2[0]
        y = u * u * p0[1] + 2 * u * t * p1[1] + t * t * p2[1]
        pts.append((x, y))
    return pts


def blade_world_closed() -> list[tuple[float, float]]:
    """One simple comma: inner aperture arc → drive → outer → pivot → back."""
    px, py = pivot_xy(0)
    dx, dy = drive_xy(0, THETA_CLOSED)

    inner = _arc(0.0, 0.0, R_CLOSED, INNER_A0, INNER_A1, 22)
    start = inner[0]
    end = inner[-1]

    # Outer points just beyond the two pins, on the housing side.
    d_ang = math.atan2(dy, dx)
    p_ang = math.atan2(py, px)
    d_out = (R_BLADE_OUTER * math.cos(d_ang), R_BLADE_OUTER * math.sin(d_ang))
    p_out = (R_BLADE_OUTER * math.cos(p_ang), R_BLADE_OUTER * math.sin(p_ang))

    # Lead: inner end out to the drive pin, bulging away from the hole.
    lead_ctrl = (
        0.35 * end[0] + 0.65 * d_out[0] + 6.0 * math.cos(d_ang + 0.7),
        0.35 * end[1] + 0.65 * d_out[1] + 6.0 * math.sin(d_ang + 0.7),
    )
    lead = _bezier(end, lead_ctrl, d_out, 12)

    # Short outer rim from drive to pivot.
    # Walk the smaller positive sweep from d_ang toward p_ang (p_ang is 0).
    outer = _arc(0.0, 0.0, R_BLADE_OUTER, d_ang, p_ang, 10)[1:]

    # Trail: pivot back down to the inner start.
    trail_ctrl = (
        0.40 * p_out[0] + 0.60 * start[0] + 5.0 * math.cos(p_ang - 0.9),
        0.40 * p_out[1] + 0.60 * start[1] + 5.0 * math.sin(p_ang - 0.9),
    )
    trail = _bezier(p_out, trail_ctrl, start, 12)[:-1]

    return inner + lead + outer + trail


def _clean(poly: list[tuple[float, float]]) -> list[tuple[float, float]]:
    out = []
    for p in poly:
        if not out or (p[0] - out[-1][0]) ** 2 + (p[1] - out[-1][1]) ** 2 > 0.03:
            out.append(p)
    if len(out) > 2 and (out[0][0] - out[-1][0]) ** 2 + (out[0][1] - out[-1][1]) ** 2 < 0.03:
        out.pop()
    return out


BLADE_POLY = _clean([world_to_local(x, y, 0, THETA_CLOSED) for x, y in blade_world_closed()])

# Material around the sliding drive pin so it stays on the leaf when open.
SLOT_ARM_POLY = [
    (2.2, -3.6),
    (SLOT_OUT + 3.4, -3.6),
    (SLOT_OUT + 3.4, 3.6),
    (2.2, 3.6),
]


def blade_world(i: int, theta: float) -> list[tuple[float, float]]:
    return [local_to_world(x, y, i, theta) for x, y in BLADE_POLY]


def aperture_radius(theta: float, samples: int = 120) -> float:
    polys = [blade_world(i, theta) for i in range(N)]
    hit = R_WINDOW
    for s in range(samples):
        a = 2.0 * math.pi * s / samples
        ux, uy = math.cos(a), math.sin(a)
        best = R_WINDOW
        for poly in polys:
            m = len(poly)
            for j in range(m):
                x1, y1 = poly[j]
                x2, y2 = poly[(j + 1) % m]
                sx, sy = x2 - x1, y2 - y1
                den = ux * sy - uy * sx
                if abs(den) < 1e-9:
                    continue
                t = (x1 * sy - y1 * sx) / den
                u = (x1 * uy - y1 * ux) / den
                if t > 0.35 and 0.0 <= u <= 1.0:
                    best = min(best, t)
        hit = min(hit, best)
    return hit


def pin_sep(theta: float) -> float:
    px, py = pivot_xy(0)
    dx, dy = drive_xy(0, theta)
    return math.hypot(dx - px, dy - py)


def kinematics_json() -> dict:
    return {
        "n": N,
        "rPivot": R_PIVOT,
        "rDrive": R_DRIVE,
        "rWindow": R_WINDOW,
        "rOuter": R_OUTER,
        "rClosed": R_CLOSED,
        "thetaClosed": THETA_CLOSED,
        "thetaOpen": THETA_OPEN,
        "blade": BLADE_POLY,
        "pinR": PIN_R,
        "bossR": BOSS_R,
        "slotIn": SLOT_IN,
        "slotOut": SLOT_OUT,
        "slotHalf": SLOT_HALF,
        "bladeThick": BLADE_THICK,
        "ringThick": RING_THICK,
        "coverThick": COVER_THICK,
        "apertureClosed": aperture_radius(THETA_CLOSED),
        "apertureOpen": aperture_radius(THETA_OPEN),
        "pinSepClosed": pin_sep(THETA_CLOSED),
        "pinSepOpen": pin_sep(THETA_OPEN),
    }


def render_preview(path: Path, t: float, title: str) -> None:
    from PIL import Image, ImageDraw, ImageFont

    size = 920
    scale = 8.8
    img = Image.new("RGB", (size, size), (243, 246, 251))
    draw = ImageDraw.Draw(img, "RGBA")
    cx = cy = size // 2
    theta = rotor_angle(t)

    def xy(x, y):
        return (cx + x * scale, cy - y * scale)

    draw.ellipse([xy(-R_OUTER, R_OUTER), xy(R_OUTER, -R_OUTER)], outline=(138, 148, 161, 255), width=6)
    draw.ellipse([xy(-R_WINDOW, R_WINDOW), xy(R_WINDOW, -R_WINDOW)], outline=(183, 192, 202, 220), width=2)

    colors = [
        (158, 168, 180, 230),
        (136, 146, 158, 230),
        (118, 128, 140, 230),
        (104, 114, 126, 230),
    ]
    for i in range(N):
        pts = [xy(*p) for p in blade_world(i, theta)]
        if len(pts) > 3:
            draw.polygon(pts, fill=colors[i % len(colors)], outline=(40, 48, 58, 255))
        px, py = pivot_xy(i)
        dx, dy = drive_xy(i, theta)
        pr = 2.0 * scale / 2
        draw.ellipse([xy(px, py)[0] - pr, xy(px, py)[1] - pr, xy(px, py)[0] + pr, xy(px, py)[1] + pr], fill=(201, 162, 39, 255))
        draw.ellipse([xy(dx, dy)[0] - pr, xy(dx, dy)[1] - pr, xy(dx, dy)[0] + pr, xy(dx, dy)[1] + pr], fill=(196, 138, 0, 255))

    r = aperture_radius(theta)
    draw.ellipse([xy(-r, r), xy(r, -r)], outline=(10, 142, 163, 255), width=3)
    try:
        font = ImageFont.load_default()
    except Exception:
        font = None
    phi = math.degrees(blade_angle(0, theta))
    draw.text(
        (22, 18),
        f"{title}  t={t:.2f}  Ø{2 * r:.1f} mm  φ={phi:.1f}°  pts={len(BLADE_POLY)}",
        fill=(18, 32, 51, 255),
        font=font,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path)
    print("wrote", path, "aperture_d", round(2 * r, 2), "phi", round(phi, 2), "pin_sep", round(pin_sep(theta), 2))


def main() -> None:
    out = Path("/tmp/iris-preview")
    out.mkdir(exist_ok=True)
    print("local blade pts", len(BLADE_POLY))
    print(
        "closed",
        round(2 * aperture_radius(THETA_CLOSED), 2),
        "open",
        round(2 * aperture_radius(THETA_OPEN), 2),
        "sep",
        round(pin_sep(THETA_CLOSED), 2),
        "->",
        round(pin_sep(THETA_OPEN), 2),
    )
    render_preview(out / "closed.png", 0.0, "closed")
    render_preview(out / "mid.png", 0.5, "mid")
    render_preview(out / "open.png", 1.0, "open")
    Path("/tmp/iris-preview/kinematics.json").write_text(json.dumps(kinematics_json(), indent=2))


if __name__ == "__main__":
    main()
