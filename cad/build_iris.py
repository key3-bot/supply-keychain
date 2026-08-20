# FreeCAD 1.1 headless dilating iris. Units: mm.
# Housing cup + coplanar S-warped blades (no rigid tilt intersections).

import math
import os
import sys

import FreeCAD as App
import Mesh
import Part

try:
    import MeshPart  # preferred when snap libs resolve
except Exception:
    MeshPart = None

ROOT = os.environ.get("CAD_ROOT", "/home/node/supply-keychain/cad")
sys.path.insert(0, ROOT)
import iris_geom as G

EXPORTS = os.path.join(ROOT, "exports")
DOC_PATH = os.path.join(ROOT, "dilating-iris.FCStd")
os.makedirs(EXPORTS, exist_ok=True)

PACK_BOT, PACK_TOP = G.pack_envelope()


def solid_to_obj(doc, name, shape, color):
    obj = doc.addObject("Part::Feature", name)
    obj.Shape = shape
    if hasattr(obj, "ViewObject") and obj.ViewObject:
        obj.ViewObject.ShapeColor = color
    return obj


def mesh_export(shape, path, deflection=0.08):
    if MeshPart is not None:
        try:
            mesh = MeshPart.meshFromShape(
                Shape=shape,
                LinearDeflection=deflection,
                AngularDeflection=0.45,
                Relative=False,
            )
            mesh.write(path)
            print("wrote", path, "facets", mesh.CountFacets)
            return
        except Exception as exc:
            print("MeshPart failed, falling back to tessellate:", exc)
    # Fallback path for environments where MeshPart cannot load (e.g. libcurl).
    mesh = Mesh.Mesh()
    mesh.addFacets(shape.tessellate(deflection))
    mesh.write(path)
    print("wrote", path, "facets", mesh.CountFacets, "(tessellate)")


def face_from_poly(poly):
    pts = [App.Vector(x, y, 0) for x, y in poly]
    pts.append(pts[0])
    wire = Part.makePolygon(pts)
    return Part.Face(wire)


