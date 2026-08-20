# FreeCAD 1.1 headless cart-double pendulum. Units: mm.
# Real joints: 608 bearings, Ø8 shafts, SRC012 slip rings, AS5047P boards,
# AMT102-V cart encoder, Teensy STEP, wire looms through the hollow links.

import math
import os
import sys

import FreeCAD as App
import Import
import Mesh
import Part

try:
    import MeshPart
except Exception:
    MeshPart = None

ROOT = os.environ.get("CAD_ROOT", "/home/node/supply-keychain/cad")
sys.path.insert(0, ROOT)
import pendulum_geom as G

VENDOR = os.path.join(ROOT, "vendor")
EXPORTS = os.path.join(ROOT, "exports")
DOC_PATH = os.path.join(ROOT, "cart-double-pendulum.FCStd")
os.makedirs(EXPORTS, exist_ok=True)

TEENSY_STEP = os.path.join(VENDOR, "Teensy_4.1_Assembly.STEP")

# Export pose (hanging-ish, readable)
TRAVEL = 0.0
SHOULDER = G.POSE_SHOULDER0
ELBOW = G.POSE_ELBOW0


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
            print("wrote", path, "facets", mesh.CountFacets)
            return
        except Exception as exc:
            print("MeshPart failed, tessellate:", exc)
    mesh = Mesh.Mesh()
    mesh.addFacets(shape.tessellate(deflection))
    mesh.write(path)
    print("wrote", path, "facets", mesh.CountFacets, "(tessellate)")


def fuse_all(shapes):
    out = None
    for s in shapes:
        if s is None:
            continue
        out = s if out is None else out.fuse(s)
    return out


def cylinder(r, h, x=0, y=0, z=0, axis="z"):
    base = App.Vector(x, y, z)
    if axis == "z":
        return Part.makeCylinder(r, h, base)
    if axis == "y":
        c = Part.makeCylinder(r, h, App.Vector(0, 0, 0), App.Vector(0, 1, 0))
        return c.translate(base)
    if axis == "x":
        c = Part.makeCylinder(r, h, App.Vector(0, 0, 0), App.Vector(1, 0, 0))
        return c.translate(base)
    raise ValueError(axis)


def box(dx, dy, dz, x=0, y=0, z=0):
    return Part.makeBox(dx, dy, dz, App.Vector(x, y, z))


def bearing_608(x, y, z, axis="z"):
    """608-2Z: ID8 OD22 W7 with race groove look."""
    od = G.BEARING_OD / 2.0
    id_ = G.BEARING_ID / 2.0
    w = G.BEARING_W
    outer = cylinder(od, w, x, y, z, axis)
    inner = cylinder(id_, w + 0.4, x, y, z - 0.2 if axis == "z" else z, axis)
    # slight OD chamfer ring
    ring = cylinder(od + 0.15, 1.2, x, y, z + (w - 1.2) / 2.0, axis)
    return outer.cut(inner).fuse(ring.cut(cylinder(od - 0.8, 1.4, x, y, z + (w - 1.4) / 2.0, axis)))


def shaft_od8(length, x, y, z, axis="z"):
    return cylinder(G.SHAFT_D / 2.0, length, x, y, z, axis)


def slip_ring_src012(x, y, z0):
    """Prosper SRC012-12 / Adafruit 1195: Ø12.4 × 19.5 capsule."""
    body = cylinder(G.SLIP_OD / 2.0, G.SLIP_L, x, y, z0)
    rings = []
    for i, zz in enumerate((3.0, 7.5, 12.0, 16.5)):
        rings.append(cylinder(G.SLIP_OD / 2.0 + 0.35, 1.0, x, y, z0 + zz - 0.5))
    bore = cylinder(G.SLIP_BORE / 2.0, G.SLIP_L + 2, x, y, z0 - 1)
    return fuse_all([body] + rings).cut(bore)


def as5047p_board(x, y, z, rot_z_deg=0.0):
    """ams AS5047P-TS_EK_AB envelope: 28×22×1.6, 4×Ø2.6 holes, chip + magnet seat."""
    bw, bh, bt = G.AS_BOARD
    board = box(bw, bh, bt, -bw / 2.0, -bh / 2.0, 0)
    for hx, hy in G.AS_HOLES:
        board = board.cut(cylinder(G.AS_HOLE_R, bt + 1, hx - bw / 2.0, hy - bh / 2.0, -0.5))
    chip = box(5.0, 6.4, 1.1, -2.5, -3.2, bt)
    # magnet is separate on shaft; small keeper ring on board face
    keeper = cylinder(4.0, 0.6, 0, 0, bt + 1.1)
    shape = board.fuse(chip).fuse(keeper)
    if abs(rot_z_deg) > 1e-9:
        shape = shape.rotate(App.Vector(0, 0, 0), App.Vector(0, 0, 1), rot_z_deg)
    return shape.translate(App.Vector(x, y, z))


