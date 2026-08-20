# FreeCAD 1.1 headless cart-double pendulum — pristine local-frame parts.
# Units: mm. Viewer poses + animates; export pose is identity (hanging down).

import math
import os
import sys

import FreeCAD as App
import Mesh
import Part

try:
    import MeshPart
except Exception:
    MeshPart = None

ROOT = os.environ.get("CAD_ROOT", "/home/node/supply-keychain/cad")
sys.path.insert(0, ROOT)
import pendulum_geom as G

EXPORTS = os.path.join(ROOT, "exports")
DOC_PATH = os.path.join(ROOT, "cart-double-pendulum.FCStd")
os.makedirs(EXPORTS, exist_ok=True)


def solid_to_obj(doc, name, shape, color):
    obj = doc.addObject("Part::Feature", name)
    obj.Shape = shape
    if hasattr(obj, "ViewObject") and obj.ViewObject:
        obj.ViewObject.ShapeColor = color
    return obj


def mesh_export(shape, path, deflection=0.12):
    if MeshPart is not None:
        try:
            mesh = MeshPart.meshFromShape(
                Shape=shape,
                LinearDeflection=deflection,
                AngularDeflection=0.5,
                Relative=False,
            )
            mesh.write(path)
            print("wrote", path, "facets", mesh.CountFacets, flush=True)
            return
        except Exception as exc:
            print("MeshPart failed, tessellate:", exc, flush=True)
    mesh = Mesh.Mesh()
    mesh.addFacets(shape.tessellate(deflection))
    mesh.write(path)
    print("wrote", path, "facets", mesh.CountFacets, "(tessellate)", flush=True)


def fuse_all(shapes):
    out = None
    for s in shapes:
        if s is None:
            continue
        out = s if out is None else out.fuse(s)
    return out


def cyl(r, h, x=0, y=0, z=0, axis="z"):
    if axis == "z":
        return Part.makeCylinder(r, h, App.Vector(x, y, z))
    if axis == "y":
        c = Part.makeCylinder(r, h, App.Vector(0, 0, 0), App.Vector(0, 1, 0))
        return c.translate(App.Vector(x, y, z))
    if axis == "x":
        c = Part.makeCylinder(r, h, App.Vector(0, 0, 0), App.Vector(1, 0, 0))
        return c.translate(App.Vector(x, y, z))
    raise ValueError(axis)


def box(dx, dy, dz, x=0, y=0, z=0):
    return Part.makeBox(dx, dy, dz, App.Vector(x, y, z))


def bearing_608_local():
    """Centered on origin, axis = Y (joint axis)."""
    od, id_, w = G.BEARING_OD / 2.0, G.BEARING_ID / 2.0, G.BEARING_W
    outer = cyl(od, w, 0, -w / 2.0, 0, "y")
    inner = cyl(id_, w + 0.4, 0, -w / 2.0 - 0.2, 0, "y")
    groove = cyl(od + 0.2, 1.2, 0, -0.6, 0, "y").cut(cyl(od - 0.9, 1.4, 0, -0.7, 0, "y"))
    return outer.cut(inner).fuse(groove)


def slip_ring_local():
    """Capsule on Y axis, centered, bore along Y."""
    body = cyl(G.SLIP_OD / 2.0, G.SLIP_L, 0, -G.SLIP_L / 2.0, 0, "y")
    rings = []
    for t in (-0.35, -0.12, 0.12, 0.35):
        y0 = t * G.SLIP_L - 0.5
        rings.append(cyl(G.SLIP_OD / 2.0 + 0.35, 1.0, 0, y0, 0, "y"))
    bore = cyl(G.SLIP_BORE / 2.0, G.SLIP_L + 2, 0, -G.SLIP_L / 2.0 - 1, 0, "y")
    return fuse_all([body] + rings).cut(bore)


def magnet_local():
    return cyl(G.MAGNET_D / 2.0, G.MAGNET_H, 0, -G.MAGNET_H / 2.0, 0, "y")


def as5047p_local():
    """Board in XZ plane, chip facing -Y (toward magnet on shaft)."""
    bw, bh, bt = G.AS_BOARD
    # board spans X=width, Z=height, thin in Y
    board = box(bw, bt, bh, -bw / 2.0, 0, -bh / 2.0)
    for hx, hz in G.AS_HOLES:
        board = board.cut(cyl(G.AS_HOLE_R, bt + 1, hx - bw / 2.0, -0.5, hz - bh / 2.0, "y"))
    chip = box(5.0, 1.1, 6.4, -2.5, bt, -3.2)
    keeper = cyl(4.0, 0.6, 0, bt + 1.1, 0, "y")
    return board.fuse(chip).fuse(keeper)