def _bounds():
    xs = [p[0] for p in G.BLADE_POLY] + [p[0] for p in G.SLOT_ARM_POLY] + [-G.BOSS_R, G.SLOT_OUT + G.BOSS_R]
    ys = [p[1] for p in G.BLADE_POLY] + [p[1] for p in G.SLOT_ARM_POLY] + [-G.ARM_HALF - 1, G.ARM_HALF + 1]
    return min(xs) - 1.0, max(xs) + 1.0, min(ys) - 1.0, max(ys) + 1.0


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
    body = body.cut(hole).cut(slot.fuse(cap_a).fuse(cap_b))
    # Foreign-pin keep-outs across the stroke. Decimate heavily — full 500+
    # pairwise fuses hang FreeCAD; nearest-neighbor samples are enough for the mesh.
    cuts = list(getattr(G, "PIN_CUTS", []) or [])
    if cuts:
        # Keep only cuts that actually hit the blade outline, quantized ~1.2 mm.
        kept = []
        seen = set()
        for cx, cy, r in cuts:
            key = (round(float(cx) / 1.2), round(float(cy) / 1.2))
            if key in seen:
                continue
            if not G._point_in_poly(float(cx), float(cy), G.BLADE_POLY):
                # still keep if disk overlaps outline bbox-ish near body
                if abs(float(cy)) > 18 and abs(float(cx)) > 30:
                    continue
            seen.add(key)
            kept.append((float(cx), float(cy), float(r)))
        # Cap to keep boolean time sane.
        if len(kept) > 80:
            step = max(1, len(kept) // 80)
            kept = kept[::step][:80]
        print("blade pin keep-outs candidate", len(cuts), "using", len(kept))
        for i, (cx, cy, r) in enumerate(kept):
            cyl = Part.makeCylinder(r, G.BLADE_THICK + 2, App.Vector(cx, cy, -1))
            body = body.cut(cyl)
            if (i + 1) % 20 == 0:
                print("  cut", i + 1, "/", len(kept))
    return body


def ring(od, id_, z0, thick):
    outer = Part.makeCylinder(od / 2.0, thick, App.Vector(0, 0, z0))
    inner = Part.makeCylinder(id_ / 2.0, thick + 2, App.Vector(0, 0, z0 - 1))
    return outer.cut(inner)


def stator():
    floor = ring(96.0, 64.0, 0.0, G.STATOR_FLOOR)
    wall = ring(96.0, 88.0, G.STATOR_FLOOR, G.WALL_TOP - G.STATOR_FLOOR)
    slot = Part.makeBox(10.0, 28.0, 3.4, App.Vector(38.0, -8.0, G.ROTOR_Z - 0.3))
    wall = wall.cut(slot)
    lip = ring(68.0, 64.0, G.STATOR_FLOOR, 0.8)
    shape = floor.fuse(wall).fuse(lip)
    pin_h = max(4.0, PACK_TOP - 2.0)
    for i in range(G.N):
        x, y = G.pivot_xy(i)
        pin = Part.makeCylinder(G.PIN_R, pin_h, App.Vector(x, y, 2.0))
        boss = Part.makeCylinder(2.1, 0.6, App.Vector(x, y, G.STATOR_FLOOR))
        shape = shape.fuse(pin).fuse(boss)
    for ang in (math.radians(45), math.radians(135), math.radians(225), math.radians(315)):
        hx = 45.5 * math.cos(ang)
        hy = 45.5 * math.sin(ang)
        shape = shape.cut(Part.makeCylinder(1.6, 14, App.Vector(hx, hy, -1)))
    return shape


def rotor():
    body = ring(86.5, 74.0, G.ROTOR_Z, G.RING_THICK)
    for i in range(24):
        a = i * math.pi * 2 / 24
        nub = Part.makeCylinder(0.55, G.RING_THICK, App.Vector(43.5 * math.cos(a), 43.5 * math.sin(a), G.ROTOR_Z))
        body = body.fuse(nub)
    pin_z0 = G.BLADE_Z0 - 0.5 * G.BLADE_THICK - 0.25
    pin_len = G.ROTOR_Z + 0.4 - pin_z0
    for i in range(G.N):
        x, y = G.drive_xy(i, G.THETA_CLOSED)
        pin = Part.makeCylinder(G.PIN_R, pin_len, App.Vector(x, y, pin_z0))
        boss = Part.makeCylinder(2.0, 0.8, App.Vector(x, y, G.ROTOR_Z))
        body = body.fuse(pin).fuse(boss)
    lever = Part.makeBox(12.0, 4.4, G.RING_THICK, App.Vector(34.0, -2.2, G.ROTOR_Z))
    knob = Part.makeCylinder(2.4, G.RING_THICK, App.Vector(47.2, 0, G.ROTOR_Z))
    return body.fuse(lever).fuse(knob)


def cover():
    return ring(96.0, 72.0, G.COVER_Z, G.COVER_THICK)


def place_blade(i, theta):
    px, py = G.pivot_xy(i)
    ang = math.degrees(G.blade_angle(i, theta))
    z = G.BLADE_Z0 + i * getattr(G, "BLADE_PITCH", 0.0)
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
    print("pack", round(PACK_BOT, 2), "->", round(PACK_TOP, 2), "pitch", getattr(G, "BLADE_PITCH", 0), "cover", G.COVER_Z)
    for t in (0.0, 0.5, 1.0):
        clr = G.neighbor_clearance(G.rotor_angle(t))
        print("clear t", t, "min_sep", clr["min_abs_sep"], "need", clr["need"], "ok", clr["ok"])

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
        mesh_export(shape, os.path.join(EXPORTS, name + ".stl"), 0.14 if name == "iris-blade" else 0.08)

    for i in range(G.N):
        solid_to_obj(doc, "blade_%d" % i, place_blade(i, mid), (0.55 + 0.03 * (i % 3), 0.60, 0.66))

    doc.saveAs(DOC_PATH)
    print("saved", DOC_PATH)
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
