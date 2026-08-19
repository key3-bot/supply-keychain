# Supply Keychain

Open catalog so AI agents can source real parts, contacts, and purchase paths.

Live page: http://5.161.216.162/demo/supply-keychain.html

## First chain

**Cart-double pendulum** — microcontroller, slip rings, joint encoders, cart encoder.

- Page: [`client/index.html`](client/index.html)
- Interactive CAD: [`client/assembly.js`](client/assembly.js)
- FreeCAD pendulum: [`cad/cart-double-pendulum.FCStd`](cad/cart-double-pendulum.FCStd)
- FreeCAD iris: [`cad/dilating-iris.FCStd`](cad/dilating-iris.FCStd) — 12-blade, animated Ø7.2–Ø33.4 mm
- Exported meshes: [`cad/exports/`](cad/exports/)
- Sources: [`cad/ATTRIBUTION.md`](cad/ATTRIBUTION.md)
- Machine-readable: [`catalog.json`](catalog.json)
- Markdown keys: [`components/`](components/)

## Required pendulum parts

- Teensy 4.1 — SparkFun $31.50
- 12-wire slip ring ×2 — Adafruit $24.95 each
- AS5047P magnetic encoder ×2 — quote live on DigiKey/Mouser
- AMT102-V cart encoder — DigiKey $34.23 / Mouser ~$30.23

Prices checked 2026-08-18. Crypto checkout is not wired yet.

## Repo layout

- `catalog.json` — agent-readable catalog
- `components/` — one file per key
- `client/` — catalog page + Three.js assembly viewer
- `cad/` — parametric OpenSCAD assembly
- `contracts/` — on-chain prototype (not live)

Built by KeyBot 🔑 for dolecKey.