def amt102_local():
    """Radial encoder, shaft along Y, body mostly +Y from mount face."""
    body = cyl(G.AMT_R, G.AMT_BODY_H, 0, 0, 0, "y")
    base = cyl(G.AMT_R, G.AMT_BASE_H, 0, -G.AMT_BASE_H, 0, "y")
    hub = cyl(6.0, 8.0, 0, -4.0, 0, "y")
    plate = box(34.0, 1.5, 34.0, -17.0, -G.AMT_BASE_H - 1.5, -17.0)
    for hx, hz in ((-12, -12), (12, -12), (-12, 12), (12, 12)):
        plate = plate.cut(cyl(1.8, 4, hx, -G.AMT_BASE_H - 2.0, hz, "y"))
    return fuse_all([body, base, hub, plate])


def shaft_local(length):
    return cyl(G.SHAFT_D / 2.0, length, 0, -length / 2.0, 0, "y")


def collar_local():
    return cyl(7.0, 4.0, 0, -2.0, 0, "y").cut(cyl(G.SHAFT_D / 2.0 + 0.05, 5.0, 0, -2.5, 0, "y"))


def rail():
    r = box(G.RAIL_LEN, G.RAIL_W, G.RAIL_H, -G.RAIL_LEN / 2.0, -G.RAIL_W / 2.0, 0)
    # top V channels
    g1 = box(G.RAIL_LEN + 2, 3.5, 2.2, -G.RAIL_LEN / 2.0 - 1, -8.0, G.RAIL_H - 1.8)
    g2 = box(G.RAIL_LEN + 2, 3.5, 2.2, -G.RAIL_LEN / 2.0 - 1, 4.5, G.RAIL_H - 1.8)
    # feet
    feet = []
    for x in (-G.RAIL_LEN / 2.0 + 20, G.RAIL_LEN / 2.0 - 40):
        feet.append(box(30, G.RAIL_W + 16, 4, x, -(G.RAIL_W + 16) / 2.0, -4))
    return r.cut(g1).cut(g2).fuse(fuse_all(feet))


def cart():
    """Cart in world frame at travel=0. Shoulder hole on center, deck at CART_TOP."""
    z0 = G.CART_Z0
    body = box(G.CART_L, G.CART_W, G.CART_H, -G.CART_L / 2.0, -G.CART_W / 2.0, z0)
    # rail tunnel
    body = body.cut(
        box(G.CART_L + 4, G.RAIL_W + 2.0, G.RAIL_H + 2.0, -G.CART_L / 2.0 - 2, -(G.RAIL_W + 2.0) / 2.0, z0 - 1)
    )
    # shoulder bearing bore (through deck)
    body = body.cut(cyl(G.BEARING_OD / 2.0 + 0.08, G.CART_H + 4, 0, 0, z0 - 2))
    # slip-ring pocket from top
    body = body.cut(cyl(G.SLIP_OD / 2.0 + 1.0, 16.0, 0, 0, G.CART_TOP - 16.0))
    # side walls raised for bearing flanges
    for y in (-G.CART_W / 2.0 + 2, G.CART_W / 2.0 - 6):
        body = body.fuse(box(28.0, 4.0, 10.0, -14.0, y, G.CART_TOP))
    # teensy standoffs
    for bx, by in ((14, 18), (14, -18), (48, 18), (48, -18)):
        body = body.fuse(cyl(2.3, 4.0, bx, by, G.CART_TOP))
        body = body.cut(cyl(0.95, 5.0, bx, by, G.CART_TOP - 0.5))
    # AMT bracket pad -X
    pad = box(10.0, 28.0, 20.0, -G.CART_L / 2.0 - 8, -14.0, z0 + 8)
    body = body.fuse(pad)
    # cable exit
    body = body.cut(box(10.0, 18.0, 12.0, G.CART_L / 2.0 - 8, -9.0, G.CART_TOP - 14))
    return body


