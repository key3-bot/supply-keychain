#!/usr/bin/env python3
"""Cart-double pendulum — pristine layout + FK. Units: mm.

Convention (CAD Z-up):
  X = rail travel
  Y = lateral (joint shaft axis)
  Z = up

  Shoulder pivot at cart top center.
  Link local: length along +Z (hanging down is world -Z after R_y).
  Angle 0 = hanging straight down.
  Positive shoulder/elbow = swing toward +X (right-hand about +Y).

Parts are authored in local frames and posed by the viewer.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

# --- rail / cart ---
RAIL_LEN = 420.0
RAIL_W = 28.0
RAIL_H = 14.0

CART_L = 96.0
CART_W = 64.0
CART_H = 32.0
CART_Z0 = RAIL_H  # cart bottom on rail top
CART_TOP = CART_Z0 + CART_H

# Shoulder pivot (world when travel=0)
SHOULDER_X = 0.0
SHOULDER_Y = 0.0
SHOULDER_Z = CART_TOP + 8.0  # slightly above cart deck

# Shaft / bearings
SHAFT_D = 8.0
BEARING_ID = 8.0
BEARING_OD = 22.0
BEARING_W = 7.0

# SRC012-12 / Adafruit 1195
SLIP_OD = 12.4
SLIP_L = 19.5
SLIP_BORE = 4.2

# Links (local length along +Z from proximal pivot)
LINK1_L = 180.0
LINK1_W = 18.0
LINK1_T = 12.0  # thickness along Y (shaft axis)

LINK2_L = 120.0
LINK2_W = 14.0
LINK2_T = 10.0

# AS5047P-TS_EK_AB
AS_BOARD = (28.0, 22.0, 1.6)
AS_HOLES = ((3.0, 3.0), (25.0, 3.0), (3.0, 19.0), (25.0, 19.0))
AS_HOLE_R = 1.3
MAGNET_D = 6.0
MAGNET_H = 2.5

# AMT102-V envelope
AMT_R = 15.5
AMT_BODY_H = 10.5
AMT_BASE_H = 12.0

TEENSY = (61.0, 17.78, 4.0)

# Default rest pose (hanging + mild bend) — used only for static FreeCAD screenshot
POSE_SHOULDER0 = math.radians(25.0)
POSE_ELBOW0 = math.radians(-40.0)


def shoulder_origin(travel: float = 0.0) -> tuple[float, float, float]:
    return (travel + SHOULDER_X, SHOULDER_Y, SHOULDER_Z)


def link_dir(abs_angle: float) -> tuple[float, float, float]:
    """Unit direction of a link at absolute angle from downward (-Z)."""
    # a=0 → (0,0,-1); a=+90° → (+1,0,0)
    return (math.sin(abs_angle), 0.0, -math.cos(abs_angle))


def elbow_origin(travel: float, shoulder: float) -> tuple[float, float, float]:
    ox, oy, oz = shoulder_origin(travel)
    dx, dy, dz = link_dir(shoulder)
    return (ox + dx * LINK1_L, oy + dy * LINK1_L, oz + dz * LINK1_L)


def tip_origin(travel: float, shoulder: float, elbow: float) -> tuple[float, float, float]:
    ex, ey, ez = elbow_origin(travel, shoulder)
    a = shoulder + elbow
    dx, dy, dz = link_dir(a)
    return (ex + dx * LINK2_L, ey + dy * LINK2_L, ez + dz * LINK2_L)


def kinematics_json() -> dict:
    return {
        "units": "mm",
        "up": "Z",
        "rail": {"len": RAIL_LEN, "w": RAIL_W, "h": RAIL_H},
        "cart": {"l": CART_L, "w": CART_W, "h": CART_H, "z0": CART_Z0, "top": CART_TOP},
        "shoulder": {"x": SHOULDER_X, "y": SHOULDER_Y, "z": SHOULDER_Z},
        "shaftD": SHAFT_D,
        "bearing": {"id": BEARING_ID, "od": BEARING_OD, "w": BEARING_W},
        "slipRing": {"od": SLIP_OD, "l": SLIP_L, "bore": SLIP_BORE},
        "link1": {"l": LINK1_L, "w": LINK1_W, "t": LINK1_T},
        "link2": {"l": LINK2_L, "w": LINK2_W, "t": LINK2_T},
        "as5047p": {"board": list(AS_BOARD), "magnetD": MAGNET_D, "magnetH": MAGNET_H},
        "amt102": {"r": AMT_R, "bodyH": AMT_BODY_H},
        "teensy": list(TEENSY),
        "angleZero": "hanging_down",
        "rotationAxis": "Y",
        "defaultPose": {
            "travel": 0.0,
            "shoulder": POSE_SHOULDER0,
            "elbow": POSE_ELBOW0,
        },
        "elbow0": list(elbow_origin(0.0, POSE_SHOULDER0)),
        "tip0": list(tip_origin(0.0, POSE_SHOULDER0, POSE_ELBOW0)),
    }


def main() -> None:
    k = kinematics_json()
    print(json.dumps(k, indent=2))
    out = Path("/tmp/pendulum-kinematics.json")
    out.write_text(json.dumps(k, indent=2))
    print("wrote", out)


if __name__ == "__main__":
    main()
