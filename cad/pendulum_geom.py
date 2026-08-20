#!/usr/bin/env python3
"""Cart double-pendulum — mating dimensions + FK. Units: mm.

CAD frame: Z-up, X = rail travel, Y = joint shaft axis.

Mechanical stack (shoulder & elbow share the same pattern)
----------------------------------------------------------
  Fixed cheeks (on cart for shoulder; on link1 distal for elbow)
    hold 608 bearings (OD22 / ID8 / W7).
  A rotating hub sits in the gap between cheeks and is pinned by the Ø8 shaft.
  The next link is fused to / clamped on that hub so the joint *fits* the arm.
  Slip ring rides the +Y shaft stub; magnet + AS5047P sit on the −Y stub.

Angle 0 = hanging straight down (−Z). Positive angle swings toward +X
(right-hand rule about +Y). Viewer poses local-frame meshes with FK.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

# ── rail / cart ──────────────────────────────────────────────
RAIL_LEN = 440.0
RAIL_W = 30.0
RAIL_H = 16.0
RAIL_FOOT_W = 48.0

CART_L = 110.0
CART_W = 72.0
CART_H = 34.0
CART_Z0 = RAIL_H
CART_TOP = CART_Z0 + CART_H

# ── bearings / shaft (608ZZ) ─────────────────────────────────
SHAFT_D = 8.0
BEARING_ID = 8.0
BEARING_OD = 22.0
BEARING_W = 7.0
CHEEK_T = 7.0  # cheek plate thickness along Y

# Gap between cheek *inner* faces — rotating hub lives here
SHOULDER_HUB_W = 14.0
ELBOW_HUB_W = 12.0

# Outer face-to-face of cheeks
def cheek_span(hub_w: float) -> float:
    return hub_w + 2.0 * CHEEK_T


# ── links ────────────────────────────────────────────────────
# Length = pivot-to-pivot along local +Z
LINK1_L = 170.0
LINK2_L = 115.0

# Arm cross-section (rounded bar)
LINK1_ARM_R = 7.0  # spar radius
LINK2_ARM_R = 5.5

# Proximal hub of link1 is the shoulder rotating hub
LINK1_HUB_R = 13.0  # radial size of hub (sits inside cheek gap)
LINK2_HUB_R = 11.0

# Distal clevis on link1 (holds elbow hub)
LINK1_CLEVIS_REACH = 18.0  # half-length of fork past pivot along ± nothing; fork depth
LINK1_CLEVIS_GAP = ELBOW_HUB_W + 0.4  # clearance around elbow hub
LINK1_CLEVIS_T = 5.5  # each fork tine thickness (Y)

# Tip mass
TIP_R = 10.0
TIP_H = 20.0

# ── slip ring SRC012-12 ──────────────────────────────────────
SLIP_OD = 12.4
SLIP_L = 19.5
SLIP_BORE = 4.2

# ── AS5047P-TS_EK_AB ─────────────────────────────────────────
AS_BOARD = (28.0, 22.0, 1.6)  # X, Z, Y-thickness when mounted facing −Y
AS_HOLES = ((3.0, 3.0), (25.0, 3.0), (3.0, 19.0), (25.0, 19.0))
AS_HOLE_R = 1.3
MAGNET_D = 6.0
MAGNET_H = 2.5

# ── AMT102-V ─────────────────────────────────────────────────
AMT_R = 15.5
AMT_BODY_H = 10.5
AMT_BASE_H = 12.0

# ── Teensy 4.1 envelope ──────────────────────────────────────
TEENSY = (61.0, 17.78, 4.0)

# Shoulder pivot height: through cheek centers above cart deck
SHOULDER_Z = CART_TOP + 16.0
SHOULDER_X = 0.0
SHOULDER_Y = 0.0

# Rest pose (for FCStd snapshot only)
POSE_SHOULDER0 = math.radians(28.0)
POSE_ELBOW0 = math.radians(-42.0)


def shoulder_origin(travel: float = 0.0) -> tuple[float, float, float]:
    return (travel + SHOULDER_X, SHOULDER_Y, SHOULDER_Z)


def link_dir(abs_angle: float) -> tuple[float, float, float]:
    """Unit direction of a link; a=0 → (0,0,-1), a=+90° → (+1,0,0)."""
    return (math.sin(abs_angle), 0.0, -math.cos(abs_angle))


def elbow_origin(travel: float, shoulder: float) -> tuple[float, float, float]:
    ox, oy, oz = shoulder_origin(travel)
    dx, dy, dz = link_dir(shoulder)
    return (ox + dx * LINK1_L, oy + dy * LINK1_L, oz + dz * LINK1_L)


def tip_origin(travel: float, shoulder: float, elbow: float) -> tuple[float, float, float]:
    ex, ey, ez = elbow_origin(travel, shoulder)
    dx, dy, dz = link_dir(shoulder + elbow)
    return (ex + dx * LINK2_L, ey + dy * LINK2_L, ez + dz * LINK2_L)


def kinematics_json() -> dict:
    return {
        "units": "mm",
        "up": "Z",
        "rail": {"len": RAIL_LEN, "w": RAIL_W, "h": RAIL_H},
        "cart": {
            "l": CART_L,
            "w": CART_W,
            "h": CART_H,
            "z0": CART_Z0,
            "top": CART_TOP,
        },
        "shoulder": {"x": SHOULDER_X, "y": SHOULDER_Y, "z": SHOULDER_Z},
        "cheekT": CHEEK_T,
        "shoulderHubW": SHOULDER_HUB_W,
        "elbowHubW": ELBOW_HUB_W,
        "shaftD": SHAFT_D,
        "bearing": {"id": BEARING_ID, "od": BEARING_OD, "w": BEARING_W},
        "slipRing": {"od": SLIP_OD, "l": SLIP_L, "bore": SLIP_BORE},
        "link1": {
            "l": LINK1_L,
            "armR": LINK1_ARM_R,
            "hubR": LINK1_HUB_R,
            "hubW": SHOULDER_HUB_W,
            "clevisGap": LINK1_CLEVIS_GAP,
            "clevisT": LINK1_CLEVIS_T,
        },
        "link2": {
            "l": LINK2_L,
            "armR": LINK2_ARM_R,
            "hubR": LINK2_HUB_R,
            "hubW": ELBOW_HUB_W,
            "tipR": TIP_R,
            "tipH": TIP_H,
        },
        "as5047p": {
            "board": list(AS_BOARD),
            "magnetD": MAGNET_D,
            "magnetH": MAGNET_H,
            # local offset from joint origin: board faces −Y
            "y": -(cheek_span(SHOULDER_HUB_W) / 2.0 + 6.0),
        },
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
        "hangExtent": abs(tip_origin(0.0, 0.0, 0.0)[2] - SHOULDER_Z) + TIP_R,
    }


def main() -> None:
    k = kinematics_json()
    print(json.dumps(k, indent=2))
    out = Path(__file__).resolve().parent / "exports" / "pendulum-kinematics.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(k, indent=2))
    print("wrote", out)


if __name__ == "__main__":
    main()