def link_bar(length, width, thick):
    """Proximal pivot at origin; length along +Z (down when hanging). Thickness along Y."""
    # bar from z=0 to z=length, centered in X/Y
    bar = box(width, thick, length, -width / 2.0, -thick / 2.0, 0)
    bore = G.SHAFT_D / 2.0 + 0.06
    # proximal + distal bores along Y
    bar = bar.cut(cyl(bore, thick + 4, 0, -thick / 2.0 - 2, 0, "y"))
    bar = bar.cut(cyl(bore, thick + 4, 0, -thick / 2.0 - 2, length, "y"))
    # wire tunnel along length
    tunnel = cyl(2.3, length - 20.0, 0, 0, 10.0)
    bar = bar.cut(tunnel)
    # side exits
    for z in (length * 0.3, length * 0.7):
        bar = bar.cut(cyl(1.7, width + 4, -width / 2.0 - 2, 0, z, "x"))
    # lightening
    for z0 in (28.0, length * 0.45, length - 48.0):
        if 18 < z0 < length - 22:
            bar = bar.cut(box(width - 7, thick - 4, 22, -(width - 7) / 2.0, -(thick - 4) / 2.0, z0))
    # proximal boss
    boss = cyl(width / 2.0 + 1.0, thick + 2, 0, -(thick + 2) / 2.0, 0, "y")
    boss = boss.cut(cyl(bore, thick + 4, 0, -(thick + 2) / 2.0 - 1, 0, "y"))
    return bar.fuse(boss)


def tip_mass_local():
    """At distal end of link2 local frame (z=LINK2_L)."""
    return cyl(9.0, 18.0, 0, -9.0, G.LINK2_L, "y")


def teensy_local():
    tw, th, tt = G.TEENSY
    board = box(tw, th, tt, -tw / 2.0, -th / 2.0, 0)
    usb = box(9.0, 8.0, 3.5, -tw / 2.0 - 1, -4.0, tt)
    eth = box(17.0, 15.0, 13.0, tw / 2.0 - 18, -7.5, tt)
    return board.fuse(usb).fuse(eth)


def shoulder_joint_local():
    """Assembled shoulder stack about Y through origin (world shoulder point)."""
    parts = []
    # bearings left/right of cart walls-ish
    b1 = bearing_608_local().translate(App.Vector(0, -G.LINK1_T / 2.0 - 2.0, 0))
    b2 = bearing_608_local().translate(App.Vector(0, G.LINK1_T / 2.0 + 2.0, 0))
    parts += [b1, b2]
    parts.append(shaft_local(G.LINK1_T + 36.0))
    # slip ring on +Y side
    parts.append(slip_ring_local().translate(App.Vector(0, G.LINK1_T / 2.0 + 14.0, 0)))
    # magnet on -Y for encoder
    parts.append(magnet_local().translate(App.Vector(0, -G.LINK1_T / 2.0 - 12.0, 0)))
    parts.append(collar_local().translate(App.Vector(0, G.LINK1_T / 2.0 + 6.0, 0)))
    return fuse_all(parts)


def elbow_joint_local():
    parts = []
    b1 = bearing_608_local().translate(App.Vector(0, -G.LINK2_T / 2.0 - 2.0, 0))
    b2 = bearing_608_local().translate(App.Vector(0, G.LINK1_T / 2.0 + 2.0, 0))
    parts += [b1, b2]
    parts.append(shaft_local(G.LINK1_T + G.LINK2_T + 28.0))
    parts.append(slip_ring_local().translate(App.Vector(0, G.LINK1_T / 2.0 + 14.0, 0)))
    parts.append(magnet_local().translate(App.Vector(0, -G.LINK2_T / 2.0 - 12.0, 0)))
    parts.append(collar_local().translate(App.Vector(0, G.LINK1_T / 2.0 + 6.0, 0)))
    return fuse_all(parts)


def wire_segment(a, b, r=0.55):
    d = App.Vector(b.x - a.x, b.y - a.y, b.z - a.z)
    L = d.Length
    if L < 1e-6:
        return None
    return Part.makeCylinder(r, L, a, d)


def harness_world():
    """Simple rest-pose loom in world coords (static prop; animation hides fine)."""
    t = 0.0
    s = G.POSE_SHOULDER0
    e = G.POSE_ELBOW0
    sh = G.shoulder_origin(t)
    el = G.elbow_origin(t, s)
    tip = G.tip_origin(t, s, e)
    pts = [
        App.Vector(22, 10, G.CART_TOP + 8),
        App.Vector(sh[0] + 10, 16, sh[2] - 6),
        App.Vector(sh[0] + 8, 14, sh[2] + 4),
        App.Vector((sh[0] + el[0]) / 2, 10, (sh[2] + el[2]) / 2),
        App.Vector(el[0] + 6, 16, el[2]),
        App.Vector((el[0] + tip[0]) / 2, 8, (el[2] + tip[2]) / 2),
        App.Vector(tip[0], 6, tip[2]),
    ]
    segs = []
    for a, b in zip(pts[:-1], pts[1:]):
        segs.append(wire_segment(a, b, 0.65))
        segs.append(Part.makeSphere(0.7, b))
    # cart encoder run
    segs.append(wire_segment(App.Vector(22, 10, G.CART_TOP + 8), App.Vector(-G.CART_L / 2 - 6, 20, G.CART_Z0 + 18), 0.5))
    return fuse_all(segs)


