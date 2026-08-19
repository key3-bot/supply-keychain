#!/usr/bin/env python3
"""Dilating iris — swept comma that tiles shut and still opens.

Winner from parameter sweep:
  N=8, R_CLOSED=3.6, inner span 90°, outer fat +6°
  aperture Ø7.2 → Ø32.7 mm, closed coverage gaps=0
"""

from __future__ import annotations

import json
import math
from pathlib import Path

N = 12
R_PIVOT = 32.0
R_DRIVE = 40.0
R_WINDOW = 34.0
R_OUTER = 48.0
R_BLADE_OUTER = 43.0
R_CLOSED = 3.6
BLADE_THICK = 0.30
BLADE_PITCH = 0.0  # coplanar pack — overlap via tilt, not Z stack
BLADE_TILT = math.radians(5.5)  # same local lean on every leaf → cyclic over/under
BLADE_Z0 = 4.40  # mid-cavity so tilted edges stay inside the cup
RING_THICK = 1.8
COVER_THICK = 1.8
PIN_R = 1.05
BOSS_R = 2.4
# Housing cup: floor 0–2.6, wall 2.6–8.5, cover 8.5–10.3.
# Coplanar tilted pack centered ~4.4 mm. Rotor 6.55–8.35. Cover captures all of it.
STATOR_FLOOR = 2.6
WALL_TOP = 8.5
ROTOR_Z = 6.55
COVER_Z = 8.5

THETA_CLOSED = math.radians(10.0)
THETA_OPEN = math.radians(40.0)

INNER_SPAN = math.radians(100.0)
FAT = math.radians(4.0)


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


def _polar(r: float, a: float) -> tuple[float, float]:
    return (r * math.cos(a), r * math.sin(a))


def _arc(r: float, a0: float, a1: float, steps: int) -> list[tuple[float, float]]:
    return [_polar(r, a0 + (a1 - a0) * k / steps) for k in range(steps + 1)]


def _bezier(p0, p1, p2, steps: int) -> list[tuple[float, float]]:
    pts = []
    for k in range(1, steps + 1):
        t = k / steps
        u = 1.0 - t
        pts.append(
            (
                u * u * p0[0] + 2 * u * t * p1[0] + t * t * p2[0],
                u * u * p0[1] + 2 * u * t * p1[1] + t * t * p2[1],
            )
        )
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
    mid = 0.5 * THETA_CLOSED
    a0 = mid - 0.5 * INNER_SPAN
    a1 = mid + 0.5 * INNER_SPAN
    inner = _arc(R_CLOSED, a0, a1, 24)
    start, end = inner[0], inner[-1]

    dxy = drive_xy(0, THETA_CLOSED)
    d_ang = math.atan2(dxy[1], dxy[0])
    p_ang = 0.0
    a_out1 = d_ang + math.radians(4.0) + FAT
    a_out0 = p_ang - math.radians(8.0) - FAT
    d_out = _polar(R_BLADE_OUTER, a_out1)
    p_out = _polar(R_BLADE_OUTER, a_out0)

    lead_ctrl = (
        0.25 * end[0] + 0.55 * d_out[0] + 6.0 * math.cos(d_ang + 0.9),
        0.25 * end[1] + 0.55 * d_out[1] + 6.0 * math.sin(d_ang + 0.9),
    )
    trail_ctrl = (
        0.40 * p_out[0] + 0.40 * start[0] + 5.0 * math.cos(p_ang - 1.05),
        0.40 * p_out[1] + 0.40 * start[1] + 5.0 * math.sin(p_ang - 1.05),
    )
    poly = (
        inner
        + _bezier(end, lead_ctrl, d_out, 12)
        + _arc(R_BLADE_OUTER, a_out1, a_out0, 14)[1:]
        + _bezier(p_out, trail_ctrl, start, 12)[:-1]
    )
    return _clean(poly)


def blade_local_poly() -> list[tuple[float, float]]:
    local = [world_to_local(x, y, 0, THETA_CLOSED) for x, y in blade_world_closed()]
    poly = _clean(local)
    if _area(poly) < 0:
        poly.reverse()
    return poly


BLADE_POLY = blade_local_poly()

SLOT_IN = max(4.0, pin_sep(THETA_CLOSED) - 2.2)
SLOT_OUT = pin_sep(THETA_OPEN) + 2.8
SLOT_HALF = 1.15
ARM_HALF = 3.4

SLOT_ARM_POLY = [
    (2.0, -ARM_HALF),
    (SLOT_OUT + 2.8, -ARM_HALF),
    (SLOT_OUT + 2.8, ARM_HALF),
    (2.0, ARM_HALF),
]


def blade_world(i: int, theta: float) -> list[tuple[float, float]]:
    return [local_to_world(x, y, i, theta) for x, y in BLADE_POLY]


def _point_in_poly(x: float, y: float, poly: list[tuple[float, float]]) -> bool:
    inside = False
    m = len(poly)
    for i in range(m):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % m]
        if (y1 > y) != (y2 > y):
            xin = (x2 - x1) * (y - y1) / (y2 - y1 + 1e-15) + x1
            if x < xin:
                inside = not inside
    return inside


def coverage_gaps(theta: float, rings: int = 8, rays: int = 72) -> int:
    polys = [blade_world(i, theta) for i in range(N)]
    misses = 0
    r0 = R_CLOSED + 1.8
    r1 = 29.0
    for ri in range(rings):
        r = r0 + (r1 - r0) * ri / max(1, rings - 1)
        for s in range(rays):
            a = 2.0 * math.pi * s / rays
            x, y = r * math.cos(a), r * math.sin(a)
            if not any(_point_in_poly(x, y, p) for p in polys):
                misses += 1
    return misses


def aperture_radius(theta: float, samples: int = 180) -> float:
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
                if t > 0.2 and 0.0 <= u <= 1.0:
                    best = min(best, t)
        hit = min(hit, best)
    return hit


def validate() -> list[str]:
    notes = []
    prev = 0.0
    for t in (0.0, 0.25, 0.5, 0.75, 1.0):
        th = rotor_angle(t)
        lx, ly = world_to_local(*drive_xy(0, th), 0, th)
        d = 2 * aperture_radius(th)
        ok = abs(ly) < 1e-6 and SLOT_IN - 0.3 <= lx <= SLOT_OUT + 0.3
        notes.append(
            "t=%.2f pin=(%.2f,%.2f) sep=%.2f Ø=%.1f φ=%.1f gaps=%d ok=%s"
            % (t, lx, ly, pin_sep(th), d, math.degrees(blade_angle(0, th)), coverage_gaps(th), ok)
        )
        if t > 0 and d + 0.6 < prev:
            notes.append("  WARN aperture shrank")
        prev = d
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
        "closedGaps": coverage_gaps(THETA_CLOSED),
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
    draw.ellipse([xy(-R_WINDOW, R_WINDOW), xy(R_WINDOW, -R_WINDOW)], outline=(183, 192, 202, 160), width=2)

    colors = [
        (158, 168, 180, 210),
        (136, 146, 158, 210),
        (118, 128, 140, 210),
        (104, 114, 126, 210),
    ]
    for i in range(N):
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
        "%s  t=%.2f  Ø%.1f mm  gaps=%d" % (title, t, 2 * r, coverage_gaps(theta)),
        fill=(18, 32, 51, 255),
        font=font,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path)
    print("wrote", path, "Ø", round(2 * r, 2), "gaps", coverage_gaps(theta))


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
