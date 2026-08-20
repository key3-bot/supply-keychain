# Cart-double pendulum

**Kind:** assembly  
**Status:** design BOM  
**Repo:** https://github.com/key3-bot/cart-double-pendulum-policy  
**Demo:** /demo/supply-keychain.html (Pendulum tab)

Underactuated cart with two rotary links. One horizontal cart force must swing both links from hang to upright and hold them. Hardware needs a fast MCU, joint-angle sensing through rotating shafts, and a cart-position encoder.

## Required parts

| ID | Role | Qty | Why |
|---|---|---|---|
| [teensy-4.1](teensy-4.1.md) | microcontroller | 1 | 1 kHz control loop, SPI + quadrature |
| [slip-ring-12-wire](slip-ring-12-wire.md) | joint wiring | 2 | Power + encoder lines through shoulder and elbow |
| [as5047p](as5047p.md) | joint encoder | 2 | Absolute angle, no homing |
| [amt102-v](amt102-v.md) | cart encoder | 1 | Incremental cart travel |

## CAD (2026-08-20 pristine rebuild)

Fitted articulated assembly in `cad/cart-double-pendulum.FCStd` / viewer **Pendulum** mode:

- **Cart cheeks** hold 608 bearings; **link1 hub** seats in the cheek gap
- **Link1 distal clevis** holds elbow bearings; **link2 hub** seats in the fork
- Shoulder/elbow hardware: Ø8 shaft, slip ring, magnet, collar (local-frame STLs)
- Rounded spars, wire tunnels, tip mass fused on link2
- AS5047P on both joints, AMT102-V + Teensy on cart
- Viewer FK animates cart travel + double-link swing (no orphan wiring mesh)
- Rebuild: `freecad.cmd cad/run_pendulum.py`

Rail motor, driver, and PSU are still mechanical follow-ons.

## Crypto

Not wired. Buy via supplier carts for now.
