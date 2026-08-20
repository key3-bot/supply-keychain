#!/usr/bin/env python3
"""Cart double-pendulum — buildable mating dims + FK. Units: mm.

CAD: Z-up, X = rail travel, Y = lateral (joint shaft axis).

Build intent
------------
Pendulum hangs **off the +Y side of the cart**, not through the deck.
Swing plane is XZ at y = SHOULDER_Y (outboard of cart & rail) so arms never
collide with cart body or rail at any angle.

Shoulder (fixed on cart)
  Twin cheeks on the +Y face, 608 bearings, Ø8 shaft.
  Link1 proximal hub fills the cheek gap and rotates with the shaft.
  Slip ring on outer (+Y) stub; magnet + AS5047P on inner (−Y) stub.

Elbow (on link1 distal)
  Clevis fork is part of link1; 608s in the tines.
  Link2 proximal hub fills the clevis gap (the second arm *is* the hub+spar).
  Same slip-ring / encoder pattern.

Angle 0 = hang straight down (−Z). +angle = toward +X (RH about +Y).
Local link frames: length along +Z from proximal pivot.
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

CART_L = 120.0
CART_W = 70.0
CART_H = 36.0
CART_Z0 = RAIL_H
CART_TOP = CART_Z0 + CART_H

# ── bearings / shaft (608ZZ) ─────────────────────────────────
SHAFT_D = 8.0
BEARING_ID = 8.0
BEARING_OD = 22.0
BEARING_W = 7.0
CHEEK_T = 8.0  # cheek / tine thickness along Y

SHOULDER_HUB_W = 16.0  # rotating hub width (Y) between cheek inners
ELBOW_HUB_W = 14.0


def cheek_span(hub_w: float) -> float:
    """Outer face-to-face of the two cheeks/tines."""
    return hub_w + 2.0 * CHEEK_T


# ── links (pivot-to-pivot along local +Z) ────────────────────
LINK1_L = 160.0
LINK2_L = 110.0

LINK1_ARM_R = 8.0
LINK2_ARM_R = 6.0

LINK1_HUB_R = 14.0
LINK2_HUB_R = 12.0

# Clevis gap = elbow hub + running clearance
LINK1_CLEVIS_GAP = ELBOW_HUB_W + 0.5
LINK1_CLEVIS_T = CHEEK_T
LINK1_CLEVIS_R = 15.0

TIP_R = 11.0
TIP_H = 22.0

# ── SRC012-12 slip ring ──────────────────────────────────────
SLIP_OD = 12.4
SLIP_L = 19.5
SLIP_BORE = 4.2

# ── AS5047P ──────────────────────────────────────────────────
AS_BOARD = (28.0, 22.0, 1.6)  # X, Z, Y-thickness
AS_HOLES = ((3.0, 3.0), (25.0, 3.0), (3.0, 19.0), (25.0, 19.0))
AS_HOLE_R = 1.3
MAGNET_D = 6.0
MAGNET_H = 2.5

# ── AMT102-V / Teensy ────────────────────────────────────────
AMT_R = 15.5
AMT_BODY_H = 10.5
AMT_BASE_H = 12.0
TEENSY = (61.0, 17.78, 4.0)

# ── shoulder outboard mount ──────────────────────────────────
# Cheeks sit on +Y face of cart. Pivot axis // Y through cheek centers.
# Hang plane y = SHOULDER_Y is fully outside cart (+CART_W/2) and rail.
SIDE_BRACKET = 22.0  # stand-off from cart +Y face to pivot center
SHOULDER_Y = CART_W / 2.0 + SIDE_BRACKET  # 35 + 22 = 57 mm
SHOULDER_X = 0.0
SHOULDER_Z = CART_TOP + 8.0  # 60 mm — above deck; hang is outboard

SWING_SHOULDER_MAX = math.radians(50.0)
SWING_ELBOW_MAX = math.radians(60.0)

POSE_SHOULDER0 = math.radians(20.0)
POSE_ELBOW0 = math.radians(-35.0)


def shoulder_origin(travel: float = 0.0) -> tuple[float, float, float]:
    return (travel + SHOULDER_X, SHOULDER_Y, SHOULDER_Z)


def link_dir(abs_angle: float) -> tuple[float, float, float]:
    """a=0 → (0,0,-1); a=+90° → (+1,0,0)."""
    return (math.sin(abs_angle), 0.0, -math.cos(abs_angle))


def elbow_origin(travel: float, shoulder: float) -> tuple[float, float, float]:
    ox, oy, oz = shoulder_origin(travel)
    dx, dy, dz = link_dir(shoulder)
    return (ox + dx * LINK1_L, oy + dy * LINK1_L, oz + dz * LINK1_L)


def tip_origin(travel: float, shoulder: float, elbow: float) -> tuple[float, float, float]:
    ex, ey, ez = elbow_origin(travel, shoulder)
    dx, dy, dz = link_dir(shoulder + elbow)
    return (ex + dx * LINK2_L, ey + dy * LINK2_L, ez + dz * LINK2_L)


def clears_cart(travel: float = 0.0, shoulder: float = 0.0, elbow: float = 0.0) -> bool:
    """Hang plane must stay outboard of cart +Y face (with hub radius margin)."""
    # Linkage lives in plane y = SHOULDER_Y. Hub extends ±LINK1_HUB_R along Y
    # only at the shoulder cheeks — those are *outside* the cart body by design.
    # Spar centerline stays at y = SHOULDER_Y for all angles (rotation about Y).
    return SHOULDER_Y - max(LINK1_ARM_R, LINK2_ARM_R) >= CART_W / 2.0 + 3.0


def kinematics_json() -> dict:
    checks = {
        "hang": clears_cart(0, 0, 0),
        "planeClearOfCart": SHOULDER_Y - LINK1_ARM_R >= CART_W / 2.0 + 3.0,
        "planeClearOfRail": SHOULDER_Y - LINK1_ARM_R >= RAIL_W / 2.0 + 5.0,
    }
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
        "sideBracket": SIDE_BRACKET,
        "cheekT": CHEEK_T,
        "shoulderHubW": SHOULDER_HUB_W,
        "elbowHubW": ELBOW_HUB_W,
        "cheekSpanShoulder": cheek_span(SHOULDER_HUB_W),
        "cheekSpanElbow": cheek_span(ELBOW_HUB_W),
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
            "clevisR": LINK1_CLEVIS_R,
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
            "yFromJoint": -(cheek_span(SHOULDER_HUB_W) / 2.0 + 7.0),
        },
        "amt102": {"r": AMT_R, "bodyH": AMT_BODY_H},
        "teensy": list(TEENSY),
        "angleZero": "hanging_down",
        "rotationAxis": "Y",
        "hangPlane": "outboard +Y, clears cart/rail",
        "clearanceChecks": checks,
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
    assert k["clearanceChecks"]["hang"], "hang plane collides cart"
    print("clearance OK", k["clearanceChecks"])


if __name__ == "__main__":
    main()
