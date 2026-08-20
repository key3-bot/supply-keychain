#!/usr/bin/env python3
"""Cart-double pendulum layout and kinematics. Units: mm.

Stack (CAD Z-up, X along rail, Y lateral):
  rail top z=10
  cart body z=10..32
  shoulder joint axis through cart at origin (x=0,y=0)
  link1 hangs/swings about shoulder
  elbow at end of link1
  link2 about elbow

Sensors / pass-throughs (datasheet envelopes):
  SRC012-12 slip ring: Ø12.4 × 19.5, bore ~Ø4 clearance for shaft
  AS5047P-TS_EK_AB: 28 × 22 × 1.6 PCB, magnet Ø6 × 2.5 on shaft
  AMT102-V: housing ~Ø31, overall ~28.8 tall on cart encoder shaft
  608-2Z bearings: ID8 OD22 W7
  Joint shaft: Ø8
"""

from __future__ import annotations

import json
import math
from pathlib import Path

# --- layout constants ---
RAIL_LEN = 400.0
RAIL_W = 22.0
RAIL_H = 10.0

CART_L = 90.0
CART_W = 58.0
CART_H = 28.0
CART_Z0 = RAIL_H  # sits on rail top

# Shoulder axis at cart centerline
SHOULDER_X = 0.0
SHOULDER_Y = 0.0

SHAFT_D = 8.0
BEARING_ID = 8.0
BEARING_OD = 22.0
BEARING_W = 7.0

SLIP_OD = 12.4
SLIP_L = 19.5
SLIP_BORE = 4.2

LINK1_L = 180.0
LINK1_W = 18.0
LINK1_T = 10.0
LINK1_BORE = 8.05

LINK2_L = 120.0
LINK2_W = 14.0
LINK2_T = 8.0

# Board envelopes
AS_BOARD = (28.0, 22.0, 1.6)
AS_HOLES = ((3.0, 3.0), (25.0, 3.0), (3.0, 19.0), (25.0, 19.0))
AS_HOLE_R = 1.3
MAGNET_D = 6.0
MAGNET_H = 2.5

AMT_R = 15.5
AMT_H = 28.77

TEENSY = (61.0, 17.78, 4.0)

# Vertical stack at shoulder (from cart floor local)
# cart floor at CART_Z0; shoulder shaft stands on cart midplane
CART_TOP = CART_Z0 + CART_H  # 38
SHOULDER_Z = CART_TOP  # joint plane at cart top face

# Slip ring sits in cart well, axis = shoulder
SLIP_A_Z0 = SHOULDER_Z - 4.0 - SLIP_L  # mostly inside cart pocket

# Link1 pivot boss sits above cart top bearings
LINK1_Z0 = SHOULDER_Z + 6.0  # underside of link1 at shoulder

# Elbow at far end of link1 (along link local +Z when hanging down inverted... 
# Convention: links extend in +Z when angles=0 means upright? 
# For desktop demo, angles=0 is hanging down in -Z lab frame is natural for cart pendulum.
# Use: link local +X along length, joint rotation about Y.
# At pose (0,0): both links hang down (-world Z).

ELBOW_ALONG = LINK1_L  # distance shoulder->elbow along link1

# Default static pose for FreeCAD export (radians): hanging + slight elbow bend
POSE_SHOULDER0 = math.radians(18.0)  # from downward vertical, toward +X
POSE_ELBOW0 = math.radians(-35.0)


def clamp(v, a, b):
    return max(a, min(b, v))


def cart_xy(travel: float = 0.0) -> tuple[float, float]:
    """Cart center XY; travel along rail X."""
    return (travel, 0.0)


def shoulder_origin(travel: float = 0.0) -> tuple[float, float, float]:
    cx, cy = cart_xy(travel)
    return (cx + SHOULDER_X, cy + SHOULDER_Y, SHOULDER_Z)


