# Cart-double pendulum

**Kind:** assembly  
**Status:** design BOM  
**Repo:** https://github.com/key3-bot/cart-double-pendulum-policy  
**Demo:** /demo/cart_pendulum_demo.html

Underactuated cart with two rotary links. One horizontal cart force must swing both links from hang to upright and hold them. Hardware needs a fast MCU, joint-angle sensing through rotating shafts, and a cart-position encoder.

## Required parts

| ID | Role | Qty | Why |
|---|---|---|---|
| [teensy-4.1](teensy-4.1.md) | microcontroller | 1 | 1 kHz control loop, SPI + quadrature |
| [slip-ring-12-wire](slip-ring-12-wire.md) | joint wiring | 2 | Power + encoder lines through shoulder and elbow |
| [as5047p](as5047p.md) | joint encoder | 2 | Absolute angle, no homing |
| [amt102-v](amt102-v.md) | cart encoder | 1 | Incremental cart travel |

Rail, motor, driver, and PSU are mechanical follow-ons after the sensing chain is locked.

## Crypto

Not wired. Buy via supplier carts for now.
