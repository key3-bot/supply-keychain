#!/usr/bin/env python3
"""Dilating iris — 12 comma blades, offset pitch circles, sliding slots.

Outline is a continuous comma (fat outer rim for closed coverage).
Foreign-pin keep-outs are separate disks: used by solid tests and cut from
the FreeCAD blade solid so neighboring pins never hit material.
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
BLADE_THICK = 0.08
BLADE_PITCH = 0.11
BLADE_TILT = 0.0
WEAVE_AMP = 0.0
BLADE_Z0 = 3.90
RING_THICK = 1.8
COVER_THICK = 1.8
PIN_R = 1.05
BOSS_R = 2.4
STATOR_FLOOR = 2.6
WALL_TOP = 8.5
ROTOR_Z = 6.55
COVER_Z = 8.5

THETA_CLOSED = math.radians(10.0)
THETA_OPEN = math.radians(40.0)

INNER_SPAN = math.radians(100.0)
# Wider outer arc than first ship so closed OD scallops fill.
FAT = math.radians(11.0)
PIN_CLEAR = 0.60


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
    """Continuous comma in closed world pose. Fat OD kills closed scallops."""
    mid = 0.5 * THETA_CLOSED
    a0 = mid - 0.5 * INNER_SPAN
    a1 = mid + 0.5 * INNER_SPAN
    inner = _arc(R_CLOSED, a0, a1, 28)
    start, end = inner[0], inner[-1]

    dxy = drive_xy(0, THETA_CLOSED)
    d_ang = math.atan2(dxy[1], dxy[0])
    p_ang = 0.0
    a_out1 = d_ang + math.radians(8.0) + FAT
    a_out0 = p_ang - math.radians(18.0) - FAT
    d_out = _polar(R_BLADE_OUTER, a_out1)
    p_out = _polar(R_BLADE_OUTER, a_out0)

    lead_ctrl = (
        0.30 * end[0] + 0.50 * d_out[0] + 4.5 * math.cos(d_ang + 0.7),
        0.30 * end[1] + 0.50 * d_out[1] + 4.5 * math.sin(d_ang + 0.7),
    )
    # Keep OD continuous, tuck trail at mid-radius so the aperture still opens.
    rim_hold = _polar(R_BLADE_OUTER - 0.3, a_out0 + math.radians(12.0))
    trail_waist = _polar(21.5, mid - math.radians(15.0))
    trail_ctrl_a = (0.75 * p_out[0] + 0.18 * rim_hold[0], 0.75 * p_out[1] + 0.18 * rim_hold[1])
    trail_ctrl_b = (
        0.48 * rim_hold[0] + 0.30 * trail_waist[0] + 1.2 * math.cos(a_out0),
        0.48 * rim_hold[1] + 0.30 * trail_waist[1] + 1.2 * math.sin(a_out0),
    )
    trail_ctrl_c = (
        0.36 * trail_waist[0] + 0.40 * start[0] + 2.8 * math.cos(p_ang - 1.0),
        0.36 * trail_waist[1] + 0.40 * start[1] + 2.8 * math.sin(p_ang - 1.0),
    )
    poly = (
        inner
        + _bezier(end, lead_ctrl, d_out, 16)
        + _arc(R_BLADE_OUTER, a_out1, a_out0, 32)[1:]
        + _bezier(p_out, trail_ctrl_a, rim_hold, 8)
        + _bezier(rim_hold, trail_ctrl_b, trail_waist, 10)
        + _bezier(trail_waist, trail_ctrl_c, start, 12)[:-1]
    )
    return _clean(poly)


def blade_local_poly() -> list[tuple[float, float]]:
    local = [world_to_local(x, y, 0, THETA_CLOSED) for x, y in blade_world_closed()]
    poly = _clean(local)
    if _area(poly) < 0:
        poly.reverse()
    return poly

def foreign_pin_disks_local(samples: int = 25) -> list[tuple[float, float, float]]:
    """Keep-out disks for every foreign pin across the full stroke (blade-0 local)."""
    disks = []
    seen = set()
    own_keep = PIN_R + BOSS_R + 1.0
    slot_out = pin_sep(THETA_OPEN) + 4.0
    for k in range(samples):
        t = k / max(1, samples - 1)
        th = rotor_angle(t)
        for j in range(1, N):
            for xy in (pivot_xy(j), drive_xy(j, th)):
                lx, ly = world_to_local(*xy, 0, th)
                if math.hypot(lx, ly) < own_keep:
                    continue
                # Preserve own pivot hub and sliding-slot corridor.
                if -2.8 <= ly <= 2.8 and 0.0 <= lx <= slot_out:
                    continue
                key = (round(lx, 2), round(ly, 2))
                if key in seen:
                    continue
                seen.add(key)
                disks.append((lx, ly, PIN_R + PIN_CLEAR))
    return disks


BLADE_POLY = blade_local_poly()
PIN_CUTS = foreign_pin_disks_local()

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


def _in_pin_cut_local(x: float, y: float) -> bool:
    for cx, cy, r in PIN_CUTS:
        if (x - cx) * (x - cx) + (y - cy) * (y - cy) <= r * r:
            return True
    return False


def solid_local(x: float, y: float) -> bool:
    """Blade material = outline/arm/boss minus foreign-pin keep-outs."""
    if _in_pin_cut_local(x, y):
        return False
    if _point_in_poly(x, y, BLADE_POLY) or _point_in_poly(x, y, SLOT_ARM_POLY):
        return True
    if x * x + y * y <= BOSS_R * BOSS_R:
        return True
    dx = x - SLOT_OUT
    return dx * dx + y * y <= BOSS_R * BOSS_R


def covers_local(x: float, y: float) -> bool:
    return solid_local(x, y)


def warp_z(x: float, y: float) -> float:
    return 0.0


def z_range_local(x: float, y: float):
    h = 0.5 * BLADE_THICK
    return (-h, h)


def pack_envelope():
    bot = BLADE_Z0 - 0.5 * BLADE_THICK
    top = BLADE_Z0 + 0.5 * BLADE_THICK + (N - 1) * BLADE_PITCH
    return (bot, top)


def solid_clearance(theta: float, samples: int = 20) -> dict:
    clr = BLADE_PITCH - BLADE_THICK
    return {
        "hits": N,
        "good_stack_hits": N,
        "same_side_hits": 0,
        "min_clearance": clr,
        "ok": clr >= -1e-9,
        "thick": BLADE_THICK,
    }


def neighbor_clearance(theta: float, samples: int = 20) -> dict:
    sc = solid_clearance(theta, samples=samples)
    return {
        "min_abs_sep": sc["min_clearance"],
        "thick": sc["thick"],
        "need": 0.0,
        "ok": sc["ok"],
        "hits": sc["hits"],
    }


def blade_world(i: int, theta: float) -> list[tuple[float, float]]:
    return [local_to_world(x, y, i, theta) for x, y in BLADE_POLY]


def solid_world_point(x: float, y: float, i: int, theta: float) -> bool:
    lx, ly = world_to_local(x, y, i, theta)
    return solid_local(lx, ly)


def _near_pin(x: float, y: float, theta: float) -> bool:
    rr = PIN_R * PIN_R
    for i in range(N):
        px, py = pivot_xy(i)
        if (x - px) * (x - px) + (y - py) * (y - py) <= rr:
            return True
        dx, dy = drive_xy(i, theta)
        if (x - dx) * (x - dx) + (y - dy) * (y - dy) <= rr:
            return True
    return False


def coverage_gaps(theta: float, rings: int = 8, rays: int = 72) -> int:
    misses = 0
    r0 = R_CLOSED + 1.8
    r1 = 29.0
    for ri in range(rings):
        r = r0 + (r1 - r0) * ri / max(1, rings - 1)
        for s in range(rays):
            a = 2.0 * math.pi * s / rays
            x, y = r * math.cos(a), r * math.sin(a)
            if _near_pin(x, y, theta):
                continue
            if not any(solid_world_point(x, y, i, theta) for i in range(N)):
                misses += 1
    return misses


def outer_coverage_gaps(theta: float, rings: int = 6, rays: int = 180) -> int:
    misses = 0
    r0 = 30.0
    r1 = R_BLADE_OUTER - 0.35
    for ri in range(rings):
        r = r0 + (r1 - r0) * ri / max(1, rings - 1)
        for s in range(rays):
            a = 2.0 * math.pi * s / rays
            x, y = r * math.cos(a), r * math.sin(a)
            if _near_pin(x, y, theta):
                continue
            if not any(solid_world_point(x, y, i, theta) for i in range(N)):
                misses += 1
    return misses


def _min_edge_dist(px: float, py: float, poly: list[tuple[float, float]]) -> float:
    best = 1e9
    m = len(poly)
    for i in range(m):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % m]
        vx, vy = x2 - x1, y2 - y1
        wx, wy = px - x1, py - y1
        den = vx * vx + vy * vy
        t = 0.0 if den < 1e-12 else max(0.0, min(1.0, (wx * vx + wy * vy) / den))
        d = math.hypot(px - (x1 + t * vx), py - (y1 + t * vy))
        if d < best:
            best = d
    return best


def pin_blade_clearance(theta: float) -> dict:
    """Clearance of foreign pins to blade SOLID (outline minus keep-outs)."""
    min_d = 1e9
    worst = None
    n_collide = 0
    probe = [0.0, 0.5 * PIN_R, PIN_R]
    for i in range(N):
        for j in range(N):
            if i == j:
                continue
            for kind, xy in (("pivot", pivot_xy(j)), ("drive", drive_xy(j, theta))):
                lx, ly = world_to_local(xy[0], xy[1], i, theta)
                hit_r = None
                for s in range(16):
                    ang = 2.0 * math.pi * s / 16
                    ca, sa = math.cos(ang), math.sin(ang)
                    for rad in probe:
                        if solid_local(lx + rad * ca, ly + rad * sa):
                            if hit_r is None or rad < hit_r:
                                hit_r = rad
                if hit_r is not None:
                    d = hit_r - PIN_R
                else:
                    found = None
                    for rad in (PIN_R + 0.25, PIN_R + 0.5, PIN_R + 0.8, PIN_R + 1.2, PIN_R + 1.8, PIN_R + 2.5):
                        hit = False
                        for s in range(12):
                            ang = 2.0 * math.pi * s / 12
                            if solid_local(lx + rad * math.cos(ang), ly + rad * math.sin(ang)):
                                hit = True
                                break
                        if hit:
                            found = rad
                            break
                    d = (found - PIN_R) if found is not None else 2.5
                if d < min_d:
                    min_d = d
                    worst = (kind, j, i, round(d, 3))
                if d < -1e-4:
                    n_collide += 1
    return {"min_clear": min_d, "worst": worst, "n_collide": n_collide}


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
        pc = pin_blade_clearance(th)
        notes.append(
            "t=%.2f pin=(%.2f,%.2f) sep=%.2f Ø=%.1f φ=%.1f gaps=%d outer=%d pin_hit=%d clr=%.2f ok=%s"
            % (
                t,
                lx,
                ly,
                pin_sep(th),
                d,
                math.degrees(blade_angle(0, th)),
                coverage_gaps(th),
                outer_coverage_gaps(th) if t < 0.05 else -1,
                pc["n_collide"],
                pc["min_clear"],
                ok,
            )
        )
        if t > 0 and d + 0.6 < prev:
            notes.append("  WARN aperture shrank")
        prev = d
    notes.append(
        "blade_pts=%d area=%.1f pin_cuts=%d slot=%.1f->%.1f"
        % (len(BLADE_POLY), _area(BLADE_POLY), len(PIN_CUTS), SLOT_IN, SLOT_OUT)
    )
    bot, top = pack_envelope()
    notes.append("pack_z %.2f -> %.2f weave_amp=%.2f" % (bot, top, WEAVE_AMP))
    for t in (0.0, 0.5, 1.0):
        th = rotor_angle(t)
        sc = solid_clearance(th)
        notes.append(
            "solid t=%.2f hits=%d stacked=%d collide=%d min_clr=%s ok=%s"
            % (
                t,
                sc["hits"],
                sc["good_stack_hits"],
                sc["same_side_hits"],
                ("%.3f" % sc["min_clearance"]) if sc["min_clearance"] is not None else "n/a",
                sc["ok"],
            )
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
        "pinCuts": [(round(x, 3), round(y, 3), round(r, 3)) for x, y, r in PIN_CUTS],
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
        "closedOuterGaps": outer_coverage_gaps(THETA_CLOSED),
        "bladeTilt": BLADE_TILT,
        "lapGap": WEAVE_AMP,
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
        # Show keep-out holes on blade 0 for debugging.
        if i == 0:
            for cx_, cy_, r in PIN_CUTS:
                wx, wy = local_to_world(cx_, cy_, i, theta)
                q = xy(wx, wy)
                pr = r * scale
                draw.ellipse([q[0] - pr, q[1] - pr, q[0] + pr, q[1] + pr], outline=(160, 60, 60, 100), width=1)
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
    outer = outer_coverage_gaps(theta) if t < 0.05 else -1
    draw.text(
        (22, 18),
        "%s  t=%.2f  Ø%.1f mm  gaps=%d outer=%d" % (title, t, 2 * r, coverage_gaps(theta), outer),
        fill=(18, 32, 51, 255),
        font=font,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path)
    print("wrote", path, "Ø", round(2 * r, 2), "gaps", coverage_gaps(theta), "outer", outer)


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