def rot_y(x, y, z, ang):
    c, s = math.cos(ang), math.sin(ang)
    # rotation about Y: x' = c*x + s*z, z' = -s*x + c*z
    return (c * x + s * z, y, -s * x + c * z)


def link1_frame(travel: float, shoulder: float):
    """Return origin + basis for link1. Length along local +X after hang baseline.

    Baseline: hanging down is rotation that maps link +X to world -Z.
    shoulder angle is measured from downward vertical toward +X (right-hand about +Y).
    """
    ox, oy, oz = shoulder_origin(travel)
    # downward direction = -Z; rotate about Y by shoulder from that.
    # point along link at distance L: start from (0,0,-L) then rotate about Y by shoulder
    # R_y(s) * (0,0,-L) = (s_s*L, 0, -c_s*L) wait:
    # R_y(s).(x,y,z) = (c x + s z, y, -s x + c z)
    # (0,0,-L) -> (-s L, 0, -c L)  so at s=0 hangs to -Z. Good.
    return {
        "origin": (ox, oy, oz),
        "shoulder": shoulder,
        "travel": travel,
    }


def elbow_origin(travel: float, shoulder: float) -> tuple[float, float, float]:
    ox, oy, oz = shoulder_origin(travel)
    # elbow at distance LINK1_L along hanging link
    s, c = math.sin(shoulder), math.cos(shoulder)
    # R_y(s).(LINK1_L, 0, 0) if length along +X after mapping hang...
    # Easier: unit direction of link1 from shoulder:
    # at shoulder=0: (0,0,-1); general: (sin(s), 0, -cos(s))
    dx, dy, dz = math.sin(shoulder), 0.0, -math.cos(shoulder)
    return (ox + dx * LINK1_L, oy + dy * LINK1_L, oz + dz * LINK1_L)


def tip_origin(travel: float, shoulder: float, elbow: float) -> tuple[float, float, float]:
    ex, ey, ez = elbow_origin(travel, shoulder)
    # link2 angle is absolute from downward, or relative to link1?
    # Use relative: absolute angle of link2 = shoulder + elbow
    a = shoulder + elbow
    dx, dy, dz = math.sin(a), 0.0, -math.cos(a)
    return (ex + dx * LINK2_L, ey + dy * LINK2_L, ez + dz * LINK2_L)


def link_direction(abs_angle: float) -> tuple[float, float, float]:
    return (math.sin(abs_angle), 0.0, -math.cos(abs_angle))


def kinematics_json() -> dict:
    return {
        "units": "mm",
        "rail": {"len": RAIL_LEN, "w": RAIL_W, "h": RAIL_H},
        "cart": {"l": CART_L, "w": CART_W, "h": CART_H, "z0": CART_Z0},
        "shaftD": SHAFT_D,
        "bearing": {"id": BEARING_ID, "od": BEARING_OD, "w": BEARING_W},
        "slipRing": {"od": SLIP_OD, "l": SLIP_L, "bore": SLIP_BORE},
        "link1": {"l": LINK1_L, "w": LINK1_W, "t": LINK1_T},
        "link2": {"l": LINK2_L, "w": LINK2_W, "t": LINK2_T},
        "as5047p": {"board": AS_BOARD, "magnetD": MAGNET_D, "magnetH": MAGNET_H},
        "amt102": {"r": AMT_R, "h": AMT_H},
        "teensy": TEENSY,
        "shoulderZ": SHOULDER_Z,
        "defaultPose": {"travel": 0.0, "shoulder": POSE_SHOULDER0, "elbow": POSE_ELBOW0},
        "elbow0": elbow_origin(0.0, POSE_SHOULDER0),
        "tip0": tip_origin(0.0, POSE_SHOULDER0, POSE_ELBOW0),
    }


def main():
    k = kinematics_json()
    print(json.dumps(k, indent=2))
    out = Path("/tmp/pendulum-kinematics.json")
    out.write_text(json.dumps(k, indent=2))
    print("wrote", out)


if __name__ == "__main__":
    main()
