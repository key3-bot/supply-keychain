# FreeCAD 1.1 headless dilating iris. Units: mm.
# Housing is a cup: floor + tall wall + retaining cover so the blade pack stays captured.

import math
import os
import sys

import FreeCAD as App
import MeshPart
import Part

ROOT = os.environ.get("CAD_ROOT", "/home/node/supply-keychain/cad")
sys.path.insert(0, ROOT)
import iris_geom as G

EXPORTS = os.path.join(ROOT, "exports")
DOC_PATH = os.path.join(ROOT, "dilating-iris.FCStd")
os.makedirs(EXPORTS, exist_ok=True)

PACK_TOP = G.BLADE_Z0 + G.BLADE_THICK + (G.N - 1) * G.BLADE_PITCH


def solid_to_obj(doc, name, shape, color):
    obj = doc.addObject("Part::Feature", name)
    obj.Shape = shape
    if hasattr(obj, "ViewObject") and obj.ViewObject:
        obj.ViewObject.ShapeColor = color
    return obj


def mesh_export(shape, path, deflection=0.08):
    mesh = MeshPart.meshFromShape(
        Shape=shape,
        LinearDeflection=deflection,
        AngularDeflection=0.45,
        Relative=False,
    )
    mesh.write(path)
    print("wrote", path, "facets", mesh.CountFacets)


def face_from_poly(poly):
    pts = [App.Vector(x, y, 0) for x, y in poly]
    pts.append(pts[0])
    wire = Part.makePolygon(pts)
    return Part.Face(wire)


def blade_solid():
    body = face_from_poly(G.BLADE_POLY).extrude(App.Vector(0, 0, G.BLADE_THICK))
    arm = face_from_poly(G.SLOT_ARM_POLY).extrude(App.Vector(0, 0, G.BLADE_THICK))
    hub = Part.makeCylinder(G.BOSS_R, G.BLADE_THICK)
    drive_boss = Part.makeCylinder(G.BOSS_R, G.BLADE_THICK, App.Vector(G.SLOT_OUT, 0, 0))
    body = body.fuse(arm).fuse(hub).fuse(drive_boss)

    hole = Part.makeCylinder(G.PIN_R + 0.08, G.BLADE_THICK + 2, App.Vector(0, 0, -1))
    slot = Part.makeBox(
        G.SLOT_OUT - G.SLOT_IN,
        G.SLOT_HALF * 2,
        G.BLADE_THICK + 2,
        App.Vector(G.SLOT_IN, -G.SLOT_HALF, -1),
    )
    cap_a = Part.makeCylinder(G.SLOT_HALF, G.BLADE_THICK + 2, App.Vector(G.SLOT_IN, 0, -1))
    cap_b = Part.makeCylinder(G.SLOT_HALF, G.BLADE_THICK + 2, App.Vector(G.SLOT_OUT, 0, -1))
    return body.cut(hole).cut(slot.fuse(cap_a).fuse(cap_b))


def ring(od, id_, z0, thick):
    outer = Part.makeCylinder(od / 2.0, thick, App.Vector(0, 0, z0))
    inner = Part.makeCylinder(id_ / 2.0, thick + 2, App.Vector(0, 0, z0 - 1))
    return outer.cut(inner)


