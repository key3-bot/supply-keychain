# CAD sources

## Teensy 4.1
- File: `vendor/Teensy_4.1_Assembly.STEP`
- Source: https://github.com/blackketter/teensy.pretty
- Original: Zack Kummer / GrabCAD Teensy 4.1
- License: MIT (library repo)

## 12-wire slip ring
- Modeled in FreeCAD from Prosper SRC012 / Adafruit 1195 datasheet
- SRC012-12: Ø12 mm, L 19.5 mm, 12 × 2A, AWG28
- Datasheet: https://cdn-shop.adafruit.com/datasheets/SRC012.pdf

## AS5047P adapter
- Modeled from ams AS5047P-TS_EK_AB eval kit manual
- PCB 28 × 22 mm, 4 × Ø2.6 mm holes, magnet Ø6 × 2.5 mm

## AMT102-V
- Modeled from Same Sky AMT10-V datasheet
- Housing R15.50 (Ø31 mm), overall height 28.77 mm

## Dilating iris
- Original 12-blade mechanism in `dilating-iris.FCStd`
- Offset pitch circles (pivot Ø64, drive Ø80) with sliding slots
- Housing is a cup: floor + wall + retaining cover.
- 12 notched comma blades (neighbor pin keep-outs in the 2D outline)
- Aperture ≈ Ø6.8 mm closed to Ø28.4 mm open

## Cart-double pendulum (real joint stack)
- Source: `pendulum_geom.py` + `build_assembly.py` → `cart-double-pendulum.FCStd`
- Rail 400×22×10, cart 90×58×28 with shoulder well and encoder pad
- Joints: Ø8 shaft, 608-2Z bearings (ID8 OD22 W7), clamp collar
- SRC012-12 slip rings at shoulder (in cart well) and elbow (on joint Y)
- AS5047P boards + Ø6×2.5 magnets at both joints
- AMT102-V on cart side bracket for cart travel
- Hollow links (wire tunnels) L1=180 / L2=120, tip mass, harness loom
- Teensy 4.1: vendor STEP mesh placed on cart top