def magnet_on_shaft(x, y, z):
    return cylinder(G.MAGNET_D / 2.0, G.MAGNET_H, x, y, z)


def amt102(x, y, z, axis="y"):
    """Same Sky AMT10-V radial envelope ~Ø31 × 28.8 with base plate."""
    body = cylinder(G.AMT_R, 10.5, 0, 0, 0, "z")
    base = cylinder(G.AMT_R, 12.0, 0, 0, -12.0, "z")
    hub = cylinder(6.0, 8.0, 0, 0, -4.0, "z")
    plate = box(34.0, 34.0, 1.5, -17.0, -17.0, -13.5)
    for hx, hy in ((-12, -12), (12, -12), (-12, 12), (12, 12)):
        plate = plate.cut(cylinder(1.8, 3, hx, hy, -14.0))
    shape = fuse_all([body, base, hub, plate])
    if axis == "y":
        shape = shape.rotate(App.Vector(0, 0, 0), App.Vector(1, 0, 0), -90)
    return shape.translate(App.Vector(x, y, z))


def wire_bundle(points, radius=0.55):
    """Polyline tube for wiring. points: list of App.Vector."""
    if len(points) < 2:
        return None
    bits = []
    for a, b in zip(points[:-1], points[1:]):
        d = b.sub(a)
        L = d.Length
        if L < 1e-6:
            continue
        bits.append(Part.makeCylinder(radius, L, a, d))
        bits.append(Part.makeSphere(radius * 1.05, b))
    return fuse_all(bits)


def rail():
    r = box(G.RAIL_LEN, G.RAIL_W, G.RAIL_H, -G.RAIL_LEN / 2.0, -G.RAIL_W / 2.0, 0)
    # V-groove-ish top channels
    groove = box(G.RAIL_LEN + 2, 4.0, 2.0, -G.RAIL_LEN / 2.0 - 1, -2.0, G.RAIL_H - 1.5)
    return r.cut(groove)


def cart_body():
    z0 = G.CART_Z0
    body = box(G.CART_L, G.CART_W, G.CART_H, -G.CART_L / 2.0, -G.CART_W / 2.0, z0)
    # rail tunnel
    tunnel = box(G.CART_L + 2, G.RAIL_W + 1.2, G.RAIL_H + 1.5, -G.CART_L / 2.0 - 1, -(G.RAIL_W + 1.2) / 2.0, z0 - 0.5)
    body = body.cut(tunnel)
    # shoulder bearing pockets (through)
    sx, sy = G.SHOULDER_X, G.SHOULDER_Y
    body = body.cut(cylinder(G.BEARING_OD / 2.0 + 0.05, G.CART_H + 2, sx, sy, z0 - 1))
    # slip-ring well from top
    body = body.cut(cylinder(G.SLIP_OD / 2.0 + 0.8, 14.0, sx, sy, G.CART_TOP - 14.0))
    # Teensy standoff bosses
    for bx, by in ((12, 14), (12, -14), (40, 14), (40, -14)):
        body = body.fuse(cylinder(2.2, 3.0, bx, by, G.CART_TOP))
        body = body.cut(cylinder(0.9, 4.0, bx, by, G.CART_TOP - 0.5))
    # cable exit slot rear
    body = body.cut(box(8.0, 16.0, 10.0, -G.CART_L / 2.0 - 1, -8.0, G.CART_TOP - 12.0))
    # encoder bracket pad left side
    pad = box(8.0, 18.0, 16.0, -G.CART_L / 2.0 - 6, -9.0, z0 + 6.0)
    body = body.fuse(pad)
    return body


def link_bar(length, width, thick, bore_r, hollow_r=2.2):
    """Link along +X from 0..length, centered on YZ, with end bores and wire channel."""
    bar = box(length, width, thick, 0, -width / 2.0, -thick / 2.0)
    # end bores for shafts
    bar = bar.cut(cylinder(bore_r, thick + 2, 0, 0, -thick / 2.0 - 1))
    bar = bar.cut(cylinder(bore_r, thick + 2, length, 0, -thick / 2.0 - 1))
    # longitudinal wire tunnel (open along X, slightly off center Z)
    tunnel = cylinder(hollow_r, length - 16.0, 8.0, 0, -0.5, "x")
    bar = bar.cut(tunnel)
    # side access holes for wires mid-span
    for x in (length * 0.35, length * 0.65):
        bar = bar.cut(cylinder(1.6, width + 2, x, -width / 2.0 - 1, 0, "y"))
    # lightening pockets
    for x0 in (28.0, length / 2.0 - 10, length - 50.0):
        if 12 < x0 < length - 24:
            pocket = box(18.0, width - 6.0, thick - 3.0, x0, -(width - 6.0) / 2.0, -(thick - 3.0) / 2.0)
            bar = bar.cut(pocket)
    return bar