def stator():
    # Floor + window. Inner hole is the optical aperture well.
    floor = ring(96.0, 64.0, 0.0, G.STATOR_FLOOR)
    # Tall outer wall captures the whole blade pack and the drive ring.
    wall = ring(96.0, 88.0, G.STATOR_FLOOR, G.WALL_TOP - G.STATOR_FLOOR)
    # Drive-arm window so the rotor knob can sweep 0–30° without leaving the cup.
    slot = Part.makeBox(10.0, 28.0, 3.4, App.Vector(38.0, -8.0, G.ROTOR_Z - 0.3))
    wall = wall.cut(slot)
    # Inner window lip keeps leaves from dropping into the hole.
    lip = ring(68.0, 64.0, G.STATOR_FLOOR, 0.8)
    shape = floor.fuse(wall).fuse(lip)
    pin_h = PACK_TOP - 2.2
    for i in range(G.N):
        x, y = G.pivot_xy(i)
        pin = Part.makeCylinder(G.PIN_R, pin_h, App.Vector(x, y, 2.2))
        boss = Part.makeCylinder(2.1, 0.6, App.Vector(x, y, G.STATOR_FLOOR))
        shape = shape.fuse(pin).fuse(boss)
    for ang in (math.radians(45), math.radians(135), math.radians(225), math.radians(315)):
        hx = 45.5 * math.cos(ang)
        hy = 45.5 * math.sin(ang)
        shape = shape.cut(Part.makeCylinder(1.6, 14, App.Vector(hx, hy, -1)))
    return shape


def rotor():
    # Drive ring sits on top of the pack, still inside the cup. Pins hang into slots.
    body = ring(86.5, 74.0, G.ROTOR_Z, G.RING_THICK)
    for i in range(24):
        a = i * math.pi * 2 / 24
        nub = Part.makeCylinder(0.55, G.RING_THICK, App.Vector(43.5 * math.cos(a), 43.5 * math.sin(a), G.ROTOR_Z))
        body = body.fuse(nub)
    pin_len = G.ROTOR_Z + 0.4 - G.BLADE_Z0
    for i in range(G.N):
        x, y = G.drive_xy(i, G.THETA_CLOSED)
        pin = Part.makeCylinder(G.PIN_R, pin_len, App.Vector(x, y, G.BLADE_Z0 - 0.15))
        boss = Part.makeCylinder(2.0, 0.8, App.Vector(x, y, G.ROTOR_Z))
        body = body.fuse(pin).fuse(boss)
    lever = Part.makeBox(12.0, 4.4, G.RING_THICK, App.Vector(34.0, -2.2, G.ROTOR_Z))
    knob = Part.makeCylinder(2.4, G.RING_THICK, App.Vector(47.2, 0, G.ROTOR_Z))
    return body.fuse(lever).fuse(knob)


def cover():
    # Flat retainer on the wall. Overlaps the drive ring so the pack cannot lift out.
    return ring(96.0, 72.0, G.COVER_Z, G.COVER_THICK)


def place_blade(i, theta):
    px, py = G.pivot_xy(i)
    ang = math.degrees(G.blade_angle(i, theta))
    z = G.BLADE_Z0 + i * G.BLADE_PITCH
    return (
        blade_solid()
        .rotate(App.Vector(0, 0, 0), App.Vector(0, 0, 1), ang)
        .translate(App.Vector(px, py, z))
    )


def main():
    print("FreeCAD", App.Version())
    print(
        "iris aperture closed/open",
        round(2 * G.aperture_radius(G.THETA_CLOSED), 2),
        round(2 * G.aperture_radius(G.THETA_OPEN), 2),
    )
    print("pack_top", round(PACK_TOP, 2), "cover", G.COVER_Z, "wall", G.WALL_TOP)
    doc = App.newDocument("DilatingIris")

    blade = blade_solid()
    mid = G.rotor_angle(0.45)
    parts = {
        "iris-stator": stator(),
        "iris-rotor": rotor(),
        "iris-cover": cover(),
        "iris-blade": blade,
    }
    colors = {
        "iris-stator": (0.22, 0.25, 0.29),
        "iris-rotor": (0.79, 0.64, 0.15),
        "iris-cover": (0.18, 0.20, 0.23),
        "iris-blade": (0.62, 0.67, 0.73),
    }
    for name, shape in parts.items():
        solid_to_obj(doc, name.replace("-", "_"), shape, colors[name])
        mesh_export(shape, os.path.join(EXPORTS, name + ".stl"))

    for i in range(G.N):
        solid_to_obj(doc, "blade_%d" % i, place_blade(i, mid), (0.55 + 0.03 * (i % 3), 0.60, 0.66))

    doc.saveAs(DOC_PATH)
    print("saved", DOC_PATH)
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
