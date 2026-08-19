#!/usr/bin/env python3
"""Dilating iris — offset pitch circles, comma blades, sliding slots.

Units: mm.
Blade local: pivot at origin, +X through the drive pin / slot.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

N = 8
R_PIVOT = 32.0
R_DRIVE = 40.0
R_WINDOW = 34.0
R_OUTER = 48.0
R_BLADE_OUTER = 44.0
R_CLOSED = 6.0
BLADE_THICK = 0.70
RING_THICK = 2.8
COVER_THICK = 1.8
PIN_R = 1.05
BOSS_R = 3.2

# Offset radii give a large blade swing and a real aperture change.
THETA_CLOSED = math.radians(10.0)
THETA_OPEN = math.radians(40.0)

# Closed-pose inner edge on the small aperture circle.
INNER_A0 = math.radians(-40.0)
INNER_A1 = math.radians(82.0)


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


def pin_sep(theta: float) -> float:
    px, py = pivot_xy(0)
    dx, dy = drive_xy(0, theta)
    return math.hypot(dx - px, dy - py)


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


def _clean(poly: list[tuple[float, float]], eps: float = 0.04) -> list[tuple[float, float]]:
    out = []
    for p in poly:
        if not out or (p[0] - out[-1][0]) ** 2 + (p[1] - out[-1][1]) ** 2 > eps * eps:
            out.append(p)
    if len(out) > 2 and (out[0][0] - out[-1][0]) ** 2 + (out[0][1] - out[-1][1]) ** 2 < eps * eps:
        out.pop()
    return out


def _area(poly: list[tuple[float, float]]) -> float:
    a = 0.0
    m = len(poly)
    for i in range(m):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % m]
        a += x1 * y2 - x2 * y1
    return 0.5 * a


def blade_world_closed() -> list[tuple[float, float]]:
    """Comma leaf for blade 0 in world coords at the closed pose."""
    px, py = pivot_xy(0)
    dx, dy = drive_xy(0, THETA_CLOSED)

    inner = _arc(0.0, 0.0, R_CLOSED, INNER_A0, INNER_A1, 24)
    start = inner[0]
    end = inner[-1]

    d_ang = math.atan2(dy, dx)
    p_ang = math.atan2(py, px)

    # Lead: aperture end → outside drive pin → outer rim near drive.
    d_out = (
        R_BLADE_OUTER * math.cos(d_ang + math.radians(4)),
        R_BLADE_OUTER * math.sin(d_ang + math.radians(4)),
    )
    lead_ctrl = (
        0.30 * end[0] + 0.70 * d_out[0] + 5.5 * math.cos(d_ang + 0.85),
        0.30 * end[1] + 0.70 * d_out[1] + 5.5 * math.sin(d_ang + 0.85),
    )
    lead = _bezier(end, lead_ctrl, d_out, 14)

    # Outer rim drive → pivot (short sweep).
    outer = _arc(0.0, 0.0, R_BLADE_OUTER, d_ang + math.radians(4), p_ang - math.radians(8), 12)[1:]

    # Trail: outer near pivot → below pivot → aperture start.
    p_out = (
        R_BLADE_OUTER * math.cos(p_ang - math.radians(8)),
        R_BLADE_OUTER * math.sin(p_ang - math.radians(8)),
    )
    trail_ctrl = (
        0.45 * p_out[0] + 0.55 * start[0] + 4.5 * math.cos(p_ang - 1.0),
        0.45 * p_out[1] + 0.55 * start[1] + 4.5 * math.sin(p_ang - 1.0),
    )
    trail = _bezier(p_out, trail_ctrl, start, 14)[:-1]

    return _clean(inner + lead + outer + trail)


def blade_local_poly() -> list[tuple[float, float]]:
    local = [world_to_local(x, y, 0, THETA_CLOSED) for x, y in blade_world_closed()]
    poly = _clean(local)
    if _area(poly) < 0:
        poly.reverse()
    return poly


BLADE_POLY = blade_local_poly()

# Pin always sits on local +X at distance pin_sep(theta). Cover full travel.
SLOT_IN = max(4.5, pin_sep(THETA_CLOSED) - 2.5)
SLOT_OUT = pin_sep(THETA_OPEN) + 3.0
SLOT_HALF = 1.2

# Wide arm fused into the solid so open-pose drive pins stay on the leaf.
SLOT_ARM_POLY = [
    (2.2, -5.0),
    (SLOT_OUT + 4.0, -5.0),
    (SLOT_OUT + 4.0, 5.0),
    (2.2, 5.0),
]


def blade_world(i: int, theta: float) -> list[tuple[float, float]]:
    return [local_to_world(x, y, i, theta) for x, y in BLADE_POLY]


def blade_draw_poly(i: int, theta: float) -> list[tuple[float, float]]:
    """Preview outline = leaf union rough arm box corners in world."""
    # Just draw the main leaf; arm is shown separately.
    return blade_world(i, theta)


def aperture_radius(theta: float, samples: int = 160) -> float:
    # Include arm so aperture accounts for the full solid.
    polys = []
    for i in range(N):
        leaf = blade_world(i, theta)
        arm = [local_to_world(x, y, i, theta) for x, y in SLOT_ARM_POLY]
        polys.append(leaf)
        polys.append(arm)
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


def validate() -> list[str]:
    notes = []
    for t in (0.0, 0.25, 0.5, 0.75, 1.0):
        th = rotor_angle(t)
        lx, ly = world_to_local(*drive_xy(0, th), 0, th)
        ok = abs(ly) < 1e-6 and SLOT_IN - 0.3 <= lx <= SLOT_OUT + 0.3
        notes.append(
            "t=%.2f pin=(%.2f,%.2f) sep=%.2f Ø=%.1f φ=%.1f ok=%s"
            % (t, lx, ly, pin_sep(th), 2 * aperture_radius(th), math.degrees(blade_angle(0, th)), ok)
        )
    notes.append(
        "blade_pts=%d area=%.1f slot=%.1f->%.1f"
        % (len(BLADE_POLY), _area(BLADE_POLY), SLOT_IN, SLOT_OUT)
    )
    return notes


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
        "slotArm": SLOT_ARM_POLY,
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
    draw.ellipse([xy(-R_WINDOW, R_WINDOW), xy(R_WINDOW, -R_WINDOW)], outline=(183, 192, 202, 180), width=2)
    draw.ellipse([xy(-R_PIVOT, R_PIVOT), xy(R_PIVOT, -R_PIVOT)], outline=(201, 162, 39, 70), width=1)
    draw.ellipse([xy(-R_DRIVE, R_DRIVE), xy(R_DRIVE, -R_DRIVE)], outline=(196, 138, 0, 70), width=1)

    colors = [
        (158, 168, 180, 220),
        (136, 146, 158, 220),
        (118, 128, 140, 220),
        (104, 114, 126, 220),
    ]
    for i in range(N):
        arm = [xy(*local_to_world(x, y, i, theta)) for x, y in SLOT_ARM_POLY]
        draw.polygon(arm, fill=(120, 130, 142, 90), outline=(80, 90, 100, 120))
        pts = [xy(*p) for p in blade_world(i, theta)]
        if len(pts) > 3:
            draw.polygon(pts, fill=colors[i % len(colors)], outline=(40, 48, 58, 255))
        px, py = pivot_xy(i)
        dx, dy = drive_xy(i, theta)
        pr = 2.05 * scale / 2
        for x, y, col in ((px, py, (201, 162, 39, 255)), (dx, dy, (196, 138, 0, 255))):
            q = xy(x, y)
            draw.ellipse([q[0] - pr, q[1] - pr, q[0] + pr, q[1] + pr], fill=col)

    r = aperture_radius(theta)
    draw.ellipse([xy(-r, r), xy(r, -r)], outline=(10, 142, 163, 255), width=3)
    try:
        font = ImageFont.load_default()
    except Exception:
        font = None
    draw.text(
        (22, 18),
        "%s  t=%.2f  Ø%.1f mm  φ=%.1f°" % (title, t, 2 * r, math.degrees(blade_angle(0, theta))),
        fill=(18, 32, 51, 255),
        font=font,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path)
    print("wrote", path, "Ø", round(2 * r, 2))


def main() -> None:
    out = Path("/tmp/iris-preview")
    out.mkdir(exist_ok=True)
    for line in validate():
        print(line)
    render_preview(out / "closed.png", 0.0, "closed")
    render_preview(out / "mid.png", 0.5, "mid")
    render_preview(out / "open.png", 1.0, "open")
    Path("/tmp/iris-preview/kinematics.json").write_text(json.dumps(kinematics_json(), indent=2))


if __name__ == "__main__":
    main()
