# FreeCAD 1.1 headless assembly
# Accurate vendor STEP + datasheet solids. Units: mm.

import os
import sys

import FreeCAD as App
import Import
import Mesh
import MeshPart
import Part

ROOT = os.environ.get("CAD_ROOT", "/home/node/supply-keychain/cad")
VENDOR = os.path.join(ROOT, "vendor")
EXPORTS = os.path.join(ROOT, "exports")
os.makedirs(EXPORTS, exist_ok=True)

TEENSY_STEP = os.path.join(VENDOR, "Teensy_4.1_Assembly.STEP")
DOC_PATH = os.path.join(ROOT, "cart-double-pendulum.FCStd")


def solid_to_obj(doc, name, shape, color):
    obj = doc.addObject("Part::Feature", name)
    obj.Shape = shape
    if hasattr(obj, "ViewObject") and obj.ViewObject:
        obj.ViewObject.ShapeColor = color
    return obj


def mesh_export(shape, path, deflection=0.15):
    mesh = MeshPart.meshFromShape(
        Shape=shape,
        LinearDeflection=deflection,
        AngularDeflection=0.5,
        Relative=False,
    )
    mesh.write(path)
    print("wrote", path, "facets", mesh.CountFacets)


def slip_ring():
    # Adafruit 1195 / Prosper SRC012C-12: OD 12 mm, L 19.5 mm
    body = Part.makeCylinder(6.0, 19.5)
    rings = []
    for z in (3.0, 9.75, 16.5):
        rings.append(Part.makeCylinder(6.6, 1.1, App.Vector(0, 0, z - 0.55)))
    return body.fuse(rings[0]).fuse(rings[1]).fuse(rings[2])


def as5047p():
    # AS5047P-TS_EK_AB: 28 x 22 mm board, 4 x 2.6 mm holes, 1.6 mm PCB
    board = Part.makeBox(28.0, 22.0, 1.6)
    holes = []
    for x, y in ((3.0, 3.0), (25.0, 3.0), (3.0, 19.0), (25.0, 19.0)):
        h = Part.makeCylinder(1.3, 2.2, App.Vector(x, y, -0.3))
        holes.append(h)
    cut = board
    for h in holes:
        cut = cut.cut(h)
    chip = Part.makeBox(5.0, 6.4, 1.1, App.Vector(11.5, 7.8, 1.6))
    magnet = Part.makeCylinder(3.0, 2.5, App.Vector(14.0, 11.0, 1.6 + 1.1))
    return cut.fuse(chip).fuse(magnet)


def amt102():
    # AMT10-V / AMT102 radial: R15.50 housing, 28.77 mm overall height
    housing = Part.makeCylinder(15.5, 10.34)
    base = Part.makeCylinder(15.5, 18.43, App.Vector(0, 0, -18.43))
    shaft = Part.makeCylinder(3.0, 12.0, App.Vector(0, 0, -6.0))
    return housing.fuse(base).fuse(shaft)


def rail():
    return Part.makeBox(400.0, 22.0, 10.0, App.Vector(-200.0, -11.0, 0.0))


def cart():
    return Part.makeBox(80.0, 52.0, 22.0, App.Vector(-40.0, -26.0, 10.0))


def link(length, width, thick):
    return Part.makeBox(width, thick, length, App.Vector(-width / 2.0, -thick / 2.0, 0.0))


def main():
    print("FreeCAD", App.Version())
    doc = App.newDocument("PendulumAssembly")

    print("importing Teensy STEP...")
    Import.insert(TEENSY_STEP, doc.Name)
    teensy_shapes = []
    for obj in list(doc.Objects):
        if hasattr(obj, "Shape") and not obj.Shape.isNull():
            teensy_shapes.append(obj.Shape)
    if not teensy_shapes:
        raise RuntimeError("Teensy STEP imported no solids")
    teensy = teensy_shapes[0]
    for extra in teensy_shapes[1:]:
        try:
            teensy = teensy.fuse(extra)
        except Exception:
            pass
    # Official board is 61.0 x 17.78 mm. Center on cart top.
    bb = teensy.BoundBox
    print("teensy bbox", bb.XLength, bb.YLength, bb.ZLength)
    teensy = teensy.translate(App.Vector(16.0 - (bb.XMin + bb.XMax) / 2.0, 0.0 - (bb.YMin + bb.YMax) / 2.0, 35.0 - bb.ZMin))

    parts = {
        "teensy-4.1": teensy,
        "slip-ring-12-wire-a": slip_ring().translate(App.Vector(0, 0, 32.0)),
        "slip-ring-12-wire-b": slip_ring().translate(App.Vector(0, 0, 221.0)),
        "as5047p-a": as5047p().translate(App.Vector(10.0, -11.0, 40.0)),
        "as5047p-b": as5047p().translate(App.Vector(10.0, -11.0, 229.0)),
        "amt102-v": amt102().rotate(App.Vector(0, 0, 0), App.Vector(1, 0, 0), 90).translate(App.Vector(-28.0, 32.0, 21.0)),
        "rail": rail(),
        "cart": cart(),
        "link1": link(180.0, 16.0, 8.0).translate(App.Vector(0, 0, 51.5)),
        "link2": link(120.0, 12.0, 6.0).rotate(App.Vector(0, 0, 0), App.Vector(0, 1, 0), -22).translate(App.Vector(8.0, 0, 241.5)),
    }

    colors = {
        "teensy-4.1": (0.12, 0.48, 0.22),
        "slip-ring-12-wire-a": (0.79, 0.64, 0.15),
        "slip-ring-12-wire-b": (0.79, 0.64, 0.15),
        "as5047p-a": (0.09, 0.19, 0.14),
        "as5047p-b": (0.09, 0.19, 0.14),
        "amt102-v": (0.17, 0.17, 0.17),
        "rail": (0.60, 0.65, 0.71),
        "cart": (0.85, 0.87, 0.91),
        "link1": (0.50, 0.55, 0.60),
        "link2": (0.64, 0.68, 0.72),
    }

    for name, shape in parts.items():
        solid_to_obj(doc, name.replace("-", "_"), shape, colors[name])
        deflection = 0.35 if name == "teensy-4.1" else 0.12
        mesh_export(shape, os.path.join(EXPORTS, name + ".stl"), deflection)

    doc.saveAs(DOC_PATH)
    print("saved", DOC_PATH)
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