def place_link(shape, origin, abs_angle):
    """Map link local (+X along length, Z up through thickness) into world hanging frame."""
    ox, oy, oz = origin
    # local point (L,0,0) should go to origin + dir*L
    # Start with link along +X, then rotate about Y by (abs_angle - 90°) so +X maps to hang dir
    # hang dir = (sin a, 0, -cos a). Angle of this from +X in XZ plane: atan2(z,x)=atan2(-cos,sin)= -pi/2 - a? 
    # R_y(theta).(1,0,0) = (cos theta, 0, -sin theta). Want (sin a, 0, -cos a)
    # cos theta = sin a, -sin theta = -cos a => sin theta = cos a => theta = pi/2 - a
    theta_deg = math.degrees(math.pi / 2.0 - abs_angle)
    s = shape.rotate(App.Vector(0, 0, 0), App.Vector(0, 1, 0), theta_deg)
    return s.translate(App.Vector(ox, oy, oz))


def joint_stack_shoulder():
    """Bearings + shaft + slip ring + magnet at shoulder (world coords)."""
    sx, sy, sz = G.shoulder_origin(TRAVEL)
    z0 = G.CART_Z0
    parts = []
    # lower bearing in cart floor
    parts.append(bearing_608(sx, sy, z0 + 1.0))
    # upper bearing near cart top
    parts.append(bearing_608(sx, sy, G.CART_TOP - G.BEARING_W - 1.0))
    # shaft through cart into link
    shaft_len = G.CART_H + 28.0
    parts.append(shaft_od8(shaft_len, sx, sy, z0 - 2.0))
    # slip ring in well
    parts.append(slip_ring_src012(sx, sy, G.CART_TOP - 3.0 - G.SLIP_L))
    # magnet on shaft top for AS5047P under cart / beside — put under lower end
    parts.append(magnet_on_shaft(sx, sy, z0 - 2.0 - G.MAGNET_H))
    # clamp collar above slip ring
    collar = cylinder(7.0, 4.0, sx, sy, G.CART_TOP + 1.0).cut(cylinder(G.SHAFT_D / 2.0 + 0.05, 5, sx, sy, G.CART_TOP + 0.5))
    parts.append(collar)
    return fuse_all(parts)


def joint_stack_elbow(origin, abs_angle):
    """Elbow bearings/shaft/slip ring/magnet placed at elbow origin, shaft along joint Y."""
    ox, oy, oz = origin
    # Build in local then rotate so shaft // world Y stays, link plane is XZ
    # Local: shaft along Y through origin
    bits = []
    bits.append(bearing_608(0, -G.LINK1_T / 2.0 - 1.0, 0, axis="y"))
    bits.append(bearing_608(0, G.LINK2_T / 2.0 + 1.0, 0, axis="y"))
    bits.append(shaft_od8(G.LINK1_T + G.LINK2_T + 18.0, 0, -G.LINK1_T / 2.0 - 8.0, 0, axis="y"))
    # slip ring along shaft (offset +Y)
    slip = slip_ring_src012(0, 0, 0)
    slip = slip.rotate(App.Vector(0, 0, 0), App.Vector(1, 0, 0), -90)
    slip = slip.translate(App.Vector(0, G.LINK2_T / 2.0 + 8.0, 0))
    bits.append(slip)
    # magnet at -Y end for encoder board
    mag = magnet_on_shaft(0, 0, 0)
    mag = mag.rotate(App.Vector(0, 0, 0), App.Vector(1, 0, 0), -90)
    mag = mag.translate(App.Vector(0, -G.LINK1_T / 2.0 - 10.0 - G.MAGNET_H, 0))
    bits.append(mag)
    shape = fuse_all(bits)
    # rotate stack so "link plane" matches elbow absolute? shaft stays on Y; no need for hang rot
    return shape.translate(App.Vector(ox, oy, oz))