def main():
    print("FreeCAD", App.Version(), flush=True)
    print("pristine local-frame export", flush=True)
    doc = App.newDocument("PendulumAssembly")

    parts = {
        "rail": rail(),
        "cart": cart(),
        "link1": link_bar(G.LINK1_L, G.LINK1_W, G.LINK1_T),
        "link2": link_bar(G.LINK2_L, G.LINK2_W, G.LINK2_T),
        "tip-mass": tip_mass_local(),
        "shoulder-joint": shoulder_joint_local(),
        "elbow-joint": elbow_joint_local(),
        "slip-ring-12-wire-a": slip_ring_local(),
        "slip-ring-12-wire-b": slip_ring_local(),
        "as5047p-a": as5047p_local(),
        "as5047p-b": as5047p_local(),
        "amt102-v": amt102_local(),
        "teensy-4.1": teensy_local(),
        "wiring": harness_world(),
    }

    # Place static world props in doc for FCStd screenshot at rest pose
    # Links/joints left local — viewer animates them.
    colors = {
        "rail": (0.58, 0.63, 0.70),
        "cart": (0.86, 0.88, 0.92),
        "link1": (0.48, 0.54, 0.60),
        "link2": (0.62, 0.66, 0.72),
        "tip-mass": (0.75, 0.22, 0.18),
        "shoulder-joint": (0.42, 0.46, 0.50),
        "elbow-joint": (0.42, 0.46, 0.50),
        "slip-ring-12-wire-a": (0.80, 0.65, 0.16),
        "slip-ring-12-wire-b": (0.80, 0.65, 0.16),
        "as5047p-a": (0.07, 0.17, 0.12),
        "as5047p-b": (0.07, 0.17, 0.12),
        "amt102-v": (0.14, 0.14, 0.14),
        "teensy-4.1": (0.12, 0.48, 0.22),
        "wiring": (0.10, 0.10, 0.10),
    }

    # For FCStd readability, also drop a posed assembly snapshot group
    s = G.POSE_SHOULDER0
    e = G.POSE_ELBOW0
    sh = G.shoulder_origin(0)
    el = G.elbow_origin(0, s)

    def place_hanging(shape, origin, abs_angle):
        # IMPORTANT: copy first — FreeCAD rotate/translate mutate in place.
        # local +Z → world link_dir(abs_angle)
        # R_y(theta): (0,0,1) -> (sin theta, 0, cos theta). Want (sin a, 0, -cos a)
        # sin theta = sin a, cos theta = -cos a => theta = pi - a
        theta = math.degrees(math.pi - abs_angle)
        out = shape.copy()
        out.rotate(App.Vector(0, 0, 0), App.Vector(0, 1, 0), theta)
        out.translate(App.Vector(*origin))
        return out

    posed = {
        "posed-link1": place_hanging(parts["link1"], sh, s),
        "posed-link2": place_hanging(parts["link2"], el, s + e),
        "posed-shoulder": parts["shoulder-joint"].copy().translate(App.Vector(*sh)),
        "posed-elbow": parts["elbow-joint"].copy().translate(App.Vector(*el)),
        "posed-tip": place_hanging(parts["tip-mass"], el, s + e),
        "posed-teensy": parts["teensy-4.1"].copy().translate(App.Vector(18.0, 0.0, G.CART_TOP + 4.0)),
        "posed-amt": parts["amt102-v"].copy().translate(App.Vector(-G.CART_L / 2.0 - 6.0, 18.0, G.CART_Z0 + 18.0)),
        "posed-as-a": parts["as5047p-a"].copy().translate(App.Vector(sh[0], sh[1] - 18.0, sh[2])),
        "posed-as-b": parts["as5047p-b"].copy().translate(App.Vector(el[0], el[1] - 18.0, el[2])),
    }

    for name, shape in list(parts.items()) + list(posed.items()):
        if shape is None:
            continue
        col = colors.get(name, colors.get(name.replace("posed-", ""), (0.6, 0.6, 0.6)))
        solid_to_obj(doc, name.replace("-", "_"), shape, col)
        # export only canonical local/world parts (not posed-*)
        if not name.startswith("posed-"):
            mesh_export(shape, os.path.join(EXPORTS, name + ".stl"), 0.14 if "wire" in name else 0.11)

    doc.saveAs(DOC_PATH)
    print("saved", DOC_PATH, flush=True)
    import json
    from pathlib import Path

    Path(os.path.join(EXPORTS, "pendulum-kinematics.json")).write_text(
        json.dumps(G.kinematics_json(), indent=2)
    )
    print("ok", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