def import_teensy():
    # Prefer already-exported mesh path via simple solid envelope so headless
    # rebuilds stay fast. Full STEP is huge and hangs FreeCADCmd fuse on snap.
    use_step = os.environ.get("PENDULUM_TEENSY_STEP", "0") == "1"
    if use_step and os.path.isfile(TEENSY_STEP):
        print("importing Teensy STEP (slow)...")
        doc_tmp = App.newDocument("TeensyImport")
        Import.insert(TEENSY_STEP, doc_tmp.Name)
        shapes = []
        for obj in list(doc_tmp.Objects):
            if hasattr(obj, "Shape") and not obj.Shape.isNull():
                shapes.append(obj.Shape)
        shape = shapes[0] if shapes else None
        for extra in shapes[1:]:
            try:
                shape = shape.fuse(extra)
            except Exception:
                pass
        if shape is not None:
            bb = shape.BoundBox
            print("teensy bbox", round(bb.XLength, 2), round(bb.YLength, 2), round(bb.ZLength, 2))
            shape = shape.translate(
                App.Vector(
                    18.0 - (bb.XMin + bb.XMax) / 2.0,
                    0.0 - (bb.YMin + bb.YMax) / 2.0,
                    G.CART_TOP + 3.2 - bb.ZMin,
                )
            )
            App.closeDocument(doc_tmp.Name)
            return shape
        App.closeDocument(doc_tmp.Name)
    print("teensy envelope solid (set PENDULUM_TEENSY_STEP=1 for full STEP)")
    tw, th, tt = G.TEENSY
    board = box(tw, th, tt, 18.0 - tw / 2.0, -th / 2.0, G.CART_TOP + 3.2)
    # USB / Ethernet block hints
    usb = box(8.0, 8.0, 3.0, 18.0 - tw / 2.0 - 1.0, -4.0, G.CART_TOP + 3.2 + tt)
    eth = box(16.0, 14.0, 12.0, 18.0 + tw / 2.0 - 18.0, -7.0, G.CART_TOP + 3.2 + tt)
    return board.fuse(usb).fuse(eth)


def wires():
    """Approximate harness: Teensy -> shoulder slip -> up link1 -> elbow slip -> link2."""
    sx, sy, sz = G.shoulder_origin(TRAVEL)
    ex, ey, ez = G.elbow_origin(TRAVEL, SHOULDER)
    # teensy area
    t = App.Vector(30, 0, G.CART_TOP + 6)
    s_base = App.Vector(sx + 8, sy + 10, G.CART_TOP - 8)
    s_top = App.Vector(sx + 6, sy + 8, G.CART_TOP + 10)
    # along link1 toward elbow (sample mid)
    d1 = G.link_direction(SHOULDER)
    mid1 = App.Vector(sx + d1[0] * G.LINK1_L * 0.5, sy + 6, sz + d1[2] * G.LINK1_L * 0.5)
    e_side = App.Vector(ex + 6, ey + 12, ez)
    d2 = G.link_direction(SHOULDER + ELBOW)
    mid2 = App.Vector(ex + d2[0] * G.LINK2_L * 0.45, ey + 5, ez + d2[2] * G.LINK2_L * 0.45)
    tip = App.Vector(*G.tip_origin(TRAVEL, SHOULDER, ELBOW))
    tip = App.Vector(tip.x, tip.y + 4, tip.z)

    loom1 = wire_bundle([t, s_base, s_top, mid1, e_side], 0.7)
    loom2 = wire_bundle([e_side, mid2, tip], 0.55)
    # cart encoder run
    amt = App.Vector(-G.CART_L / 2.0 - 10, 20, G.CART_Z0 + 18)
    loom3 = wire_bundle([t, App.Vector(-10, 16, G.CART_TOP + 4), amt], 0.5)
    return fuse_all([loom1, loom2, loom3])


def main():
    print("FreeCAD", App.Version())
    print("pose travel", TRAVEL, "shoulder_deg", round(math.degrees(SHOULDER), 1), "elbow_deg", round(math.degrees(ELBOW), 1))
    print("elbow", tuple(round(v, 1) for v in G.elbow_origin(TRAVEL, SHOULDER)))
    print("tip", tuple(round(v, 1) for v in G.tip_origin(TRAVEL, SHOULDER, ELBOW)))

    doc = App.newDocument("PendulumAssembly")

    rail_s = rail()
    cart_s = cart_body()
    teensy_s = import_teensy()

    # Shoulder AS5047P under cart reading magnet on shaft bottom
    as_a = as5047p_board(G.SHOULDER_X + 18.0, G.SHOULDER_Y, G.CART_Z0 - 1.6 - 0.5, rot_z_deg=90)
    # shift so chip faces magnet under shoulder
    as_a = as_a.translate(App.Vector(-18.0, 0, 0))

    amt = amt102(-G.CART_L / 2.0 - 8.0, 22.0, G.CART_Z0 + 16.0, axis="y")

    shoulder = joint_stack_shoulder()

    # Link1 at shoulder, angle SHOULDER
    link1_local = link_bar(G.LINK1_L, G.LINK1_W, G.LINK1_T, G.SHAFT_D / 2.0 + 0.05)
    link1_s = place_link(link1_local, G.shoulder_origin(TRAVEL), SHOULDER)

    elbow_o = G.elbow_origin(TRAVEL, SHOULDER)
    elbow = joint_stack_elbow(elbow_o, SHOULDER + ELBOW)

    # Elbow encoder board on -Y side of elbow
    as_b = as5047p_board(0, 0, 0)
    as_b = as_b.rotate(App.Vector(0, 0, 0), App.Vector(1, 0, 0), 90)
    as_b = as_b.translate(App.Vector(elbow_o[0], elbow_o[1] - 16.0, elbow_o[2]))

    link2_local = link_bar(G.LINK2_L, G.LINK2_W, G.LINK2_T, G.SHAFT_D / 2.0 + 0.05, hollow_r=1.8)
    link2_s = place_link(link2_local, elbow_o, SHOULDER + ELBOW)

    harness = wires()

    # Small tip mass
    tip = G.tip_origin(TRAVEL, SHOULDER, ELBOW)
    bob = cylinder(8.0, 16.0, tip[0], tip[1] - 8.0, tip[2] - 4.0, axis="y")

    parts = {
        "rail": rail_s,
        "cart": cart_s,
        "teensy-4.1": teensy_s,
        "amt102-v": amt,
        "as5047p-a": as_a,
        "as5047p-b": as_b,
        "slip-ring-12-wire-a": slip_ring_src012(G.SHOULDER_X, G.SHOULDER_Y, G.CART_TOP - 3.0 - G.SLIP_L),
        "slip-ring-12-wire-b": None,  # filled below from elbow stack extract — export full elbow joint instead
        "link1": link1_s,
        "link2": link2_s,
        "shoulder-joint": shoulder,
        "elbow-joint": elbow,
        "wiring": harness,
        "tip-mass": bob,
    }

    # Separate elbow slip ring solid for catalog highlight (duplicate of capsule at elbow)
    elbow_slip = slip_ring_src012(0, 0, 0)
    elbow_slip = elbow_slip.rotate(App.Vector(0, 0, 0), App.Vector(1, 0, 0), -90)
    elbow_slip = elbow_slip.translate(App.Vector(elbow_o[0], elbow_o[1] + G.LINK2_T / 2.0 + 8.0, elbow_o[2]))
    parts["slip-ring-12-wire-b"] = elbow_slip

    colors = {
        "rail": (0.60, 0.65, 0.71),
        "cart": (0.85, 0.87, 0.91),
        "teensy-4.1": (0.12, 0.48, 0.22),
        "amt102-v": (0.15, 0.15, 0.15),
        "as5047p-a": (0.08, 0.18, 0.12),
        "as5047p-b": (0.08, 0.18, 0.12),
        "slip-ring-12-wire-a": (0.79, 0.64, 0.15),
        "slip-ring-12-wire-b": (0.79, 0.64, 0.15),
        "link1": (0.50, 0.55, 0.60),
        "link2": (0.64, 0.68, 0.72),
        "shoulder-joint": (0.45, 0.48, 0.52),
        "elbow-joint": (0.45, 0.48, 0.52),
        "wiring": (0.12, 0.12, 0.12),
        "tip-mass": (0.72, 0.22, 0.18),
    }

    for name, shape in parts.items():
        if shape is None:
            continue
        solid_to_obj(doc, name.replace("-", "_"), shape, colors.get(name, (0.6, 0.6, 0.6)))
        deflection = 0.35 if name == "teensy-4.1" else (0.25 if name == "wiring" else 0.12)
        mesh_export(shape, os.path.join(EXPORTS, name + ".stl"), deflection)

    # Keep legacy simple names expected by older viewers for main structure
    # (already writing rail/cart/link1/link2)

    doc.saveAs(DOC_PATH)
    print("saved", DOC_PATH)
    Path = __import__("pathlib").Path
    Path(os.path.join(EXPORTS, "pendulum-kinematics.json")).write_text(
        __import__("json").dumps(G.kinematics_json(), indent=2)
    )
    print("exports", EXPORTS)
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
